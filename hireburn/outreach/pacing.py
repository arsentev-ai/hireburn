"""Human-pace queue for LinkedIn outreach. A person presses "send" — always.

What this module does:

* ``plan`` spreads actions (view a profile, then send a message) over working hours
  with random gaps, hourly and daily caps, and a longer break every few actions;
* ``Pacer`` checks, at the moment of acting, the real log of what was done — caps
  hold even if the plan is stale or a second queue runs;
* a STOP file halts everything. Seeing a warning, a captcha, a "you're sending too
  many" banner or a restriction notice → ``hireburn outreach stop``. Resuming needs
  a cool-down and an explicit confirmation that the account is fine.

What it never does: log in, click, type, send, scrape, run a headless browser, rotate
fingerprints or proxies. The queue shows you the profile link and the draft; you
read the profile, edit the draft if needed, send it by hand and confirm. LinkedIn's
User Agreement forbids bots and automated messaging; this tool stays on the right
side of it and so does your account.

Defaults are deliberately conservative. We hit a LinkedIn restriction when the pace
was not human.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping

ACTIONS = ("view", "connect", "message", "follow_up")


@dataclass
class Limits:
    per_hour: dict[str, int] = field(default_factory=lambda: {"view": 30, "connect": 8, "message": 10, "follow_up": 10})
    per_day: dict[str, int] = field(default_factory=lambda: {"view": 120, "connect": 25, "message": 40, "follow_up": 40})
    sends_per_hour: int = 10          # connect + message + follow_up together
    gap_seconds: tuple[float, float] = (20.0, 60.0)
    view_to_send_seconds: tuple[float, float] = (45.0, 150.0)  # read the profile before writing
    break_every: int = 8
    break_seconds: tuple[float, float] = (300.0, 900.0)
    work_hours: tuple[int, int] = (9, 18)
    weekdays_only: bool = True
    cooldown_hours_after_stop: int = 48

    @classmethod
    def from_mapping(cls, m: Mapping[str, Any] | None) -> "Limits":
        lim = cls()
        for k, v in (m or {}).items():
            if not hasattr(lim, k):
                raise ValueError(f"unknown limit {k!r}")
            cur = getattr(lim, k)
            if isinstance(cur, dict):
                cur = {**cur, **{a: int(n) for a, n in v.items()}}
            elif isinstance(cur, tuple):
                cur = tuple(float(x) if isinstance(cur[0], float) else int(x) for x in v)
            elif isinstance(cur, bool):
                cur = bool(v)
            else:
                cur = type(cur)(v)
            setattr(lim, k, cur)
        lim.check()
        return lim

    def check(self) -> None:
        lo, hi = self.gap_seconds
        if lo < 5 or hi < lo:
            raise ValueError("gap_seconds must be at least 5 s and (min, max)")
        if not 0 <= self.work_hours[0] < self.work_hours[1] <= 24:
            raise ValueError("work_hours must be (start, end) within 0–24")
        if self.sends_per_hour > 20:
            raise ValueError("sends_per_hour above 20 is not a human pace; hireburn refuses it")


def _is_send(action: str) -> bool:
    return action in ("connect", "message", "follow_up")


class _Window:
    def __init__(self) -> None:
        self.times: dict[str, list[datetime]] = {a: [] for a in ACTIONS}

    def add(self, action: str, at: datetime) -> None:
        self.times[action].append(at)

    def in_last_hour(self, action: str, now: datetime) -> list[datetime]:
        return [t for t in self.times[action] if now - timedelta(hours=1) < t <= now]

    def sends_last_hour(self, now: datetime) -> list[datetime]:
        return sorted(t for a in ACTIONS if _is_send(a) for t in self.in_last_hour(a, now))

    def on_day(self, action: str, now: datetime) -> int:
        return sum(1 for t in self.times[action] if t.date() == now.date())


def next_allowed(now: datetime, action: str, win: _Window, lim: Limits) -> datetime:
    """Earliest moment ≥ now when ``action`` respects working hours and caps."""
    t = now
    for _ in range(10000):
        start_h, end_h = lim.work_hours
        if lim.weekdays_only and t.weekday() >= 5:
            t = (t + timedelta(days=7 - t.weekday())).replace(hour=start_h, minute=0, second=0, microsecond=0)
            continue
        if t.hour < start_h:
            t = t.replace(hour=start_h, minute=0, second=0, microsecond=0)
            continue
        if t.hour >= end_h:
            t = (t + timedelta(days=1)).replace(hour=start_h, minute=0, second=0, microsecond=0)
            continue
        if win.on_day(action, t) >= lim.per_day.get(action, 10**9):
            t = (t + timedelta(days=1)).replace(hour=start_h, minute=0, second=0, microsecond=0)
            continue
        hour = win.in_last_hour(action, t)
        if len(hour) >= lim.per_hour.get(action, 10**9):
            t = min(hour) + timedelta(hours=1, seconds=1)
            continue
        if _is_send(action):
            sends = win.sends_last_hour(t)
            if len(sends) >= lim.sends_per_hour:
                t = sends[0] + timedelta(hours=1, seconds=1)
                continue
        return t
    raise RuntimeError("could not schedule within limits")


def plan(drafts: Iterable[Mapping[str, Any]], start: datetime, limits: Limits | None = None,
         seed: int | None = None, view_first: bool = True) -> list[dict[str, Any]]:
    """Schedule drafts. Each draft becomes: view profile → (pause) → send by hand."""
    lim = limits or Limits()
    rng = random.Random(seed)
    win = _Window()
    t = start
    out: list[dict[str, Any]] = []
    n = 0
    for d in drafts:
        kind = d.get("kind", "message")
        send_action = "connect" if kind == "connect" else ("follow_up" if kind.startswith("follow_up") else "message")
        steps = (["view"] if view_first and send_action != "follow_up" else []) + [send_action]
        for action in steps:
            t = next_allowed(t, action, win, lim)
            win.add(action, t)
            n += 1
            out.append({"seq": n, "at": t.isoformat(timespec="milliseconds"), "action": action,
                        "candidate_id": d.get("candidate_id"), "draft_id": d.get("id"),
                        "profile_url": d.get("profile_url", "")})
            lo, hi = lim.view_to_send_seconds if action == "view" else lim.gap_seconds
            gap = rng.uniform(lo, hi) + rng.randint(0, 999) / 1000.0
            if n % lim.break_every == 0:
                gap += rng.uniform(*lim.break_seconds)
            out[-1]["gap_after_ms"] = int(gap * 1000)
            t = t + timedelta(milliseconds=int(gap * 1000))
    return out


# ------------------------------------------------------------------ live checks + stop


@dataclass
class StopState:
    stopped: bool
    reason: str = ""
    since: str = ""
    resume_after: str = ""


class Pacer:
    """Guards a live session: reads the action log and the STOP file before every step."""

    def __init__(self, state_dir: str | Path, limits: Limits | None = None, rng: random.Random | None = None):
        self.dir = Path(state_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.lim = limits or Limits()
        self.rng = rng or random.Random()
        self.log_path = self.dir / "actions.jsonl"
        self.stop_path = self.dir / "STOP"

    def log(self) -> list[dict[str, Any]]:
        if not self.log_path.exists():
            return []
        return [json.loads(x) for x in self.log_path.read_text(encoding="utf-8").splitlines() if x.strip()]

    def record(self, action: str, candidate_id: str, draft_id: str = "", outcome: str = "done",
               at: datetime | None = None) -> None:
        at = at or datetime.now()
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": at.isoformat(timespec="milliseconds"), "action": action,
                                 "candidate_id": candidate_id, "draft_id": draft_id, "outcome": outcome}) + "\n")

    def stop_state(self, now: datetime | None = None) -> StopState:
        if not self.stop_path.exists():
            return StopState(False)
        data = json.loads(self.stop_path.read_text(encoding="utf-8"))
        return StopState(True, data.get("reason", ""), data.get("since", ""), data.get("resume_after", ""))

    def stop(self, reason: str, now: datetime | None = None) -> StopState:
        now = now or datetime.now()
        after = now + timedelta(hours=self.lim.cooldown_hours_after_stop)
        state = StopState(True, reason, now.isoformat(timespec="seconds"), after.isoformat(timespec="seconds"))
        self.stop_path.write_text(json.dumps(asdict(state)), encoding="utf-8")
        return state

    def resume(self, confirmed_account_ok: bool, now: datetime | None = None) -> None:
        now = now or datetime.now()
        st = self.stop_state()
        if not st.stopped:
            return
        if not confirmed_account_ok:
            raise PermissionError("open LinkedIn yourself, check there is no warning or restriction, then confirm")
        if now < datetime.fromisoformat(st.resume_after):
            raise PermissionError(f"cool-down until {st.resume_after} (stopped: {st.reason})")
        self.stop_path.unlink()

    def check(self, action: str, now: datetime | None = None) -> tuple[bool, float, str]:
        """(allowed, seconds to wait, reason). Uses the real log, not the plan."""
        now = now or datetime.now()
        st = self.stop_state()
        if st.stopped:
            return False, float("inf"), f"STOPPED: {st.reason} (since {st.since}); see `hireburn outreach resume`"
        win = _Window()
        last = None
        for e in self.log():
            if e.get("outcome") != "done" or e.get("action") not in ACTIONS:
                continue
            at = datetime.fromisoformat(e["at"])
            win.add(e["action"], at)
            last = max(last, at) if last else at
        allowed_at = next_allowed(now, action, win, self.lim)
        if last is not None:
            min_gap = timedelta(seconds=self.lim.gap_seconds[0])
            allowed_at = max(allowed_at, last + min_gap)
        wait = (allowed_at - now).total_seconds()
        if wait > 0:
            return False, wait, f"next {action} allowed at {allowed_at.isoformat(timespec='seconds')}"
        return True, 0.0, "ok"

    def jitter(self) -> float:
        lo, hi = self.lim.gap_seconds
        return self.rng.uniform(lo, hi) + self.rng.randint(0, 999) / 1000.0
