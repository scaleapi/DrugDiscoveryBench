# Running any agent / model through a proxy

By default each agent CLI is coupled to one provider: `claude-code` speaks the
Anthropic Messages API, `codex` speaks the OpenAI Responses API, and `gemini-cli`
speaks the Gemini `generateContent` API. That coupling is to the **wire format**,
not the backend model — so an LLM **proxy** that speaks those formats and re-routes
to any backend dissolves it. You can then:

- use **one API key and one endpoint** for the agent, web search, and the judge;
- run **any agent CLI against any backend model** (e.g. `claude-code` driving a
  Gemini or GPT model);
- centralize quota, logging, and cost controls.

This guide uses [**LiteLLM**](https://docs.litellm.ai/) as the proxy because it is
open-source, portable, and exposes all three wire formats from one process. None of
this requires Scale's internal proxy — an external researcher can run it with the
OSS proxy plus their own provider keys.

> **Model names in examples are illustrative.** Substitute current, real model IDs.

---

## 1. The single-key shortcut (recommended)

`scripts/run_eval.sh` understands two convenience vars. Set them and it derives the
per-role agent/judge credentials automatically:

```bash
export LLM_API_KEY="sk-your-proxy-key"          # one (e.g. LiteLLM virtual) key
export LLM_BASE_URL="https://your-proxy.example.com"   # proxy root

scripts/run_eval.sh 69b025e20c10fe76b7aaf812 --model your-model-alias --agent claude-code
```

Derivation (only fills vars you haven't set; explicit per-role vars always win):

| Derived var | Value | Why |
|---|---|---|
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `JUDGE_API_KEY` | `$LLM_API_KEY` | one key everywhere |
| `ANTHROPIC_BASE_URL` | `$LLM_BASE_URL` (root) | LiteLLM serves `/v1/messages` at the root |
| `GOOGLE_GEMINI_BASE_URL` | `$LLM_BASE_URL` (root) | root → `vertex_ai/` routing (see [Gemini](#gemini-cli)) |
| `OPENAI_BASE_URL` | `$LLM_BASE_URL/v1` | OpenAI clients append `/v1/...` |
| `JUDGE_BASE_URL` | `$LLM_BASE_URL/v1` | judge speaks OpenAI-compatible `/v1` |

---

## 2. A portable LiteLLM `config.yaml`

Front any number of providers behind one proxy. Each `model_name` is an alias your
clients send; `litellm_params.model` is the real backend.

```yaml
model_list:
  - model_name: gpt-5.5
    litellm_params:
      model: openai/gpt-5.5
      api_key: os.environ/OPENAI_API_KEY
  - model_name: claude-sonnet-4-6
    litellm_params:
      model: anthropic/claude-sonnet-4-6
      api_key: os.environ/ANTHROPIC_API_KEY
  - model_name: gemini-3.5-flash
    litellm_params:
      model: gemini/gemini-3.5-flash
      api_key: os.environ/GEMINI_API_KEY

# Optional: a judge alias mapped to whatever you want grading to use
  - model_name: judge
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY
```

Run it:

```bash
pip install 'litellm[proxy]'
litellm --config config.yaml          # listens on http://0.0.0.0:4000
```

Then:

```bash
export LLM_API_KEY="$LITELLM_MASTER_KEY"   # or a virtual key (see §6)
export LLM_BASE_URL="http://localhost:4000"
export JUDGE_MODEL="judge"
scripts/run_eval.sh 69b025e20c10fe76b7aaf812 --model claude-sonnet-4-6 --agent claude-code
```

LiteLLM exposes, from that one endpoint:
- `/v1/messages` — Anthropic format (for `claude-code`)
- `/v1/responses` and `/v1/chat/completions` — OpenAI format (for `codex` and the judge)
- Gemini-format ingress (for `gemini-cli`)

Each ingress is a **format adapter**: a request arriving in one format is translated
and dispatched to whatever backend the model alias resolves to, regardless of the
backend's native provider.

---

## 3. Per-CLI specifics

### claude-code

`ANTHROPIC_BASE_URL` → proxy root; requests hit LiteLLM's **translating**
`/v1/messages` endpoint, so the model alias can resolve to a non-Anthropic backend.

```bash
export ANTHROPIC_BASE_URL="http://localhost:4000"
export ANTHROPIC_API_KEY="$LLM_API_KEY"      # or ANTHROPIC_AUTH_TOKEN for Bearer
scripts/run_eval.sh <task> --model openai/gpt-4o --agent claude-code   # Claude Code → GPT
```

**Verified:** `claude --model openai/gpt-5.4` through a LiteLLM proxy returns a
correct Anthropic-format response (and `POST /v1/messages/count_tokens` works for
the non-Anthropic model). So Claude Code genuinely drives a non-Anthropic backend.

**Caveats when the backend is non-Anthropic** (this is community-supported, not
officially supported by Anthropic — which only blesses Bedrock/Vertex/Foundry):
- **Anthropic-only request params:** Claude Code sends params like `context_management`
  (and `cache_control`) that some backends reject. Verified: a **Vertex/Gemini**
  backend 400s with `litellm.UnsupportedParamsError: vertex_ai does not support
  parameters: ['context_management']`. Fix on the proxy side with
  `litellm_settings: { drop_params: true }` (strips unsupported params). OpenAI
  backends did not hit this. So **Claude Code → GPT works out of the box; Claude
  Code → Gemini needs the proxy configured with `drop_params: true`.**
- **Prompt caching:** `cache_control` blocks may be dropped by the proxy → higher cost/latency.
- **Token counting:** Claude Code calls `POST /v1/count_tokens`; the proxy must implement it or counting fails.
- **Tool use:** depends on the proxy correctly translating Claude's tool-call format.
- Use the **`/v1/messages`** translating endpoint, **not** the native `/anthropic/...`
  passthrough (the passthrough does not translate to other providers).

### codex

Codex uses the **OpenAI Responses API** (`/v1/responses`), not Chat Completions. Any
endpoint you point it at must serve Responses. LiteLLM does, and **auto-bridges** to
backends that lack a native Responses API (e.g. Anthropic), so a Codex request can
still target a non-OpenAI model through an alias.

```bash
export OPENAI_BASE_URL="http://localhost:4000/v1"
export OPENAI_API_KEY="$LLM_API_KEY"
scripts/run_eval.sh <task> --model gpt-5.5 --agent codex
```

**Verified** (codex `0.122.0` in the image, against a LiteLLM proxy): the agent
routes through the proxy and returns correct output. Two things to know:
- **Codex `0.122` honors the base URL only from `config.toml`, not the env var.**
  Harbor's Codex adapter handles this — it writes `openai_base_url = "$OPENAI_BASE_URL"`
  into `$CODEX_HOME/config.toml`. (If you invoke `codex` yourself with only
  `OPENAI_BASE_URL` set, it ignores it and hits `wss://api.openai.com/v1/responses`.)
- **Codex tries a WebSocket Responses transport first** (`wss://<proxy>/v1/responses`).
  LiteLLM doesn't serve that, so it returns `503` and codex retries ~5× (~30 s) before
  **falling back to HTTP `/v1/responses`**, which works. So runs succeed but start with
  ~30 s of WSS-retry log noise against a LiteLLM proxy.

> Newer Codex versions (0.134+) hardcode the WSS endpoint and ignore the `config.toml`
> base URL entirely — which is why the image pins `0.122.0`.

### gemini-cli

`gemini-cli` reaches a proxy via `GOOGLE_GEMINI_BASE_URL`. Point it at the proxy
**root** (not the `/gemini` passthrough): the root path lets `vertex_ai/…` models
route to Vertex, which keeps `google_web_search` grounding on Vertex quota instead
of the Gemini Developer API's hard 1,500 searches/day cap.

```bash
export GOOGLE_GEMINI_BASE_URL="http://localhost:4000"
export GEMINI_API_KEY="$LLM_API_KEY"          # the proxy's key, not a Google AIza… key
scripts/run_eval.sh <task> --model vertex_ai/global/gemini-3.5-flash --agent gemini-cli
```

**Verified** (gemini-cli `0.46.0` in the image, against a LiteLLM proxy): the agent
routes through the proxy and returns correct output. Because the key is the proxy's
`sk-…` key (not a Google `AIza…` key), a direct-to-Google call would 401 — so a valid
response is itself proof the request went through the proxy.

To make the name `gemini-cli` sends resolve to a **non-Gemini** backend, alias it in
`router_settings`:

```yaml
router_settings:
  model_group_alias: {"gemini-2.5-pro": "claude-sonnet-4-6"}
```

The image's baked `/etc/gemini-cli/settings.json` pins api-key auth (required once a
base URL is set, or gemini-cli ≥ ~0.47 crashes with "Invalid auth method selected")
and disables gemini's native web tools. `run_eval.sh` loads it via
`GEMINI_CLI_SYSTEM_SETTINGS_PATH`. Because that auth and the `tools.exclude` are
coupled in the system settings, `--native-web` has **no effect** for gemini-cli.

---

## 4. The judge

The judge is independent of the agent. It calls any **OpenAI-API-compatible**
endpoint — the model can be from any provider as long as the endpoint speaks the
OpenAI format:

```bash
export JUDGE_BASE_URL="http://localhost:4000/v1"   # or api.openai.com/v1, or any gateway
export JUDGE_API_KEY="$LLM_API_KEY"
export JUDGE_MODEL="judge"                          # any model your endpoint serves
```

Each `task.toml` reads these from the environment (`JUDGE_MODEL` defaults to `gpt-4o`
if unset). Nothing about the judge is provider-specific.

---

## 5. Provider coupling — summary

| CLI | Decouple from its provider? | How | Hard requirement |
|---|---|---|---|
| `claude-code` | ✅ (community-supported) | `ANTHROPIC_BASE_URL` → proxy `/v1/messages` | proxy must translate tools + implement `/v1/count_tokens` for full functionality |
| `codex` | ✅ | `OPENAI_BASE_URL` → proxy `/v1` | endpoint must serve the **Responses API** |
| `gemini-cli` | ✅ (via alias) | `GOOGLE_GEMINI_BASE_URL` + `model_group_alias` | api-key auth pinned in system settings (already baked in the image) |

The decoupler in every case is the proxy's **alias table**: the CLI sends a model
string in its own namespace; the proxy maps it to any backend.

> **`--model` and Harbor's prefix-stripping.** Harbor's `codex` and `gemini-cli`
> adapters pass only the **last `/`-segment** of `--model` to the CLI (e.g.
> `openai/gpt-5.1-codex` → `gpt-5.1-codex`, `vertex_ai/global/gemini-3.5-flash` →
> `gemini-3.5-flash`). So the **bare** name must be one your proxy serves — and since
> the provider prefix is dropped before the CLI sees it, vertex-vs-developer routing
> for gemini is decided by how your proxy maps that bare name, not by the prefix you
> pass. (`claude-code` keeps the full `--model` string.) Confirm your proxy resolves
> the bare names, or add `model_group_alias` entries for them.

---

## 6. One key, scoped (optional, virtual keys)

The master key works for a quick benchmark. For a scoped, shareable key, generate a
LiteLLM **virtual key** limited to specific models:

```bash
curl 'http://localhost:4000/key/generate' \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"models": ["gpt-5.5", "claude-sonnet-4-6", "gemini-3.5-flash", "judge"]}'
```

A virtual key is a bearer token usable across every ingress format and every model
it's allowed to call — so a single key can drive the agent, web search, and the
judge. (Virtual keys require a Postgres DB + master key; without that, use the master
key directly.)

---

## References

- LiteLLM proxy config & `model_list`: https://docs.litellm.ai/docs/proxy/configs
- Anthropic `/v1/messages` (unified): https://docs.litellm.ai/docs/anthropic_unified/
- Claude Code with non-Anthropic models: https://docs.litellm.ai/docs/tutorials/claude_non_anthropic_models
- Claude Code LLM gateway (official): https://code.claude.com/docs/en/llm-gateway
- OpenAI Responses API via LiteLLM: https://docs.litellm.ai/docs/response_api
- Gemini CLI via LiteLLM: https://docs.litellm.ai/docs/tutorials/litellm_gemini_cli
- LiteLLM virtual keys: https://docs.litellm.ai/docs/proxy/virtual_keys
