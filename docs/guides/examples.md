# Cookbook

Copy-paste recipes. Examples that use a real model show `"openai:gpt-4o-mini"`;
the offline ones use the bundled `ScriptedProvider` and actually run when these
docs are built.

## Basics

### A minimal agent

```python
from spine_core import Agent

agent = Agent("openai:gpt-4o-mini")
print((await agent.run("Capital of France?")).answer)
```

### Synchronous (no `await`)

```python exec="1" source="above" result="text"
from spine_core import Agent
from spine_core.testing import ScriptedProvider, text

agent = Agent(ScriptedProvider(text("Paris")))
print(agent.run_sync("Capital of France?").answer)
```

### Inspect the full result

```python exec="1" source="above" result="text"
from spine_core import Agent
from spine_core.testing import ScriptedProvider, text

agent = Agent(ScriptedProvider(text("42", input_tokens=12, output_tokens=1)))
r = agent.run_sync("the answer?")
print("answer       :", r.answer)
print("stopped      :", r.stopped_reason.value)
print("steps        :", r.state.step)
print("tokens       :", r.usage.total_tokens)
print("trace events :", [e.type for e in r.trace])
```

## Tools

### One tool

```python
from spine_core import Agent, tool

@tool
async def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b

agent = Agent("openai:gpt-4o-mini", tools=[add])
print((await agent.run("add 17 and 25")).answer)
```

### Multiple tools, validated args

```python
@tool
async def weather(city: str) -> str:
    """Current weather for a city."""
    return f"sunny in {city}"

@tool
async def convert(celsius: float) -> float:
    """Celsius to Fahrenheit."""
    return celsius * 9 / 5 + 32

agent = Agent("openai:gpt-4o-mini", tools=[weather, convert])
```

Bad arguments never reach your function — the kernel feeds the validation error
back to the model to retry.

### Tools running in parallel

```python
agent = Agent("openai:gpt-4o-mini", tools=[weather, add], parallel_tools=True)
# a batch of tool calls fans out concurrently; results keep call order
```

## Switching AI models

### At construction

```python
a = Agent("openai:gpt-4o-mini")
b = Agent("anthropic:claude-sonnet-4-6")
```

### Any OpenAI-compatible endpoint (Ollama, Groq, vLLM, …)

```python
import openai
from spine_providers import OpenAIProvider

local = Agent(provider=OpenAIProvider(
    "llama3.1",
    client=openai.AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="ollama"),
))
```

### Pick the model at runtime

```python
def make_agent(model: str) -> Agent:
    return Agent(model, tools=[add])

agent = make_agent("openai:gpt-4o-mini" if cheap else "anthropic:claude-sonnet-4-6")
```

### Automatic failover

```python
from spine_middleware import ModelFallback

agent = Agent(
    "openai:gpt-4o-mini",
    middleware=[ModelFallback("anthropic:claude-sonnet-4-6", "openai:gpt-4o")],
)
# on a provider error the kernel switches provider for that step
```

## Streaming tokens

```python
agent = Agent("openai:gpt-4o-mini")
async for event in agent.stream("write a haiku about otters"):
    if event.type == "token":
        print(event.data["delta"], end="", flush=True)
print("\n---\n", agent.last_result.answer)
```

## Structured output

```python
from pydantic import BaseModel
from spine_middleware import StructuredOutput

class Invoice(BaseModel):
    vendor: str
    total: float

agent = Agent("openai:gpt-4o-mini", middleware=[StructuredOutput(Invoice)])
res = await agent.run("Extract: ACME billed $42.50")
print(res.state.scratch["structured_output"])   # {"vendor": "ACME", "total": 42.5}
```

On invalid JSON it feeds the validation error back as a repair turn (capped), then
fails loud.

## Human-in-the-loop

```python
from spine_core import Agent, tool

@tool(approve=True)
async def refund(order_id: str, amount: float) -> str:
    """Issue a refund — requires approval."""
    return f"refunded ${amount} on {order_id}"

res = await agent.run("refund order 991 for $20")
if res.interrupted:
    print("approve?", res.interrupt)            # {"tool": "refund", "arguments": {...}}
    res = await agent.resume(res.resume_token, decision="approve")
print(res.answer)
```

