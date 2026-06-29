#!/usr/bin/env bash
#
# Run a BiOMNI eval task via Harbor.
#
# Usage:
#   ./run_eval.sh <task-id>
#   ./run_eval.sh <task-id> --model claude-sonnet-4-6 --agent claude-code
#   ./run_eval.sh <task-id> --model gpt-5.5 --agent codex
#   ./run_eval.sh <task-id> -k 5 -n 10          # 5 trials, 10 concurrent
#   ./run_eval.sh all                            # run all 82 tasks
#
# Required env vars:
#   For Claude Code:  ANTHROPIC_API_KEY (and optionally ANTHROPIC_BASE_URL)
#   For Codex:        OPENAI_API_KEY (and optionally OPENAI_BASE_URL)
#   For the judge:    JUDGE_BASE_URL, JUDGE_API_KEY, JUDGE_MODEL
#
# Single-proxy shortcut (one key, one endpoint for everything):
#   LLM_API_KEY            One key used for the agent AND the judge when their
#                          per-role keys are unset (e.g. a LiteLLM virtual key).
#   LLM_BASE_URL           One proxy root; per-role base URLs are derived from it
#                          when unset (OpenAI/judge get a /v1 suffix; Anthropic
#                          and Gemini use the root). See docs/model-proxy.md.
#                          Per-role vars always win if you set them explicitly.
#
# Optional env vars:
#   HARBOR_EXECUTOR        Harbor executor backend (default: docker).
#   HARBOR_EXEC_KWARGS     Backend kwargs for a non-docker executor, as a space-
#                          separated list of key=value pairs (each passed via --ek).
#                          Required when HARBOR_EXECUTOR is not "docker" — there are
#                          no built-in defaults; supply your own backend/account
#                          resources (e.g. a registry secret + data-lake volume).
#   BRAVE_SEARCH_API_KEY   Injected into trials so Biomni's search_web (Brave) works.
#                          This is the web-search FUNNEL: agents' native web tools are
#                          disabled by default (they reach the web via server-side
#                          grounding the egress proxy can't see, defeating the
#                          denylist), so all web search must go through search_web,
#                          which is Scale-content-filtered in the image. Without this
#                          key, search_web errors and agents have no web search.
#
# Flags:
#   --native-web   Do NOT disable agents' native web tools (debug/escape hatch;
#                  re-opens the server-side-search bypass of the egress denylist).
#                  Applies to claude-code and codex only. For gemini-cli it has
#                  NO effect: the required api-key auth and tools.exclude are
#                  coupled in the image's /etc/gemini-cli/settings.json (highest
#                  merge precedence), so the native web tools cannot be re-enabled
#                  without dropping auth. A true gemini escape hatch needs an
#                  auth-only system-settings variant baked into the image.

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────
MODEL="${MODEL:-claude-sonnet-4-6}"
AGENT="${AGENT:-claude-code}"
K=1
N=1
EXECUTOR="${HARBOR_EXECUTOR:-docker}"
NATIVE_WEB=0
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TASK_DIR="$REPO_ROOT/benchmark/tasks"

# ── Parse args ────────────────────────────────────────────────────────────
if [ $# -lt 1 ]; then
    echo "Usage: ./run_eval.sh <task-id|all> [--model MODEL] [--agent AGENT] [-k K] [-n N]"
    exit 1
fi

TASK_ID="$1"; shift

while [ $# -gt 0 ]; do
    case "$1" in
        --model)  MODEL="$2"; shift 2 ;;
        --agent)  AGENT="$2"; shift 2 ;;
        -k)       K="$2"; shift 2 ;;
        -n)       N="$2"; shift 2 ;;
        --native-web) NATIVE_WEB=1; shift ;;
        *)        echo "Unknown arg: $1"; exit 1 ;;
    esac
done

# ── Single-proxy shortcut: one key + one endpoint for agent and judge ───────
# Route everything through a single (e.g. LiteLLM) proxy with one virtual key:
#   export LLM_API_KEY=sk-...                 # one key
#   export LLM_BASE_URL=https://proxy.host    # proxy root
# The per-role vars are auto-derived below ONLY when unset, so any explicit
# per-role var (ANTHROPIC_API_KEY, JUDGE_BASE_URL, ...) always takes precedence.
if [ -n "${LLM_API_KEY:-}" ]; then
    : "${ANTHROPIC_API_KEY:=$LLM_API_KEY}"
    : "${OPENAI_API_KEY:=$LLM_API_KEY}"
    : "${GEMINI_API_KEY:=$LLM_API_KEY}"
    : "${JUDGE_API_KEY:=$LLM_API_KEY}"
