<p align="center">
  <img src="assets/scale-logo.png" alt="Scale" height="44">
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="assets/phylo-logo.png" alt="Phylo" height="44">
</p>

<p align="center">
  <h1 align="center">Drug Discovery Agent Benchmark</h1>
</p>

A benchmark for evaluating AI agents on real drug-discovery and life-sciences
workflows. It contains **82 [Harbor](https://github.com/harbor-framework/harbor)-formatted
eval tasks**, each a self-contained biomedical research problem, graded by an LLM
judge against expert-authored rubrics. Tasks run inside a pre-built Docker image
that ships a complete biomedical toolchain, so an agent can pull data, run analyses,
and compute answers entirely within the trial container.

## Requirements

**OS:** macOS or Linux (Docker on Windows works but is less tested).

Software you install on the **host**:

| Software | Version | Why / install |
|----------|---------|---------------|
| Docker (Desktop or Engine) | **24+**, with the **Compose v2** plugin | Runs every trial; Harbor's docker executor uses `docker compose`. Must be **running** before you start. [Docker Desktop](https://docs.docker.com/get-started/get-docker/) / [Engine](https://docs.docker.com/engine/install/). Tested with Docker 29.x. |
| Python (host) | **3.10–3.13** | Host interpreter for the Harbor CLI. (LiteLLM, a Harbor dependency, caps at `<3.14`.) `python3 --version`. |
| Harbor | **`0.13.1`** | The eval runner — `pip install harbor==0.13.1` (or `uv tool install harbor@0.13.1`). Pinned for reproducibility. |
| Trial image | `ghcr.io/scaleapi/drugdiscoverybench:1.0.0-lightweight` | Pulled in [step 1](#1-pull-the-docker-image-6-gb-1030-min). |

**Host resources:** the image is **~6 GB compressed to pull but ~23 GB on disk** (**30+ GB free recommended**); each task can use up to **8 GB RAM** (**16 GB total recommended**).

**Time:** first-time setup ~30–60 min (the ~6 GB pull dominates); a single task run takes up to ~45 min (agent timeout 45 min, judge 10 min).

You do **not** install the biomedical toolchain or agent CLIs — they're baked into the `1.0.0-lightweight` image at pinned versions: conda env (Python 3.11) + R + the BiOMNI tool suite, Node 22, `@anthropic-ai/claude-code` 2.1.190, `@openai/codex` 0.122.0, `@google/gemini-cli` 0.46.0 (see [What's in the image](#whats-in-the-image)).

## Quick Start

### 1. Pull the Docker image (~6 GB, 10–30 min)

```bash
# Public image — no login required.
docker pull ghcr.io/scaleapi/drugdiscoverybench:1.0.0-lightweight
```

### 2. Clone this repo and install Harbor

```bash
git clone https://github.com/scaleapi/DrugDiscoveryBench.git
cd DrugDiscoveryBench

# Install the Harbor CLI (https://github.com/harbor-framework/harbor). Pin the version
# so a future release can't change behavior under you.
pip install harbor==0.13.1
# or: uv tool install harbor@0.13.1
```

### 3. Get the rubrics

The scoring rubrics and reference answers are **not** stored in this repo — so the
benchmark can be public without leaking answers into training data, they are
released through a gated HuggingFace dataset. Each task's `tests/rubrics.json`
ships with empty `ground_truth` / `outcome_rubrics` / `process_rubrics`; a helper
script fills them in.

```bash
# 1. Request access (one click) and wait for the auto-approval e-mail:
#    https://huggingface.co/datasets/ScaleAI/DrugDiscoveryBench
# 2. Authenticate (cached login, or set HF_TOKEN):
pip install huggingface_hub
huggingface-cli login

# 3. Populate every task's rubrics.json in place:
python scripts/populate_rubrics.py
# (add --dry-run to preview without writing)
```

Without this step the judge has no rubrics to grade against and every trial scores 0.

### 4. Set credentials and run

Two LLM roles need credentials:

| Role | What it does | Passed via |
|------|-------------|------------|
| **Agent** | The model being evaluated (runs inside the trial container) | agent env vars (below) |
| **Judge** | Grades the agent's answer against rubrics | `JUDGE_*` env vars |

```bash
# --- Agent credentials (default agent is claude-code) ---
export ANTHROPIC_API_KEY="your-key"

# Web search: agents' native web tools are disabled by default (they bypass the
# egress denylist), so web search is funneled through Biomni's search_web, which
# needs a Brave key. Without it, agents have no web search.
export BRAVE_SEARCH_API_KEY="your-brave-key"   # api.search.brave.com

# --- Judge credentials (any OpenAI-API-compatible endpoint) ---
export JUDGE_BASE_URL="https://api.openai.com/v1"
export JUDGE_API_KEY="your-key"
export JUDGE_MODEL="gpt-4o"     # any model your JUDGE_BASE_URL serves

# Run a single task
scripts/run_eval.sh 69b025e20c10fe76b7aaf812

# Run with a specific model and agent
scripts/run_eval.sh 69b025e20c10fe76b7aaf812 --model claude-sonnet-4-6 --agent claude-code

# Run with Codex
export OPENAI_API_KEY="your-key"
scripts/run_eval.sh 69b025e20c10fe76b7aaf812 --model gpt-5.5 --agent codex

# Run all tasks, 5 trials each, 10 concurrent
scripts/run_eval.sh all -k 5 -n 10
```

> **One proxy, one key:** if you route LLM traffic through a single proxy, set
> `LLM_API_KEY` and `LLM_BASE_URL` and the per-role **API keys and base URLs** above
> are derived automatically (any one you set explicitly still wins). You still set
> `JUDGE_MODEL`, pick the agent model with `--model`, and — if you want web search —
> `BRAVE_SEARCH_API_KEY` (a separate Brave service, not the LLM proxy). See
> [Running against any model / proxy](#running-against-any-model--proxy).

### 5. Where are my results?

Each run writes to `jobs/<timestamp>/<task_id>/`:

```
jobs/<timestamp>/<task_id>/verifier/reward.json          ← your score (0–100)
jobs/<timestamp>/<task_id>/verifier/grades_detail.json   ← per-criterion breakdown
jobs/<timestamp>/<task_id>/agent/                         ← full agent transcript
```

## Agent credentials by harness

By default each agent calls its own provider's API and only accepts that
provider's model names — `claude-code` → Anthropic, `codex` → OpenAI,
`gemini-cli` → Gemini. To mix and match (e.g. run `claude-code` on a non-Anthropic
model), front everything with a proxy — see the [next section](#running-against-any-model--proxy).

| Agent (`--agent`) | Credential env var | Optional base-URL override |
|---|---|---|
| `claude-code` | `ANTHROPIC_API_KEY` | `ANTHROPIC_BASE_URL` |
| `codex` | `OPENAI_API_KEY` | `OPENAI_BASE_URL` (`/v1`) |
| `gemini-cli` | `GEMINI_API_KEY` | `GOOGLE_GEMINI_BASE_URL` |

For **gemini-cli**, the key and base URL must match: with no `GOOGLE_GEMINI_BASE_URL`,
`GEMINI_API_KEY` is a Google AI Studio key (`AIza…`) and calls go direct to Google;
if you set a gateway base URL, `GEMINI_API_KEY` must be **that gateway's key**.
`run_eval.sh` defaults the base URL to a LiteLLM proxy **root** (not the `/gemini`
passthrough) so `vertex_ai/…` models route to Vertex and `google_web_search`
grounding uses Vertex quota instead of the Gemini Developer API's 1,500/day cap.
Use a `vertex_ai/global/gemini-3.x` model for that path. Details: [docs/model-proxy.md](docs/model-proxy.md#gemini-cli).

## Running against any model / proxy

The agent and judge can both point at an LLM **proxy** (e.g. an
[OpenAI-compatible](https://docs.litellm.ai/) gateway like LiteLLM) instead of
the provider APIs directly. A proxy lets you use **one key for everything**, route
any agent CLI at any backend model, and centralize quota/logging.

```bash
# One key + one endpoint for the agent and the judge:
export LLM_API_KEY="your-proxy-key"
export LLM_BASE_URL="https://your-proxy.example.com"
# run_eval.sh derives ANTHROPIC_/OPENAI_/GEMINI_/JUDGE_ base URLs + keys from these
# (OpenAI and the judge get a /v1 suffix; Anthropic and Gemini use the root).
# Any per-role var you set explicitly still wins.

# Still set explicitly (not derived from the key):
export JUDGE_MODEL="gpt-4o"                       # any alias your proxy serves
export BRAVE_SEARCH_API_KEY="your-brave-key"      # optional — only if you want web search

# --model is the alias your proxy resolves; the default agent is claude-code.
scripts/run_eval.sh 69b025e20c10fe76b7aaf812 --model your-model-alias --agent claude-code
```

**What controls the agent** (the model that actually executes the trajectory and
solves the task — distinct from the judge):

- **`--agent`** — which CLI *harness* runs the trajectory: `claude-code` (default),
  `codex`, or `gemini-cli`.
- **`--model`** — the model that harness drives, i.e. the alias your proxy resolves.
  **This is the problem-solving model.** It's passed straight to the agent CLI inside
  the trial container (`harbor run -m`).
- **`LLM_BASE_URL` + `LLM_API_KEY`** become *that agent's* endpoint and key — for
  `claude-code`, `ANTHROPIC_BASE_URL` → your proxy root and `ANTHROPIC_API_KEY` → your
  key (injected into the container). So the agent's own LLM calls go through your proxy,
  and `--model` can resolve to **any** backend the proxy fronts (including non-Anthropic).

This includes the advanced case of driving **Claude Code against a non-Anthropic
model** (Gemini, GPT, …) through a proxy's Anthropic-format endpoint. See
**[docs/model-proxy.md](docs/model-proxy.md)** for a portable LiteLLM `config.yaml`,
per-CLI specifics, the Codex Responses-API requirement, and the caveats.

<details>
<summary><b>Using Harbor CLI directly</b></summary>

The wrapper script is a convenience layer over `harbor run`. Call Harbor directly for full control:

```bash
harbor run \
    -p benchmark/tasks/69b025e20c10fe76b7aaf812 \
    -m claude-sonnet-4-6 -a claude-code \
    -e docker \
    --ae "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY" \
    --environment-build-timeout-multiplier 3.0 \
    -k 1 -n 1 --yes
```

Key flags:
- `-p` — path to a task directory (repeat for multiple tasks)
- `-m` — model name, `-a` — agent (`claude-code`, `codex`, `gemini-cli`)
- `-e` — Harbor executor (`docker` for local; other backends need `HARBOR_EXEC_KWARGS`)
- `--ae` — pass env vars into the agent container
- `-k` — trials per task, `-n` — max concurrent trials
- `--environment-build-timeout-multiplier 3.0` — triples Harbor's image-build/pull
  timeout; the ~6 GB image can exceed the default on a slow connection or under
  emulation (e.g. Apple Silicon running an amd64 image).

> If you call Harbor directly (not via `run_eval.sh`), remember the judge reads
> `JUDGE_BASE_URL` / `JUDGE_API_KEY` / `JUDGE_MODEL` from the environment.

</details>

## How eval tasks work

Each task is a self-contained Harbor trial. The agent CLI runs inside the image
and invokes the bundled biomedical tools directly from Python/Bash (every tool is
importable as `biomni.tool.<domain>.<name>`); `/workspace` is the shared working
directory and the data lake is mounted read-only when available. When the agent is
done it writes its final answer to `/workspace/answer.md`, and the judge grades that
answer against the task's `rubrics.json`. No network hop to a remote tool API — the
agent and the full tool surface live in the same container.

## What's in the image

The `drugdiscoverybench:1.0.0-lightweight` Docker image (**~6 GB compressed to pull,
~23 GB on disk**) is a self-contained trial environment built on
[BiOMNI](https://github.com/snap-stanford/Biomni), with our own fixes and improvements
on top (dependency/tool repairs, agent-CLI co-location, egress hardening, and more):

| Component | Details |
|-----------|---------|
| BiOMNI source | Full Python package with the BiOMNI tool suite across 17 domains |
| Conda env | `biomni_e1` with Python 3.11, R, bioinformatics CLI tools |
| Agent CLIs | Node 22 — `@anthropic-ai/claude-code`, `@openai/codex`, `@google/gemini-cli` (plus a Grok binary, see [Appendix: Grok CLI](#appendix-grok-cli)) |
| Data lake | `1.0.0-lightweight` (default) bakes the **eval data-lake files** (read-only at `/workspace/data/biomni_data/data_lake/`); `query_*` DB clients still hit live APIs. `core`/`full` add local `query_*` databases (see [Data lake](#data-lake)) |

## Repository Layout

```
benchmark/
├── _template/                  Shared boilerplate (task.toml, Dockerfile, judge, test runner)
├── tasks/                      82 eval tasks, one directory per task ID
│   └── <24-char-hex>/
│       ├── environment/Dockerfile
│       ├── instruction.md      Task prompt
│       ├── task.toml           Harbor config (image, env vars, timeouts)
│       └── tests/
│           ├── judge.py        LLM-based rubric judge
│           ├── rubrics.json    Scoring rubrics (empty until populated from the gated HF dataset)
│           └── test.sh         Verifier entry point
└── README.md

scripts/
├── run_eval.sh                 Wrapper script for running tasks via Harbor
└── populate_rubrics.py         Fills rubrics.json from the gated HF dataset (see Quick Start step 3)

docs/
├── model-proxy.md              Running any agent/model through a proxy
└── egress-hardening.md         Egress denylist + web-search funnel
```

## Trial outputs

Each trial writes to `jobs/<timestamp>/<task_id>/`:

| File | Contents |
|------|----------|
| `agent/` | Full agent transcript, trajectory, session logs |
| `verifier/reward.json` | Numeric scores (Harbor reads this for aggregation) |
| `verifier/grades_detail.json` | Per-criterion grades with LLM justifications |
| `exception.txt` | Present only if the trial errored |

## Data lake

Biomni tools can read from a local "data lake" — copies of major biomedical
databases baked into the image — for fast, deterministic, **offline** lookups.
The image comes in three tiers that trade size for offline coverage:

| Tier (tag) | Baked data | Pull / on-disk | Offline DB coverage |
|------------|-----------|----------------|---------------------|
| **`1.0.0-lightweight`** (default) | The Biomni **data-lake files used by the eval** (read-only at `/workspace/data/biomni_data/data_lake/`) — curated flat-file datasets (BindingDB, GTEx, DepMap, GWAS Catalog, MSigDB, …). Heavy `query_*` DB clients (PubChem, ChEMBL, UniProt, …) still hit **live APIs**. | ~6 GB / ~23 GB | data-lake files (`query_*` live) |
| **`1.0.0-core`** | ~21 local databases — cBioPortal, UniProt, ChEMBL, ENCODE, Ensembl, ClinicalTrials (AACT), STRING, openFDA, Reactome, GEO, GWAS, PDB, … (`BIOMNI_LOCAL_DB_ONLY=1`) | 37 GB / 211 GB | ~74% |
| **`1.0.0-full`** | `core` + PubChem, PubMed, AlphaFold, Open Targets | 136 GB / 570 GB | ~99.7% |

> **All 82 tasks pin `1.0.0-lightweight`.** It bakes the data-lake files the eval
> uses, so those file reads are offline and reproducible (matching how the benchmark
> was run). The heavy `query_*` database clients (PubChem, ChEMBL, UniProt, …) still
> hit live public APIs on `lightweight`; the `core` and `full` tiers bake those
> databases in too, serving roughly **~74%** and **~99.7%** of `query_*` calls
> offline.

**Switching tiers.** Tasks ship pinned to `lightweight`. To run the whole suite
against another tier, rewrite every task's `docker_image` + Dockerfile `FROM` with:

```bash
python scripts/set_image_tier.py core         # or: full
python scripts/set_image_tier.py lightweight  # switch back (default)
```

(Idempotent; `--dry-run` to preview.)

<details>
<summary><b>Per-database tier membership</b> (which tools answer offline in each tier)</summary>

Each baked database replaces the live API/DB the corresponding tool would otherwise call.

**`core` — 21 databases (~74% of eval DB-query calls):**

| Tool(s) | Database / API replaced |
|---|---|
| `query_pdb`, `query_pdb_identifiers` | RCSB PDB (structure metadata) |
| `query_chembl` | ChEMBL (bioactivity / drug-target) |
| `query_uniprot` | UniProt (Sprot+TrEMBL) |
| `query_cbioportal` | cBioPortal (cancer mutations / clinical / CNA) |
| `query_clinicaltrials` | ClinicalTrials.gov (CTTI AACT) |
| `query_stringdb` | STRING (PPI, human v12) |
| `query_clinvar` | ClinVar |
| `query_arxiv` | arXiv |
| `query_encode` | ENCODE |
| `search_nakb`, `get_nakb_structure` | NAKB (nucleic-acid structures) |
| `query_geo` | NCBI GEO |
| `query_ensembl`, `get_gene_coding_sequence` | Ensembl GRCh38 |
| `query_openfda` | openFDA (drug labels) |
| `query_gwas_catalog` | NHGRI-EBI GWAS Catalog |
| `query_reactome`, `query_pathway_db` | Reactome |
| `query_pathway_db` | WikiPathways |
| `query_monarch` | Monarch (disease-gene-phenotype) |
| `query_quickgo` | QuickGO / Gene Ontology |
| `query_gtopdb` | Guide to Pharmacology |
| `query_synapse` | Synapse (public catalog metadata) |
| `query_jaspar`, `identify_transcription_factor_binding_sites` | JASPAR (TF motifs) |

**`full` — core's 21 + these 4 "giants" (~99.7%):**

| Tool | Database / API |
|---|---|
| `query_pubchem` | PubChem (compounds) |
| `query_pubmed` | PubMed (literature) |
| `query_opentarget` | Open Targets (target-disease) |
| `query_alphafold` | AlphaFold DB (Swiss-Prot predicted structures) |

</details>

> **Note on the egress healthcheck:** every task's healthcheck expects
> `http://scale.com` to return `403`, which is served by a proxy baked into the
> published `ghcr.io/scaleapi/drugdiscoverybench` image. If you build your own image
> without that proxy, the healthcheck fails before the agent runs. See
> [docs/egress-hardening.md](docs/egress-hardening.md).

## Appendix: Grok CLI

The official [xAI Grok CLI](https://x.ai/cli) (npm `@xai-official/grok`, binary
`grok`) is baked into the image as of `2.10.3`. **It is not yet a Harbor agent** —
the installed Harbor has no `grok` adapter, so `--agent grok` does not work. Today
grok is only a runnable binary inside the container (manual / non-Harbor use):

```bash
docker run --rm -it -e GROK_API_KEY=your-key \
    ghcr.io/scaleapi/drugdiscoverybench:1.0.0-lightweight grok --help
```

It reads `GROK_API_KEY` and `GROK_BASE_URL` (default `https://api.x.ai/v1`; an
OpenAI-compatible proxy works). To drive Grok through the eval harness, a Harbor
`grok` adapter must land upstream first.

## License

The benchmark code, task definitions, and docs in this repository are released under
the [MIT License](LICENSE). Scoring rubrics and reference answers are **not** in this
repo — they are distributed via the gated HuggingFace dataset
[`ScaleAI/DrugDiscoveryBench`](https://huggingface.co/datasets/ScaleAI/DrugDiscoveryBench)
(see Quick Start). The Docker image bundles third-party software and data — notably
[BiOMNI](https://github.com/snap-stanford/Biomni) (Apache-2.0) and the baked
biomedical datasets — under their own licenses (see the image's `NOTICE`).