## Sub-agents

Expose an agent as a tool another agent can call:

```python exec="1" source="above" result="text"
from spine_core import Agent
from spine_core.testing import ScriptedProvider, calls, text

translator = Agent(ScriptedProvider(text("Bonjour")), name="translator")

main = Agent(
    ScriptedProvider(calls(("translator", {"input": "say hi in French"})), text("Done: Bonjour")),
    tools=[translator.as_tool()],
)
print(main.run_sync("translate hello").answer)
```

Delegation depth is bounded, so an A→B→A cycle can't run forever.

## Multi-agent orchestration

### Sequential pipeline

```python
from spine_orchestration import Sequential

pipe = Sequential(researcher, writer, editor)   # each answer feeds the next
result = await pipe.run("write about otters")
```

### Supervisor routing

```python
from spine_orchestration import supervisor

boss = supervisor("openai:gpt-4o-mini", {
    "billing": billing_agent,
    "technical": tech_agent,
})
result = await boss.run("my invoice is wrong")
```

### Handoff between peers

```python
from spine_orchestration import Handoff

team = Handoff({"triage": triage, "expert": expert}, start="triage")
result = await team.run("escalate this")
print(result.answer, "| path:", team.path)   # "Fixed by the expert. | path: ['triage', 'expert']"
```

An agent hands off by calling an injected `transfer_to_<peer>` tool; the named
peer then takes over with the original task. Bounded by `max_handoffs`.

## Memory

```python
from spine_backends import InMemoryVectorMemory, OpenAIEmbedder
from spine_middleware import MemoryRecall

mem = InMemoryVectorMemory(embedder=OpenAIEmbedder(), dim=1536)
await mem.save("The customer's plan is Enterprise.", session_id="acme")

agent = Agent("openai:gpt-4o-mini", middleware=[MemoryRecall(mem, k=3)])
```

## Caching

```python
from spine_middleware import Cache

cache = Cache(ttl_s=3600)
agent = Agent("openai:gpt-4o-mini", middleware=[cache])
await agent.run("expensive question")   # miss → calls model
await agent.run("expensive question")   # hit  → free, no model call
print(cache.hits, cache.misses)
```

## Guardrails

```python
from spine_middleware import PIIRedaction, PromptInjectionScreen, ContentPolicy

agent = Agent(
    "openai:gpt-4o-mini",
    tools=tools,
    middleware=[
        ContentPolicy(banned=["password"]),     # block input/output
        PromptInjectionScreen(),                 # screen tool output
        PIIRedaction(),                          # redact PII everywhere
    ],
)
```

## MCP tools

```python
from spine_mcp import MCPToolset

async with MCPToolset(url="https://mcp.example.com/mcp") as mcp:
    agent = Agent("openai:gpt-4o-mini", tools=await mcp.load_tools())
    print((await agent.run("list my repos")).answer)
```

## Evaluation

```python
from spine_eval import evaluate, load_dataset, Contains

report = await evaluate(agent, load_dataset("evals/smoke.yaml"), [Contains()], concurrency=4)
print(f"{report.pass_rate:.0%} pass · ${report.cost_total_usd:.4f}")
```

## Extending

### A custom middleware

```python
from spine_core import Middleware, StepContext

class TokenBudgetLogger(Middleware):
    async def after_model(self, ctx: StepContext) -> None:
        print(f"step {ctx.state.step}: {ctx.state.usage.total_tokens} tokens so far")

agent = Agent("openai:gpt-4o-mini", middleware=[TokenBudgetLogger()])
```

### A custom provider

```python
from spine_core import Message, ModelResponse, Usage, register_provider

class UppercaseProvider:
    def __init__(self, model: str) -> None:
        self.model = model
    async def complete(self, messages, tools=None, **kw) -> ModelResponse:
        last = next(m for m in reversed(messages) if m.role.value == "user")
        return ModelResponse(message=Message.assistant((last.content or "").upper()), usage=Usage())

register_provider("upper", lambda model: UppercaseProvider(model))
print((await Agent("upper:v1").run("shout")).answer)   # "SHOUT"
```
