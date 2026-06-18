"""Multi-tenancy: per-tenant cost budget enforced across runs, tenants isolated."""

from __future__ import annotations

from spine_core import Agent, StopReason
from spine_core.messages import Message, ModelResponse, Usage
from spine_middleware import TenantBudget


class CostlyProvider:
    def __init__(self, cost: float) -> None:
        self.cost = cost

    async def complete(self, messages, tools=None, **kw):  # type: ignore[no-untyped-def]
        return ModelResponse(
            message=Message.assistant("ok"),
            usage=Usage(input_tokens=10, output_tokens=5, cost_usd=self.cost),
        )


async def test_tenant_budget_blocks_after_exceeded() -> None:
    budget = TenantBudget(max_cost_usd=0.05)
    provider = CostlyProvider(0.03)

    agent_a = Agent(provider, middleware=[budget], tenant_id="acme")
    first = await agent_a.run("one")
    assert first.ok  # 0.03 spent

    second = await agent_a.run("two")
    assert second.ok  # 0.06 spent — this run completed but pushed over the line

    third = await agent_a.run("three")
    assert third.stopped_reason is StopReason.MAX_COST  # now blocked before the model
    assert budget.spend("acme")["cost"] >= 0.05


async def test_tenants_are_isolated() -> None:
    budget = TenantBudget(max_cost_usd=0.05)
    provider = CostlyProvider(0.10)

    over = Agent(provider, middleware=[budget], tenant_id="big")
    await over.run("spend")  # big now over budget

    other = Agent(provider, middleware=[budget], tenant_id="small")
    result = await other.run("hi")
    assert result.ok  # small tenant unaffected
    assert budget.spend("small")["cost"] == 0.10
    assert budget.spend("big")["cost"] == 0.10
