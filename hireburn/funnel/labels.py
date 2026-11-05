"""AI-interview label → who is still working on day N, and decision lag.

Input (``candidates.csv``), one row per candidate::

    id,entered,ai_label,human_label,account,first_work,working_day_n
    c001,1,HIRE,pass,yes,9,yes
    c002,3,MAYBE,,no,,

* ``entered``     — day number or ISO date the candidate entered your pipeline.
* ``ai_label``    — HIRE / MAYBE / NO from the AI interview, empty if none.
* ``human_label`` — pass / fail from a human interview, empty if none.
* ``account``     — yes if the person got a work account (trial or start).
* ``first_work``  — day number or ISO date of the first real working action; empty if none.
* ``working_day_n`` — yes if the person is working on the day you check (``--day``).

What it reports:

* per label: candidates, accounts, started, working on day N, share working;
* a two-sided Fisher exact test for HIRE vs MAYBE (small groups say little — the test
  makes that visible instead of letting a percentage gap speak for itself);
* AI label × human result agreement table;
* median days from entry to first working action, and an equal-window view
  (first action within 7 / 14 days, only among people followed for that long),
  because medians over starters favour late entrants.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable, Mapping

from hireburn._io import md_table, pct

LABELS = ("HIRE", "MAYBE", "NO")
_YES = {"yes", "y", "true", "1", "x"}


def _yes(v: Any) -> bool:
    return str(v or "").strip().lower() in _YES


def _day(v: Any, origin: date | None) -> int | None:
    s = str(v or "").strip()
    if not s:
        return None
    if s.lstrip("-").isdigit():
        return int(s)
    try:
        d = date.fromisoformat(s[:10])
    except ValueError:
        raise ValueError(f"cannot read day {s!r}: use a day number or YYYY-MM-DD") from None
    if origin is None:
        raise ValueError("mixing ISO dates with day numbers is not supported")
    return (d - origin).days + 1


@dataclass
class Candidate:
    id: str
    entered: int | None
    ai_label: str
    human_label: str
    account: bool
    first_work: int | None
    working: bool


def parse(rows: Iterable[Mapping[str, Any]]) -> list[Candidate]:
    rows = list(rows)
    iso = [str(r.get(k, "")) for r in rows for k in ("entered", "first_work") if "-" in str(r.get(k, ""))[1:]]
    origin = min(date.fromisoformat(s[:10]) for s in iso) if iso else None
    out = []
    for n, r in enumerate(rows, 1):
        label = str(r.get("ai_label", "") or "").strip().upper()
        if label and label not in LABELS:
            raise ValueError(f"candidate row {n}: ai_label {label!r} is not HIRE, MAYBE or NO")
        human = str(r.get("human_label", "") or "").strip().lower()
        if human and human not in ("pass", "fail"):
            raise ValueError(f"candidate row {n}: human_label {human!r} is not pass or fail")
        out.append(
            Candidate(
                id=str(r.get("id", n)),
                entered=_day(r.get("entered"), origin),
                ai_label=label,
                human_label=human,
                account=_yes(r.get("account")),
                first_work=_day(r.get("first_work"), origin),
                working=_yes(r.get("working_day_n")),
            )
        )
    return out


def fisher_exact(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact test p-value for the 2×2 table [[a, b], [c, d]]."""
    r1, r2, c1, n = a + b, c + d, a + c, a + b + c + d
    if n == 0:
        return 1.0

    def logp(x: int) -> float:
        return (
            math.lgamma(r1 + 1) + math.lgamma(r2 + 1) + math.lgamma(c1 + 1) + math.lgamma(n - c1 + 1)
            - math.lgamma(n + 1) - math.lgamma(x + 1) - math.lgamma(r1 - x + 1)
            - math.lgamma(c1 - x + 1) - math.lgamma(r2 - c1 + x + 1)
        )

    lo, hi = max(0, c1 - r2), min(r1, c1)
    p_obs = logp(a)
    total = sum(math.exp(logp(x)) for x in range(lo, hi + 1) if logp(x) <= p_obs + 1e-7)
    return min(1.0, total)


