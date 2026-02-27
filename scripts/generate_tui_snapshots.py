#!/usr/bin/env python3
"""Generate TUI-style snapshots for the Rastion Hub website."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.terminal_theme import TerminalTheme
from rich.text import Text

OUT_DIR = Path(__file__).resolve().parents[1] / "public" / "tui-screens"
WIDTH = 96

THEME = TerminalTheme(
    (11, 15, 25),
    (232, 238, 247),
    [
        (35, 39, 51),
        (244, 102, 119),
        (166, 218, 149),
        (238, 212, 159),
        (138, 173, 244),
        (198, 160, 246),
        (145, 215, 227),
        (202, 211, 245),
    ],
    [
        (73, 77, 100),
        (245, 169, 127),
        (166, 227, 161),
        (238, 212, 159),
        (138, 173, 244),
        (198, 160, 246),
        (145, 215, 227),
        (245, 245, 245),
    ],
)


def _save(name: str, renderable: object) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / f"{name}.svg"
    console = Console(record=True, width=WIDTH)
    console.print(renderable)
    console.save_svg(str(target), title=f"Rastion {name}", theme=THEME)
    return target


def startup() -> Path:
    banner = Panel(
        (
            "[bold]Rastion v0.1 - Your Optimization Lab[/bold]\n\n"
            "Pure Rich terminal UI with keyboard navigation.\n"
            "Not signed in\n"
            "Use UP/DOWN (or j/k) to move, Enter to select, Q to cancel."
        ),
        border_style="cyan",
    )
    body = Text()
    body.append("Choose an action:\n\n", style="bold")
    options = [
        "1. Browse Problems",
        "2. Browse Solvers",
        "3. Solve a Problem",
        "4. Compare Solvers (Benchmark)",
        "5. View Run History",
        "6. Settings",
        "7. Install Solver (URL or Hub)",
        "8. Hub: Push",
        "9. Hub: Pull",
        "10. Hub: Search",
        "11. Onboarding / Logout",
        "Q. Quit",
    ]
    for idx, option in enumerate(options):
        marker = "▶ " if idx == 0 else "  "
        style = "bold cyan" if idx == 0 else "white"
        body.append(f"{marker}{option}\n", style=style)
    body.append("\n↑/↓ or j/k navigate  Enter select  Q cancel", style="dim")
    menu = Panel(body, title="Rastion v0.1", border_style="cyan")
    return _save("startup", Group(banner, Text(), menu))


def onboarding() -> Path:
    body = Text()
    body.append("Choose action:\n\n", style="bold")
    body.append("▶ Start onboarding with GitHub token\n", style="bold cyan")
    body.append("  Logout\n", style="white")
    body.append("\n↑/↓ or j/k navigate  Enter select  Q cancel", style="dim")
    menu = Panel(body, title="Onboarding / Logout", border_style="cyan")
    prompt = Panel(
        "[bold]GitHub token[/bold]\n\nType your value and press Enter. Type Q to cancel.",
        title="Onboarding",
        border_style="cyan",
    )
    success = Panel(
        (
            "[bold green]welcome octocat[/bold green]\n\n"
            "Smarter routing and scheduling cuts fuel waste, cost, and commuting time."
        ),
        title="Onboarding complete",
        border_style="green",
    )
    return _save("onboarding", Group(menu, Text(), prompt, Text(), success))


def hub_push() -> Path:
    text = Text()
    text.append("Pushed problem 'shareable_maxcut' to http://localhost:8000", style="bold green")
    return _save("hub-push", Panel(text, title="Hub Push", border_style="green"))


def hub_pull_solver() -> Path:
    text = Text()
    text.append(
        "Pulled solver 'qaoa-lite' into ~/.rastion/registry/solvers/qaoa-lite",
        style="bold green",
    )
    return _save("hub-pull-solver", Panel(text, title="Hub Pull", border_style="green"))


def benchmark() -> Path:
    table = Table(title="Compare Solvers (Benchmark)")
    table.add_column("Solver", style="cyan")
    table.add_column("Runs")
    table.add_column("Best Objective")
    table.add_column("Mean Runtime (s)")
    table.add_row("baseline", "3", "183.0", "0.012")
    table.add_row("neal", "3", "192.0", "0.048")
    table.add_row("qaoa-lite", "3", "198.0", "0.210")
    note = Text("Best objective: qaoa-lite (higher cut_weight).", style="bold green")
    return _save("benchmark", Group(table, Text(), note))


def run_history() -> Path:
    table = Table(title="Recent Runs")
    table.add_column("Timestamp")
    table.add_column("Solver", style="cyan")
    table.add_column("Status")
    table.add_column("Objective")
    table.add_row("2026-02-26T10:41:07Z", "qaoa-lite", "SUCCESS", "198.0")
    table.add_row("2026-02-26T10:40:11Z", "neal", "SUCCESS", "192.0")
    table.add_row("2026-02-26T10:39:24Z", "baseline", "SUCCESS", "183.0")
    return _save("run-history", table)


def hub_search() -> Path:
    problems = Table(title="Hub Problems")
    problems.add_column("Name", style="cyan")
    problems.add_column("Version")
    problems.add_column("Owner")
    problems.add_column("Downloads")
    problems.add_column("Rating")
    problems.add_row("facility_location", "0.1.0", "team-opt", "37", "4.7")

    solvers = Table(title="Hub Solvers")
    solvers.add_column("Name", style="magenta")
    solvers.add_column("Version")
    solvers.add_column("Owner")
    solvers.add_column("Downloads")
    solvers.add_column("Rating")
    solvers.add_row("milp-fastlane", "0.3.0", "ops-lab", "128", "4.9")
    return _save("hub-search", Group(problems, Text(), solvers))


def artifact_selection() -> Path:
    text = Text()
    text.append("Target artifact: milp-fastlane\n", style="bold")
    text.append("Type: solver\n", style="cyan")
    text.append("Next action: Hub Pull", style="green")
    return _save("artifact-selection", Panel(text, title="Artifact Selection", border_style="cyan"))


def downloaded() -> Path:
    text = Text()
    text.append(
        'Pulled solver "milp-fastlane" into ~/.rastion/registry/solvers/milp-fastlane\n',
        style="bold green",
    )
    text.append("Ready for 3. Solve a Problem or 4. Compare Solvers", style="white")
    return _save("downloaded", Panel(text, title="Downloaded", border_style="green"))


def main() -> int:
    outputs = [
        startup(),
        onboarding(),
        hub_push(),
        hub_pull_solver(),
        benchmark(),
        run_history(),
        hub_search(),
        artifact_selection(),
        downloaded(),
    ]
    for output in outputs:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
