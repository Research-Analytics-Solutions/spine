#!/usr/bin/env bash
# Reproducible footprint benchmark: installs each framework in an isolated venv
# and measures transitive dependency count + on-disk install size.
#
# Requires: uv.  Usage: bash scripts/benchmark.sh
set -euo pipefail

WORK=${WORK:-/tmp/spine-bench}
rm -rf "$WORK"; mkdir -p "$WORK"; cd "$WORK"

# name | pip spec | import module
TARGETS=$(cat <<'EOF'
spinekit|spinekit|spine_core
langchain|langchain|langchain
langgraph|langgraph|langgraph
crewai|crewai|crewai
llama-index|llama-index-core|llama_index.core
pydantic-ai|pydantic-ai-slim|pydantic_ai
smolagents|smolagents|smolagents
openai-agents|openai-agents|agents
EOF
)

printf "%-16s %-12s %10s %10s\n" framework version packages size_mb
echo "$TARGETS" | while IFS='|' read -r name spec mod; do
  v="$WORK/venv_$name"
  uv venv "$v" -q
  if uv pip install --python "$v/bin/python" "$spec" -q >/dev/null 2>&1; then
    ver=$(uv pip freeze --python "$v/bin/python" | grep -iE "^${spec%%\[*}==" | head -1 | cut -d= -f3)
    npkgs=$(uv pip freeze --python "$v/bin/python" | wc -l | tr -d ' ')
    sp=$("$v/bin/python" -c "import sysconfig;print(sysconfig.get_paths()['purelib'])")
    size=$(du -sm "$sp" | cut -f1)
    printf "%-16s %-12s %10s %10s\n" "$name" "$ver" "$npkgs" "$size"
  else
    printf "%-16s %-12s %10s %10s\n" "$name" "FAILED" "-" "-"
  fi
done
