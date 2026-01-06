"""CLI interface for the shipping agent."""

import os
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from src.agent import ShippingAgent
from src.agent.agent import is_mock_mode


def setup_database():
    """Set up database and return session with demo customer context."""
    from src.db.migrations import run_migrations
    from src.db.database import get_db_session
    from src.db.seed import seed_demo_data, get_demo_customer, has_demo_data
    from src.agent.context import CustomerContext

    # Run migrations
    try:
        run_migrations()
    except Exception as e:
        # Tables might already exist
        pass

    # Get or create demo customer
    with get_db_session() as db:
        if not has_demo_data(db):
            seed_demo_data(db)

        customer = get_demo_customer(db)
        if customer:
            context = CustomerContext.from_customer(customer)
            return context, customer.id

    return None, None


def main() -> None:
    """Run the shipping agent CLI."""
    load_dotenv()
    console = Console()

    mock = is_mock_mode()
    mode_text = "[yellow](MOCK MODE)[/yellow] " if mock else ""

    console.print(Panel.fit(
        f"[bold blue]Shipping Agent[/bold blue] {mode_text}\n"
        "Get rates, validate addresses, and create shipping labels.\n"
        "Type [bold]quit[/bold] to exit, [bold]reset[/bold] to clear history.",
        border_style="blue",
    ))
    console.print()

    if mock:
        console.print("[yellow]Running in mock mode - no API keys required.[/yellow]")
        console.print("[dim]Set MOCK_MODE=0 and add API keys to .env for real mode.[/dim]\n")

    # Set up database and get customer context
    console.print("[dim]Setting up database...[/dim]")
    context, customer_id = setup_database()

    if context:
        console.print(f"[dim]Loaded customer: {context.store_name} ({context.plan_tier} plan)[/dim]")
        console.print(f"[dim]Labels used: {context.labels_used}/{context.labels_limit}[/dim]\n")

    try:
        # Create agent with database connection
        from src.db.database import SessionLocal

        db = SessionLocal()
        agent = ShippingAgent(context=context, db=db if context else None)
    except ValueError as e:
        console.print(f"[red]Setup error:[/red] {e}")
        console.print("\nOptions:")
        console.print("  1. Run with [bold]MOCK_MODE=1 uv run ship[/bold] to test without API keys")
        console.print("  2. Copy .env.example to .env and add your API keys")
        sys.exit(1)

    console.print("[dim]Try: 'Get rates for a 2lb package to Los Angeles, CA 90001'[/dim]")
    console.print("[dim]Or: 'Show my unfulfilled orders'[/dim]\n")

    try:
        while True:
            try:
                user_input = console.input("[bold green]You:[/bold green] ").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Goodbye![/dim]")
                break

            if not user_input:
                continue

            if user_input.lower() == "quit":
                console.print("[dim]Goodbye![/dim]")
                break

            if user_input.lower() == "reset":
                agent.reset()
                console.print("[dim]Conversation cleared.[/dim]\n")
                continue

            if user_input.lower() == "help":
                console.print(Panel(
                    "**Commands:**\n"
                    "- `quit` - Exit the agent\n"
                    "- `reset` - Clear conversation history\n"
                    "- `help` - Show this message\n\n"
                    "**Examples:**\n"
                    "- Show my unfulfilled orders\n"
                    "- Get rates for a 2lb package to Chicago, IL 60601\n"
                    "- Validate address: 123 Main St, Los Angeles, CA 90001\n"
                    "- Ship it with the cheapest option\n"
                    "- What's the fastest way to ship to NYC?",
                    title="Help",
                    border_style="dim",
                ))
                console.print()
                continue

            try:
                with console.status("[bold blue]Thinking...[/bold blue]"):
                    response = agent.chat(user_input)
                console.print()
                console.print(Panel(
                    Markdown(response),
                    title="[bold blue]Agent[/bold blue]",
                    border_style="blue",
                ))
                console.print()
            except Exception as e:
                console.print(f"[red]Error:[/red] {e}\n")
    finally:
        # Clean up database session
        if context:
            db.close()


if __name__ == "__main__":
    main()
