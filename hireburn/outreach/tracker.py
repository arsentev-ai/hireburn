"""Replies and follow-ups.

Input (``replies.csv``) — one row per candidate, kept by hand or exported from your notes::

    candidate_id,sent,follow_ups_sent,last_follow_up,replied,outcome
    p01,2026-01-05,0,,2026-01-06,interested
    p02,2026-01-05,1,2026-01-09,,

* ``sent`` / ``last_follow_up`` / ``replied`` — ISO dates (or day numbers).
* ``outcome`` — interested, booked, not_interested, stop, or empty.

Rules: follow up after ``follow_up_days`` (default 4, then 10) with no reply; at most
two follow-ups; never follow up anyone who replied, said no, or asked to stop — they
go to the do-not-contact list.
"""

from __future__ import annotations

import statistics
from datetime import date, timedelta
from typing import Any, Iterable, Mapping, Sequence

from hireburn._io import md_table, pct

NEGATIVE = {"not_interested", "stop", "unsubscribe", "do_not_contact"}


def _d(v: Any) -> date | None:
    s = str(v or "").strip()
    if not s:
        return None
    if s.isdigit():
        return date(2000, 1, 1) + timedelta(days=int(s) - 1)
    return date.fromisoformat(s[:10])


def analyse(rows: Iterable[Mapping[str, Any]], today: date, follow_up_days: Sequence[int] = (4, 10)) -> dict[str, Any]:
    rows = list(rows)
    sent = [r for r in rows if _d(r.get("sent"))]
    replied = [r for r in sent if _d(r.get("replied"))]
    lags = [(_d(r["replied"]) - _d(r["sent"])).days for r in replied]
    due, dnc = [], []
    outcomes: dict[str, int] = {}
    for r in sent:
        cid = r.get("candidate_id", "?")
        out = str(r.get("outcome", "") or "").strip().lower()
        if out:
            outcomes[out] = outcomes.get(out, 0) + 1
        if out in NEGATIVE:
            dnc.append(cid)
            continue
        if _d(r.get("replied")):
            continue
        n = int(r.get("follow_ups_sent") or 0)
        if n >= len(follow_up_days):
            continue
        since = _d(r.get("last_follow_up")) or _d(r.get("sent"))
        base = _d(r.get("sent"))
        if (today - base).days >= follow_up_days[n] and (today - since).days >= 3:
            due.append({"candidate_id": cid, "follow_up": n + 1, "days_since_first": (today - base).days})
    return {
        "sent": len(sent),
        "replied": len(replied),
        "reply_rate": len(replied) / len(sent) if sent else None,
        "median_days_to_reply": statistics.median(lags) if lags else None,
        "outcomes": outcomes,
        "follow_ups_due": due,
        "do_not_contact": dnc,
    }


def render(res: dict[str, Any]) -> str:
    out = ["## Outreach replies", "",
           f"- sent {res['sent']} · replied {res['replied']} · reply rate **{pct(res['replied'], res['sent'])}**"
           + (f" · median {res['median_days_to_reply']:g} days to reply" if res["median_days_to_reply"] is not None else "")]
    if res["outcomes"]:
        out.append("- outcomes: " + ", ".join(f"{k} {v}" for k, v in sorted(res["outcomes"].items())))
    if res["follow_ups_due"]:
        out += ["", md_table(["follow-up due", "number", "days since first message"],
                             [[d["candidate_id"], d["follow_up"], d["days_since_first"]] for d in res["follow_ups_due"]]), ""]
    else:
        out.append("- no follow-ups due today")
    if res["do_not_contact"]:
        out.append(f"- do not contact again: {', '.join(res['do_not_contact'])}")
    return "\n".join(out) + "\n"
