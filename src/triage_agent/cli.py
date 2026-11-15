from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from triage_agent.engine import TriageAgent, load_tickets, save_results
from triage_agent.models import Ticket

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Support Ticket Triage Agent — priority, routing, reply draft, escalate?",
)
console = Console()


@app.command("run")
def run_batch(
    tickets_path: Path = typer.Argument(..., help="Path to tickets JSON/CSV"),
    output_dir: Path = typer.Option(Path("output"), "--output", "-o"),
) -> None:
    """Triage a batch of support tickets and write a report."""
    tickets = load_tickets(tickets_path)
    agent = TriageAgent()
    mode = "openai" if agent.llm.enabled else "rules"
    console.print(
        Panel.fit(
            f"[bold]Tickets:[/bold] {len(tickets)}\n[bold]Mode:[/bold] {mode}",
            title="Support Ticket Triage Agent",
        )
    )
    report = agent.triage_many(tickets)
    _print_table(report.results)
    paths = save_results(report, output_dir)
    console.print(
        f"\nEscalations: [bold red]{report.escalations}[/bold red] / {report.total}"
    )
    console.print(f"Saved JSON -> {paths['json']}")
    console.print(f"Saved report -> {paths['markdown']}")


@app.command()
def ticket(
    subject: str = typer.Option(..., "--subject", "-s"),
    body: str = typer.Option(..., "--body", "-b"),
    ticket_id: str = typer.Option("T-manual", "--id"),
    plan: str = typer.Option("pro", "--plan"),
    email: str = typer.Option("customer@example.com", "--email"),
) -> None:
    """Triage a single ticket from the CLI."""
    agent = TriageAgent()
    result = agent.triage(
        Ticket(
            id=ticket_id,
            subject=subject,
            body=body,
            customer_plan=plan,
            customer_email=email,
        )
    )
    _print_table([result])
    console.print(Panel(result.suggested_reply, title="Suggested reply"))


@app.command()
def demo(
    tickets_path: Optional[Path] = typer.Argument(
        None, help="Defaults to data/sample_tickets.json"
    ),
) -> None:
    """Run the sample SaaS inbox demo."""
    path = tickets_path or Path("data/sample_tickets.json")
    if not path.exists():
        # allow running from installed package cwd variants
        alt = Path(__file__).resolve().parents[2] / "data" / "sample_tickets.json"
        path = alt if alt.exists() else path
    run_batch(path, Path("output"))


def _print_table(results) -> None:
    table = Table(title="Triage decisions")
    table.add_column("ID")
    table.add_column("Priority")
    table.add_column("Category")
    table.add_column("Owner")
    table.add_column("Escalate")
    table.add_column("SLA min")
    table.add_column("Summary")
    for r in results:
        table.add_row(
            r.ticket_id,
            r.priority.value,
            r.category.value,
            r.owner_team.value,
            "YES" if r.escalate else "no",
            str(r.sla_minutes),
            r.summary[:60] + ("..." if len(r.summary) > 60 else ""),
        )
    console.print(table)


if __name__ == "__main__":
    app()
