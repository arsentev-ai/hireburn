# Security policy

## Supported versions

Security fixes go into the latest release on PyPI and into `main`.

| Version | Supported |
| ------- | --------- |
| 0.1.x   | yes       |

## Reporting a vulnerability

Please do not open a public issue. Report privately through GitHub:
**Security → Report a vulnerability** on this repository
(<https://github.com/arsentev-ai/hireburn/security/advisories/new>).

Include the version, what an attacker can do, and a minimal made-up input that shows it.
You can expect a first reply within 7 days. Once a fix is released, the advisory is published
with credit to the reporter unless you prefer to stay anonymous.

## Scope

hireburn runs locally and makes no network calls. Issues that matter most here:

- the generated candidate page (`hireburn avatar page`): script injection through config or
  transcript fields, or any way to start the interview without the AI disclosure and consent;
- file handling in the CSV / YAML / JSON readers (path traversal, writing outside the output
  folder);
- anything that could leak candidate data the user did not ask to export.

Please never include real candidate data in a report.
