"""hireburn command line.

    hireburn funnel FUNNEL.csv                 losses per stage, show-up and completion rates
    hireburn labels CANDIDATES.csv --day 30    AI label vs who is working on day N, decision lag
    hireburn disclosure DISCLOSURE.yaml        candidate disclosure checklist (yardstick, not legal advice)

    hireburn avatar checklist                  recording checklist
    hireburn avatar script INTERVIEW.yaml      everything the avatar says, clip by clip
    hireburn avatar plan INTERVIEW.yaml        player steps: clips + at most one follow-up per question
    hireburn avatar page INTERVIEW.yaml -o page.html [--rubric RUBRIC.yaml]
    hireburn avatar score TRANSCRIPT.json... --rubric RUBRIC.yaml [--scorer module:Class | --manual scores.json]

    hireburn outreach draft CANDIDATES.csv --templates TEMPLATES.yaml -o drafts.json
    hireburn outreach plan drafts.json --start 2026-01-05T09:00 -o queue.json
    hireburn outreach run queue.json --drafts drafts.json   a person works through the queue
    hireburn outreach stop --reason "captcha"  |  hireburn outreach resume --account-checked
    hireburn outreach track REPLIES.csv --today 2026-01-20

    hireburn demo [--out DIR]                  all of the above on the synthetic example company
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import webbrowser
from datetime import date, datetime
from pathlib import Path
from typing import Any

from hireburn import CONCEPT_DOI, __version__
from hireburn._io import load, md_table
from hireburn.avatar import checklist as av_checklist
from hireburn.avatar import interview as av_interview
from hireburn.avatar import page as av_page
from hireburn.avatar import providers as av_providers
from hireburn.avatar import rubric as av_rubric
from hireburn.avatar import script as av_script
from hireburn.funnel import disclosure, labels, metrics
from hireburn.outreach import messages, pacing, tracker


def _emit(args: argparse.Namespace, data: Any, text: str) -> None:
    if getattr(args, "json", False):
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    else:
        print(text)


def _write(path: str | None, content: str) -> None:
    if path:
        Path(path).write_text(content, encoding="utf-8")
        print(f"wrote {path}", file=sys.stderr)


# ------------------------------------------------------------------ funnel


def cmd_funnel(a):
    rep = metrics.analyse(load(a.file))
    _emit(a, rep.to_dict(), metrics.render(rep))


def cmd_labels(a):
    res = labels.analyse(load(a.file), day=a.day, snapshot=a.snapshot)
    _emit(a, res, labels.render(res))


def cmd_disclosure(a):
    html = Path(a.page).read_text(encoding="utf-8") if a.page else None
    res = disclosure.evaluate(load(a.file) if a.file else {}, html)
    _emit(a, res, disclosure.render(res))
    if a.strict and res["counts"]["no"]:
        return 2


# ------------------------------------------------------------------ avatar


def cmd_av_checklist(a):
    print(av_checklist.render())


def cmd_av_script(a):
    cfg = load(a.file)
    clips = av_script.build(cfg)
    _emit(a, av_script.to_json(clips), av_script.render(clips, cfg))


def cmd_av_plan(a):
    print(json.dumps(av_interview.plan(load(a.file)), indent=2, ensure_ascii=False))


def cmd_av_page(a):
    html = av_page.build(load(a.file), load(a.rubric) if a.rubric else None)
    if a.out:
        _write(a.out, html)
    else:
        print(html)


def _scorer(a):
    if a.manual:
        return av_providers.ManualScorer(a.manual)
    if a.scorer:
        return av_providers.load_object(a.scorer)
    print("⚠ no --scorer given: using KeywordDemoScorer, a toy for wiring things up — not an assessment.", file=sys.stderr)
    return av_providers.KeywordDemoScorer()


def cmd_av_score(a):
    rub = load(a.rubric)
    sc = _scorer(a)
    results = [av_rubric.label(load(f), rub, sc) for f in a.files]
    _emit(a, results, av_rubric.render(results))


# ------------------------------------------------------------------ outreach


def cmd_out_draft(a):
    cfg = load(a.templates)
    drafts, errors = messages.draft_all(load(a.file), cfg, kinds=a.kind or ["first"])
    data = messages.to_json(drafts)
    if a.out:
        _write(a.out, json.dumps(data, indent=2, ensure_ascii=False))
    rows = [[d.id, d.chars, "; ".join(d.warnings)] for d in drafts]
    print(f"## Drafts\n\n{md_table(['draft', 'chars', 'warnings'], rows, 'lrl')}\n")
    for e in errors:
        print(f"- skipped: {e}")


def cmd_out_plan(a):
    drafts = load(a.drafts)
    lim = pacing.Limits.from_mapping(load(a.limits) if a.limits else None)
    start = datetime.fromisoformat(a.start) if a.start else datetime.now()
    q = pacing.plan(drafts, start, lim, seed=a.seed)
    if a.out:
        _write(a.out, json.dumps(q, indent=2, ensure_ascii=False))
    print(render_queue(q, lim))


def render_queue(q: list[dict], lim: pacing.Limits, head: int = 12) -> str:
    rows = [[e["seq"], e["at"][:19].replace("T", " "), e["action"], e["candidate_id"], f"{e['gap_after_ms'] / 1000:.1f}s"]
            for e in q[:head]]
    sends = [e for e in q if pacing._is_send(e["action"])]
    span = ""
    if q:
        first, last = datetime.fromisoformat(q[0]["at"]), datetime.fromisoformat(q[-1]["at"])
        days = len({e["at"][:10] for e in q})
        span = f"{len(q)} steps ({len(sends)} sends by hand) over {days} working day(s), {first:%H:%M} → {last:%a %H:%M}"
    return "\n".join([
        "## Human-pace queue", "",
        md_table(["#", "when", "action", "candidate", "pause after"], rows, "rllll"),
        "" if len(q) <= head else f"\n… {len(q) - head} more",
        f"- {span}",
        f"- caps: messages ≤{lim.per_hour['message']}/h, profile views ≤{lim.per_hour['view']}/h, all sends ≤{lim.sends_per_hour}/h; "
        f"pauses {lim.gap_seconds[0]:.0f}–{lim.gap_seconds[1]:.0f} s + ms jitter, a {lim.break_seconds[0] / 60:.0f}–{lim.break_seconds[1] / 60:.0f} min break every {lim.break_every}; "
        f"{lim.work_hours[0]}:00–{lim.work_hours[1]}:00{', weekdays' if lim.weekdays_only else ''}",
        "- a person opens each profile and presses send; hireburn never sends.",
    ]) + "\n"


def cmd_out_run(a):
    queue = load(a.queue)
    drafts = {d["id"]: d for d in load(a.drafts)} if a.drafts else {}
    lim = pacing.Limits.from_mapping(load(a.limits) if a.limits else None)
    pacer = pacing.Pacer(a.state, lim)
    done = {(e["draft_id"], e["action"]) for e in pacer.log() if e.get("outcome") in ("done", "skipped")}
    print("hireburn outreach run — you send, hireburn keeps the pace. Keys: d = done, s = skip, "
          "w = I saw a warning/captcha/restriction (stops everything), q = quit.\n")
    for item in queue:
        key = (item["draft_id"], item["action"])
        if key in done:
            continue
        while True:
            ok, wait, why = pacer.check(item["action"])
            if ok:
                break
            if wait == float("inf") or a.no_wait:
                print(why)
                return 3
            print(f"… {why}; waiting {wait:.0f}s (Ctrl-C to leave, progress is saved)")
            time.sleep(min(wait, 300))
        print(f"\n[{item['seq']}] {item['action'].upper()} · {item['candidate_id']} · {item.get('profile_url', '')}")
        if item["action"] == "view":
            print("Open the profile and read it. Is the draft still right for this person?")
        else:
            print("Send this by hand (edit it if the profile suggested something better):\n")
            print(drafts.get(item["draft_id"], {}).get("text", "(draft not found — pass --drafts)"))
        if a.open and item.get("profile_url"):
            webbrowser.open(item["profile_url"])
        ans = input("\n[d/s/w/q] > ").strip().lower()[:1]
        if ans == "q":
            return 0
        if ans == "w":
            st = pacer.stop(input("What did you see? > ").strip() or "warning")
            print(f"Stopped. Cool-down until {st.resume_after}. Do nothing on LinkedIn from this queue until then.")
            return 3
        pacer.record(item["action"], item["candidate_id"], item["draft_id"], "done" if ans == "d" else "skipped")
        if ans == "d":
            pause = pacer.jitter()
            print(f"pause {pause:.1f}s")
            time.sleep(pause)
    print("queue finished")
    return 0


def cmd_out_stop(a):
    st = pacing.Pacer(a.state).stop(a.reason)
    print(f"STOPPED ({st.reason}). Resume not before {st.resume_after}.")


def cmd_out_resume(a):
    pacing.Pacer(a.state).resume(confirmed_account_ok=a.account_checked)
    print("resumed")


def cmd_out_track(a):
    res = tracker.analyse(load(a.file), date.fromisoformat(a.today) if a.today else date.today())
    _emit(a, res, tracker.render(res))


# ------------------------------------------------------------------ demo


def _example_dir(arg: str | None) -> Path:
    if arg:
        return Path(arg)
    for base in (Path.cwd(), Path(__file__).resolve().parents[1]):
        p = base / "examples" / "example-company"
        if p.is_dir():
            return p
    packaged = Path(__file__).resolve().parent / "_example" / "example-company"
    if packaged.is_dir():
        return packaged
    raise SystemExit("example data not found; pass --data path/to/examples/example-company")


def cmd_demo(a):
    ex = _example_dir(a.data)
    out = Path(a.out) if a.out else None
    if out:
        out.mkdir(parents=True, exist_ok=True)
    parts = [f"# hireburn {__version__} — demo on a SYNTHETIC example company",
             "", "All numbers below are made up and round on purpose. No real company, person or vendor.", ""]

    parts.append(metrics.render(metrics.analyse(load(ex / "funnel.csv"))))
    parts.append(labels.render(labels.analyse(load(ex / "candidates.csv"), day=30, snapshot=60)))

    cfg, rub = load(ex / "interview.yaml"), load(ex / "rubric.yaml")
    clips = av_script.build(cfg)
    parts.append(f"## Avatar: record once\n\n- {len(clips)} clips, about {sum(c.estimated_seconds for c in clips) / 60:.1f} min of speech "
                 f"(opening with the AI disclosure, {len(cfg['questions'])} questions, transitions, closing, 3 fallbacks)\n"
                 f"- interview plan: pre-recorded clips + at most {av_interview.MAX_FOLLOW_UPS} voice-AI follow-up per question\n")
    transcripts = sorted((ex / "transcripts").glob("*.json"))
    results = [av_rubric.label(load(f), rub, av_providers.KeywordDemoScorer()) for f in transcripts]
    parts.append(av_rubric.render(results))

    html = av_page.build(cfg, rub)
    parts.append(disclosure.render(disclosure.evaluate(load(ex / "disclosure.yaml"), html)))

    tpl = load(ex / "templates.yaml")
    drafts, errors = messages.draft_all(load(ex / "outreach.csv"), tpl)
    q = pacing.plan(messages.to_json(drafts), datetime(2026, 1, 5, 9, 0), pacing.Limits(), seed=7)
    parts.append(f"## Outreach drafts\n\n- {len(drafts)} personal drafts; skipped: " + ("; ".join(errors) or "none") + "\n")
    parts.append(render_queue(q, pacing.Limits(), head=8))
    parts.append(tracker.render(tracker.analyse(load(ex / "replies.csv"), date(2026, 1, 20))))
    parts.append(f"---\nMethod: payrollburn AI-hiring report, DOI {CONCEPT_DOI} · https://arsentev.ai/research/ai-hiring\n")
    text = "\n".join(parts)
    print(text)
    if out:
        (out / "demo-report.md").write_text(text, encoding="utf-8")
        (out / "candidate-page.html").write_text(html, encoding="utf-8")
        (out / "recording-script.md").write_text(av_script.render(clips, cfg), encoding="utf-8")
        (out / "queue.json").write_text(json.dumps(q, indent=2), encoding="utf-8")
        print(f"wrote demo-report.md, candidate-page.html, recording-script.md, queue.json to {out}", file=sys.stderr)


# ------------------------------------------------------------------ parser


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="hireburn", description="Open-source AI HR hunter: avatar interviews, human-pace outreach, funnel leaks.")
    p.add_argument("--version", action="version", version=f"hireburn {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("funnel", help="losses per stage, show-up and completion rates")
    s.add_argument("file"); s.add_argument("--json", action="store_true"); s.set_defaults(fn=cmd_funnel)
    s = sub.add_parser("labels", help="AI label vs who is working on day N")
    s.add_argument("file"); s.add_argument("--day", type=int, default=30)
    s.add_argument("--snapshot", type=int, help="day number of the snapshot, for the equal-window view")
    s.add_argument("--json", action="store_true"); s.set_defaults(fn=cmd_labels)
    s = sub.add_parser("disclosure", help="candidate disclosure checklist (not legal advice)")
    s.add_argument("file", nargs="?"); s.add_argument("--page", help="candidate page HTML to check")
    s.add_argument("--strict", action="store_true", help="exit 2 if any item is 'no'")
    s.add_argument("--json", action="store_true"); s.set_defaults(fn=cmd_disclosure)

    av = sub.add_parser("avatar", help="record-once avatar interview kit").add_subparsers(dest="sub", required=True)
    s = av.add_parser("checklist"); s.set_defaults(fn=cmd_av_checklist)
    s = av.add_parser("script"); s.add_argument("file"); s.add_argument("--json", action="store_true"); s.set_defaults(fn=cmd_av_script)
    s = av.add_parser("plan"); s.add_argument("file"); s.set_defaults(fn=cmd_av_plan)
    s = av.add_parser("page"); s.add_argument("file"); s.add_argument("--rubric"); s.add_argument("-o", "--out"); s.set_defaults(fn=cmd_av_page)
    s = av.add_parser("score"); s.add_argument("files", nargs="+"); s.add_argument("--rubric", required=True)
    s.add_argument("--scorer", help="your Scorer: package.module:ClassName"); s.add_argument("--manual", help="JSON of scores typed by a person")
    s.add_argument("--json", action="store_true"); s.set_defaults(fn=cmd_av_score)

    out = sub.add_parser("outreach", help="LinkedIn outreach at a human pace; a person sends").add_subparsers(dest="sub", required=True)
    s = out.add_parser("draft"); s.add_argument("file"); s.add_argument("--templates", required=True)
    s.add_argument("--kind", action="append", help="template name (repeatable), default: first"); s.add_argument("-o", "--out"); s.set_defaults(fn=cmd_out_draft)
    s = out.add_parser("plan"); s.add_argument("drafts"); s.add_argument("--start", help="ISO datetime, default now")
    s.add_argument("--limits", help="YAML/JSON overriding default limits"); s.add_argument("--seed", type=int)
    s.add_argument("-o", "--out"); s.set_defaults(fn=cmd_out_plan)
    s = out.add_parser("run"); s.add_argument("queue"); s.add_argument("--drafts"); s.add_argument("--limits")
    s.add_argument("--state", default=".hireburn"); s.add_argument("--open", action="store_true", help="open each profile in your browser")
    s.add_argument("--no-wait", action="store_true", help="exit instead of waiting for the next allowed slot"); s.set_defaults(fn=cmd_out_run)
    s = out.add_parser("stop"); s.add_argument("--reason", required=True); s.add_argument("--state", default=".hireburn"); s.set_defaults(fn=cmd_out_stop)
    s = out.add_parser("resume"); s.add_argument("--account-checked", action="store_true"); s.add_argument("--state", default=".hireburn"); s.set_defaults(fn=cmd_out_resume)
    s = out.add_parser("track"); s.add_argument("file"); s.add_argument("--today"); s.add_argument("--json", action="store_true"); s.set_defaults(fn=cmd_out_track)

    s = sub.add_parser("demo", help="run everything on the synthetic example company")
    s.add_argument("--data"); s.add_argument("--out"); s.set_defaults(fn=cmd_demo)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        rc = args.fn(args)
    except (ValueError, PermissionError, FileNotFoundError) as e:
        print(f"hireburn: {e}", file=sys.stderr)
        return 1
    return int(rc or 0)


if __name__ == "__main__":
    raise SystemExit(main())
