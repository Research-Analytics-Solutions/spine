# Guards

Guards are hard, always-on ceilings enforced **inside the kernel loop**. They are
the reason a runaway loop is *structurally impossible* in Spine: the check runs
every iteration, in the core, and cannot be bypassed by a misbehaving middleware.

```python
from spine_core import Agent, Guards

agent = Agent(
    "openai:gpt-4o-mini",
    guards=Guards(
        max_steps=12,        # max model turns
        max_cost_usd=0.50,   # cumulative USD ceiling
        max_tokens=100_000,  # cumulative token ceiling
        timeout_s=30,        # wall-clock
        max_depth=8,         # sub-agent delegation depth
    ),
)
```

Every limit is opt-in — `None` means no ceiling.

## How a trip surfaces

When a guard trips, the run stops with the matching reason and the last answer is
returned:

```python
result = await agent.run("…")
if result.stopped_reason.value == "max_cost":
    print("budget hit:", result.usage.cost_usd)
```

!!! note "Ceilings, not exact caps"
    Cost and token guards are checked *before the next* step, so a run can
    overshoot by at most the one model call already in flight. They stop runaway
    spend; they are not exact-to-the-cent caps.

## Beyond the core

- **Cost only counts if it's measured.** Native providers price their own usage;
  for others add [`CostTracking`](../reference/middleware.md) so `max_cost_usd`
  bites.
- **Per-tenant budgets** — [`TenantBudget`](../guides/guardrails.md) enforces a
  cumulative ceiling per `tenant_id` across many runs.
- **Loop detection** — [`LoopGuard`](../reference/middleware.md) stops an agent
  repeating the same tool action.
