# Benchmark Tasks

82 [Harbor](https://github.com/harbor-framework/harbor)-formatted evaluation tasks
for testing AI agents against BiOMNI's biomedical tool suite.

## Directory layout

```
benchmark/
├── _template/                   Shared boilerplate
│   ├── environment/Dockerfile   FROM the biomni image (ghcr.io/scaleapi/drugdiscoverybench)
│   ├── instruction_appendix.md  Appended to every task's prompt
│   └── tests/{judge.py, test.sh}
├── tasks/                       82 tasks, one dir per task ID
│   └── <24-char-hex>/
│       ├── instruction.md       Task prompt + appendix
│       ├── task.toml            Harbor config (image, env, timeouts)
│       └── tests/
│           ├── judge.py         LLM-based rubric judge
│           ├── rubrics.json     Scoring rubrics
│           └── test.sh          Verifier entry point
└── README.md
```

## Trial container architecture

Each trial container **is** the BiOMNI image (`ghcr.io/scaleapi/drugdiscoverybench:1.0.0-lightweight`).
One `docker pull` gets:

- The BiOMNI conda env + Python source + the BiOMNI tool suite
- Node 22 + `@anthropic-ai/claude-code` + `@openai/codex` + `@google/gemini-cli`
  (plus a `grok` binary baked in as of `2.10.3` but not yet wired as a Harbor agent —
  see the root README's [Grok CLI appendix](../README.md#appendix-grok-cli))

**No MCP.** The agent invokes BiOMNI directly via Bash — every tool is importable
as `biomni.tool.<domain>.<name>`, e.g.
`python -c "from biomni.tool.<domain> import <name>; print(<name>(...))"`. The
on-container reference (`/biomni/biomni/tool/<domain>.py`, `env_desc.py`,
`know_how/*.md`) is described in `_template/instruction_appendix.md`. `/workspace`
is the shared working directory.

## Running a task

See the root [README](../README.md) for full quickstart instructions, or use
the provided wrapper script:

```bash
scripts/run_eval.sh <task-id> --model claude-sonnet-4-6 --agent claude-code
```

Or call Harbor directly:

```bash
harbor run -p benchmark/tasks/<task-id> -m claude-sonnet-4-6 -a claude-code -e docker \
    --ae "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY" -k 1 -n 1 --yes
```

## Grading

Each task's `tests/judge.py` is an LLM-as-judge that scores the agent's
`/workspace/answer.md` against `rubrics.json`. The judge credentials are injected
from the environment by Harbor: `JUDGE_MODEL` (defaults to `gpt-4o`), plus
`JUDGE_BASE_URL` + `JUDGE_API_KEY` for any OpenAI-API-compatible endpoint (the
provider API directly or a proxy). See [docs/model-proxy.md](../docs/model-proxy.md).
Score =
`max(0, earned / possible * 100)` where `earned` sums met positive weights minus
met negative penalties and `possible` sums all positive weights.

## Data lake

The image ships in three tiers (see the root [README](../README.md#data-lake) for
the full table). Tasks pin **`1.0.0-lightweight`**, which bakes no data lake — tools
fall back to live public APIs. The **`1.0.0-core`** (~21 local DBs, ~74% offline)
and **`1.0.0-full`** (+ PubChem/PubMed/AlphaFold/Open Targets, ~99.7%) tiers bake
the databases into the image at `/workspace/data/biomni_data/data_lake/` for
offline, deterministic runs.

## Outputs

Each trial writes to `jobs/<timestamp>/<task_id>/`:

| File | Contents |
|------|----------|
| `agent/` | Full agent transcript, trajectory, session logs |
| `verifier/reward.json` | Numeric scores (Harbor reads this for aggregation) |
| `verifier/grades_detail.json` | Per-criterion grades with LLM justifications |
| `exception.txt` | Present only if the trial errored |

## Per-task customization

Most tasks share the `_template/` boilerplate by design. If a specific task
needs different timeouts, env vars, or a different judge model, edit its
`task.toml` directly.
