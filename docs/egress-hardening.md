# Egress hardening — denylist enforcement + web-search funnel

Scale publishes blog/papers on `labs.scale.com` / `static.scale.com` whose content
overlaps some tasks' source data. An agent that reads it can shortcut the task,
invalidating the measurement. This doc describes the two-layer prevention shipped
here (the integrity *guarantee* is still the judge/trace analysis — these layers
are defense-in-depth, not an airtight boundary).

## Channels an agent can reach Scale content

| Channel | Where the fetch happens | Caught by the egress proxy? |
|---|---|---|
| **V1 direct fetch** — shell `curl`/`requests`, `web_fetch` client fallback | in the container | **Yes**, if the client honors `HTTP_PROXY` |
| **V2 server-side grounding** — gemini `google_web_search`, claude `WebSearch`, codex web | on the vendor's servers | **No** — content returns inside the model API response |
| **V3 search-API snippets** — Brave via Biomni `search_web` | the search provider fetches | Partly — the page fetch is server-side |

## Layer 1 — egress denylist proxy (V1)

A CONNECT-aware proxy baked into the biomni image refuses a denylist of Scale hosts
(exact-host) and tunnels the rest. The denylist **ships inside the image** and is
enforced at container **boot**, so tasks need no per-task egress configuration. The
default list includes the content subdomains `labs.scale.com` / `static.scale.com`
(the `scale.com` apex alone does NOT cover the blog under exact-host match).

So per task, `scripts/apply_egress_block.sh` stamps only:

1. `[environment.healthcheck]` — fails the trial unless `http://scale.com` → 403
   before the agent runs.

A single task may set `EGRESS_DENY_HOSTS` in `[environment.env]` to *extend* the
blocked list at run time; absent that, the image default applies.

**Limits:** the proxy is app-level (a client using `--noproxy`/raw sockets bypasses
it) and is blind to V2. It's a speed-bump + signal, not a boundary.

## Layer 2 — web-search funnel (V2/V3), wired in `run_eval.sh`

V2 server-side grounding returns inside the model API response over the LLM
endpoint, so no network policy can see it. The lever is the **tool layer**: disable
the agents' native web tools and funnel all search through Biomni's `search_web`
(Brave), which is Scale-content-filtered in the image so it can't surface Scale
hosts. `run_eval.sh` does this by default (use `--native-web` to opt out):

| Agent | Native web tool(s) | Disabled via |
|---|---|---|
| claude-code | `WebSearch`, `WebFetch` | `--ak disallowed_tools="WebSearch WebFetch"` → `--disallowedTools` |
| gemini-cli | `google_web_search`, `web_fetch`, `web_search` | `tools.exclude` in the image's `/etc/gemini-cli/settings.json` (loaded via `GEMINI_CLI_SYSTEM_SETTINGS_PATH`) |
| codex | `web_search` | off by default in `config.toml` |

`BRAVE_SEARCH_API_KEY` is injected into trials so `search_web` works (without it the
funnel has no search path). The `search_web` Scale filter and the gemini system
settings file are provided by the biomni image.

### Why the gemini system-settings file

gemini-cli >=0.47 resolves auth to `gateway` when `GOOGLE_GEMINI_BASE_URL` is set and
rejects it ("Invalid auth method selected") unless
`settings.security.auth.selectedType == gemini-api-key`. Harbor's gemini-cli adapter
overwrites the *user* `~/.gemini/settings.json` on install, so both that auth setting
and `tools.exclude` are baked into the **system** settings file (highest merge
precedence, untouched by the adapter) and loaded via `GEMINI_CLI_SYSTEM_SETTINGS_PATH`.
