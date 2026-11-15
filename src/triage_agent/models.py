from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Priority(str, Enum):
    P0 = "P0"  # outage / data loss / payment broken
    P1 = "P1"  # major feature broken, many users impacted
    P2 = "P2"  # degraded experience, workaround exists
    P3 = "P3"  # question / how-to / minor issue


class Category(str, Enum):
    BILLING = "billing"
    BUG = "bug"
    ACCOUNT = "account"
    INTEGRATION = "integration"
    FEATURE_REQUEST = "feature_request"
    HOW_TO = "how_to"
    SECURITY = "security"
    OTHER = "other"


class Team(str, Enum):
    BILLING = "Billing"
    ENGINEERING = "Engineering"
    SUCCESS = "Customer Success"
    SECURITY = "Security"
    PRODUCT = "Product"


class Ticket(BaseModel):
    id: str
    subject: str
    body: str
    customer_email: str = "customer@example.com"
    customer_plan: str = "pro"  # free | pro | enterprise
    channel: str = "email"  # email | chat | in_app
    metadata: dict[str, Any] = Field(default_factory=dict)


class TriageResult(BaseModel):
    ticket_id: str
    priority: Priority
    category: Category
    owner_team: Team
    tags: list[str] = Field(default_factory=list)
    sentiment: str = "neutral"  # positive | neutral | frustrated | angry
    escalate: bool = False
    escalate_reason: str | None = None
    sla_minutes: int = 480
    summary: str
    suggested_reply: str
    confidence: float = 0.7
    mode: str = "rules"
    rationale: list[str] = Field(default_factory=list)


class BatchReport(BaseModel):
    total: int
    by_priority: dict[str, int]
    by_team: dict[str, int]
    escalations: int
    results: list[TriageResult]
