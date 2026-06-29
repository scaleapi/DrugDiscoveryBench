#!/usr/bin/env python3
"""Standalone rubric judge for Harbor trials.

Reads an agent-produced answer file (terse final answer) plus optional
trajectory, grades against bundled outcome + process rubrics via an OpenAI-
compatible LLM (LiteLLM proxy), and writes ``reward.json`` for Harbor.

Designed to live inside a trial container with no Biomni deps. Only needs
the ``openai`` Python package and a LiteLLM key.

Error handling:
  * Each LLM call retries up to ``JUDGE_MAX_RETRIES`` times (default 3) with
    exponential backoff on transient errors (network blips, 429s, 5xx, and
    judge responses that fail to parse as JSON).
  * Outcome and process grading are independent. A failure in one DOES NOT
    block the other; whichever succeeds is written to ``reward.json``. A
    ``judge_skipped_<kind>`` numeric flag plus a textual reason in the
    sidecar ``grades_detail.json`` records what fell through.
  * If both kinds fail, ``reward.json`` still gets written with ``score=0.0``
    and ``judge_failed=1`` so Harbor sees *something* instead of treating
    the verifier as missing.
"""

import argparse
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path


def _read_text(path: str | None) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.is_file():
        return ""
    return p.read_text(errors="replace").strip()


def _parse_weight(w: str) -> int:
    m = re.search(r"([+-]\d+)", w or "")
    return int(m.group(1)) if m else 0


def _build_judge_prompt(kind: str, prompt: str, reference: str, agent_output: str, rubrics: list[dict]) -> str:
    kind_label = "outcome (final answer)" if kind == "outcome" else "process (methodology and execution)"
    ref_label = "Ground Truth" if kind == "outcome" else "Expert Reference Trace"
    agent_label = "Final Answer" if kind == "outcome" else "Trajectory"
    criteria_lines = []
    for i, r in enumerate(rubrics):
        criteria_lines.append(f"{i + 1}. [{r['weight']}] {r['title']}")
        if r.get("justification"):
            criteria_lines.append(f"   Justification: {r['justification']}")
    criteria_text = "\n".join(criteria_lines)

    return f"""You are evaluating an AI agent's {kind_label} on a biomedical task.

## Task Prompt
{prompt}

## {ref_label}
{reference}

## Agent's {agent_label}
{agent_output}

## Rubric Criteria
{criteria_text}

## Grading Instructions
- Focus on the substance and correctness of the agent's work, not surface formatting.
- Ignore minor differences in whitespace, capitalization, punctuation, or spacing unless a criterion explicitly requires a specific format.
- A criterion about factual correctness should be graded "met" if the correct information is present, regardless of how it is formatted.
- NUMERIC TOLERANCE: when a criterion specifies a numeric value, grade it "met" if the agent's value agrees within reasonable rounding / measurement error — e.g. a difference only at or beyond the last reported significant figure (such as 669.3189 vs 669.3190), or within ~0.1% relative. Do NOT mark a numerically-correct answer "not met" over last-digit rounding or floating-point precision. (This tolerance does NOT apply to exact identifiers, accession IDs, integer counts, or categorical values — those must match exactly.)
- Only grade "not met" when the agent's output is materially wrong or missing relative to what the criterion asks for.
- IMPORTANT: Grade each criterion LITERALLY — "met" means the described condition IS TRUE / IS PRESENT in the agent's output, "not met" means it IS NOT TRUE / IS NOT PRESENT. Do NOT consider whether the condition is good or bad. The weight is not your concern.

For each criterion, first reason about whether the condition is met, then give your grade. Respond with a JSON array (no other text):
[
  {{"criterion": 1, "justification": "brief reasoning about whether the condition is met", "grade": "met" or "not met"}},
  ...
]"""


_MAX_RETRIES = int(os.environ.get("JUDGE_MAX_RETRIES", "3"))
_RETRY_BASE_SEC = float(os.environ.get("JUDGE_RETRY_BASE_SEC", "2.0"))

