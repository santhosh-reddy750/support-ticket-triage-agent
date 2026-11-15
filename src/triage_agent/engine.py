from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from triage_agent.llm import LLMClient
from triage_agent.models import (
    BatchReport,
    Category,
    Priority,
    Team,
    Ticket,
    TriageResult,
)
from triage_agent.replies import draft_reply, summarize
from triage_agent import rules


SYSTEM_PROMPT = """You are a SaaS support triage agent.
Given one support ticket, return JSON with:
priority (P0|P1|P2|P3),
category (billing|bug|account|integration|feature_request|how_to|security|other),
owner_team (Billing|Engineering|Customer Success|Security|Product),
sentiment (positive|neutral|frustrated|angry),
escalate (boolean),
escalate_reason (string|null),
tags (string array),
summary (one line),
suggested_reply (professional email body),
confidence (0-1),
rationale (string array of short reasons).

Rules of thumb:
- P0: outage, data loss, payment broken, security incident
- P1: major breakage / enterprise high impact
- P2: degraded experience with workaround
- P3: how-to / feature request / minor
Escalate P0, security, angry tone, or enterprise+high severity.
"""


class TriageAgent:
    """End-to-end ticket triage: classify -> prioritize -> route -> draft -> escalate?"""

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()

    def triage(self, ticket: Ticket) -> TriageResult:
        if self.llm.enabled:
            llm_result = self._triage_with_llm(ticket)
            if llm_result is not None:
                return llm_result
        return self._triage_with_rules(ticket)

    def triage_many(self, tickets: list[Ticket]) -> BatchReport:
        results = [self.triage(t) for t in tickets]
        by_priority = Counter(r.priority.value for r in results)
        by_team = Counter(r.owner_team.value for r in results)
        return BatchReport(
            total=len(results),
            by_priority=dict(by_priority),
            by_team=dict(by_team),
            escalations=sum(1 for r in results if r.escalate),
            results=results,
        )

    def _triage_with_rules(self, ticket: Ticket) -> TriageResult:
        category = rules.classify_category(ticket)
        priority = rules.classify_priority(ticket, category)
        sentiment = rules.sentiment_for(ticket)
        escalate, reason = rules.should_escalate(ticket, priority, sentiment, category)
        owner = rules.owner_for(category)
        tags = rules.extract_tags(ticket, category, priority)
        sla = rules.sla_minutes(priority, ticket.customer_plan)
        summary = summarize(ticket, category, priority)
        reply = draft_reply(
            ticket, category=category, priority=priority, escalate=escalate
        )
        rationale = [
            f"category from keywords -> {category.value}",
            f"priority -> {priority.value}",
            f"plan={ticket.customer_plan}",
            f"sentiment={sentiment}",
        ]
        if escalate and reason:
            rationale.append(f"escalate because {reason}")
        return TriageResult(
            ticket_id=ticket.id,
            priority=priority,
            category=category,
            owner_team=owner,
            tags=tags,
            sentiment=sentiment,
            escalate=escalate,
            escalate_reason=reason,
            sla_minutes=sla,
            summary=summary,
            suggested_reply=reply,
            confidence=0.78,
            mode="rules",
            rationale=rationale,
        )

    def _triage_with_llm(self, ticket: Ticket) -> TriageResult | None:
        payload = self.llm.complete_json(
            SYSTEM_PROMPT,
            (
                f"Ticket ID: {ticket.id}\n"
                f"Plan: {ticket.customer_plan}\n"
                f"Channel: {ticket.channel}\n"
                f"From: {ticket.customer_email}\n"
                f"Subject: {ticket.subject}\n"
                f"Body:\n{ticket.body}"
            ),
        )
        if not payload:
            return None
        try:
            priority = Priority(str(payload.get("priority", "P2")))
            category = Category(str(payload.get("category", "other")))
            owner = Team(str(payload.get("owner_team", Team.SUCCESS.value)))
        except ValueError:
            return None

        sentiment = str(payload.get("sentiment") or "neutral")
        escalate = bool(payload.get("escalate", False))
        reason = payload.get("escalate_reason")
        tags = payload.get("tags") if isinstance(payload.get("tags"), list) else []
        rationale = (
            payload.get("rationale") if isinstance(payload.get("rationale"), list) else []
        )
        confidence = payload.get("confidence", 0.85)
        try:
            confidence_f = float(confidence)
        except (TypeError, ValueError):
            confidence_f = 0.85

        summary = str(payload.get("summary") or summarize(ticket, category, priority))
        reply = str(
            payload.get("suggested_reply")
            or draft_reply(ticket, category=category, priority=priority, escalate=escalate)
        )
        return TriageResult(
            ticket_id=ticket.id,
            priority=priority,
            category=category,
            owner_team=owner,
            tags=[str(t) for t in tags],
            sentiment=sentiment,
            escalate=escalate,
            escalate_reason=str(reason) if reason else None,
            sla_minutes=rules.sla_minutes(priority, ticket.customer_plan),
            summary=summary,
            suggested_reply=reply,
            confidence=max(0.0, min(1.0, confidence_f)),
            mode="openai",
            rationale=[str(r) for r in rationale],
        )


def load_tickets(path: str | Path) -> list[Ticket]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and "tickets" in raw:
            raw = raw["tickets"]
        return [Ticket.model_validate(item) for item in raw]
    if path.suffix.lower() == ".csv":
        tickets: list[Ticket] = []
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                tickets.append(
                    Ticket(
                        id=row.get("id") or row.get("ticket_id") or "unknown",
                        subject=row.get("subject") or "",
                        body=row.get("body") or row.get("description") or "",
                        customer_email=row.get("customer_email") or "customer@example.com",
                        customer_plan=row.get("customer_plan") or "pro",
                        channel=row.get("channel") or "email",
                    )
                )
        return tickets
    raise ValueError("Supported ticket formats: .json or .csv")


def save_results(report: BatchReport, output_dir: str | Path) -> dict[str, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "triage_results.json"
    md_path = out / "triage_report.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    md_path.write_text(_to_markdown(report), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def _to_markdown(report: BatchReport) -> str:
    lines = [
        "# Support Ticket Triage Report",
        "",
        f"- Total tickets: **{report.total}**",
        f"- Escalations: **{report.escalations}**",
        f"- By priority: {report.by_priority}",
        f"- By team: {report.by_team}",
        "",
    ]
    for result in report.results:
        lines.extend(
            [
                f"## {result.ticket_id} — {result.summary}",
                "",
                f"- Priority: `{result.priority.value}`",
                f"- Category: `{result.category.value}`",
                f"- Owner: **{result.owner_team.value}**",
                f"- Sentiment: {result.sentiment}",
                f"- SLA target: {result.sla_minutes} minutes",
                f"- Escalate: **{result.escalate}**"
                + (f" ({result.escalate_reason})" if result.escalate_reason else ""),
                f"- Confidence: {result.confidence:.2f} ({result.mode})",
                f"- Tags: {', '.join(result.tags)}",
                "",
                "### Suggested reply",
                "",
                "```",
                result.suggested_reply,
                "```",
                "",
            ]
        )
    return "\n".join(lines)
