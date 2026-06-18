# API reference

Auto-generated from the source. The public surface lives in `spine_core`.

## Agent

::: spine_core.Agent
    options:
      members:
        - run
        - stream
        - resume
        - as_tool
        - run_sync
        - resume_sync

## Result & stop reasons

::: spine_core.Result
::: spine_core.StopReason

## Guards

::: spine_core.Guards

## Messages

::: spine_core.Message
::: spine_core.ModelResponse
::: spine_core.Usage
::: spine_core.ToolCall

## Tools

::: spine_core.tool
::: spine_core.raw_tool
::: spine_core.Tool

## Middleware

::: spine_core.Middleware
::: spine_core.StepContext
::: spine_core.ToolContext
::: spine_core.ErrorAction
::: spine_core.StopRun

## Providers

::: spine_core.Provider
::: spine_core.StreamingProvider
::: spine_core.StreamChunk

## State & memory

::: spine_core.State
::: spine_core.Memory
::: spine_core.Embedder

## Registries

::: spine_core.register_provider
::: spine_core.register_middleware
::: spine_core.register_checkpoint
::: spine_core.register_memory

## Middleware (`spine_middleware`)

::: spine_middleware.Retry
::: spine_middleware.ModelFallback
::: spine_middleware.LoopGuard
::: spine_middleware.CircuitBreaker
::: spine_middleware.RateLimit
::: spine_middleware.CostTracking
::: spine_middleware.Cache
::: spine_middleware.Compaction
::: spine_middleware.StructuredOutput
::: spine_middleware.ToolTimeout
::: spine_middleware.ToolOutputTruncation
::: spine_middleware.Idempotency
::: spine_middleware.Sandbox
::: spine_middleware.PIIRedaction
::: spine_middleware.PromptInjectionScreen
::: spine_middleware.ContentPolicy
::: spine_middleware.TenantBudget
::: spine_middleware.MemoryRecall
::: spine_middleware.Recorder
::: spine_middleware.Replayer

## Backends (`spine_backends`)

::: spine_backends.SQLiteCheckpoint
::: spine_backends.RedisCheckpoint
::: spine_backends.PostgresCheckpoint
::: spine_backends.InMemoryVectorMemory
::: spine_backends.BufferMemory
::: spine_backends.PgVectorMemory
::: spine_backends.HashEmbedder
::: spine_backends.OpenAIEmbedder

## Providers (`spine_providers`)

::: spine_providers.OpenAIProvider
::: spine_providers.AnthropicProvider

## Eval (`spine_eval`)

::: spine_eval.evaluate
::: spine_eval.load_dataset
::: spine_eval.EvalReport
::: spine_eval.Case
::: spine_eval.LLMJudge

## Orchestration (`spine_orchestration`)

::: spine_orchestration.Sequential
::: spine_orchestration.supervisor
::: spine_orchestration.Handoff

## Adapters

::: spine_mcp.MCPToolset
::: spine_a2a.A2AAgent
::: spine_otel.OTelMiddleware
