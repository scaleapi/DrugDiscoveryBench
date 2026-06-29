#!/bin/bash
# Harbor verifier for the cad-apoe task.
# Reads the agent's terse final answer from /workspace/answer.md, optionally
# pulls a trajectory log (path conventions still TBD — try a few), then runs
# the bundled judge to produce reward.json.

set -u  # do NOT set -e: we always want reward.json written

ANSWER_FILE="/workspace/answer.md"
REWARD_FILE="/logs/verifier/reward.json"
TESTS_DIR="$(dirname "$0")"

mkdir -p "$(dirname "$REWARD_FILE")"

# Locate a trajectory file if Harbor wrote one. These paths are guesses; we
# update once we've observed where the harness actually drops agent logs.
TRAJECTORY_FILE=""
for candidate in \
    /logs/agent/output.txt \
    /logs/agent/stdout.txt \
    /logs/agent/trajectory.json \
    /logs/agent/trajectory.txt; do
    if [ -f "$candidate" ]; then
        TRAJECTORY_FILE="$candidate"
        break
    fi
done

# If the agent never produced an answer file, score 0 immediately.
# reward.json must contain only numeric fields (Harbor parses as dict[str, float|int]).
if [ ! -f "$ANSWER_FILE" ]; then
    echo '{"score": 0.0, "answer_file_present": 0}' > "$REWARD_FILE"
    echo "FAIL: $ANSWER_FILE missing — reward 0" >&2
    exit 0
fi

# Persist the REAL answer.md into the trial logs so any offline re-grade reads it
# directly, instead of reconstructing the answer from the trajectory (which is
# CLI-specific and fragile — e.g. gemini-cli's write_file vs claude-code's Write).
cp "$ANSWER_FILE" "$(dirname "$REWARD_FILE")/answer.md" 2>/dev/null || true

python3 "$TESTS_DIR/judge.py" \
    --answer-file "$ANSWER_FILE" \
    --rubrics-file "$TESTS_DIR/rubrics.json" \
    --trajectory-file "$TRAJECTORY_FILE" \
    --output "$REWARD_FILE"

# Exit clean either way — Harbor reads the reward file, not the exit code.
exit 0