# When agent_output exceeds _CHUNK_THRESHOLD_CHARS, the judge grades it in
# overlapping-free chunks of ~_CHUNK_TARGET_CHARS each and OR-aggregates the
# per-criterion grades. Defaults are sized for claude-sonnet-4-6's 1M-token
# context — chunks stay well under that even after rubric/prompt overhead.
_CHUNK_THRESHOLD_CHARS = int(os.environ.get("JUDGE_CHUNK_THRESHOLD_CHARS", "500000"))
_CHUNK_TARGET_CHARS = int(os.environ.get("JUDGE_CHUNK_TARGET_CHARS", "300000"))


def _is_retryable(exc: BaseException) -> bool:
    """Treat network/rate/5xx errors and JSON-parse failures as retryable.

    Anything else (auth, malformed request, etc.) bubbles immediately —
    retrying won't help.
    """
    # openai SDK errors are present at runtime but importing them at module
    # load conflicts with the strict-deps test container; check by name.
    cls = type(exc).__name__
    if cls in {
        "APIConnectionError", "APITimeoutError", "RateLimitError",
        "InternalServerError", "APIStatusError",
    }:
        return True
    if isinstance(exc, (json.JSONDecodeError, ValueError, TimeoutError, ConnectionError)):
        return True
    # Anything else (AuthenticationError, BadRequestError) — don't retry.
    return False


def _extract_grade_array(text: str) -> list[dict]:
    """Pull the grades array out of the judge's response.

    Judges often prepend prose (numbered analysis, markdown headings) before
    the final JSON array. That prose can contain stray ``[`` / ``]`` — e.g.
    R-style indexing like ``colon[!duplicated(colon$id), ]`` — so a greedy
    ``\\[.*\\]`` regex over the whole response latches onto the wrong opening
    bracket. We scan every ``[`` position and use ``JSONDecoder.raw_decode``
    to find the largest list-of-dicts that parses cleanly; this is robust to
    arbitrary prose before/after and to ``[``/``]`` inside justifications.
    """
    decoder = json.JSONDecoder()
    best: list[dict] | None = None
    for m in re.finditer(r"\[", text):
        try:
            obj, _ = decoder.raw_decode(text, m.start())
        except json.JSONDecodeError:
            # Try a per-block sanitizer (lone backslashes, control chars) and retry.
            tail = text[m.start():]
            fixed = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', tail)
            fixed = re.sub(r'[\x00-\x1f]', ' ', fixed)
            try:
                obj, _ = decoder.raw_decode(fixed, 0)
            except json.JSONDecodeError:
                continue
        if not isinstance(obj, list) or not obj or not all(isinstance(x, dict) for x in obj):
            continue
        if best is None or len(obj) > len(best):
            best = obj
    if best is None:
        raise ValueError(f"No JSON array of grade objects in judge response: {text[:200]}")
    return best


def _call_judge(prompt: str, model: str, base_url: str, api_key: str, expected_n: int = 0) -> list[dict]:
    """Call the LLM judge with bounded retries. Raises only after all retries fail.

    `expected_n` (when > 0) guards against a truncated / short response: if the
    judge returns fewer grade objects than criteria, that's treated as a
    retryable parse failure (re-roll) instead of being silently scored with the
    missing criteria defaulted to "not met".
    """
    from openai import OpenAI
    client = OpenAI(base_url=base_url, api_key=api_key)

    last_exc: BaseException | None = None
    last_raw_text: str = ""
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            last_raw_text = resp.choices[0].message.content or ""
            grades = _extract_grade_array(last_raw_text)
            if expected_n and len(grades) < expected_n:
                raise ValueError(
                    f"judge returned {len(grades)} grade(s) for {expected_n} criteria "
                    f"(short/truncated response)"
                )
            return grades
        except BaseException as exc:  # noqa: BLE001
            last_exc = exc
            if attempt >= _MAX_RETRIES or not _is_retryable(exc):
                # On persistent parse failures, drop the raw response so the
                # next debug session doesn't have to re-run the trial.
                if last_raw_text and isinstance(exc, (ValueError, json.JSONDecodeError)):
                    dump = Path(os.environ.get("JUDGE_RAW_DUMP_DIR", "/logs/verifier")) / "judge_raw_response.txt"
                    try:
                        dump.parent.mkdir(parents=True, exist_ok=True)
                        dump.write_text(last_raw_text)
                        print(f"[judge] dumped raw response to {dump}", file=sys.stderr)
                    except OSError:
                        pass
                raise
            wait = _RETRY_BASE_SEC * (2 ** (attempt - 1))
            print(
                f"[judge] {type(exc).__name__} on attempt {attempt}/{_MAX_RETRIES}: "
                f"{str(exc)[:140]} — retrying in {wait:.1f}s",
                file=sys.stderr,
            )
            time.sleep(wait)
    # Defensive: should never reach here (loop either returns or raises).
    raise last_exc  # type: ignore[misc]


