# CLI

The `spine` command (from `spine-cli`, built on Typer + Rich).

| Command | Purpose |
|---|---|
| `spine init <name> [--template minimal]` | Scaffold a new project |
| `spine run <agent> <input>` | Run an agent defined in `agents/` |
| `spine chat <input>` | Run the agent described by `spine.toml` |
| `spine dev <input>` | Run and stream every trace event live |
| `spine trace [session]` | List recent runs, or inspect a recorded trace |
| `spine eval <suite> [--scorer contains\|exact]` | Run the eval harness |
| `spine doctor` | Validate config, plugins, model, env |
| `spine plugin list` | List installed `spine.plugins` entry points |
| `spine version` | Print versions |

## Generated project

```
my-agent/
├── pyproject.toml        # pins spine-core + chosen plugins
├── spine.toml            # declarative config
├── .env.example          # documented secrets
├── agents/assistant.py   # an Agent definition
├── tools/__init__.py     # @tool functions, auto-discovered
├── evals/smoke.yaml      # starter eval suite
└── tests/
```

## `spine.toml`

An agent's full behavior is reproducible from version control:

```toml
[spine]
default_model = "openai:gpt-4o-mini"
system = "You are a helpful assistant."

[spine.guards]
max_steps = 8
max_cost_usd = 0.50
timeout_s = 30

[spine.middleware]            # order matters — top-down onion
chain = ["Retry", "CostTracking", "LoopGuard"]

[spine.backends]
checkpoint = "sqlite"

[spine.plugins.sqlite]
path = "runs.db"

[spine.plugins.CostTracking]
input_per_mtok = 0.15
output_per_mtok = 0.60
```

`${ENV_VAR}` references are interpolated at load time, so secrets never live in
the file. `spine chat` / `spine eval` / `spine dev` build the agent from this.
