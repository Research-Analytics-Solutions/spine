# CLI

The `spine` command (from `spine-cli`, built on Typer + Rich). There are two ways
to use Spine — **as a library** (no CLI, no project) and **as a scaffolded
project** (the CLI drives `spine.toml`). Both are first-class.

## Two ways to use Spine

### Without a template (library only)

Import and run — nothing else required. Good for embedding in an existing app, a
notebook, or a script.

```python
from spine_core import Agent, tool

@tool
async def add(a: int, b: int) -> int:
    """Add."""
    return a + b

agent = Agent("openai:gpt-4o-mini", tools=[add])
print((await agent.run("add 2 and 2")).answer)
```

You wire the agent, tools, guards, and middleware in code. You don't need
`spine.toml`, the CLI, or any project layout.

### With a template (scaffolded project)

`spine init` generates a project where behavior is declared in `spine.toml` and
reproducible from version control. Good for teams, deployment, and the
`chat`/`dev`/`eval` workflow.

```bash
uv run spine init my-agent
cd my-agent && uv sync
uv run spine doctor
uv run spine chat "say hello"
```

**Why a project?** Config (model, guards, middleware chain, backend) lives in one
declarative file with `${ENV}` interpolation; tools are auto-discovered; runs
record traces you can inspect with `spine trace`.

## Commands

| Command | Purpose |
|---|---|
| `spine init <name> [--template minimal] [--path .]` | Scaffold a project |
| `spine run <target> <input> [--path .]` | Run an agent **defined in code** (`agents/<name>.py:agent` or `module:attr`) |
| `spine chat <input> [--path .]` | Run the agent **built from `spine.toml`** |
| `spine dev <input> [--path .]` | Like `chat`, but stream every trace event live |
| `spine trace [session] [--path .]` | List recent runs, or print one recorded trace |
| `spine eval <suite> [--scorer contains\|exact] [--path .]` | Run the eval harness |
| `spine doctor [--path .]` | Validate config, plugins, model, env |
| `spine plugin list` | List installed `spine.plugins` entry points |
| `spine version` | Print versions |

### `run` vs `chat`

- **`run <target>`** loads an `Agent` object you wrote — `agents/assistant.py`
  exposing `agent`, or any `module:attr`. Full control in Python.
  ```bash
  spine run assistant "hello"
  spine run mypkg.agents:support_agent "help"
  ```
- **`chat`** *builds* the agent from `spine.toml` — resolving the model, guards,
  middleware chain (by name), and checkpoint backend, and auto-discovering tools
  from the `tools/` package. No agent file needed.

### `dev`

Streams the live trace — every `step_start`, `model_call`, `token`,
`tool_call`, `final` — then prints the answer and saves the trace.

```bash
spine dev "summarize this repo"
```

### `trace`

```bash
spine trace                 # table of recent runs (.spine/traces/*.json)
spine trace <session_id>    # full event list for one run
```

### `doctor`

Checks: `spine.toml` parses, plugins load, every middleware-chain name and the
checkpoint backend are registered, the default model resolves, and warns on a
missing provider API key.

### `eval`

```bash
spine eval evals/smoke.yaml --scorer contains
```

Builds the `spine.toml` agent, runs the dataset, prints a Cost/Latency/
Efficacy/Reliability table, and **exits non-zero on any failure** (CI-friendly).

## Generated project layout

```
my-agent/
├── pyproject.toml        # pins spine-core + chosen plugins
├── spine.toml            # declarative config
├── .env.example          # documented secrets (copy to .env)
├── agents/
│   └── assistant.py      # an Agent definition (for `spine run`)
├── tools/
│   └── __init__.py       # @tool functions, auto-discovered (for `spine chat`)
├── evals/
│   └── smoke.yaml        # starter eval suite
└── tests/
```

Tool discovery: `spine chat`/`eval`/`dev` import the project's `tools` package and
collect every `Tool` instance exposed there.

## `spine.toml` reference

```toml
[spine]
default_model = "openai:gpt-4o-mini"   # scheme:model
system = "You are a helpful assistant."

[spine.guards]
max_steps = 8
max_cost_usd = 0.50
max_tokens = 100000
timeout_s = 30
max_depth = 8

[spine.middleware]
chain = ["Retry", "CostTracking", "LoopGuard"]   # order = the onion, top-down

[spine.backends]
checkpoint = "sqlite"     # memory | sqlite | redis | postgres
memory = "vector"         # optional: vector | buffer | pgvector

# per-plugin config, keyed by the plugin/middleware/backend name
[spine.plugins.sqlite]
path = "runs.db"

[spine.plugins.CostTracking]
input_per_mtok = 0.15
output_per_mtok = 0.60

[spine.plugins.redis]
url = "${REDIS_URL}"      # ${ENV} interpolated at load; secrets stay out of the file
```

Only registered names resolve. `spine doctor` tells you which are missing and
which plugin to install. See [Plugin authoring](plugins.md) to add your own.
