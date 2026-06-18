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
