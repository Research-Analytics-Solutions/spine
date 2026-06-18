"""OpenTelemetry observability for Spine.

```python
from spine_core import Agent
from spine_otel import OTelMiddleware, configure_otlp

agent = Agent("anthropic:claude-sonnet-4-6", middleware=[configure_otlp()])
```
"""

from __future__ import annotations

from spine_otel.middleware import OTelMiddleware, configure_otlp

__all__ = ["OTelMiddleware", "configure_otlp"]