fi
if [ -n "${LLM_BASE_URL:-}" ]; then
    BASE="${LLM_BASE_URL%/}"                   # strip any trailing slash
    : "${ANTHROPIC_BASE_URL:=$BASE}"           # LiteLLM serves /v1/messages at root
    : "${GOOGLE_GEMINI_BASE_URL:=$BASE}"       # proxy ROOT (not /gemini) for vertex routing
    : "${OPENAI_BASE_URL:=$BASE/v1}"           # OpenAI clients append /v1/...
    : "${JUDGE_BASE_URL:=$BASE/v1}"            # judge speaks OpenAI-compatible /v1
fi

# ── Agent selection ───────────────────────────────────────────────────────
# Use DrugDiscoveryBench's preinstalled-CLI adapters (scripts/harbor_agents.py) via
# Harbor's --agent-import-path. They reuse the image's pinned, working CLIs
# instead of letting Harbor reinstall them at trial setup — the upstream
# installers (claude-code native build; codex/gemini nvm) are SIGKILLed in the
# trial container. The adapters fall back to Harbor's normal install if no CLI
# is present. Agents without a preinstalled adapter fall back to plain -a.
# (case, not an associative array, for bash 3.2 / macOS compatibility)
case "$AGENT" in
    claude-code) AGENT_IMPORT="harbor_agents:PreinstalledClaudeCode" ;;
    codex)       AGENT_IMPORT="harbor_agents:PreinstalledCodex" ;;
    gemini-cli)  AGENT_IMPORT="harbor_agents:PreinstalledGeminiCli" ;;
    *)           AGENT_IMPORT="" ;;
esac
AGENT_FLAGS=()
if [ -n "$AGENT_IMPORT" ]; then
    export PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}"
    AGENT_FLAGS+=(--agent-import-path "$AGENT_IMPORT")
else
    AGENT_FLAGS+=(-a "$AGENT")
fi

# ── Build agent env flags ─────────────────────────────────────────────────
AE_FLAGS=()
if [ "$AGENT" = "claude-code" ]; then
    : "${ANTHROPIC_API_KEY:?Set ANTHROPIC_API_KEY for Claude Code}"
    AE_FLAGS+=(--ae "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY")
    [ -n "${ANTHROPIC_BASE_URL:-}" ] && AE_FLAGS+=(--ae "ANTHROPIC_BASE_URL=$ANTHROPIC_BASE_URL")
elif [ "$AGENT" = "codex" ]; then
    : "${OPENAI_API_KEY:?Set OPENAI_API_KEY for Codex}"
    AE_FLAGS+=(--ae "OPENAI_API_KEY=$OPENAI_API_KEY")
    [ -n "${OPENAI_BASE_URL:-}" ] && AE_FLAGS+=(--ae "OPENAI_BASE_URL=$OPENAI_BASE_URL")
elif [ "$AGENT" = "gemini-cli" ]; then
    # Route gemini-cli through the LiteLLM proxy ROOT (not the /gemini
    # passthrough) so vertex_ai/ models resolve to Vertex — this moves
    # gemini-cli's google_web_search grounding onto Vertex quota instead of
    # the Gemini Developer API's hard 1,500 searches/day cap. Use
    # a vertex model, e.g. --model vertex_ai/global/gemini-3.5-flash. The
    # image's baked /root/.gemini/settings.json pins api-key auth and points
    # the web-search/web-fetch aliases at the vertex model.
    : "${GEMINI_API_KEY:?Set GEMINI_API_KEY (LiteLLM virtual key) for gemini-cli}"
    AE_FLAGS+=(--ae "GEMINI_API_KEY=$GEMINI_API_KEY")
    AE_FLAGS+=(--ae "GOOGLE_GEMINI_BASE_URL=${GOOGLE_GEMINI_BASE_URL:-https://your-litellm-proxy.example.com}")
    # Load the image's baked SYSTEM settings (/etc/gemini-cli/settings.json). With
    # GOOGLE_GEMINI_BASE_URL set, gemini-cli >=0.47 resolves auth to 'gateway' and
    # crashes ("Invalid auth method selected") unless settings.security.auth.
    # selectedType == 'gemini-api-key'. Harbor's gemini-cli adapter OVERWRITES the
    # USER ~/.gemini/settings.json on install, so that auth (and the tools.exclude
    # that disables gemini's native web tools) only survives in the SYSTEM settings,
    # which the adapter never touches and gemini merges at highest precedence.
    # (Native web tools are thus always off for gemini-cli; web search goes through
    # Biomni search_web. --native-web does not re-enable them for gemini.)
    AE_FLAGS+=(--ae "GEMINI_CLI_SYSTEM_SETTINGS_PATH=/etc/gemini-cli/settings.json")
fi

