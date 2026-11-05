from datetime import date, datetime, timedelta

import pytest

from hireburn._io import load
from hireburn.outreach import messages, pacing, tracker


def test_drafts_require_hook_and_skip_dnc(example):
    drafts, errors = messages.draft_all(load(example / "outreach.csv"), load(example / "templates.yaml"))
    ids = {d.candidate_id for d in drafts}
    assert ids == {"p01", "p02", "p03", "p06"}
    assert any("p04" in e and "hook" in e for e in errors)
    assert any("p05" in e and "do_not_contact" in e for e in errors)
    assert all("{" not in d.text for d in drafts)


def test_connect_note_limit(example):
    cfg = load(example / "templates.yaml")
    cfg["note_max_chars"] = 50
    drafts, _ = messages.draft_all(load(example / "outreach.csv"), cfg, kinds=["connect"])
    assert all(any("limit" in w for w in d.warnings) for d in drafts)


def test_lint_spam():
    assert messages.lint("GUARANTEED offer, click here", "first", {})


def _drafts(n, kind="first"):
    return [{"id": f"c{i}:{kind}", "candidate_id": f"c{i}", "kind": kind} for i in range(n)]


def test_plan_respects_caps_and_hours():
    lim = pacing.Limits()
    q = pacing.plan(_drafts(60), datetime(2026, 1, 5, 9, 0), lim, seed=1)  # Monday
    sends = [datetime.fromisoformat(e["at"]) for e in q if e["action"] == "message"]
    views = [datetime.fromisoformat(e["at"]) for e in q if e["action"] == "view"]
    assert len(sends) == 60 and len(views) == 60
    for t in sends:
        assert sum(1 for x in sends if t - timedelta(hours=1) < x <= t) <= 10
    for t in views:
        assert sum(1 for x in views if t - timedelta(hours=1) < x <= t) <= 30
    for day in {t.date() for t in sends}:
        assert sum(1 for t in sends if t.date() == day) <= 40
    allt = [datetime.fromisoformat(e["at"]) for e in q]
    assert all(9 <= t.hour < 18 and t.weekday() < 5 for t in allt)
    assert all(b > a for a, b in zip(allt, allt[1:]))
    gaps = [(b - a).total_seconds() for a, b in zip(allt, allt[1:])]
    assert min(gaps) >= 20


def test_plan_view_then_send_and_ms_jitter():
    q = pacing.plan(_drafts(3), datetime(2026, 1, 5, 9, 0), seed=3)
    assert [e["action"] for e in q[:2]] == ["view", "message"]
    assert any(e["gap_after_ms"] % 1000 for e in q)


def test_plan_weekend_rolls_to_monday():
    q = pacing.plan(_drafts(1), datetime(2026, 1, 10, 12, 0), seed=1)  # Saturday
    assert datetime.fromisoformat(q[0]["at"]).weekday() == 0


def test_limits_refuse_bot_pace():
    with pytest.raises(ValueError):
        pacing.Limits.from_mapping({"sends_per_hour": 100})
    with pytest.raises(ValueError):
        pacing.Limits.from_mapping({"gap_seconds": [1, 2]})
    with pytest.raises(ValueError):
        pacing.Limits.from_mapping({"no_such": 1})


def test_pacer_stop_resume(tmp_path):
    p = pacing.Pacer(tmp_path)
    now = datetime(2026, 1, 5, 10, 0)
    assert p.check("message", now)[0]
    p.stop("captcha", now)
    ok, wait, why = p.check("message", now)
    assert not ok and "captcha" in why
    with pytest.raises(PermissionError):
        p.resume(confirmed_account_ok=True, now=now + timedelta(hours=1))
    with pytest.raises(PermissionError):
        p.resume(confirmed_account_ok=False, now=now + timedelta(days=3))
    p.resume(confirmed_account_ok=True, now=now + timedelta(days=3))
    assert not p.stop_path.exists()


def test_pacer_uses_real_log(tmp_path):
    p = pacing.Pacer(tmp_path)
    t0 = datetime(2026, 1, 5, 10, 0)
    for i in range(10):
        p.record("message", f"c{i}", at=t0 + timedelta(minutes=i))
    ok, wait, _ = p.check("message", t0 + timedelta(minutes=10))
    assert not ok and wait > 0
    ok, _, _ = p.check("view", t0 + timedelta(minutes=10))
    assert ok
    ok, wait, _ = p.check("view", t0 + timedelta(minutes=9, seconds=5))
    assert not ok  # min gap since last action


def test_tracker(example):
    res = tracker.analyse(load(example / "replies.csv"), date(2026, 1, 20))
    assert res["sent"] == 8 and res["replied"] == 4
    due = {d["candidate_id"]: d["follow_up"] for d in res["follow_ups_due"]}
    assert due == {"p02": 1, "p03": 2, "p09": 1}
    assert res["do_not_contact"] == ["p06"]
