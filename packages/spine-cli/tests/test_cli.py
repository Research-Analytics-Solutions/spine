"""CLI behavior: scaffold, run, doctor, plugin discovery, config loading."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from spine_cli.app import app
from spine_cli.config import ConfigError, load_config

runner = CliRunner()

_SCRIPTED_AGENT = """\
from spine_core import Agent
from spine_core.testing import ScriptedProvider, text

agent = Agent(ScriptedProvider(text("scripted hi")))
"""


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "spine-cli" in result.stdout


def test_init_scaffolds_runnable_project(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", "my-agent", "--path", str(tmp_path)])
    assert result.exit_code == 0
    root = tmp_path / "my-agent"
    assert (root / "spine.toml").is_file()
    assert (root / "agents" / "assistant.py").is_file()
    assert (root / "tools" / "__init__.py").is_file()
    # the scaffolded config must actually parse
    config = load_config(root / "spine.toml")
    assert config.default_model.startswith("anthropic:")
    assert config.guards.max_steps == 8


def test_init_refuses_non_empty_dir(tmp_path: Path) -> None:
    root = tmp_path / "taken"
    root.mkdir()
    (root / "stuff.txt").write_text("x")
    result = runner.invoke(app, ["init", "taken", "--path", str(tmp_path)])
    assert result.exit_code == 1
    assert "already exists" in result.stdout


def test_init_rejects_unknown_template(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", "p", "--template", "nope", "--path", str(tmp_path)])
    assert result.exit_code == 1


def test_plugin_list_shows_anthropic() -> None:
    result = runner.invoke(app, ["plugin", "list"])
    assert result.exit_code == 0
    assert "anthropic" in result.stdout


def test_run_executes_project_agent(tmp_path: Path) -> None:
    proj = tmp_path / "proj"
    (proj / "agents").mkdir(parents=True)
    (proj / "spine.toml").write_text('[spine]\ndefault_model = "anthropic:x"\n')
    (proj / "agents" / "echo_agent.py").write_text(_SCRIPTED_AGENT)

    result = runner.invoke(app, ["run", "echo_agent", "hello", "--path", str(proj)])
    assert result.exit_code == 0, result.stdout
    assert "scripted hi" in result.stdout


def test_doctor_passes_on_scaffolded_project(tmp_path: Path) -> None:
    runner.invoke(app, ["init", "proj", "--path", str(tmp_path)])
    result = runner.invoke(app, ["doctor", "--path", str(tmp_path / "proj")])
    assert result.exit_code == 0
    assert "anthropic" in result.stdout


def test_doctor_fails_without_config(tmp_path: Path) -> None:
    result = runner.invoke(app, ["doctor", "--path", str(tmp_path)])
    assert result.exit_code == 1


def test_config_env_interpolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_CHECKPOINT_URL", "redis://localhost:6379")
    cfg = tmp_path / "spine.toml"
    cfg.write_text(
        '[spine]\ndefault_model = "anthropic:x"\n'
        '[spine.plugins.redis]\nurl = "${MY_CHECKPOINT_URL}"\n'
    )
    config = load_config(cfg)
    assert config.plugins["redis"]["url"] == "redis://localhost:6379"


def test_config_unset_env_raises(tmp_path: Path) -> None:
    cfg = tmp_path / "spine.toml"
    cfg.write_text('[spine]\n[spine.plugins.x]\nkey = "${DEFINITELY_UNSET_VAR_XYZ}"\n')
    with pytest.raises(ConfigError):
        load_config(cfg)


_TOOLS_PKG = '''\
from spine_core import tool


@tool
async def echo(text: str) -> str:
    """Echo."""
    return text
'''


def _config_project(
    tmp_path: Path, *, model: str, chain: str = "[]", checkpoint: str = "memory"
) -> Path:
    proj = tmp_path / "proj"
    (proj / "tools").mkdir(parents=True)
    (proj / "tools" / "__init__.py").write_text(_TOOLS_PKG)
    (proj / "spine.toml").write_text(
        f'[spine]\ndefault_model = "{model}"\n'
        f"[spine.middleware]\nchain = {chain}\n"
        f'[spine.backends]\ncheckpoint = "{checkpoint}"\n'
    )
    return proj


def test_build_agent_applies_config(tmp_path: Path) -> None:
    from spine_cli.builder import build_agent

    proj = _config_project(tmp_path, model="anthropic:x", chain='["Retry", "LoopGuard"]')
    config = load_config(proj / "spine.toml")
    agent = build_agent(config, proj)

    # middleware chain resolved from names; tools auto-discovered
    assert [type(m).__name__ for m in agent.chain.middlewares] == ["Retry", "LoopGuard"]
    assert "echo" in agent.tools


def test_chat_runs_config_agent_and_records_trace(tmp_path: Path) -> None:
    from spine_core.provider import register_provider
    from spine_core.testing import ScriptedProvider, text

    register_provider("faketest", lambda model: ScriptedProvider(text("hello from config")))
    proj = _config_project(tmp_path, model="faketest:x", chain='["Retry"]')

    result = runner.invoke(app, ["chat", "hi there", "--path", str(proj)])
    assert result.exit_code == 0, result.stdout
    assert "hello from config" in result.stdout
    assert list((proj / ".spine" / "traces").glob("*.json"))


def test_trace_lists_and_inspects(tmp_path: Path) -> None:
    from spine_core.provider import register_provider
    from spine_core.testing import ScriptedProvider, text

    register_provider("faketest2", lambda model: ScriptedProvider(text("answer")))
    proj = _config_project(tmp_path, model="faketest2:x")
    runner.invoke(app, ["chat", "hi", "--path", str(proj)])

    listing = runner.invoke(app, ["trace", "--path", str(proj)])
    assert listing.exit_code == 0
    session = next((proj / ".spine" / "traces").glob("*.json")).stem

    detail = runner.invoke(app, ["trace", session, "--path", str(proj)])
    assert detail.exit_code == 0
    assert "model_call" in detail.stdout or "step_start" in detail.stdout


def test_doctor_flags_unknown_middleware(tmp_path: Path) -> None:
    proj = _config_project(tmp_path, model="anthropic:x", chain='["NoSuchMiddleware"]')
    result = runner.invoke(app, ["doctor", "--path", str(proj)])
    assert result.exit_code == 1
    assert "NoSuchMiddleware" in result.stdout
