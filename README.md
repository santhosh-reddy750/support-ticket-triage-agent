# Support Ticket Triage Agent

**Real problem:** SaaS support inboxes get flooded. Agents waste time deciding priority, routing tickets to the wrong team, and writing the first reply — while urgent outages sit behind “how do I…” questions.

**What this project does:** An AI triage agent that reads each ticket and returns:

| Decision | Example |
|---|---|
| Priority | `P0` / `P1` / `P2` / `P3` |
| Category | billing, bug, security, integration, … |
| Owner team | Billing, Engineering, Security, Success, Product |
| SLA target | minutes until first response |
| Escalate? | yes/no + reason |
| Suggested reply | ready-to-send first response |

Built for the exact workflow AI/ML and SaaS startups run in Intercom/Zendesk/Freshdesk.

## Real-world use case

A 10-person SaaS company receives 80+ tickets/day.

1. Export or webhook tickets into JSON/CSV  
2. Run the triage agent on the batch  
3. Auto-tag + assign in the helpdesk  
4. Agents only edit the drafted reply instead of starting from zero  

Impact: faster first response, fewer misroutes, P0 incidents surface immediately.

## Demo (no API key required)

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -e ".[dev]"
python -m triage_agent demo
```

Sample inbox: `data/sample_tickets.json` (outage, double charge, SSO lockout, security breach, angry churn threat, how-to, feature request).

Outputs:
- `output/triage_results.json` — machine-readable decisions
- `output/triage_report.md` — human review report

## CLI

```bash
# Batch triage
python -m triage_agent run data/sample_tickets.json -o output

# Single ticket
python -m triage_agent ticket \
  --subject "Production API is down" \
  --body "All users getting 500s on checkout" \
  --plan enterprise \
  --email ops@acme.com
```

## Optional LLM mode

Copy `.env.example` → `.env` and set `OPENAI_API_KEY`.

- **With key:** richer classification + natural reply drafts (OpenAI-compatible APIs supported)
- **Without key:** deterministic rules engine — still production-shaped and fully demoable

## How it works

```text
Ticket JSON/CSV
      │
      ▼
┌─────────────┐   ┌──────────────┐   ┌────────────┐   ┌──────────────┐
│  Classify   │──▶│  Prioritize  │──▶│   Route    │──▶│ Draft reply  │
│  category   │   │  P0-P3 + SLA │   │ owner team │   │ + escalate?  │
└─────────────┘   └──────────────┘   └────────────┘   └──────────────┘
```

Rules encode support ops heuristics (security → P0 + Security team, enterprise outage → escalate, angry refund threats → escalate, how-to → P3 / Success).

## Project layout

```text
src/triage_agent/
  engine.py     # triage pipeline
  rules.py      # deterministic support heuristics
  replies.py    # first-response templates
  llm.py        # optional OpenAI path
  cli.py        # Typer + Rich CLI
data/sample_tickets.json
tests/
```

## Why this belongs on an AI/ML startup profile

- Solves a **budgeted business problem** (support cost + SLA)
- Shows **agent decisioning** with confidence, rationale, escalation
- Ships **offline + LLM** paths (pragmatic production design)
- Easy for a founder/hiring manager to demo in 2 minutes

## License

MIT
