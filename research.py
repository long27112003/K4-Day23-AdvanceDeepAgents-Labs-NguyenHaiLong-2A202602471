"""research.py - STUDENT IMPLEMENTS.  The main script.   Guide: GUIDE.md, part 3.

Usage:  python research.py "survey about world model"
Result: reports/<slug>.md   reports/<slug>.sources.json   reports/<slug>.meta.json
"""
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

from agents import FINALIZER_PATH, REPORT_PATH, SOURCES_PATH, VALIDATOR_PATH, WORKDIR, build_lead_agent
from model import make_model
from sandbox import download, open_sandbox, upload

ROOT = Path(__file__).parent
REPORTS = ROOT / "reports"
VALIDATOR_SOURCE = ROOT / "check_citations.py"
FINALIZER_SOURCE = ROOT / "finalize_citations.py"   # provided: uploaded next to your validator


def slugify(topic):
    """Turn a topic into a safe file name: lower case, runs of non-word characters become one "-", max 60 chars,
    never empty (fall back to "topic"). The topic is user input: "../../x" must not escape reports/."""
    if not topic or not isinstance(topic, str):
        return "topic"
    cleaned = topic.lower()
    cleaned = re.sub(r"[^\w]+", "-", cleaned).strip("-")
    if not cleaned:
        return "topic"
    cleaned = cleaned[:60].rstrip("-")
    return cleaned or "topic"


def build_prompt(topic):
    """The user message sent to the lead agent."""
    return (
        f"Please conduct an in-depth academic survey on the topic: '{topic}'.\n\n"
        "Follow your system instructions carefully:\n"
        "1. Use `write_todos` to plan and break this topic into at least 3-4 distinct sub-questions.\n"
        "2. Delegate each sub-question to a `researcher` subagent via `task` in parallel, passing full context and note format.\n"
        "3. Ensure your sources span at least 3 source families (arxiv, hf-daily, hf-search, web).\n"
        "4. Consolidate notes into `/tmp/work/research/sources.json`.\n"
        "5. Synthesize a comprehensive survey report in `/tmp/work/report/report.md` following REPORT_TEMPLATE.md.\n"
        "6. Run `/tmp/work/research/finalize_citations.py` and `/tmp/work/research/check_citations.py` with `execute` until OK.\n"
        "7. Have `citation-checker` spot-check claims."
    )


def summarize(messages, elapsed, model_name):
    """Return {"model", "elapsed_s", "subagent_calls", "tool_calls": {name: count}, "tokens": {"input", "output"}}."""
    tool_calls_counter = Counter()
    total_input_tokens = 0
    total_output_tokens = 0

    for msg in messages:
        t_calls = getattr(msg, "tool_calls", None)
        if t_calls is None and isinstance(msg, dict):
            t_calls = msg.get("tool_calls")
        if t_calls:
            for tc in t_calls:
                name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                if name:
                    tool_calls_counter[name] += 1

        usage = getattr(msg, "usage_metadata", None)
        if usage is None and isinstance(msg, dict):
            usage = msg.get("usage_metadata")
        if usage and isinstance(usage, dict):
            total_input_tokens += usage.get("input_tokens", 0)
            total_output_tokens += usage.get("output_tokens", 0)
        elif hasattr(msg, "response_metadata") and isinstance(msg.response_metadata, dict):
            token_usage = msg.response_metadata.get("token_usage") or msg.response_metadata.get("usage")
            if token_usage and isinstance(token_usage, dict):
                total_input_tokens += token_usage.get("prompt_tokens", 0) or token_usage.get("input_tokens", 0)
                total_output_tokens += token_usage.get("completion_tokens", 0) or token_usage.get("output_tokens", 0)

    subagent_calls = tool_calls_counter.get("task", 0)

    return {
        "model": model_name,
        "elapsed_s": round(elapsed, 1),
        "subagent_calls": subagent_calls,
        "tool_calls": dict(tool_calls_counter),
        "tokens": {
            "input": total_input_tokens,
            "output": total_output_tokens,
        },
    }


def save_outputs(backend, topic, messages, elapsed, model_name, reports_dir=REPORTS):
    """Download the report from the sandbox and write the three files into reports_dir. Return the report path."""
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    files = download(backend, [REPORT_PATH, SOURCES_PATH])
    report_bytes = files.get(REPORT_PATH)
    sources_bytes = files.get(SOURCES_PATH)

    if not report_bytes or not report_bytes.strip():
        raise RuntimeError(f"Report is missing or empty at {REPORT_PATH}")

    if not sources_bytes or not sources_bytes.strip():
        raise RuntimeError(f"Sources file is missing or empty at {SOURCES_PATH}")

    try:
        sources_data = json.loads(sources_bytes.decode("utf-8"))
        if not isinstance(sources_data, list):
            raise ValueError("sources.json is not a JSON list")
    except Exception as exc:
        raise RuntimeError(f"Invalid sources.json: {exc}")

    slug = slugify(topic)
    meta_dict = summarize(messages, elapsed, model_name)
    meta_dict["topic"] = topic
    meta_dict["n_sources"] = len(sources_data)

    distinct_families = sorted({s.get("source") for s in sources_data if isinstance(s, dict) and s.get("source")})
    meta_dict["source_families"] = distinct_families

    report_path = reports_dir / f"{slug}.md"
    sources_path = reports_dir / f"{slug}.sources.json"
    meta_path = reports_dir / f"{slug}.meta.json"

    report_path.write_bytes(report_bytes)
    sources_path.write_bytes(sources_bytes)
    meta_path.write_text(json.dumps(meta_dict, indent=2, ensure_ascii=False), encoding="utf-8")

    return report_path


def main(topic):
    """Return the process exit code (0 ok, 1 failed run, 2 no topic)."""
    if not topic or not topic.strip():
        print("Usage: python research.py <topic>", file=sys.stderr)
        return 2

    topic = topic.strip()
    model = make_model()
    model_name = getattr(model, "model_name", None) or getattr(model, "model", None) or os.getenv("LAB_MODEL", "unknown")
    start = time.monotonic()

    with open_sandbox() as backend:
        backend.execute(f"mkdir -p {WORKDIR}/research/notes {WORKDIR}/report")
        upload(backend, {
            VALIDATOR_PATH: VALIDATOR_SOURCE.read_bytes(),
            FINALIZER_PATH: FINALIZER_SOURCE.read_bytes(),
        })
        agent = build_lead_agent(backend, model)
        try:
            result = agent.invoke(
                {"messages": [{"role": "user", "content": build_prompt(topic)}]},
                config={"recursion_limit": 1000},
            )
            elapsed = time.monotonic() - start
            messages = result.get("messages", []) if isinstance(result, dict) else []
            out_path = save_outputs(backend, topic, messages, elapsed, model_name)
            print(f"Report successfully saved to {out_path}")
            return 0
        except Exception as exc:
            print(f"FAILED: {exc}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    sys.exit(main(" ".join(sys.argv[1:])))