def analyse(rows: Iterable[Mapping[str, Any]], day: int, snapshot: int | None = None) -> dict[str, Any]:
    cands = parse(rows)
    groups: dict[str, list[Candidate]] = {k: [] for k in LABELS + ("no AI interview",)}
    for c in cands:
        groups[c.ai_label or "no AI interview"].append(c)

    table = []
    for name, members in groups.items():
        started = [c for c in members if c.first_work is not None]
        working = [c for c in members if c.working]
        table.append({
            "group": name,
            "candidates": len(members),
            "account": sum(c.account for c in members),
            "started": len(started),
            "working": len(working),
            "working_share_all": len(working) / len(members) if members else None,
            "working_share_started": len(working) / len(started) if started else None,
        })

    h, m = groups["HIRE"], groups["MAYBE"]
    hw, mw = sum(c.working for c in h), sum(c.working for c in m)
    p_all = fisher_exact(hw, len(h) - hw, mw, len(m) - mw) if h and m else None
    hs = [c for c in h if c.first_work is not None]
    ms = [c for c in m if c.first_work is not None]
    hsw, msw = sum(c.working for c in hs), sum(c.working for c in ms)
    p_started = fisher_exact(hsw, len(hs) - hsw, msw, len(ms) - msw) if hs and ms else None

    agreement = []
    for label in LABELS:
        g = [c for c in groups[label] if c.human_label]
        agreement.append({
            "ai_label": label,
            "with_human_result": len(g),
            "human_pass": sum(c.human_label == "pass" for c in g),
            "human_fail": sum(c.human_label == "fail" for c in g),
        })

    lags = sorted(c.first_work - c.entered for c in cands if c.first_work is not None and c.entered is not None)
    lag = {
        "n": len(lags),
        "median_days": statistics.median(lags) if lags else None,
        "min_days": lags[0] if lags else None,
        "max_days": lags[-1] if lags else None,
    }
    windows = []
    if snapshot is not None:
        for w in (7, 14):
            eligible = [c for c in cands if c.entered is not None and snapshot - c.entered >= w]
            hit = [c for c in eligible if c.first_work is not None and c.first_work - c.entered <= w]
            windows.append({"window_days": w, "followed": len(eligible), "first_action_within": len(hit)})

    return {
        "day": day,
        "groups": table,
        "fisher_hire_vs_maybe": {"among_all": p_all, "among_started": p_started},
        "agreement": agreement,
        "lag": lag,
        "equal_window": windows,
        "caveat": (
            "An AI label is a cut-off on a model's reading of one conversation, not a measurement of "
            "job performance. With groups this small, a gap in percentages is usually noise — read the p-value."
        ),
    }


def render(res: dict[str, Any]) -> str:
    d = res["day"]
    rows = [[g["group"], g["candidates"], g["account"], g["started"], g["working"],
             pct(g["working"], g["candidates"]), pct(g["working"], g["started"])] for g in res["groups"]]
    out = [f"## AI label vs who is working on day {d}", "",
           md_table(["AI label", "candidates", "account", "started", f"working day {d}", "of all", "of started"], rows), ""]
    f = res["fisher_hire_vs_maybe"]
    if f["among_all"] is not None:
        out.append(f"- HIRE vs MAYBE, working share, Fisher exact (two-sided): p = {f['among_all']:.2f} among all"
                   + (f", p = {f['among_started']:.2f} among those who started" if f["among_started"] is not None else ""))
    out.append(f"- ⚠ {res['caveat']}")
    out += ["", "### AI label × human interview", "",
            md_table(["AI label", "with human result", "human pass", "human fail"],
                     [[a["ai_label"], a["with_human_result"], a["human_pass"], a["human_fail"]] for a in res["agreement"]]), ""]
    lag = res["lag"]
    if lag["n"]:
        out.append(f"### Decision lag\n\n- entry → first working action: median **{lag['median_days']:g} days** "
                   f"(range {lag['min_days']}–{lag['max_days']}, n = {lag['n']} who started)")
        out.append("- medians count only people who started; late entrants had less time to be counted.")
    for w in res["equal_window"]:
        out.append(f"- equal window: first action within {w['window_days']} days — {w['first_action_within']} of "
                   f"{w['followed']} followed for at least {w['window_days']} days ({pct(w['first_action_within'], w['followed'])})")
    return "\n".join(out) + "\n"
