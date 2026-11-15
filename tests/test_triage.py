from pathlib import Path

from triage_agent.engine import TriageAgent, load_tickets, save_results
from triage_agent.models import Category, Priority, Ticket


def test_outage_is_p0_and_escalates():
    agent = TriageAgent()
    result = agent.triage(
        Ticket(
            id="T-1",
            subject="Production is down",
            body="Our production API is down and checkout is failing. Urgent.",
            customer_plan="enterprise",
        )
    )
    assert result.priority == Priority.P0
    assert result.escalate is True
    assert result.owner_team.value in {"Engineering", "Customer Success", "Security"}


def test_how_to_is_low_priority():
    agent = TriageAgent()
    result = agent.triage(
        Ticket(
            id="T-2",
            subject="How do I invite teammates?",
            body="How can I invite my team? Thanks!",
            customer_plan="free",
        )
    )
    assert result.category == Category.HOW_TO
    assert result.priority == Priority.P3
    assert result.escalate is False
    assert result.owner_team.value == "Customer Success"


def test_security_routes_to_security_team():
    agent = TriageAgent()
    result = agent.triage(
        Ticket(
            id="T-3",
            subject="Possible unauthorized login",
            body="I think my account was hacked after a phishing email.",
        )
    )
    assert result.category == Category.SECURITY
    assert result.priority == Priority.P0
    assert result.owner_team.value == "Security"
    assert result.escalate is True


def test_sample_batch_and_report(tmp_path: Path):
    sample = Path(__file__).resolve().parents[1] / "data" / "sample_tickets.json"
    tickets = load_tickets(sample)
    report = TriageAgent().triage_many(tickets)
    assert report.total == 8
    assert report.escalations >= 3
    paths = save_results(report, tmp_path)
    assert paths["json"].exists()
    assert paths["markdown"].exists()
    assert "Suggested reply" in paths["markdown"].read_text(encoding="utf-8")
