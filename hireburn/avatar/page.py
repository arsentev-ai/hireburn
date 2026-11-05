"""Static candidate page with the AI disclosure built in — compliant by default.

The page cannot be generated without the disclosure facts: who the avatar is, what
is evaluated, how long recordings are kept, how to ask for a person instead. They
appear on the first screen, before the consent checkbox; the Start button stays
disabled until the candidate ticks it. ``hireburn disclosure --page`` checks the
markers on any page you edit later.

The page is a single HTML file with no external scripts. It plays the clips from
``clips_base_url`` (``<clip id>.mp4``), records answers from the microphone with
the browser's MediaRecorder, allows re-recording, and either POSTs each answer to
``upload_url`` or lets the candidate download them. If ``follow_up_url`` is set, the
page sends each answer there and plays back at most one follow-up per question.

Not legal advice: the page covers telling, explaining, consent, retention, the
alternative and human review. Notice periods, bias audits and reporting are on you
— see ``hireburn disclosure``.
"""

from __future__ import annotations

import json
from html import escape
from typing import Any, Mapping

from hireburn.avatar.interview import plan

REQUIRED = ("company", "role", "interviewer", "alternative_contact", "retention_days", "questions")


class DisclosureMissing(ValueError):
    pass


def build(cfg: Mapping[str, Any], rubric: Mapping[str, Any] | None = None) -> str:
    missing = [k for k in REQUIRED if not cfg.get(k)]
    if missing:
        raise DisclosureMissing(
            "the candidate page needs " + ", ".join(missing) + " — they are part of the AI disclosure, not optional"
        )
    who = cfg["interviewer"]
    if not who.get("name"):
        raise DisclosureMissing("interviewer.name is required: the page says whose avatar this is")
    evaluates = [c.get("what", c["id"]) for c in (rubric or {}).get("criteria", [])] or [
        q.get("listen_for", q["text"]) for q in cfg["questions"]
    ]
    p = plan(cfg)
    e = {k: escape(str(v)) for k, v in {
        "company": cfg["company"], "role": cfg["role"], "name": who["name"],
        "title": who.get("title", "hiring manager"), "minutes": cfg.get("minutes", 20),
        "alt": cfg["alternative_contact"], "days": cfg["retention_days"],
    }.items()}
    alt_href = escape(cfg["alternative_contact"] if "://" in cfg["alternative_contact"]
                      else "mailto:" + cfg["alternative_contact"])
    config = {
        "clipsBase": cfg.get("clips_base_url", "clips/"),
        "uploadUrl": cfg.get("upload_url", ""),
        "followUpUrl": cfg.get("follow_up_url", ""),
        "steps": p["steps"],
        "questions": {q.get("id", f"q{n}"): q["text"] for n, q in enumerate(cfg["questions"], 1)},
    }
    eval_items = "".join(f"<li>{escape(str(x))}</li>" for x in evaluates)
    return PAGE.format(
        **e, alt_href=alt_href, eval_items=eval_items,
        config=json.dumps(config).replace("</", "<\\/"),
    )


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{role} — first interview · {company}</title>
<style>
  :root {{ --bg:#0B0C0E; --fg:#F2EFE8; --mut:#8A8F98; --acc:#FF6A1A; }}
  body {{ margin:0; font:16px/1.5 -apple-system, "Segoe UI", sans-serif; background:var(--bg); color:var(--fg); }}
  main {{ max-width:720px; margin:0 auto; padding:32px 20px 64px; }}
  .box {{ border:1px solid #2a2d33; border-radius:14px; padding:18px 20px; margin:16px 0; }}
  .ai {{ border-color:var(--acc); }}
  h1 {{ font-size:26px; margin:0 0 4px; }} small, .mut {{ color:var(--mut); }}
  button {{ font:inherit; padding:10px 18px; border-radius:10px; border:0; background:var(--acc); color:#111; cursor:pointer; }}
  button:disabled {{ opacity:.35; cursor:not-allowed; }}
  video {{ width:100%; border-radius:14px; background:#000; margin-top:12px; }}
  a {{ color:var(--acc); }}
</style>
</head>
<body>
<main>
  <h1>{role}</h1>
  <div class="mut">First interview · {company} · about {minutes} minutes · you answer out loud</div>

  <section class="box ai" data-hireburn="disclosure">
    <strong>You will be talking to an AI avatar.</strong> The person in the video is an AI avatar created from
    recordings of {name}, {title}. It is not a live call. Short follow-up questions may come from a voice AI.
    An AI model reads the text of your answers and suggests a label; it does not decide on its own.
  </section>

  <section class="box" data-hireburn="evaluates">
    <strong>What we look at</strong> — the content of your answers only, never your voice, accent or face:
    <ul>{eval_items}</ul>
  </section>

  <section class="box" data-hireburn="human_review">
    A person on our team reads every interview before any decision. Nobody is turned down on the AI label alone.
  </section>

  <section class="box" data-hireburn="retention">
    We save your audio and a text transcript for {days} days, only for this hiring decision, visible only to the
    people who evaluate it. Ask us to delete them at any time and we will.
  </section>

  <section class="box" data-hireburn="alternative">
    Prefer to talk to a person, or need an accommodation? <a href="{alt_href}">{alt}</a> — you lose nothing by asking.
  </section>

  <label class="box" style="display:block" data-hireburn="consent">
    <input type="checkbox" id="consent"> I have read the above and agree to an interview with an AI avatar,
    and to my answers being recorded and read as described.
  </label>
  <button id="start" disabled>Start the interview</button>

  <div id="stage" hidden>
    <video id="player" playsinline controls></video>
    <p id="prompt" class="mut"></p>
    <button id="rec">Record answer</button> <button id="again" hidden>Record again</button>
    <button id="next" hidden>Next</button>
    <div id="out"></div>
  </div>
</main>
<script>
const CFG = {config};
const $ = (id) => document.getElementById(id);
$("consent").addEventListener("change", (e) => {{ $("start").disabled = !e.target.checked; }});
let i = 0, rec = null, chunks = [], lastBlob = null, followUps = {{}};
const answers = [];
function play(clip) {{
  return new Promise((ok) => {{ const v = $("player"); v.src = CFG.clipsBase + clip + ".mp4"; v.onended = ok; v.onerror = ok; v.play().catch(ok); }});
}}
async function speak(text) {{ $("prompt").textContent = text; }}
async function record() {{
  const stream = await navigator.mediaDevices.getUserMedia({{ audio: true }});
  chunks = []; rec = new MediaRecorder(stream);
  rec.ondataavailable = (e) => chunks.push(e.data);
  rec.onstop = () => {{ lastBlob = new Blob(chunks, {{ type: rec.mimeType }}); stream.getTracks().forEach(t => t.stop());
    $("again").hidden = false; $("next").hidden = false; $("rec").textContent = "Record answer"; }};
  rec.start(); $("rec").textContent = "Stop";
}}
$("rec").onclick = () => (rec && rec.state === "recording") ? rec.stop() : record();
$("again").onclick = () => {{ lastBlob = null; $("again").hidden = true; $("next").hidden = true; record(); }};
async function save(qid, blob) {{
  answers.push({{ qid, blob }});
  if (CFG.uploadUrl) {{ const f = new FormData(); f.append("question_id", qid); f.append("audio", blob, qid + ".webm");
    await fetch(CFG.uploadUrl, {{ method: "POST", body: f }}).catch(() => {{}}); }}
}}
async function askFollowUp(qid, blob) {{
  if (!CFG.followUpUrl || followUps[qid]) return null;      // at most ONE follow-up per question
  followUps[qid] = 1;
  const f = new FormData(); f.append("question_id", qid); f.append("audio", blob, qid + ".webm");
  try {{ const r = await fetch(CFG.followUpUrl, {{ method: "POST", body: f }}); const j = await r.json(); return j.text || null; }}
  catch (e) {{ return null; }}
}}
function waitNext() {{ return new Promise((ok) => {{ $("next").onclick = () => {{ $("next").hidden = true; $("again").hidden = true; ok(); }}; }}); }}
async function runSteps() {{
  for (const s of CFG.steps) {{
    if (s.step === "play") await play(s.clip);
    if (s.step === "record_answer") {{ await speak(CFG.questions[s.question_id] || ""); $("rec").hidden = false; await waitNext(); await save(s.question_id, lastBlob); }}
    if (s.step === "optional_follow_up") {{ const t = await askFollowUp(s.question_id, lastBlob);
      if (t) {{ await speak(t); await waitNext(); await save(s.question_id + ":follow_up", lastBlob); }} }}
  }}
  $("rec").hidden = true; $("prompt").textContent = "Thank you — that's all.";
  if (!CFG.uploadUrl) answers.forEach(a => {{ const l = document.createElement("a"); l.href = URL.createObjectURL(a.blob);
    l.download = a.qid + ".webm"; l.textContent = "Download " + a.qid; $("out").append(l, document.createElement("br")); }});
}}
$("start").onclick = () => {{ if (!$("consent").checked) return; $("start").hidden = true; $("stage").hidden = false; runSteps(); }};
</script>
</body>
</html>
"""
