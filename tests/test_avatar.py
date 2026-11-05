import copy

import pytest

from hireburn._io import load
from hireburn.avatar import interview, page, providers, rubric, script
from hireburn.funnel import disclosure


@pytest.fixture
def cfg(example):
    return load(example / "interview.yaml")


@pytest.fixture
def rub(example):
    return load(example / "rubric.yaml")


def test_script_discloses_avatar(cfg):
    clips = script.build(cfg)
    intro = clips[0]
    assert intro.id == "00-intro" and "AI avatar" in intro.text and cfg["interviewer"]["name"] in intro.text
    assert sum(c.kind == "question" for c in clips) == 5
    assert sum(c.kind == "transition" for c in clips) == 4
    assert {c.id for c in clips if c.kind == "fallback"} == {"95-fx-repeat", "95-fx-tech", "95-fx-human"}


def test_script_warns_on_long_question(cfg):
    cfg = copy.deepcopy(cfg)
    cfg["questions"][0]["text"] = "word " * 200
    assert script.build(cfg)[1].warning


def test_script_requires_interviewer_name(cfg):
    cfg = copy.deepcopy(cfg)
    cfg["interviewer"] = {"title": "x"}
    with pytest.raises(ValueError):
        script.build(cfg)


def test_plan_caps_follow_ups(cfg):
    p = interview.plan(cfg)
    assert p["steps"][0]["step"] == "disclosure_and_consent"
    assert sum(s["step"] == "optional_follow_up" for s in p["steps"]) == 3  # q4, q5 have 0
    bad = copy.deepcopy(cfg)
    bad["questions"][0]["max_followups"] = 2
    with pytest.raises(ValueError):
        interview.plan(bad)


def test_run_never_asks_second_follow_up(cfg):
    class Pushy:
        calls = 0

        def follow_up(self, q, a):
            Pushy.calls += 1
            return "and another thing?"

    asked = []
    t = interview.run(cfg, Pushy(), lambda qid, text: asked.append(qid) or "answer")
    assert Pushy.calls == 3
    assert len([q for q in asked if q.endswith(":follow_up")]) == 3
    assert all(turn["follow_up"] in (None, "and another thing?") for turn in t["turns"])


def test_page_requires_disclosure_facts(cfg):
    for key in ("alternative_contact", "retention_days", "interviewer"):
        bad = copy.deepcopy(cfg)
        bad.pop(key)
        with pytest.raises(page.DisclosureMissing):
            page.build(bad)


def test_page_has_all_markers_and_gated_start(cfg, rub):
    html = page.build(cfg, rub)
    assert all(disclosure.check_page(html).values())
    assert '<button id="start" disabled>' in html
    assert "<script src" not in html  # no external scripts
    assert "followUps[qid]" in html  # client-side cap of one follow-up


def test_page_escapes_html(cfg):
    cfg = copy.deepcopy(cfg)
    cfg["company"] = "<script>alert(1)</script>"
    assert "<script>alert(1)" not in page.build(cfg)


def test_rubric_labels_and_review(example, rub):
    sc = providers.KeywordDemoScorer()
    res = {r["candidate"][:10]: r for r in
           (rubric.label(load(f), rub, sc) for f in sorted((example / "transcripts").glob("*.json")))}
    assert res["example-01"]["label"] == "HIRE" and not res["example-01"]["needs_human_review"]
    assert res["example-03"]["label"] == "NO" and res["example-03"]["needs_human_review"]
    assert "organisation" in res["example-03"]["review_reasons"][1]
    assert all("not a measurement" in r["caveat"] for r in res.values())


def test_rubric_refuses_voice_criteria(rub):
    bad = copy.deepcopy(rub)
    bad["criteria"][0]["what"] = "Confident tone of voice"
    with pytest.raises(ValueError):
        rubric.validate(bad)


def test_manual_scorer(tmp_path, rub):
    f = tmp_path / "s.json"
    f.write_text('{"result": 5, "handling": {"score": 5, "evidence": "x"}, "organisation": 5, "availability": 5, "start": 5}')
    r = rubric.label({"candidate": "m"}, rub, providers.ManualScorer(f))
    assert r["label"] == "HIRE" and r["weighted_score"] == 5.0


def test_load_object():
    obj = providers.load_object("hireburn.avatar.providers:NoFollowUp")
    assert obj.follow_up({}, "x") is None
    assert isinstance(obj, providers.VoiceAgent)
