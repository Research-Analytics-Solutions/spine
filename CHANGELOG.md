# Changelog

## [0.3.0](https://github.com/Research-Analytics-Solutions/spine/compare/v0.2.0...v0.3.0) (2026-06-20)


### Features

* **middleware:** ConsoleLogger — opt-in pretty terminal logs ([72fc1f1](https://github.com/Research-Analytics-Solutions/spine/commit/72fc1f17e4dbace45fd8cc5271888bbfc8d159fc))


### Bug Fixes

* **middleware:** wrap long ConsoleLogger line (E501) ([daf8807](https://github.com/Research-Analytics-Solutions/spine/commit/daf8807e3e5e3a6c5631f988d8bb004a9e7abc26))


### Documentation

* real footprint benchmark vs other agent frameworks ([e23c236](https://github.com/Research-Analytics-Solutions/spine/commit/e23c236d88e025459fc021fc9f577ce3ed9c26d4))

## [0.2.0](https://github.com/Research-Analytics-Solutions/spine/compare/v0.1.0...v0.2.0) (2026-06-18)


### Features

* **a2a:** agent-to-agent adapter — call a remote agent as a tool ([473bdfe](https://github.com/Research-Analytics-Solutions/spine/commit/473bdfe9803dd722a27a7624ab71b64e3a2d3550))
* **backends:** Redis + Postgres checkpoint backends + conformance suite ([a9d8990](https://github.com/Research-Analytics-Solutions/spine/commit/a9d8990e41e8f6383dc26c1f11524de2ba9b89c9))
* **backends:** spine-backends with durable SQLite checkpoint ([9974652](https://github.com/Research-Analytics-Solutions/spine/commit/997465223cb3c3d7d01d3ace2eda755bfc01a1e2))
* **cli:** config-driven agent build + chat/trace commands ([8da432e](https://github.com/Research-Analytics-Solutions/spine/commit/8da432e3157e7e26861e5c01e8814f4e67c79423))
* **cli:** spine dev — live-streaming trace viewer ([5b2ed12](https://github.com/Research-Analytics-Solutions/spine/commit/5b2ed127d9520a364ee54b21f52f9a77d24c63d1))
* **cli:** spine-cli with init/run/doctor/plugin (Typer + Rich) ([422d1b5](https://github.com/Research-Analytics-Solutions/spine/commit/422d1b579c3f810e93b8f4a96f246ef29d1d77f6))
* **core:** parallel tool calls, cooperative cancellation, sub-agents ([14ce08f](https://github.com/Research-Analytics-Solutions/spine/commit/14ce08f1d32f72c3d71e0cf3db495e20408b376c))
* **core:** spine-core kernel — loop, guards, middleware, tools, HITL ([450df11](https://github.com/Research-Analytics-Solutions/spine/commit/450df1135b10b8fe5032b217eb75fba93fa9c9ca))
* **eval:** spine-eval harness + spine eval CLI command ([316c27b](https://github.com/Research-Analytics-Solutions/spine/commit/316c27bb6c1ee849bab4767c52907f404393c716))
* **mcp:** spine-mcp adapter + raw_tool core primitive ([80676fb](https://github.com/Research-Analytics-Solutions/spine/commit/80676fb403ba607b29d1e52f3b1d8317418ccd5b))
* **memory:** pluggable embedders + multiple memory types ([7f5a1b8](https://github.com/Research-Analytics-Solutions/spine/commit/7f5a1b8aa6a0649364fc6c776ffb497944835385))
* **memory:** semantic memory protocol, vector backend, recall middleware ([e59b306](https://github.com/Research-Analytics-Solutions/spine/commit/e59b306a80defc8ea8a8eebc0440d149d9d34f3b))
* **middleware:** deterministic replay (Recorder/Replayer) ([327c39b](https://github.com/Research-Analytics-Solutions/spine/commit/327c39b458d2af8e6bcaedd87741ec945a39559b))
* **middleware:** guardrails — PII redaction, injection screening, content policy ([a714367](https://github.com/Research-Analytics-Solutions/spine/commit/a714367e0510648086f28e14b27a8fea9eb311e6))
* **middleware:** prompt/response Cache + kernel cache-hit short-circuit ([0deab9c](https://github.com/Research-Analytics-Solutions/spine/commit/0deab9c55a9c44764b0744d4bf1cc225e0624501))
* **middleware:** tool timeout/truncation, circuit breaker, idempotency, rate limit ([de4e27a](https://github.com/Research-Analytics-Solutions/spine/commit/de4e27a7b8c03a5a91966182c810ffbe40f655e2))
* **middleware:** V1 middleware suite + kernel control primitives ([a6d7766](https://github.com/Research-Analytics-Solutions/spine/commit/a6d776663bdb644d5e24d7f28a8bd225c28d8617))
* **multimodal:** image/file content parts on Message + provider mapping ([4993441](https://github.com/Research-Analytics-Solutions/spine/commit/4993441cb2f3accf475a216e15c60ed1cc51f896))
* **multitenancy:** tenant_id on state + per-tenant budget guard ([b306e11](https://github.com/Research-Analytics-Solutions/spine/commit/b306e11a65323ea736fe24f07585150973906458))
* **orchestration:** sequential, supervisor, handoff patterns ([d2adb2e](https://github.com/Research-Analytics-Solutions/spine/commit/d2adb2eceb769e5dc5c7f73f8917adc2fdb382f4))
* **otel:** spine-otel — one OpenTelemetry span tree per run ([2453bf2](https://github.com/Research-Analytics-Solutions/spine/commit/2453bf2f8383389b022d2b838cf143ab497fe160))
* **providers:** add OpenAI adapter ([6005eb9](https://github.com/Research-Analytics-Solutions/spine/commit/6005eb955a8a313fa1ce5af9e96bf7d438342f9a))
* **providers:** spine-providers with Anthropic adapter ([cbe1171](https://github.com/Research-Analytics-Solutions/spine/commit/cbe1171a53a139fc51dec356ec3adf89189f2a1c))
* **sandbox:** resource-limited subprocess sandbox for sync tools ([5622d1a](https://github.com/Research-Analytics-Solutions/spine/commit/5622d1a4dfc0266fae16357a6de33919384bccef))
* **streaming:** token-level streaming through provider + kernel ([85df88a](https://github.com/Research-Analytics-Solutions/spine/commit/85df88aff07f9672d1d8e06e2d309422f243dea7))


### Bug Fixes

* **core:** auto-resolve provider scheme via plugin entry points ([4f2213d](https://github.com/Research-Analytics-Solutions/spine/commit/4f2213d419393153d62703495f691932168cb98c))
* **core:** bound provider-retry loop; make resume token durable ([1b6c434](https://github.com/Research-Analytics-Solutions/spine/commit/1b6c434c15e74864c734ebd387df50da3383e32d))


### Documentation

* contributor guide, plugin development & publishing, eval/MCP deep dives ([81b126f](https://github.com/Research-Analytics-Solutions/spine/commit/81b126f4cdbdc5fa02a8de5ea4a399b9bdddfbc4))
* deep reference — data model, cookbook, patterns, expanded CLI & API ([409701a](https://github.com/Research-Analytics-Solutions/spine/commit/409701a834202fdc5aef938814bc6ae7c66cc16f))
* fix mermaid diagram invisibility in dark mode ([359985d](https://github.com/Research-Analytics-Solutions/spine/commit/359985ddde0d6fe42c8f4824f55b43c4d2b67b3b))
* landing page hero, logo, mermaid + grid-card fixes ([13f929b](https://github.com/Research-Analytics-Solutions/spine/commit/13f929b05ddeae0f54eaee1c6d4cefe1adb38c1f))
* mkdocs-material documentation site ([4e63082](https://github.com/Research-Analytics-Solutions/spine/commit/4e630824e14303896c3d0c2e0254654f9d6bb4d2))
* reconcile with single spinekit distribution ([878a934](https://github.com/Research-Analytics-Solutions/spine/commit/878a934cfbc2611b62edadfde1d090bb6f0e69ef))
* replace ASCII four-planes box with a styled mermaid diagram ([86c3de3](https://github.com/Research-Analytics-Solutions/spine/commit/86c3de382c21bc0b53b860c5be504fabeda66ecb))


### Build & Packaging

* repackage as a single 'spinekit' distribution with extras ([a4e3765](https://github.com/Research-Analytics-Solutions/spine/commit/a4e37655c38751990134a3b6cbb62e584c31d5f1))
