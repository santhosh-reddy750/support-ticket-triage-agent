from __future__ import annotations

import re

from triage_agent.models import Category, Priority, Team, Ticket

P0_PATTERNS = [
    r"\b(down|outage|can't log ?in|cannot log ?in|data loss|deleted all|payment failed|charged twice|security breach|hacked|leak)\b",
    r"\b(production|prod)\b.*\b(down|broken|failing)\b",
    r"\burgent\b.*\b(asap|immediately|critical)\b",
]

P1_PATTERNS = [
    r"\b(broken|not working|error 500|timeout|can't (upload|export|sync)|blocked)\b",
    r"\b(all (users|team)|entire (org|company))\b",
    r"\b(enterprise|sla)\b",
]

BILLING_PATTERNS = [
    r"\b(invoice|refund|charge|billing|subscription|upgrade|downgrade|payment|card)\b",
]
SECURITY_PATTERNS = [
    r"\b(security|breach|hack|phishing|unauthorized|2fa|mfa|vulnerability)\b",
]
ACCOUNT_PATTERNS = [
    r"\b(password|reset|login|sso|invite|seat|access|permission|role)\b",
]
INTEGRATION_PATTERNS = [
    r"\b(api|webhook|zapier|slack|salesforce|integration|oauth|sdk)\b",
]
FEATURE_PATTERNS = [
    r"\b(feature request|would be nice|can you add|roadmap|suggestion)\b",
]
HOW_TO_PATTERNS = [
    r"\b(how (do|can|to)|where (do|can)|help me|guide|tutorial|docs)\b",
]
BUG_PATTERNS = [
    r"\b(bug|crash|exception|stack trace|broken|not working|error)\b",
]

ANGRY = [r"\b(lawsuit|cancel|terrible|worst|furious|unacceptable|refund now)\b"]
FRUSTRATED = [r"\b(again|still broken|frustrated|annoying|waiting|no response)\b"]


def _hit(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


def classify_category(ticket: Ticket) -> Category:
    text = f"{ticket.subject}\n{ticket.body}"
    if _hit(SECURITY_PATTERNS, text):
        return Category.SECURITY
    if _hit(BILLING_PATTERNS, text):
        return Category.BILLING
    # Outages / prod failures are bugs even if "API" keywords appear.
    if _hit(P0_PATTERNS, text) and _hit(BUG_PATTERNS + P1_PATTERNS, text):
        return Category.BUG
    if _hit(FEATURE_PATTERNS, text):
        return Category.FEATURE_REQUEST
    # Prefer how-to over account when the user is asking for guidance.
    if _hit(HOW_TO_PATTERNS, text):
        return Category.HOW_TO
    if _hit(INTEGRATION_PATTERNS, text):
        return Category.INTEGRATION
    if _hit(ACCOUNT_PATTERNS, text):
        return Category.ACCOUNT
    if _hit(BUG_PATTERNS, text):
        return Category.BUG
    return Category.OTHER


def classify_priority(ticket: Ticket, category: Category) -> Priority:
    text = f"{ticket.subject}\n{ticket.body}"
    plan = ticket.customer_plan.lower()

    if _hit(P0_PATTERNS, text) or category == Category.SECURITY:
        return Priority.P0
    if _hit(P1_PATTERNS, text) or plan == "enterprise":
        if category in {Category.BUG, Category.ACCOUNT, Category.INTEGRATION, Category.BILLING}:
            return Priority.P1
    if category in {Category.BUG, Category.BILLING, Category.ACCOUNT, Category.INTEGRATION}:
        return Priority.P2
    if category in {Category.HOW_TO, Category.FEATURE_REQUEST}:
        return Priority.P3
    return Priority.P2


def owner_for(category: Category) -> Team:
    return {
        Category.BILLING: Team.BILLING,
        Category.BUG: Team.ENGINEERING,
        Category.ACCOUNT: Team.SUCCESS,
        Category.INTEGRATION: Team.ENGINEERING,
        Category.FEATURE_REQUEST: Team.PRODUCT,
        Category.HOW_TO: Team.SUCCESS,
        Category.SECURITY: Team.SECURITY,
        Category.OTHER: Team.SUCCESS,
    }[category]


def sentiment_for(ticket: Ticket) -> str:
    text = f"{ticket.subject}\n{ticket.body}"
    if _hit(ANGRY, text):
        return "angry"
    if _hit(FRUSTRATED, text):
        return "frustrated"
    if re.search(r"\b(thanks|thank you|love|great)\b", text, re.I):
        return "positive"
    return "neutral"


def sla_minutes(priority: Priority, plan: str) -> int:
    base = {"P0": 30, "P1": 120, "P2": 480, "P3": 1440}[priority.value]
    if plan.lower() == "enterprise":
        return max(15, base // 2)
    if plan.lower() == "free":
        return int(base * 1.5)
    return base


def should_escalate(ticket: Ticket, priority: Priority, sentiment: str, category: Category) -> tuple[bool, str | None]:
    reasons: list[str] = []
    if priority == Priority.P0:
        reasons.append("P0 priority")
    if category == Category.SECURITY:
        reasons.append("security-related")
    if sentiment == "angry":
        reasons.append("angry customer tone")
    if ticket.customer_plan.lower() == "enterprise" and priority in {Priority.P0, Priority.P1}:
        reasons.append("enterprise customer high severity")
    if reasons:
        return True, "; ".join(reasons)
    return False, None


def extract_tags(ticket: Ticket, category: Category, priority: Priority) -> list[str]:
    tags = {category.value, priority.value, ticket.customer_plan.lower(), ticket.channel.lower()}
    text = f"{ticket.subject} {ticket.body}".lower()
    for token in ("api", "webhook", "login", "invoice", "refund", "sso", "export", "mobile"):
        if token in text:
            tags.add(token)
    return sorted(tags)
