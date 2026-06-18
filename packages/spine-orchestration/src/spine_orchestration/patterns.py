"""Multi-agent orchestration patterns — composed from plain agents + sub-agents.

These are thin compositions over the kernel, not new engine features:
- ``Sequential`` pipes one agent's answer into the next.
- ``supervisor`` builds an agent that routes to workers via ``Agent.as_tool``.
- ``Handoff`` lets agents transfer the conversation to a named peer.
"""

from __future__ import annotations

from spine_core import Agent, Result, Tool, raw_tool

_TRANSFER_SCHEMA = {
    "type": "object",
    "properties": {"reason": {"type": "string", "description": "Why hand off."}},
    "required": [],
}


class Sequential:
    """Run agents in order, feeding each answer as the next agent's input."""

    def __init__(self, *agents: Agent) -> None:
        if not agents:
            raise ValueError("Sequential needs at least one agent")
        self.agents = list(agents)

    async def run(self, input: str) -> Result:
        current = input
        result: Result | None = None
        for agent in self.agents:
            result = await agent.run(current)
            current = result.answer or ""
        assert result is not None
        return result


def supervisor(
    model: str,
    workers: dict[str, Agent],
    *,
    system: str | None = None,
    **kwargs: object,
) -> Agent:
    """Build a supervisor agent that delegates to ``workers`` as tools."""
    if not workers:
        raise ValueError("supervisor needs at least one worker")
    tools: list[Tool] = [agent.as_tool(name=name) for name, agent in workers.items()]
    instructions = system or (
        "You coordinate specialist agents. Choose the single best worker tool for "
        "the request, call it, then return its result."
    )
    return Agent(model, tools=tools, system=instructions, **kwargs)  # type: ignore[arg-type]


class Handoff:
    """A team of agents that can transfer the conversation to a named peer.

    Each agent is given ``transfer_to_<peer>`` tools. When an agent calls one,
    its turn ends and the named peer takes over with the original task. Bounded
    by ``max_handoffs`` so a transfer cycle can't run forever.
    """

    def __init__(self, agents: dict[str, Agent], *, start: str, max_handoffs: int = 5) -> None:
        if start not in agents:
            raise ValueError(f"start agent '{start}' not in the team")
        self.agents = agents
        self.start = start
        self.max_handoffs = max_handoffs
        self.path: list[str] = []
        self._pending: str | None = None
        self._wire()

    def _wire(self) -> None:
        for name, agent in self.agents.items():
            for peer in self.agents:
                if peer == name:
                    continue
                transfer = self._make_transfer(peer)
                agent.tools[transfer.name] = transfer

    def _make_transfer(self, target: str) -> Tool:
        async def transfer(reason: str = "") -> str:
            self._pending = target
            return f"Handing off to {target}. {reason}".strip()

        return raw_tool(
            f"transfer_to_{target}",
            f"Hand off the conversation to the {target} agent.",
            _TRANSFER_SCHEMA,
            transfer,
        )

    async def run(self, input: str) -> Result:
        current = self.start
        self.path = [current]
        result: Result | None = None
        for _ in range(self.max_handoffs + 1):
            self._pending = None
            result = await self.agents[current].run(input)
            if self._pending is None:
                return result
            current = self._pending
            self.path.append(current)
        assert result is not None
        return result  # exhausted handoffs; last agent's result stands
