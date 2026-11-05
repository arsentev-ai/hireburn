import json

from hireburn.cli import main


def test_demo_runs(capsys, example, tmp_path):
    assert main(["demo", "--data", str(example), "--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "SYNTHETIC" in out and "show-up rate" in out and "Human-pace queue" in out
    assert (tmp_path / "candidate-page.html").exists()


def test_funnel_json(capsys, example):
    assert main(["funnel", str(example / "funnel.csv"), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert round(data["show_up_rate"], 3) == 0.818


def test_disclosure_strict(example):
    assert main(["disclosure", str(example / "disclosure.yaml"), "--strict"]) == 2


def test_bad_input_returns_1(tmp_path):
    f = tmp_path / "f.csv"
    f.write_text("stage,count\na,notanumber\n")
    assert main(["funnel", str(f)]) == 1


def test_outreach_pipeline(tmp_path, example, capsys):
    d, q = tmp_path / "d.json", tmp_path / "q.json"
    assert main(["outreach", "draft", str(example / "outreach.csv"), "--templates", str(example / "templates.yaml"), "-o", str(d)]) == 0
    assert main(["outreach", "plan", str(d), "--start", "2026-01-05T09:00", "--seed", "1", "-o", str(q)]) == 0
    assert len(json.loads(q.read_text())) == 8
    st = tmp_path / "state"
    assert main(["outreach", "stop", "--reason", "captcha", "--state", str(st)]) == 0
    assert main(["outreach", "run", str(q), "--drafts", str(d), "--state", str(st), "--no-wait"]) == 3
