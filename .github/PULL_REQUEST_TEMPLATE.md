## What this changes

<!-- One or two sentences. Link the issue if there is one: "Closes #12". -->

## How I checked it

- [ ] `python3 -m pytest` passes
- [ ] `hireburn demo` still runs
- [ ] If a number is computed differently: output before and after on the example company is in this PR

## Project rules

- [ ] No new dependencies; no network calls or telemetry in the core package
- [ ] Nothing that sends, clicks, types or logs in on LinkedIn or any other site
- [ ] The AI disclosure on the candidate page is not hidden or weakened
- [ ] No real candidate data in code, tests, examples or screenshots
- [ ] `CHANGELOG.md` updated under "Unreleased"
