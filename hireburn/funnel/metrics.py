"""Stage counts → losses per stage, show-up rate, completion rate.

Input (``funnel.csv``)::

    stage,count,parent,role
    applications,2000,,
    screened,1000,,
    candidates,200,,
    booked,100,,
    held,60,,held
    no_show,25,booked,no_show
    cancelled,10,booked,cancelled
    ai_invited,50,candidates,invited
    ai_completed,30,ai_invited,completed

* Rows with an empty ``parent`` form the main chain, in file order. Each is compared
  with the main-chain row before it.
* Rows with a ``parent`` are side branches (no-shows, cancellations, an AI-interview
  track) and are compared with that parent.
* ``role`` marks the rows the rates are built from: ``held``, ``no_show``,
  ``cancelled``, ``invited``, ``completed``. Without it, rows *named* like that are used.

Formulas (from the payrollburn AI-hiring report, DOI 10.5281/zenodo.23927437):

* show-up rate   = held ÷ (held + no-show)
* completion rate = completed ÷ invited
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from hireburn._io import md_table, pct

ROLES = ("held", "no_show", "cancelled", "invited", "completed")


@dataclass
class Stage:
    name: str
    count: int
    parent: str = ""
    role: str = ""
    note: str = ""


@dataclass
class FunnelReport:
    stages: list[dict[str, Any]]
    show_up_rate: float | None
    completion_rate: float | None
    unaccounted_bookings: int | None
    biggest_loss: dict[str, Any] | None
    sharpest_drop: dict[str, Any] | None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stages": self.stages,
            "show_up_rate": self.show_up_rate,
            "completion_rate": self.completion_rate,
            "unaccounted_bookings": self.unaccounted_bookings,
            "biggest_loss": self.biggest_loss,
            "sharpest_drop": self.sharpest_drop,
            "notes": self.notes,
        }


def parse_stages(rows: Iterable[Mapping[str, Any]]) -> list[Stage]:
    stages: list[Stage] = []
    seen: set[str] = set()
    for n, row in enumerate(rows, 1):
        name = str(row.get("stage", "")).strip()
        if not name:
            raise ValueError(f"funnel row {n}: empty 'stage'")
        if name in seen:
            raise ValueError(f"funnel row {n}: stage {name!r} appears twice")
        raw = str(row.get("count", "")).replace(",", "").replace("_", "").strip()
        try:
            count = int(float(raw))
        except ValueError:
            raise ValueError(f"funnel row {n} ({name}): count {row.get('count')!r} is not a number") from None
        if count < 0:
            raise ValueError(f"funnel row {n} ({name}): negative count")
        role = str(row.get("role", "") or "").strip().lower()
        if role and role not in ROLES:
            raise ValueError(f"funnel row {n} ({name}): unknown role {role!r}; use one of {', '.join(ROLES)}")
        parent = str(row.get("parent", "") or "").strip()
        if parent and parent not in seen:
            raise ValueError(f"funnel row {n} ({name}): parent {parent!r} must be listed above it")
        stages.append(Stage(name, count, parent, role, str(row.get("note", "") or "")))
        seen.add(name)
    if not stages:
        raise ValueError("funnel: no stages")
    return stages


def _by_role(stages: list[Stage], role: str) -> Stage | None:
    for s in stages:
        if s.role == role:
            return s
    for s in stages:
        if s.name.lower().replace("-", "_").replace(" ", "_") == role:
            return s
    return None


def analyse(rows: Iterable[Mapping[str, Any]]) -> FunnelReport:
    stages = parse_stages(rows)
    by_name = {s.name: s for s in stages}
    main = [s for s in stages if not s.parent]
    first = main[0].count if main else 0
    out: list[dict[str, Any]] = []
    prev: Stage | None = None
    notes: list[str] = []
    for s in stages:
        if s.parent:
            base = by_name[s.parent]
            kind = "branch"
        else:
            base = prev
            kind = "main"
            prev = s
        rec: dict[str, Any] = {
            "stage": s.name,
            "kind": kind,
            "count": s.count,
            "compared_with": base.name if base else None,
            "conversion": (s.count / base.count) if base and base.count else None,
            "lost": (base.count - s.count) if base and kind == "main" else None,
            "share_of_first": (s.count / first) if first and kind == "main" else None,
        }
        if base and kind == "main" and s.count > base.count:
            notes.append(f"'{s.name}' ({s.count}) is larger than '{base.name}' ({base.count}): check the order of stages.")
        out.append(rec)

    held, no_show = _by_role(stages, "held"), _by_role(stages, "no_show")
    invited, completed = _by_role(stages, "invited"), _by_role(stages, "completed")
    cancelled = _by_role(stages, "cancelled")
    show_up = held.count / (held.count + no_show.count) if held and no_show and (held.count + no_show.count) else None
    completion = completed.count / invited.count if completed and invited and invited.count else None

    unaccounted = None
    if held and no_show:
        booked = by_name.get(no_show.parent) if no_show.parent else None
        if booked:
            unaccounted = booked.count - held.count - no_show.count - (cancelled.count if cancelled else 0)
            if unaccounted > 0:
                notes.append(
                    f"{unaccounted} bookings are neither held, no-show nor cancelled — usually a status nobody "
                    "updated. Treat held and no-show counts as lower bounds."
                )

    mains = [r for r in out if r["kind"] == "main" and r["lost"] is not None]
    biggest = max(mains, key=lambda r: r["lost"], default=None)
    sharpest = min((r for r in mains if r["conversion"] is not None), key=lambda r: r["conversion"], default=None)
    return FunnelReport(
        stages=out,
        show_up_rate=show_up,
        completion_rate=completion,
        unaccounted_bookings=unaccounted,
        biggest_loss={"stage": biggest["stage"], "lost": biggest["lost"]} if biggest else None,
        sharpest_drop={"stage": sharpest["stage"], "conversion": sharpest["conversion"]} if sharpest else None,
        notes=notes,
    )


def render(report: FunnelReport) -> str:
    rows = []
    for r in report.stages:
        name = r["stage"] if r["kind"] == "main" else f"  ↳ {r['stage']} (of {r['compared_with']})"
        conv = pct(r["conversion"], 1) if r["conversion"] is not None else "—"
        rows.append([
            name,
            f"{r['count']:,}",
            conv,
            f"{r['lost']:,}" if r["lost"] is not None else "",
            pct(r["share_of_first"], 1) if r["share_of_first"] is not None else "",
        ])
    parts = ["## Funnel", "", md_table(["stage", "count", "from previous", "lost here", "of first stage"], rows), ""]
    parts.append(f"- show-up rate = held ÷ (held + no-show): **{pct(report.show_up_rate, 1) if report.show_up_rate is not None else '— (needs held and no_show rows)'}**")
    parts.append(f"- completion rate = completed ÷ invited: **{pct(report.completion_rate, 1) if report.completion_rate is not None else '— (needs invited and completed rows)'}**")
    if report.biggest_loss:
        parts.append(f"- most people lost at: **{report.biggest_loss['stage']}** ({report.biggest_loss['lost']:,})")
    if report.sharpest_drop:
        parts.append(f"- sharpest drop: **{report.sharpest_drop['stage']}** (only {pct(report.sharpest_drop['conversion'], 1)} carried over)")
    for n in report.notes:
        parts.append(f"- ⚠ {n}")
    return "\n".join(parts) + "\n"
