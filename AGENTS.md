# AGENTS.md — set up hireburn for a user

You are a coding agent (Claude Code, Codex, Cursor or similar). A user asked you to install hireburn
and set it up for their vacancy. This file is the whole procedure. The user should never have to
type a command or read the README: you run everything, you ask only about their hiring.

hireburn is Python 3.10+, standard library only, no network calls. It never sends a LinkedIn
message and never calls an avatar or voice-AI provider. It writes files; people and providers do
the rest.

## 0. Ground rules

- Talk to the user in their language. Ask in small batches (step 3), not one long form.
- Never invent facts about their company, role, people or law. If an answer is missing, ask.
- Nothing about real candidates leaves the user's machine. Do not paste candidate data into web tools.
- **A person presses "Send" in LinkedIn. Always.** hireburn only plans the queue. Do not automate
  LinkedIn, do not drive a browser to send, do not raise the limits above the defaults. Say this to
  the user in plain words before the outreach step.
- The AI disclosure on the candidate page is the feature, not small print. Never remove it, never
  bypass `DisclosureMissing`. If the page refuses to build, ask the user for the missing fact.
- The HIRE / MAYBE / NO label is not a measurement. Every NO goes to a person before anyone is
  rejected. Score answer content only; never voice, accent or face.

## 1. Install

Work in a new folder the user agrees to, for example `~/hiring/<role-slug>`.

```bash
git clone https://github.com/arsentev-ai/hireburn
cd hireburn
python3 -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install .
hireburn --version
```

No git? `pip install hireburn` works too (same package on PyPI). No Python 3.10+? Tell the user what
to install for their OS, then continue. Docker is optional: `docker build -t hireburn . && docker run --rm hireburn`.

## 2. Run the demo (proves the install, shows the user what they will get)

```bash
hireburn demo --out demo-out
```

Everything in it is a synthetic example company. Show the user, in two or three lines: the funnel
table, the avatar clip count, and that `demo-out/candidate-page.html` is what candidates will see.
Open nothing in the user's browser yourself; give them the file path.

## 3. Ask the user (in this order, a few questions at a time)

1. Company name as candidates should see it.
2. Role title, and what a good first month in it looks like (one or two sentences).
3. Interviewer whose avatar this is: full name and job title. Confirm this person agrees to an
   AI avatar made from their recordings (consent and likeness).
4. Five interview questions. Offer drafts based on answer 2 if they want; they approve the final
   wording. For each question: what a good answer shows (`listen_for`) and whether the voice AI may
   ask one short follow-up (`max_followups`: 0 or 1, never more).
5. Contact for a human alternative: an email or link where a candidate can ask for a person instead
   of the avatar.
6. How long answers are kept (`retention_days`, e.g. 90) and that candidates can ask for deletion.
7. Interview length in minutes and how many days candidates have to reply.
8. For outreach: their working hours and time zone; a list of profiles they want to reach (or let
   them fill it later).

## 4. Write the config (copy the shapes from `examples/example-company/`)

Make a folder `my-hiring/` next to the clone and write:

- `interview.yaml` — company, role, minutes, reply_days, interviewer {name, title},
  alternative_contact, retention_days, clips_base_url: clips/, questions [{id, text, listen_for,
  max_followups}].
- `rubric.yaml` — one criterion per question: id, question_id, weight, what, anchors {1, 3, 5},
  evidence_words; thresholds {hire, maybe}. Keep the example's header comment: content of answers
  only.
- `templates.yaml` — connect / first / follow_up_1 / follow_up_2. Keep `{hook}`: one sentence a
  person writes after actually reading each profile. Mention the AI avatar interview and that a
  person is available instead.
- `disclosure.yaml` — answer every item of `hireburn disclosure` honestly (yes / partly / no / n/a
  with a note). This is a yardstick against NYC Local Law 144, the Illinois AI Video Interview Act,
  Illinois HB 3773 and the EU AI Act. It is not legal advice; say so.
- `outreach.csv` — `id,first_name,profile_url,role,company,manager_title,hook,do_not_contact`.
  Leave `hook` empty for the user to write; rows without a hook are skipped on purpose.

Remove every "SYNTHETIC" / "Example Company" value. Show the user the five questions and the
rubric once for approval.

## 5. Avatar: recording script and checklist

```bash
hireburn avatar checklist                     > my-hiring/recording-checklist.md
hireburn avatar script my-hiring/interview.yaml > my-hiring/recording-script.md
hireburn avatar plan   my-hiring/interview.yaml > my-hiring/interview-plan.json
```

Tell the user: a window, a phone and about twenty minutes, once. They record each clip in the
script in order, opening clip with the disclosure read exactly as written. Fix any clip the script
warns is too long. Clips go to `my-hiring/clips/` (file names from the script). Making the avatar
itself is done in the user's own avatar provider; hireburn holds no keys.

## 6. Candidate page

```bash
hireburn avatar page my-hiring/interview.yaml --rubric my-hiring/rubric.yaml -o my-hiring/candidate-page.html
hireburn disclosure my-hiring/disclosure.yaml --page my-hiring/candidate-page.html
```

If the page refuses to build, a disclosure fact is missing: ask the user, never fill it in
yourself. Report the disclosure checklist result in plain words, including every "no" and "partly".
Hosting the page is the user's choice (any static host); the Start button stays disabled until the
candidate ticks consent.

## 7. Outreach plan (a human pace, a human hand)

```bash
hireburn outreach draft my-hiring/outreach.csv --templates my-hiring/templates.yaml -o my-hiring/drafts.json
hireburn outreach plan  my-hiring/drafts.json -o my-hiring/queue.json
```

Give the user today's queue in plain words from `queue.json` (who, which action, when, the draft
text). `hireburn outreach run my-hiring/queue.json --drafts my-hiring/drafts.json` is the person's
own interactive pacer (d = done, s = skip, w = warning, q = quit): it waits for the next allowed
slot and shows the text; the person opens LinkedIn and presses Send themselves. Do not answer its
prompts on the user's behalf.
Defaults: about 10 sends per hour, 25 connection requests and 40 messages per day, working hours
only. hireburn refuses more than 20 sends per hour. On the first LinkedIn warning or captcha:
`hireburn outreach stop --reason "<what happened>"`; resume only after the user checked the
account (`hireburn outreach resume --account-checked`). Replies go into a CSV like
`examples/example-company/replies.csv`; `hireburn outreach track` lists follow-ups and the
do-not-contact list.

## 8. After first interviews: where the funnel leaks

```bash
hireburn avatar score transcripts/*.json --rubric my-hiring/rubric.yaml --manual scores.json
hireburn funnel  my-hiring/funnel.csv
hireburn labels  my-hiring/candidates.csv --day 30
```

Explain losses per stage, show-up and completion rates, and the AI label against who is still
working on day N. Remind the user: a person reads every NO before a rejection.

## 9. Hand-over message to the user

End with a short summary: where the files are, the recording script to record, the candidate page
file, today's outreach queue, and three reminders: the person presses Send; every NO is read by a
person; the label is not a measurement.

Method and case: DOI [10.5281/zenodo.23927437](https://doi.org/10.5281/zenodo.23927437) ·
software DOI [10.5281/zenodo.23979629](https://doi.org/10.5281/zenodo.23979629) ·
part of the free Digital employees catalog: [arsentev.ai/employees](https://arsentev.ai/employees).
