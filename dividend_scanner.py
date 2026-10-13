import sys
import os
import argparse
import datetime
import json
import csv

# Ensure Windows terminal prints UTF-8 symbols and emojis properly
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app import app
from typing import List, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from corporate_actions import CorporateActionsManager
from upstox_client import UpstoxClient
from config import SERVER_PORT, SERVER_HOST

console = Console()

def format_currency(val: float) -> str:
    if not val or val == 0:
        return "-"
    return f"₹{val:,.2f}"

def format_div_amount(val: float) -> str:
    if not val or val == 0:
        return "[yellow]TBA[/yellow]"
    return f"[bold green]₹{val:,.2f}[/bold green]"

def format_days_badge(days: Any) -> Text:
    if days is None:
        return Text("-", style="dim")
    if days < 0:
        return Text(f"{abs(days)}d ago", style="dim")
    elif days == 0:
        return Text("TODAY!", style="bold red on yellow")
    elif days == 1:
        return Text("1 day (Tomorrow)", style="bold red")
    elif days <= 5:
        return Text(f"{days} days", style="bold red")
    elif days <= 10:
        return Text(f"{days} days", style="bold yellow")
    elif days <= 20:
        return Text(f"{days} days", style="bold cyan")
    elif days <= 30:
        return Text(f"{days} days", style="green")
    elif days <= 45:
        return Text(f"{days} days", style="bright_green")
    elif days <= 60:
        return Text(f"{days} days", style="bright_cyan")
    elif days <= 75:
        return Text(f"{days} days", style="bright_blue")
    else:
        return Text(f"{days} days", style="magenta")

def render_summary_panel(stats: Dict[str, Any], token_status: Dict[str, Any]):
    highest = stats.get("highest_yield_stock")
    highest_str = (
        f"[bold cyan]{highest['symbol']}[/bold cyan] ({highest.get('dividend_yield', 0):.2f}%)"
        if highest else "N/A"
    )
    status_icon = "🟢 Connected" if token_status.get("valid") else "🟡 Limited / Fallback"

    panel_content = (
        f"[bold white]Upstox API:[/bold white] {status_icon}   "
        f"│ [bold white]Total Upcoming:[/bold white] [bold green]{stats.get('total_upcoming', 0)}[/bold green]   "
        f"│ [bold white]Avg Yield:[/bold white] [bold yellow]{stats.get('average_yield', 0):.2f}%[/bold yellow]   "
        f"│ [bold white]Highest Yield:[/bold white] {highest_str}\n"
        f"[dim]Timeframe Breakdown:[/dim]\n"
        f"[bold red]⚡ 5 Days:[/bold red] {stats.get('count_5_days', 0)}  │  "
        f"[bold yellow]🗓️ 10 Days:[/bold yellow] {stats.get('count_10_days', 0)}  │  "
        f"[bold cyan]📅 20 Days:[/bold cyan] {stats.get('count_20_days', 0)}  │  "
        f"[bold green]📆 30 Days:[/bold green] {stats.get('count_30_days', 0)}\n"
        f"[bold bright_green]🕒 45 Days:[/bold bright_green] {stats.get('count_45_days', 0)}  │  "
        f"[bold bright_cyan]🌐 60 Days:[/bold bright_cyan] {stats.get('count_60_days', 0)}  │  "
        f"[bold bright_blue]📊 75 Days:[/bold bright_blue] {stats.get('count_75_days', 0)}  │  "
        f"[bold magenta]🎯 90 Days:[/bold magenta] {stats.get('count_90_days', 0)}"
    )

    console.print(Panel(
        panel_content,
        title="[bold blue]📊 Indian Stock Market — Dividend Scanner[/bold blue]",
        border_style="bright_blue",
        box=box.ROUNDED
    ))

