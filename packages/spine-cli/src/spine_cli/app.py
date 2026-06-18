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

    from spine_core import list_checkpoints, list_middleware

    known_mw = set(list_middleware())
    for name in config.middleware.chain:
        if name in known_mw:
            rows.append((f"mw:{name}", "[green]ok[/]", "registered"))
        else:
            failed = True
            rows.append((f"mw:{name}", "[red]fail[/]", "not registered (install its plugin)"))

    backend = config.backends.checkpoint
    if backend and backend not in set(list_checkpoints()):
        failed = True
        rows.append((f"checkpoint:{backend}", "[red]fail[/]", "backend not registered"))
    elif backend:
        rows.append((f"checkpoint:{backend}", "[green]ok[/]", "registered"))

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


@app.command("eval")
def eval_cmd(
    suite: str = typer.Argument(..., help="Path to the eval dataset (.yaml/.json)."),
    path: Path = typer.Option(Path("."), help="Project root."),
    scorer: str = typer.Option("contains", help="Built-in scorer: contains | exact."),
) -> None:
    """Run the eval harness for the spine.toml agent against a dataset."""
    import functools

    import anyio

    try:
        from spine_eval import Contains, ExactMatch, Scorer, evaluate, load_dataset
    except ImportError as exc:
        console.print("[red]error:[/] spine-eval is not installed ([cyan]uv add spine-eval[/])")
        raise typer.Exit(1) from exc

    config_path = find_config(path)
    if config_path is None:
        console.print("[red]error:[/] no spine.toml found")
        raise typer.Exit(1)
    config = load_config(config_path)
    project_root = config_path.parent

    suite_path = Path(suite)
    if not suite_path.is_absolute():
        suite_path = project_root / suite
    if not suite_path.is_file():
        console.print(f"[red]error:[/] no eval suite at {suite_path}")
        raise typer.Exit(1)

    from spine_cli.builder import build_agent

    agent = build_agent(config, project_root)
    dataset = load_dataset(suite_path)
    options: dict[str, list[Scorer]] = {"contains": [Contains()], "exact": [ExactMatch()]}
    scorers = options.get(scorer)
    if scorers is None:
        console.print(f"[red]error:[/] unknown scorer {scorer!r} (use contains|exact)")
        raise typer.Exit(1)

    report = anyio.run(functools.partial(evaluate, agent, dataset, scorers))

    table = Table("metric", "value")
    table.add_row("cases", str(report.total))
    table.add_row("pass rate", f"{report.pass_rate:.0%} ({report.passed}/{report.total})")
    table.add_row("error rate", f"{report.error_rate:.0%}")
    table.add_row("cost (total)", f"${report.cost_total_usd:.4f}")
    table.add_row("latency avg / p95", f"{report.latency_avg_s:.2f}s / {report.latency_p95_s:.2f}s")
    for name, mean in report.scorer_means.items():
        table.add_row(f"scorer:{name}", f"{mean:.2f}")
    console.print(table)
    if report.error_rate > 0 or report.pass_rate < 1.0:
        raise typer.Exit(1)


@app.command()
def dev(
    input: str = typer.Argument(..., help="The input message."),
    path: Path = typer.Option(Path("."), help="Project root."),
) -> None:
    """Run the spine.toml agent and stream every step's trace event live."""
    import anyio

    from spine_cli.builder import build_agent, save_trace

    config_path = find_config(path)
    if config_path is None:
        console.print("[red]error:[/] no spine.toml found")
        raise typer.Exit(1)
    config = load_config(config_path)
    project_root = config_path.parent
    agent = build_agent(config, project_root)

    async def go() -> None:
        async for event in agent.stream(input):
            detail = ", ".join(f"{k}={v}" for k, v in event.data.items())
            console.print(f"[dim]{event.seq:>3}[/] [cyan]{event.type}[/] {detail}")

    anyio.run(go)
    result = agent.last_result
    if result is not None:
        save_trace(project_root, result)
        console.print(f"\n[bold]{result.answer or '(' + result.stopped_reason.value + ')'}[/]")


@app.command()
def chat(
    input: str = typer.Argument(..., help="The input message."),
    path: Path = typer.Option(Path("."), help="Project root."),
) -> None:
    """Run the agent described by spine.toml (model, guards, middleware, backend)."""
    from spine_cli.builder import build_agent, save_trace

    config_path = find_config(path)
    if config_path is None:
        console.print("[red]error:[/] no spine.toml found")
        raise typer.Exit(1)
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        console.print(f"[red]error:[/] {exc}")
        raise typer.Exit(1) from exc

    project_root = config_path.parent
    agent = build_agent(config, project_root)
    result = agent.run_sync(input)
    trace_path = save_trace(project_root, result)

    if result.stopped_reason.value == "error":
        console.print(f"[red]run failed:[/] {result.error}")
        raise typer.Exit(1)
    console.print(result.answer or f"[yellow]stopped: {result.stopped_reason.value}[/]")
    console.print(
        f"\n[dim]stopped: {result.stopped_reason.value} · steps: {result.state.step} · "
        f"${result.usage.cost_usd:.4f} · {result.usage.total_tokens} tok · "
        f"trace: {trace_path}[/]"
    )


@app.command()
def trace(
    session: str = typer.Argument(None, help="Session id to inspect; omit to list recent."),
    path: Path = typer.Option(Path("."), help="Project root."),
) -> None:
    """Inspect a recorded run trace (saved by `spine chat`)."""
    import json

    from spine_cli.builder import TRACES_DIR

    project_root = _project_root(path)
    traces_dir = project_root / TRACES_DIR
    if not traces_dir.is_dir():
        console.print("[dim]no traces recorded yet[/]")
        return

    if session is None:
        files = sorted(traces_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        table = Table("session", "stopped", "events")
        for file in files[:20]:
            data = json.loads(file.read_text())
            table.add_row(
                file.stem, data.get("stopped_reason", "?"), str(len(data.get("events", [])))
            )
        console.print(table)
        return

    file = traces_dir / f"{session}.json"
    if not file.is_file():
        console.print(f"[red]error:[/] no trace for session {session!r}")
        raise typer.Exit(1)
    data = json.loads(file.read_text())
    table = Table("seq", "step", "type", "detail")
    for event in data.get("events", []):
        detail = ", ".join(f"{k}={v}" for k, v in event.get("data", {}).items())
        table.add_row(str(event.get("seq")), str(event.get("step")), event.get("type", ""), detail)
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
