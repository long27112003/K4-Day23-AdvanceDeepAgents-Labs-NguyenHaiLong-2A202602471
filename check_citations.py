"""check_citations.py - STUDENT IMPLEMENTS `check`.   Runs INSIDE the sandbox (standard library only).

research.py uploads this file to the sandbox and the lead agent runs it with the `execute` tool:
    python3 /tmp/work/research/check_citations.py [report.md] [sources.json]
It must exit 0 and print "OK: ..." when the report is consistent, else print each problem and exit 1.
"""
import json
import sys

REPORT = "/tmp/work/report/report.md"
SOURCES = "/tmp/work/research/sources.json"


import re


def check(report_text, sources):
    """Return a list of problem strings (empty list = OK)."""
    problems = []
    if not sources or not isinstance(sources, list):
        return ["no sources in sources.json"]

    seen_urls = set()
    source_map = {}

    for s in sources:
        if not isinstance(s, dict):
            problems.append(f"source entry is not a dict: {s!r}")
            continue
        n = s.get("n")
        url = s.get("url")
        if not isinstance(n, int):
            problems.append(f"source 'n' must be an int, got {n!r}")
        elif n in source_map:
            problems.append(f"duplicate source number n={n} in sources.json")
        else:
            source_map[n] = s

        if not isinstance(url, str) or not (url.startswith("http://") or url.startswith("https://")):
            problems.append(f"source [{n}]: url must start with http:// or https://, got {url!r}")
        elif url in seen_urls:
            problems.append(f"duplicate url in sources.json: {url}")
        else:
            seen_urls.add(url)

    # 3. Split report_text at the heading "## References"
    ref_match = re.search(r"^##\s+References\s*$", report_text, flags=re.MULTILINE)
    if not ref_match:
        problems.append("missing '## References' section in report")
        return problems

    body = report_text[:ref_match.start()]
    references_section = report_text[ref_match.end():]

    # Clean body: strip fenced code blocks, inline code, and Markdown link definitions [text](url)
    cleaned_body = re.sub(r"```[\s\S]*?```", "", body)
    cleaned_body = re.sub(r"`[^`]*`", "", cleaned_body)
    cleaned_body = re.sub(r"\[[^\]]+\]\([^\)]+\)", "", cleaned_body)

    # 4 & 7. Extract citation numbers from body (support [1], [1, 2], [1-3])
    cited = set()
    for match in re.finditer(r"\[([\d\s,\-]+)\]", cleaned_body):
        raw = match.group(1).strip()
        parts = raw.split(",")
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                range_parts = part.split("-")
                if len(range_parts) == 2 and range_parts[0].strip().isdigit() and range_parts[1].strip().isdigit():
                    start_n, end_n = int(range_parts[0]), int(range_parts[1])
                    if start_n <= end_n and end_n - start_n <= 100:
                        cited.update(range(start_n, end_n + 1))
                        continue
            if part.isdigit():
                cited.add(int(part))

    for n in sorted(cited):
        if n not in source_map:
            problems.append(f"[{n}] cited in body but missing from sources.json")

    for n in sorted(source_map.keys()):
        if n not in cited:
            problems.append(f"source [{n}] never cited in body")

    # 5 & 6. Analyze lines in ## References section
    ref_lines = {}
    for line in references_section.splitlines():
        trimmed = line.strip()
        m = re.match(r"^\[(\d+)\]\s*(.*)$", trimmed)
        if m:
            ref_n = int(m.group(1))
            line_content = trimmed
            if ref_n in ref_lines:
                problems.append(f"duplicate reference line for [{ref_n}]")
            else:
                ref_lines[ref_n] = line_content

    # Every source needs exactly ONE reference line
    for n in sorted(source_map.keys()):
        if n not in ref_lines:
            problems.append(f"missing reference line for source [{n}]")

    for ref_n in sorted(ref_lines.keys()):
        if ref_n not in source_map:
            problems.append(f"reference line [{ref_n}] is not present in sources.json")
        else:
            line_str = ref_lines[ref_n]
            # Find URLs in reference line
            found_urls = re.findall(r"https?://[^\s)\]]+", line_str)
            cleaned_urls = [u.rstrip(".,;)") for u in found_urls]
            if len(cleaned_urls) == 0:
                problems.append(f"reference line [{ref_n}] has no URL")
            elif len(cleaned_urls) > 1:
                problems.append(f"reference line [{ref_n}] bundles multiple URLs: {cleaned_urls}")
            else:
                expected_url = source_map[ref_n].get("url")
                if cleaned_urls[0] != expected_url:
                    problems.append(
                        f"reference line [{ref_n}] URL mismatch: expected {expected_url}, got {cleaned_urls[0]}"
                    )

    return problems


def main(argv):
    report_path = argv[1] if len(argv) > 1 else REPORT
    sources_path = argv[2] if len(argv) > 2 else SOURCES
    try:
        with open(report_path, encoding="utf-8") as f:
            report = f.read()
        with open(sources_path, encoding="utf-8") as f:
            sources = json.load(f)
    except (OSError, ValueError) as exc:
        print(f"cannot read inputs: {exc}")
        return 1
    problems = check(report, sources)
    if problems:
        print("\n".join(problems))
        return 1
    print(f"OK: {len(sources)} sources, all citations resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