def _chunk_text(text: str, target_chars: int) -> list[str]:
    """Split text into roughly target_chars-sized chunks at paragraph/line boundaries.

    Snaps each cut forward to the next ``\\n\\n`` or ``\\n`` within a small
    window so chunks don't shear individual lines mid-content.
    """
    if len(text) <= target_chars:
        return [text]
    n_chunks = (len(text) + target_chars - 1) // target_chars
    base = len(text) // n_chunks
    chunks: list[str] = []
    pos = 0
    for _ in range(n_chunks - 1):
        end = pos + base
        window = min(end + 5000, len(text))
        nl = text.find("\n\n", end, window)
        if nl == -1:
            nl = text.find("\n", end, window)
        if nl == -1 or nl <= pos:
            nl = end
        chunks.append(text[pos:nl])
        pos = nl
    chunks.append(text[pos:])
    return chunks


def _aggregate_chunked_grades(per_chunk_grades: list[list[dict]], rubrics: list[dict]) -> list[dict]:
    """OR-aggregate per-chunk grades: criterion 'met' overall if ANY chunk graded met.

    Matches process-rubric semantics: criteria are "did the agent do X?", so
    finding X in any chunk counts. Justifications from met chunks are
    concatenated; otherwise we record how many chunks looked.
    """
    aggregated: list[dict] = []
    for i, r in enumerate(rubrics):
        met_justifications: list[str] = []
        any_met = False
        seen_chunks = 0
        for chunk_idx, chunk_grades in enumerate(per_chunk_grades):
            if i >= len(chunk_grades):
                continue
            seen_chunks += 1
            g = chunk_grades[i]
            grade_str = (g.get("grade") or "").lower()
            if grade_str in ("met", "pass"):
                any_met = True
                just = g.get("justification", "")
                if just:
                    met_justifications.append(f"[chunk {chunk_idx + 1}] {just}")
        if any_met:
            grade = "met"
            justification = " ".join(met_justifications) or "Observed in trajectory."
        elif seen_chunks == 0:
            grade = "error"
            justification = "No chunk produced a grade for this criterion."
        else:
            grade = "not met"
            justification = f"Not observed across {seen_chunks} chunks."
        aggregated.append({
            "criterion_idx": i,
            "title": r["title"],
            "weight": r["weight"],
            "grade": grade,
            "justification": justification,
        })
    return aggregated


def _compute_score(graded: list[dict]) -> dict:
    earned = possible = 0.0
    for g in graded:
        w = _parse_weight(g.get("weight", ""))
        met = (g.get("grade", "").lower() in ("met", "pass"))
        if w > 0:
            possible += w
            if met:
                earned += w
        elif w < 0:
            if met:
                earned += w  # penalty
    pct = max(0.0, (earned / possible * 100) if possible > 0 else 0.0)  # floor net-negative at 0
    return {"earned": round(earned, 1), "possible": round(possible, 1), "pct": round(pct, 1)}


