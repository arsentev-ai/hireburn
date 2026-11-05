# Examples

`example-company/` is a **synthetic** example company. Every number, name, person, link and
transcript in it is made up, and the numbers are round on purpose. It exists so every command
has something to run on:

```bash
python3 -m hireburn demo                       # all three parts
python3 -m hireburn demo --out demo-output     # also writes the candidate page, script and queue
```

| file | what it shows |
|---|---|
| `funnel.csv` | stage counts from 3,000 applications to 18 people working on day 30 |
| `candidates.csv` | 40 candidates, 10 per AI label, with outcomes on day 30 |
| `interview.yaml`, `rubric.yaml` | a five-question avatar interview for an invented support role |
| `transcripts/*.json` | three short transcripts scored by the offline demo scorer |
| `disclosure.yaml` | how the example company answers the disclosure checklist |
| `outreach.csv`, `templates.yaml`, `replies.csv` | outreach cards (one without a hook, one do-not-contact), templates, reply log |
