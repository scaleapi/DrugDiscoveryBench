# Co-located Harbor trial container.
#
# Pulls the biomni image (which already has node + claude-code + codex +
# biomni source + the full conda env). No per-task layering — the trial
# container *is* biomni. No MCP: the agent invokes biomni directly via Bash
# (`python -c "from biomni.tool.<domain> import ..."`); `/workspace` is the
# shared working directory.
FROM ghcr.io/scaleapi/drugdiscoverybench:1.0.0-lightweight
WORKDIR /workspace
