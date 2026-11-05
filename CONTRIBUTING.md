# Contributing

Thanks for taking an interest in `hireburn`.

## Reporting a problem

Open an issue with:

- the command you ran and its output;
- your Python version (`python3 --version`) and operating system;
- if a number looks wrong, a **made-up** input that reproduces it. Please never paste real
  candidate data, transcripts, names or profile links: they are personal data.

## Proposing a change

1. Fork the repository and create a branch.
2. Keep the package dependency-free: it must run on a stock `python3` 3.10+.
3. Keep it offline: no network calls, no telemetry. Provider integrations belong in your own
   adapter that implements the interfaces in `hireburn/avatar/providers.py`.
4. If you change how a number is computed, explain the reasoning in the pull request and show
   the output before and after on the example company.
5. Run `python3 -m pytest` and update `CHANGELOG.md` under an "Unreleased" heading.

## What will not be merged

- Anything that sends, clicks, types or logs in on LinkedIn or any other site; headless
  browsers; scraping; proxy or fingerprint rotation; ways around rate limits, captchas or
  detection. A person sends. Raising the default pace limits needs a good reason and a source.
- Options that hide or weaken the AI disclosure on the candidate page, or let the rubric score
  tone of voice, emotion, accent or appearance.
- Vendor-specific code in the core package. Adapters are welcome as examples in a separate
  folder, with no keys and clearly marked as third-party.

## Legal checklist

The disclosure checklist is a yardstick, not legal advice. Corrections are welcome — please
link the primary source (statute, regulation or regulator guidance) in the pull request.
