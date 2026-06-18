# spine-cli

The `spine` command — built on Typer + Rich.

```bash
spine init my-agent              # scaffold a project
cd my-agent && uv sync
spine run assistant "say hello"  # execute an agent from the project
spine doctor                     # validate config, env, plugin compatibility
spine plugin list                # list installed spine.plugins entry points
spine version
```

Config lives in `spine.toml` (model, guards, middleware order, backends) so an
agent's behavior is reproducible from version control; `${ENV_VAR}` references
keep secrets out of the file.