def _grade(kind: str, rubrics: list[dict], prompt: str, reference: str, agent_output: str,
           model: str, base_url: str, api_key: str) -> dict:
    if not rubrics or not agent_output:
        return {"graded": [], "score": {"earned": 0.0, "possible": 0.0, "pct": 0.0},
                "skipped_reason": "no rubrics" if not rubrics else "no agent output"}

    # Chunking is for the (potentially huge) process trajectory only. The
    # outcome answer is terse and is always graded in a single pass.
    if kind == "process" and len(agent_output) > _CHUNK_THRESHOLD_CHARS:
        chunks = _chunk_text(agent_output, _CHUNK_TARGET_CHARS)
        agent_label = "Final Answer" if kind == "outcome" else "Trajectory"
        per_chunk_grades: list[list[dict]] = []
        chunk_errors: list[dict] = []
        for idx, chunk in enumerate(chunks):
            chunk_note = (
                f"NOTE: The Agent's {agent_label} is too large to grade in a single pass. "
                f"This is chunk {idx + 1} of {len(chunks)}. Grade each criterion based ONLY "
                f"on what you observe in THIS chunk; results are aggregated across chunks "
                f"afterward (a criterion is 'met' overall if any chunk grades it 'met'). "
                f"If a behavior is not visible in this chunk, mark 'not met' — the evidence "
                f"may appear in another chunk.\n\n"
            )
            judge_prompt = chunk_note + _build_judge_prompt(kind, prompt, reference, chunk, rubrics)
            try:
                per_chunk_grades.append(_call_judge(judge_prompt, model, base_url, api_key,
                                                     expected_n=len(rubrics)))
            except BaseException as exc:  # noqa: BLE001
                chunk_errors.append({"chunk": idx, "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
                print(f"[judge] chunk {idx + 1}/{len(chunks)} FAILED: {exc}", file=sys.stderr)
        if not per_chunk_grades:
            raise RuntimeError(
                f"All {len(chunks)} chunks failed during {kind} grading: {chunk_errors}"
            )
        graded = _aggregate_chunked_grades(per_chunk_grades, rubrics)
        return {
            "graded": graded,
            "score": _compute_score(graded),
            "chunk_info": {
                "n_chunks": len(chunks),
                "n_succeeded": len(per_chunk_grades),
                "agent_output_chars": len(agent_output),
                "errors": chunk_errors,
            },
        }

    judge_prompt = _build_judge_prompt(kind, prompt, reference, agent_output, rubrics)
    grades_raw = _call_judge(judge_prompt, model, base_url, api_key, expected_n=len(rubrics))
    # Align by the judge's 1-based "criterion" index when present (robust to a
    # reordered response); fall back to positional order otherwise.
    by_idx: dict[int, dict] = {}
    for g in grades_raw:
        c = g.get("criterion")
        if isinstance(c, int) and 1 <= c <= len(rubrics) and c not in by_idx:
            by_idx[c] = g
    graded = []
    for i, r in enumerate(rubrics):
        g = by_idx.get(i + 1)
        if g is None:
            g = grades_raw[i] if i < len(grades_raw) else {}
        graded.append({
            "criterion_idx": i,
            "title": r["title"],
            "weight": r["weight"],
            "grade": g.get("grade", "error"),
            "justification": g.get("justification", ""),
        })
    return {"graded": graded, "score": _compute_score(graded)}


def _safe_grade(kind: str, rubrics, prompt, reference, agent_output, model, base_url, api_key):
    """Wrap _grade so a failure returns a {"error": ...} dict instead of raising.

    Keeps outcome and process grading independent — one failure must NOT
    silence the other.
    """
    try:
        return _grade(kind, rubrics, prompt, reference, agent_output, model, base_url, api_key)
    except BaseException as exc:  # noqa: BLE001
        return {
            "error": f"{type(exc).__name__}: {str(exc)[:240]}",
            "traceback": traceback.format_exc(limit=4),
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--answer-file", required=True, help="Path to agent's terse final answer")
    ap.add_argument("--rubrics-file", required=True, help="Bundled rubrics.json")
    ap.add_argument("--trajectory-file", default="", help="Optional agent trajectory for process eval")
    ap.add_argument("--output", required=True, help="Where to write reward.json")
    ap.add_argument("--judge-model", default=os.environ.get("JUDGE_MODEL", "claude-sonnet-4-6"))
    ap.add_argument("--judge-base-url", default=os.environ.get("JUDGE_BASE_URL", ""))
    ap.add_argument("--judge-api-key", default=os.environ.get("JUDGE_API_KEY", ""))
    args = ap.parse_args()

    if not args.judge_base_url or not args.judge_api_key:
        print("ERROR: JUDGE_BASE_URL and JUDGE_API_KEY must be set (env or flags).", file=sys.stderr)
        sys.exit(2)

    with open(args.rubrics_file) as f:
        bundle = json.load(f)
    task_id = bundle.get("task_id", "unknown")
    ground_truth = bundle.get("ground_truth", "")
    task_prompt = bundle.get("prompt", "")  # may be absent if not bundled
    outcome_rubrics = bundle.get("outcome_rubrics", [])
    process_rubrics = bundle.get("process_rubrics", [])

    agent_answer = _read_text(args.answer_file)
    trajectory = _read_text(args.trajectory_file)

    # Harbor's reward.json is parsed as dict[str, float|int]. Numeric metrics
    # only go in `reward`. Verbose grading metadata (per-criterion grades,
    # justifications) lands in a sidecar `grades_detail.json` next to it.
    reward: dict[str, float | int] = {
        "agent_answer_chars": len(agent_answer),
        "trajectory_chars": len(trajectory),
        "answer_file_present": 1 if agent_answer else 0,
    }
    detail: dict = {
        "task_id": task_id,
        "judge_model": args.judge_model,
        "agent_answer_chars": len(agent_answer),
        "trajectory_chars": len(trajectory),
    }

    # Outcome — independent of process.
    outcome = _safe_grade("outcome", outcome_rubrics, task_prompt, ground_truth, agent_answer,
                          args.judge_model, args.judge_base_url, args.judge_api_key)
    if "error" in outcome:
        detail["outcome_error"] = outcome["error"]
        detail["outcome_traceback"] = outcome.get("traceback", "")
        reward["outcome_judge_failed"] = 1
        print(f"[judge] outcome grading FAILED after retries: {outcome['error']}", file=sys.stderr)
    else:
        detail["outcome_graded"] = outcome.get("graded", [])
        detail["outcome_score"] = outcome["score"]
        reward["outcome_earned"] = outcome["score"]["earned"]
        reward["outcome_possible"] = outcome["score"]["possible"]
        reward["outcome_pct"] = outcome["score"]["pct"]
        reward["outcome_judge_failed"] = 0
        if "chunk_info" in outcome:
            detail["outcome_chunk_info"] = outcome["chunk_info"]

    # Process — independent of outcome; skipped if no trajectory/rubrics.
    if process_rubrics and trajectory:
        process = _safe_grade("process", process_rubrics, task_prompt, ground_truth, trajectory,
                              args.judge_model, args.judge_base_url, args.judge_api_key)
        if "error" in process:
            detail["process_error"] = process["error"]
            detail["process_traceback"] = process.get("traceback", "")
            reward["process_judge_failed"] = 1
            reward["process_present"] = 1
            print(f"[judge] process grading FAILED after retries: {process['error']}", file=sys.stderr)
        else:
            detail["process_graded"] = process.get("graded", [])
            detail["process_score"] = process["score"]
            reward["process_earned"] = process["score"]["earned"]
            reward["process_possible"] = process["score"]["possible"]
            reward["process_pct"] = process["score"]["pct"]
            reward["process_present"] = 1
            reward["process_judge_failed"] = 0
            if "chunk_info" in process:
                detail["process_chunk_info"] = process["chunk_info"]
                reward["process_n_chunks"] = process["chunk_info"]["n_chunks"]
    else:
        detail["process_skipped"] = "no rubrics" if not process_rubrics else "no trajectory file"
        reward["process_present"] = 0

    # Headline score: outcome percentage as 0-1 float (0 if outcome judge failed).
    outcome_pct = detail.get("outcome_score", {}).get("pct", 0.0)
    reward["score"] = round(outcome_pct / 100.0, 4)
    reward["judge_failed"] = int(
        reward.get("outcome_judge_failed", 0) == 1
        and reward.get("process_judge_failed", 0) in (0, 1)
        and "outcome_score" not in detail
    )

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(reward, f, indent=2)
    detail_path = Path(args.output).with_name("grades_detail.json")
    with open(detail_path, "w") as f:
        json.dump(detail, f, indent=2)
    print(f"Wrote {args.output}: score={reward['score']:.3f}  (detail → {detail_path.name})")


if __name__ == "__main__":
    main()