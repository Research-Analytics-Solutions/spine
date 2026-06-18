# Plugin authoring

Every plugin is one of four kinds, mapping 1:1 to the architecture planes:

| Kind | Implements | Registered with |
|---|---|---|
| **middleware** | hook points | `register_middleware(name, factory)` |
| **provider** | `complete` / `stream` | `register_provider(scheme, factory)` |
| **backend** | checkpoint or memory protocol | `register_checkpoint` / `register_memory` |
| **adapter** | bridges a standard (MCP, A2A, OTel) | exposes tools / providers |

## Distribution

A plugin is an ordinary PyPI package named by convention `spine-<kind>-<name>`
(e.g. `spine-backend-redis`, `spine-mw-guardrails`). It registers via standard
`importlib.metadata` entry points under the `spine.plugins` group — the same
mechanism pytest and Flask use.

```toml
# in your plugin's pyproject.toml
[project.entry-points."spine.plugins"]
my_provider = "spine_provider_acme:AcmeProvider"
```

Importing the target self-registers the scheme/name. Discovery is lazy — an
installed-but-unused plugin costs nothing at runtime. The CLI enumerates these:
`spine plugin list`.

## Example: a provider plugin

```python
# spine_provider_acme/__init__.py
from spine_core import Message, ModelResponse, Usage, register_provider

class AcmeProvider:
    def __init__(self, model: str) -> None:
        self.model = model

    async def complete(self, messages, tools=None, **kw) -> ModelResponse:
        ...  # call your API
        return ModelResponse(message=Message.assistant(text), usage=Usage(...))

def register() -> None:
    register_provider("acme", lambda model: AcmeProvider(model))

register()  # self-register on import
```

Install it and `Agent("acme:some-model")` just works.

## Example: a middleware plugin

```python
from spine_core import StepContext, register_middleware

class Stopwatch:
    async def before_model(self, ctx: StepContext) -> None:
        ctx.extra["t0"] = time.monotonic()
    async def after_model(self, ctx: StepContext) -> None:
        print("model took", time.monotonic() - ctx.extra["t0"])

register_middleware("Stopwatch", Stopwatch)
```

Now it's usable from code and from a `spine.toml` chain.

## Compatibility

Declare a core version range (`spine-core>=1.0,<2.0`). The kernel's hook-point and
protocol definitions are the stable plugin ABI, versioned with SemVer.
