#!/usr/bin/env bash
#
# Keep each benchmark task's egress healthcheck in sync.
#
# The trial image runs a small forward proxy that blocks a denylist of hosts
# whose published content overlaps task answers. The denylist ships inside the
# image, so tasks carry no per-task egress configuration -- only a healthcheck
# that fails the trial loudly if the proxy isn't blocking those hosts before the
# agent runs (so an unblocked run never scores silently).
#
# This script ensures that healthcheck is present, and removes two obsolete
# per-task artifacts left by an earlier approach:
#   - an EGRESS_DENY_HOSTS entry in [environment.env]
#   - an environment/docker-compose.yaml override
#
# A task may still set EGRESS_DENY_HOSTS in its own [environment.env] to extend
# the blocked list; absent that, the image default applies.
#
# Idempotent; safe to re-run. `--check` reports without changing anything (CI).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TASK_DIR="$REPO_ROOT/benchmark/tasks"

CHECK_ONLY=0
[ "${1:-}" = "--check" ] && CHECK_ONLY=1

read -r -d '' HEALTHCHECK_BLOCK <<'EOF' || true
[environment.healthcheck]
# Fail the trial loudly if the egress proxy isn't blocking Scale domains before
# the agent runs: http://scale.com must return 403 (served by the proxy baked
# into the biomni image). curl honors the lowercase http_proxy env set in the
# image. The start period absorbs proxy startup (a few seconds, e.g. under qemu):
# during it, failures don't count and Harbor re-checks every start_interval_sec.
command = 'test "$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 http://scale.com)" = "403"'
start_period_sec = 30.0
start_interval_sec = 2.0
interval_sec = 3.0
retries = 5

EOF

hc_updated=0; hc_skipped=0; hc_missing_anchor=0
env_removed=0
compose_removed=0; compose_conflict=0

for task in "$TASK_DIR"/*/; do
    toml="$task/task.toml"
    [ -f "$toml" ] || continue

    # 1. Ensure the healthcheck table is present (insert before [agent] if absent).
    if grep -q '^\[environment\.healthcheck\]' "$toml"; then
        hc_skipped=$((hc_skipped + 1))
    elif ! grep -q '^\[agent\]' "$toml"; then
        echo "WARN: no [agent] table in $toml -- skipping healthcheck insert" >&2
        hc_missing_anchor=$((hc_missing_anchor + 1))
    elif [ "$CHECK_ONLY" -eq 1 ]; then
        echo "WOULD INSERT healthcheck: $toml"; hc_updated=$((hc_updated + 1))
    else
        tmp="$(mktemp)"
        BLOCK="$HEALTHCHECK_BLOCK" awk '
            /^\[agent\]/ && !done { printf "%s\n\n", ENVIRON["BLOCK"]; done = 1 }
            { print }
        ' "$toml" > "$tmp"
        mv "$tmp" "$toml"; hc_updated=$((hc_updated + 1))
    fi

    # 2. Remove the obsolete EGRESS_DENY_HOSTS line (now baked into the image).
    if grep -q '^EGRESS_DENY_HOSTS' "$toml"; then
        if [ "$CHECK_ONLY" -eq 1 ]; then
            echo "WOULD REMOVE EGRESS_DENY_HOSTS: $toml"; env_removed=$((env_removed + 1))
        else
            tmp="$(mktemp)"
            grep -v '^EGRESS_DENY_HOSTS' "$toml" > "$tmp"
            mv "$tmp" "$toml"; env_removed=$((env_removed + 1))
        fi
    fi

    # 3. Remove the obsolete compose override. Only touch a compose file that
    #    exists solely to forward EGRESS_DENY_HOSTS; never clobber another one.
    envdir="$task/environment"
    compose="$envdir/docker-compose.yaml"
    if [ -f "$compose" ] && grep -q 'EGRESS_DENY_HOSTS' "$compose"; then
        if [ "$CHECK_ONLY" -eq 1 ]; then
            echo "WOULD REMOVE compose: $compose"; compose_removed=$((compose_removed + 1))
        else
            rm -f "$compose"
            rmdir "$envdir" 2>/dev/null || true
            compose_removed=$((compose_removed + 1))
        fi
    elif [ -f "$compose" ]; then
        echo "WARN: $compose exists for some other reason -- not removing" >&2
        compose_conflict=$((compose_conflict + 1))
    fi
done

echo "---"
if [ "$CHECK_ONLY" -eq 1 ]; then
    echo "check: healthcheck pending=$hc_updated (applied=$hc_skipped, no-anchor=$hc_missing_anchor); EGRESS_DENY_HOSTS to-remove=$env_removed; compose to-remove=$compose_removed (conflict=$compose_conflict)"
    if [ "$hc_updated" -ne 0 ] || [ "$env_removed" -ne 0 ] || [ "$compose_removed" -ne 0 ]; then
        echo "Run ./scripts/apply_egress_block.sh to apply."; exit 1
    fi
else
    echo "applied: healthcheck inserted=$hc_updated (already=$hc_skipped, no-anchor=$hc_missing_anchor); EGRESS_DENY_HOSTS removed=$env_removed; compose removed=$compose_removed (conflict=$compose_conflict)"
fi
