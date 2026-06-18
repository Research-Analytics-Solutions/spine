# Human-in-the-loop

A tool or middleware can pause a run for a human, and the pause is **durable** —
it can outlive the process because the resume token points at a checkpoint.

## Approval gate

One flag turns on approval for a tool:

```python
from spine_core import Agent, tool

@tool(approve=True)
async def transfer_funds(amount: int, to: str) -> str:
    """Move money — requires approval."""
    ...

res = await agent.run("pay invoice 7781")
if res.interrupted:
    # show res.interrupt to a human, persist res.resume_token
    res = await agent.resume(res.resume_token, decision="approve")
```

`decision` accepts `"approve"` / `"reject"` (or any truthy/falsey value). On
reject the tool is not executed and the rejection is fed back to the model.

## Manual interrupt

A tool can pause itself and let the human supply the result:

```python
from spine_core import Interrupt

@tool
async def ask_human(question: str) -> str:
    """Escalate to a person."""
    raise Interrupt(payload={"question": question})

# ... later, the decision becomes the tool result:
res = await agent.resume(res.resume_token, decision="ship it")
```

## Surviving a restart

The resume token is the run's session id, backed by the checkpoint store. A
**brand-new process** with the same durable store resumes the pause:

```python
from spine_backends import SQLiteCheckpoint

store = SQLiteCheckpoint("runs.db")
# process A
res = await Agent("openai:gpt-4o-mini", tools=[transfer_funds], checkpoint=store).run("pay")
session_id = res.state.session_id

# process B (after a restart) — same db file
res = await Agent("openai:gpt-4o-mini", tools=[transfer_funds], checkpoint=store).resume(session_id, "approve")
```

This is what makes long-lived approvals (hours, days) safe.
