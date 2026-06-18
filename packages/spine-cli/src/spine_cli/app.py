"""The ``spine`` CLI — Typer commands with Rich output.

Project operations are declarative and reproducible: ``init`` scaffolds, ``run``
executes an agent defined in the project, ``doctor`` validates config + plugin
compatibility, and ``plugin`` inspects installed extensions.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from spine_cli import templates
from spine_cli.config import ConfigError, find_config, load_config
from spine_cli.plugins import discover, load_all

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Spine — agent runtime CLI.")
plugin_app = typer.Typer(no_args_is_help=True, help="Manage and inspect plugins.")
app.add_typer(plugin_app, name="plugin")

console = Console()


@app.command()
def version() -> None:
    """Print Spine versions."""
    from spine_core import __version__ as core_version

    console.print(f"spine-cli [bold]0.1.0[/]  ·  spine-core [bold]{core_version}[/]")


@app.command()
def init(
    name: str = typer.Argument(..., help="Project directory to create."),
    template: str = typer.Option("minimal", "--template", "-t", help="Project template."),
    path: Path = typer.Option(Path("."), help="Where to create the project."),
) -> None:
    """Scaffold a new Spine project (like ``uv init``)."""
    try:
        files = templates.render(name, template)
    except ValueError as exc:
        console.print(f"[red]error:[/] {exc}")
        raise typer.Exit(1) from exc

    root = (path / name).resolve()
    if root.exists() and any(root.iterdir()):
        console.print(f"[red]error:[/] {root} already exists and is not empty")
        raise typer.Exit(1)

    for relpath, content in files.items():
        dest = root / relpath
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)

    console.print(f"[green]✓[/] created [bold]{name}[/] ({template}) at {root}")
    console.print(f'  next: [cyan]cd {name} && uv sync && uv run spine run assistant "hi"[/]')


@app.command()
def run(
    target: str = typer.Argument(..., help="Agent to run: 'assistant' or 'module:attr'."),
    input: str = typer.Argument(..., help="The input message for the agent."),
    path: Path = typer.Option(Path("."), help="Project root."),
) -> None:
    """Run an agent defined in the project and print its answer."""
    project_root = _project_root(path)
    try:
        agent = _load_agent(target, project_root)
    except (ImportError, AttributeError) as exc:
        console.print(f"[red]error:[/] could not load agent '{target}': {exc}")
        raise typer.Exit(1) from exc

    result = agent.run_sync(input)
    if result.stopped_reason.value == "error":
        console.print(f"[red]run failed:[/] {result.error}")
        raise typer.Exit(1)
    if result.interrupted:
        console.print(f"[yellow]⏸ interrupted[/] (resume token: {result.resume_token})")
        console.print(result.interrupt)
        return
    console.print(result.answer or "")
    console.print(
        f"\n[dim]stopped: {result.stopped_reason.value} · steps: {result.state.step} · "
        f"${result.usage.cost_usd:.4f} · {result.usage.total_tokens} tok[/]"
    )


@app.command()
def doctor(path: Path = typer.Option(Path("."), help="Project root.")) -> None:
    """Validate config, environment, and plugin compatibility."""
    import os

    from spine_core import ProviderError, resolve_provider

    rows: list[tuple[str, str, str]] = []
    failed = False

    config_path = find_config(path)
    if config_path is None:
        rows.append(("config", "[red]fail[/]", "no spine.toml found"))
        _render_doctor(rows)
        raise typer.Exit(1)
    rows.append(("config", "[green]ok[/]", str(config_path)))

    try:
        config = load_config(config_path)
    except ConfigError as exc:
        rows.append(("config parse", "[red]fail[/]", str(exc)))
        _render_doctor(rows)
        raise typer.Exit(1) from exc

    loaded = load_all()
    rows.append(
        ("plugins", "[green]ok[/]", f"{sum(p.loaded for p in loaded)}/{len(loaded)} loaded")
    )
    for plugin in loaded:
        if plugin.error:
            failed = True
            rows.append((f"  {plugin.name}", "[red]fail[/]", plugin.error))

    try:
        resolve_provider(config.default_model)
        rows.append(("model", "[green]ok[/]", config.default_model))
    except ProviderError as exc:
        failed = True
        rows.append(("model", "[red]fail[/]", str(exc)))

    scheme = config.default_model.split(":", 1)[0]
    if scheme == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
        rows.append(("ANTHROPIC_API_KEY", "[yellow]warn[/]", "unset (needed to call the model)"))

    _render_doctor(rows)
    if failed:
        raise typer.Exit(1)


@plugin_app.command("list")
def plugin_list() -> None:
    """List installed Spine plugins (entry points)."""
    plugins = discover()
    if not plugins:
        console.print("[dim]no spine.plugins entry points installed[/]")
        return
    table = Table("name", "target", "origin")
    for plugin in plugins:
        origin = "first-party" if plugin.first_party else "[yellow]third-party[/]"
        table.add_row(plugin.name, plugin.value, origin)
    console.print(table)


# -- helpers ----------------------------------------------------------------


def _project_root(path: Path) -> Path:
    config_path = find_config(path)
    return config_path.parent if config_path is not None else path.resolve()


def _load_agent(target: str, project_root: Path) -> Any:
    root = str(project_root)
    if root not in sys.path:
        sys.path.insert(0, root)
    module_name, _, attr = target.partition(":")
    if not attr:
        module_name, attr = f"agents.{target}", "agent"
    module = importlib.import_module(module_name)
    agent = getattr(module, attr)
    return agent


def _render_doctor(rows: list[tuple[str, str, str]]) -> None:
    table = Table("check", "status", "detail")
    for check, status, detail in rows:
        table.add_row(check, status, detail)
    console.print(table)
