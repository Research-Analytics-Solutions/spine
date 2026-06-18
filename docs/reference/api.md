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