# ── Web-search funnel: disable native (proxy-bypassing) web tools; keep search
#    via Biomni search_web (Brave). Native tools do server-side grounding the
#    egress proxy can't see, so leaving them on would defeat the denylist. ─────
AK_FLAGS=()
if [ "$NATIVE_WEB" -eq 0 ]; then
    if [ "$AGENT" = "claude-code" ]; then
        # Claude Code's web tools are WebSearch + WebFetch; the claude-code adapter
        # maps the disallowed_tools kwarg to --disallowedTools.
        AK_FLAGS+=(--ak "disallowed_tools=WebSearch WebFetch")
    fi
    # gemini-cli: excluded via the baked system settings (tools.exclude) set above.
    # codex: native web_search is off by default in config.toml -- nothing to do.
else
    echo "WARN: --native-web set -- agents' native web tools stay ENABLED; their server-side search can bypass the egress denylist." >&2
    if [ "$AGENT" = "gemini-cli" ]; then
        echo "WARN: --native-web has NO effect for gemini-cli -- its tools.exclude is coupled with the required api-key auth in the image's system settings, so the native web tools stay disabled. Use claude-code/codex to exercise native web tools." >&2
    fi
fi

# Brave key powers Biomni search_web (the funnel's search path). Inject for every
# agent so a shell `python -c "from biomni.tool.literature import search_web"`
# works; without it search_web errors and the agent has no web search.
if [ -n "${BRAVE_SEARCH_API_KEY:-}" ]; then
    AE_FLAGS+=(--ae "BRAVE_SEARCH_API_KEY=$BRAVE_SEARCH_API_KEY")
elif [ "$NATIVE_WEB" -eq 0 ]; then
    echo "WARN: BRAVE_SEARCH_API_KEY unset -- Biomni search_web will error and agents have no web search (native web tools are disabled). Set it, or pass --native-web." >&2
fi

# ── Validate judge credentials ────────────────────────────────────────────
: "${JUDGE_BASE_URL:?Set JUDGE_BASE_URL (e.g. https://api.openai.com/v1)}"
: "${JUDGE_API_KEY:?Set JUDGE_API_KEY}"
: "${JUDGE_MODEL:?Set JUDGE_MODEL (e.g. gpt-4o)}"
export JUDGE_BASE_URL JUDGE_API_KEY JUDGE_MODEL

# ── Resolve task paths ────────────────────────────────────────────────────
if [ "$TASK_ID" = "all" ]; then
    TASK_PATHS=()
    for d in "$TASK_DIR"/*/; do
        [ -f "$d/task.toml" ] && TASK_PATHS+=(-p "$d")
    done
    echo "Running all ${#TASK_PATHS[@]} tasks with $AGENT ($MODEL), k=$K, n=$N"
else
    if [ ! -d "$TASK_DIR/$TASK_ID" ]; then
        echo "Error: task directory $TASK_DIR/$TASK_ID not found"
        echo "Available tasks: $(ls "$TASK_DIR" | head -5) ... ($(ls "$TASK_DIR" | wc -l) total)"
        exit 1
    fi
    TASK_PATHS=(-p "$TASK_DIR/$TASK_ID")
    echo "Running task $TASK_ID with $AGENT ($MODEL), k=$K, n=$N"
fi

# ── Build executor-specific flags ─────────────────────────────────────────
# The default `docker` executor needs no extra kwargs. Any other Harbor executor
# (e.g. a remote/cloud backend) requires backend-specific kwargs — a registry
# secret, a data-lake volume mapping, etc. There are NO built-in defaults: supply
# your own via HARBOR_EXEC_KWARGS (space-separated key=value pairs), e.g.
#   HARBOR_EXEC_KWARGS='registry_secret=<name> volumes={"/workspace/data/biomni_data/data_lake":"<volume>"}'
# We fail loudly below if they're missing, so a misconfigured remote run can't
# silently start without its data lake / registry access.
EK_FLAGS=()
if [ "$EXECUTOR" != "docker" ]; then
    : "${HARBOR_EXEC_KWARGS:?EXECUTOR='$EXECUTOR' requires backend kwargs; set HARBOR_EXEC_KWARGS=\"key=value ...\" (no defaults are built in)}"
    for _kw in $HARBOR_EXEC_KWARGS; do EK_FLAGS+=(--ek "$_kw"); done
fi

# ── Run ───────────────────────────────────────────────────────────────────
harbor run \
    "${TASK_PATHS[@]}" \
    -m "$MODEL" "${AGENT_FLAGS[@]}" \
    -e "$EXECUTOR" \
    "${AE_FLAGS[@]}" \
    ${AK_FLAGS[@]+"${AK_FLAGS[@]}"} \
    ${EK_FLAGS[@]+"${EK_FLAGS[@]}"} \
    --environment-build-timeout-multiplier 3.0 \
    --job-name "biomni_$(date +%Y%m%d_%H%M%S)" \
    -k "$K" -n "$N" --yes
