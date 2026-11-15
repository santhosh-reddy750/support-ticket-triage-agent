from __future__ import annotations

from triage_agent.models import Category, Priority, Ticket


def draft_reply(
    ticket: Ticket,
    *,
    category: Category,
    priority: Priority,
    escalate: bool,
) -> str:
    name = ticket.customer_email.split("@")[0].replace(".", " ").title()
    ack = {
        Priority.P0: "I understand this is critical and I'm treating it as highest priority.",
        Priority.P1: "Thanks for flagging this — I'm prioritizing it right away.",
        Priority.P2: "Thanks for reaching out. I've reviewed your request and here's where we are.",
        Priority.P3: "Thanks for the message — happy to help.",
    }[priority]

    body_by_category = {
        Category.BILLING: (
            "I've tagged this for our Billing team. Please confirm the invoice ID / last 4 of the "
            "card if available so we can investigate charges quickly."
        ),
        Category.BUG: (
            "I've routed this to Engineering. To speed debugging, could you share: browser/OS, "
            "exact error text, and steps to reproduce?"
        ),
        Category.ACCOUNT: (
            "Customer Success will help restore access. If this is a login issue, try the password "
            "reset link while we check your account permissions."
        ),
        Category.INTEGRATION: (
            "Engineering will review the integration path (API/webhook/OAuth). Please include any "
            "request IDs, timestamps (UTC), and a redacted payload sample if possible."
        ),
        Category.SECURITY: (
            "Security has been paged. Please do not share passwords or secrets in this thread. "
            "We will follow up on a secure channel with next steps."
        ),
        Category.FEATURE_REQUEST: (
            "I've logged this with Product as a feature request. We can't commit to a timeline here, "
            "but your use case helps prioritize the roadmap."
        ),
        Category.HOW_TO: (
            "Here's the fastest path: check our docs for this workflow, and reply if you're still stuck — "
            "I'll send exact click-path steps for your plan."
        ),
        Category.OTHER: (
            "I've triaged your request and assigned the right team. Reply with any screenshots or "
            "extra context if you have them."
        ),
    }

    escalate_line = (
        "\n\nI'm also escalating this internally so a senior owner stays on it until resolved."
        if escalate
        else ""
    )

    return (
        f"Hi {name},\n\n"
        f"{ack}\n\n"
        f"{body_by_category[category]}"
        f"{escalate_line}\n\n"
        f"Ticket reference: {ticket.id}\n"
        f"Best regards,\nSupport Team"
    )


def summarize(ticket: Ticket, category: Category, priority: Priority) -> str:
    subject = ticket.subject.strip() or "Untitled request"
    return f"{priority.value} {category.value.replace('_', ' ')} — {subject}"