def display_table(dividends: List[Dict[str, Any]], title: str):
    if not dividends:
        console.print(f"[yellow]No dividend announcements found for: {title}[/yellow]\n")
        return

    table = Table(
        title=f"\n🎯 {title} ({len(dividends)} stocks)",
        title_style="bold magenta",
        box=box.ROUNDED,
        header_style="bold cyan",
        show_lines=True
    )

    table.add_column("Symbol", style="bold white", no_wrap=True)
    table.add_column("Company Name", style="white", max_width=32)
    table.add_column("Ex-Date", style="bold bright_white", justify="center")
    table.add_column("Countdown", justify="center")
    table.add_column("Announced (₹)", justify="right", style="bold green")
    table.add_column("Annual Div (₹)", justify="right", style="bold cyan")
    table.add_column("LTP (₹)", justify="right", style="bright_yellow")
    table.add_column("Yield (%)", justify="right", style="bold magenta")
    table.add_column("Type", style="dim", justify="center")
    table.add_column("Record Date", justify="center", style="dim")

    for d in dividends:
        days = d.get("days_remaining")
        badge = format_days_badge(days)
        
        div_yield = d.get("dividend_yield", 0.0)
        yield_str = f"{div_yield:.2f}%" if div_yield > 0 else "-"
        if div_yield >= 2.0:
            yield_text = f"[bold green]{yield_str}[/bold green]"
        elif div_yield > 0:
            yield_text = f"[green]{yield_str}[/green]"
        elif d.get("dividend_amount", 0.0) == 0 and d.get("annual_dividend", 0.0) == 0:
            yield_text = "[yellow]TBA[/yellow]"
        else:
            yield_text = "[dim]-[/dim]"

        table.add_row(
            d.get("symbol", ""),
            d.get("company_name", ""),
            d.get("ex_date_formatted", d.get("ex_date", "-")),
            badge,
            format_div_amount(d.get("dividend_amount", 0.0)),
            format_currency(d.get("annual_dividend", 0.0)),
            format_currency(d.get("ltp", 0.0)),
            yield_text,
            d.get("dividend_type", "Dividend"),
            d.get("record_date_formatted", d.get("record_date", "-"))
        )

    console.print(table)

def export_data(dividends: List[Dict[str, Any]], filename: str):
    if filename.endswith(".json"):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(dividends, f, indent=2)
        console.print(f"[bold green]✔ Exported {len(dividends)} records to {filename}[/bold green]")
    else:
        if not filename.endswith(".csv"):
            filename += ".csv"
        fieldnames = [
            "symbol", "company_name", "isin", "dividend_type",
            "dividend_amount", "annual_dividend", "ltp", "dividend_yield",
            "ex_date", "record_date", "days_remaining"
        ]
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(dividends)
        console.print(f"[bold green]✔ Exported {len(dividends)} records to {filename}[/bold green]")

def run_web():
    
    console.print(f"[bold green]🚀 Launching Web Dashboard on http://{SERVER_HOST}:{SERVER_PORT}...[/bold green]")
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False)

def main():
    parser = argparse.ArgumentParser(
        description="Indian Stock Market Dividend Scanner (NSE & BSE via Upstox)"
    )
    parser.add_argument(
        "--days", type=int, choices=[5, 10, 20, 30],
        help="Filter shares giving dividends within N days (5, 10, 20, 30)"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Show all upcoming dividend shares"
    )
    parser.add_argument(
        "--recent", action="store_true",
        help="Show recent dividends from past 30 days"
    )
    parser.add_argument(
        "--min-yield", type=float, default=0.0,
        help="Filter by minimum dividend yield percentage (e.g. --min-yield 1.5)"
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help="Force refresh live data from NSE & Upstox"
    )
    parser.add_argument(
        "--export", type=str,
        help="Export results to CSV or JSON (e.g. --export dividends.csv)"
    )
    parser.add_argument(
        "--web", action="store_true",
        help="Launch modern interactive Web Dashboard"
    )

    args = parser.parse_args()

    if args.web:
        run_web()
        return

    client = UpstoxClient()
    manager = CorporateActionsManager(client)

    with console.status("[bold cyan]Fetching and enriching dividend announcements...[/bold cyan]"):
        all_dividends = manager.get_all_dividends(force_refresh=args.refresh)
        stats = manager.get_statistics(all_dividends)
        token_status = client.validate_token()

    render_summary_panel(stats, token_status)

    # Determine filter
    if args.days:
        filtered = manager.filter_by_timeframe(all_dividends, args.days)
        title = f"Shares Giving Dividends Within {args.days} Days"
    elif args.recent:
        filtered = manager.filter_by_timeframe(all_dividends, "recent")
        title = "Recent Dividends (Past 30 Days)"
    elif args.all:
        filtered = manager.filter_by_timeframe(all_dividends, "all")
        title = "All Upcoming Dividend Shares"
    else:
        # Default: show categorized breakdown
        console.print("\n[bold yellow]⚡ Timeframe Breakdown:[/bold yellow]")
        for d_days, label in [(5, "Within 5 Days"), (10, "Within 10 Days"), (20, "Within 20 Days"), (30, "Within 30 Days")]:
            subset = manager.filter_by_timeframe(all_dividends, d_days)
            display_table(subset, label)
        
        console.print("[dim]\n💡 Tip: Use `python dividend_scanner.py --days 5` (or 10, 20, 30) or `--web` to launch the interactive dashboard.[/dim]\n")
        return

    # Yield filter
    if args.min_yield > 0:
        filtered = [d for d in filtered if d.get("dividend_yield", 0) >= args.min_yield]
        title += f" (Min Yield >= {args.min_yield}%)"

    display_table(filtered, title)

    if args.export:
        export_data(filtered, args.export)

if __name__ == "__main__":
    main()
