"""tools.py - STUDENT IMPLEMENTS.  Source tools for the research agents.   Guide: GUIDE.md, part 1.

Rules for every tool:
  * runs on the HOST (not in the sandbox): API keys must never enter the sandbox;
  * returns a STRING (JSON text of compact records) and NEVER raises:
        "NO RESULTS"  when the source answers with nothing,
        "ERROR: ..."  when the source keeps failing after the retries (the agent then tries another source);
  * the docstring is the tool description the LLM reads: keep it precise (what it does, what it returns, when to use it).
Try your tools without any agent:   python tools.py
"""
import json
import os
import random
import re
import time
import xml.etree.ElementTree as ET

import httpx
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()

# ---- constants (given) ----
ARXIV_URL = "https://export.arxiv.org/api/query"  # https only: http answers 301
HF_DAILY_URL = "https://huggingface.co/api/daily_papers"
HF_SEARCH_URL = "https://huggingface.co/api/papers/search"
EXA_URL = "https://mcp.exa.ai/mcp"

_last_arxiv_time = 0.0


class RetryableError(Exception):
    """Given. Raise it inside a call to ask with_retry to wait and try again (retry_after in seconds, optional)."""

    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


# ---- TODO 1: retry helper ----
def with_retry(fn, *, attempts=5, base=1.0, cap=30.0):
    """Call fn(); when it raises RetryableError or temporary network errors, wait and call it again."""
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as e:
            is_retryable = False
            retry_after = None

            if isinstance(e, RetryableError):
                is_retryable = True
                retry_after = e.retry_after
            elif isinstance(e, httpx.TransportError):
                is_retryable = True
            elif isinstance(e, httpx.HTTPStatusError):
                if e.response.status_code in (429, 500, 502, 503, 504):
                    is_retryable = True
                    ra = e.response.headers.get("Retry-After")
                    if ra:
                        try:
                            retry_after = float(ra)
                        except ValueError:
                            pass

            if not is_retryable or attempt == attempts - 1:
                raise

            if retry_after is not None:
                delay = min(float(retry_after), cap)
            else:
                backoff = base * (2 ** attempt)
                jitter = random.uniform(0.1, 0.5 * backoff)
                delay = min(backoff + jitter, cap)

            time.sleep(delay)


def _clean_spaces(text: str) -> str:
    if not text:
        return ""
    return " ".join(text.split())


# ---- TODO 2: arXiv ----
@tool
def arxiv_search(query: str, max_results: int = 10) -> str:
    """Search arXiv papers by keywords, newest first. Returns a JSON list of {id, url, published, title, summary}."""
    global _last_arxiv_time
    try:
        terms = re.findall(r"[A-Za-z0-9\-]+", query)
        if not terms:
            return "NO RESULTS"

        elapsed = time.monotonic() - _last_arxiv_time
        if elapsed < 3.0:
            time.sleep(3.0 - elapsed)
        _last_arxiv_time = time.monotonic()

        search_query = " AND ".join(f"all:{t}" for t in terms)
        clamped_results = max(1, min(max_results, 30))
        params = {
            "search_query": search_query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": clamped_results,
        }

        def _fetch():
            resp = httpx.get(ARXIV_URL, params=params, timeout=30.0)
            if resp.status_code == 429:
                ra = resp.headers.get("Retry-After")
                raise RetryableError("arXiv rate limited (429)", retry_after=float(ra) if ra else None)
            resp.raise_for_status()
            return resp

        resp = with_retry(_fetch, attempts=6, base=2.0, cap=60.0)

        root = ET.fromstring(resp.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)
        if not entries:
            return "NO RESULTS"

        records = []
        for entry in entries:
            id_text = entry.findtext("atom:id", "", ns).strip()
            raw_id = id_text.split("/abs/")[-1] if "/abs/" in id_text else id_text
            clean_id = re.sub(r"v\d+$", "", raw_id)
            url = f"https://arxiv.org/abs/{clean_id}"
            published = (entry.findtext("atom:published", "", ns) or "")[:10]
            title = _clean_spaces(entry.findtext("atom:title", "", ns))
            summary = _clean_spaces(entry.findtext("atom:summary", "", ns))[:600]

            records.append({
                "id": clean_id,
                "url": url,
                "published": published,
                "title": title,
                "summary": summary,
            })

        return json.dumps(records, ensure_ascii=False) if records else "NO RESULTS"
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}: {exc}"


# ---- TODO 3: Hugging Face ----
@tool
def hf_daily_papers(limit: int = 30, date: str = "", keyword: str = "") -> str:
    """Hugging Face Daily Papers = what is trending in AI research. Returns a JSON list of
    {id, url, published, title, summary, upvotes, github, stars} sorted by upvotes. `date` is YYYY-MM-DD (empty = latest).
    `keyword` filters title/summary; there is no topic search on this endpoint (use hf_search_papers for a topic)."""
    try:
        clamped_limit = max(1, min(limit, 100))
        params = {"limit": clamped_limit}
        if date.strip():
            params["date"] = date.strip()

        def _fetch():
            resp = httpx.get(HF_DAILY_URL, params=params, timeout=30.0)
            if resp.status_code == 429:
                ra = resp.headers.get("Retry-After")
                raise RetryableError("HF daily rate limited (429)", retry_after=float(ra) if ra else None)
            resp.raise_for_status()
            return resp

        resp = with_retry(_fetch, attempts=5, base=1.0, cap=30.0)
        items = resp.json()
        if not isinstance(items, list) or not items:
            return "NO RESULTS"

        records = []
        for item in items:
            paper = item.get("paper") if isinstance(item, dict) else None
            if not paper or not paper.get("id"):
                continue

            pid = str(paper["id"])
            url = f"https://huggingface.co/papers/{pid}"
            published = str(paper.get("publishedAt") or item.get("publishedAt") or "")[:10]
            title = _clean_spaces(str(paper.get("title") or item.get("title") or ""))
            summary = _clean_spaces(str(paper.get("summary") or item.get("summary") or ""))[:600]
            upvotes = int(paper.get("upvotes") or 0)
            github = str(paper.get("githubRepo") or "")
            stars = int(paper.get("githubStars") or 0)

            records.append({
                "id": pid,
                "url": url,
                "published": published,
                "title": title,
                "summary": summary,
                "upvotes": upvotes,
                "github": github,
                "stars": stars,
            })

        if keyword.strip():
            kw = keyword.strip().lower()
            records = [r for r in records if kw in (r["title"] + " " + r["summary"]).lower()]

        records.sort(key=lambda r: r.get("upvotes", 0), reverse=True)
        return json.dumps(records, ensure_ascii=False) if records else "NO RESULTS"
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}: {exc}"


@tool
def hf_search_papers(query: str, limit: int = 10) -> str:
    """Search Hugging Face papers by topic. Returns a JSON list of
    {id, url, published, title, summary, upvotes, github, stars}."""
    try:
        if not query.strip():
            return "NO RESULTS"
        clamped_limit = max(1, min(limit, 50))
        params = {"q": query.strip(), "limit": clamped_limit}

        def _fetch():
            resp = httpx.get(HF_SEARCH_URL, params=params, timeout=30.0)
            if resp.status_code == 429:
                ra = resp.headers.get("Retry-After")
                raise RetryableError("HF search rate limited (429)", retry_after=float(ra) if ra else None)
            resp.raise_for_status()
            return resp

        resp = with_retry(_fetch, attempts=5, base=1.0, cap=30.0)
        items = resp.json()
        if not isinstance(items, list) or not items:
            return "NO RESULTS"

        records = []
        for item in items:
            paper = item.get("paper") if isinstance(item, dict) else None
            if not paper or not paper.get("id"):
                continue

            pid = str(paper["id"])
            url = f"https://huggingface.co/papers/{pid}"
            published = str(paper.get("publishedAt") or item.get("publishedAt") or "")[:10]
            title = _clean_spaces(str(paper.get("title") or item.get("title") or ""))
            summary = _clean_spaces(str(paper.get("ai_summary") or paper.get("summary") or item.get("summary") or ""))[:600]
            upvotes = int(paper.get("upvotes") or 0)
            github = str(paper.get("githubRepo") or "")
            stars = int(paper.get("githubStars") or 0)

            records.append({
                "id": pid,
                "url": url,
                "published": published,
                "title": title,
                "summary": summary,
                "upvotes": upvotes,
                "github": github,
                "stars": stars,
            })

        return json.dumps(records, ensure_ascii=False) if records else "NO RESULTS"
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}: {exc}"


# ---- TODO 4: web search / fetch through the Exa MCP endpoint ----
def _call_exa_mcp(tool_name: str, arguments: dict) -> str:
    """Internal helper to call Exa MCP tools over HTTP POST, handling SSE, rate limit detection and key redaction."""
    api_key = (os.getenv("EXA_API_KEY") or "").strip()
    endpoint = f"{EXA_URL}?exaApiKey={api_key}" if api_key else EXA_URL
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
    }

    def _post():
        resp = httpx.post(endpoint, json=payload, headers=headers, timeout=60.0)
        if resp.status_code == 429:
            ra = resp.headers.get("Retry-After")
            raise RetryableError("Exa HTTP 429 rate limit", retry_after=float(ra) if ra else 20.0)
        resp.raise_for_status()

        parsed_data = None
        for line in resp.text.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                raw_json = line[5:].strip()
                if raw_json:
                    parsed_data = json.loads(raw_json)
                    break

        if not parsed_data:
            try:
                parsed_data = resp.json()
            except Exception:
                raise RetryableError("Failed to parse Exa SSE data")

        if "error" in parsed_data:
            err = parsed_data["error"]
            err_msg = err.get("message", str(err))
            if any(term in err_msg.lower() for term in ("rate limit", "too many requests", "quota")):
                raise RetryableError(f"Exa rate limit in RPC error: {err_msg}", retry_after=20.0)
            raise RuntimeError(f"Exa JSON-RPC error: {err_msg}")

        result = parsed_data.get("result", {})
        meta = result.get("_meta", {})
        if any(term in str(meta).lower() for term in ("ratelimit", "rate_limit", "limit reached", "exceeded")):
            raise RetryableError("Exa rate limit detected in _meta", retry_after=20.0)

        contents = result.get("content", [])
        text_blocks = []
        for c in contents:
            if isinstance(c, dict) and c.get("type") == "text":
                txt = c.get("text", "")
                if any(term in txt.lower() for term in ("rate limit reached", "too many requests", "rate limited", "free tier limit")):
                    raise RetryableError("Exa rate limit detected in text content", retry_after=20.0)
                text_blocks.append(txt)

        return "\n\n".join(text_blocks).strip()

    try:
        return with_retry(_post, attempts=5, base=2.0, cap=60.0)
    except Exception as exc:
        msg = str(exc)
        if api_key:
            msg = msg.replace(api_key, "[REDACTED]")
        raise RuntimeError(msg)


@tool
def web_search(query: str, objective: str = "", num_results: int = 5) -> str:
    """Search the web (Exa). Describe the ideal page in natural language. Returns clean text of the top results with URLs."""
    try:
        if not query.strip():
            return "NO RESULTS"
        obj = objective.strip() if objective.strip() else f"Find academic research papers and surveys about {query}"
        clamped_n = max(1, min(num_results, 10))
        text = _call_exa_mcp("web_search_exa", {"query": query.strip(), "objective": obj, "numResults": clamped_n})
        return text if text else "NO RESULTS"
    except Exception as exc:
        api_key = (os.getenv("EXA_API_KEY") or "").strip()
        msg = str(exc)
        if api_key:
            msg = msg.replace(api_key, "[REDACTED]")
        return f"ERROR: {type(exc).__name__}: {msg}"


@tool
def web_fetch(url: str) -> str:
    """Read the full content of one web page (e.g. an arXiv abstract page) as markdown. Long pages are truncated."""
    try:
        if not url.strip():
            return "NO RESULTS"
        text = _call_exa_mcp("web_fetch_exa", {"urls": [url.strip()]})
        if not text:
            return "NO RESULTS"
        return text[:12000]
    except Exception as exc:
        api_key = (os.getenv("EXA_API_KEY") or "").strip()
        msg = str(exc)
        if api_key:
            msg = msg.replace(api_key, "[REDACTED]")
        return f"ERROR: {type(exc).__name__}: {msg}"


# ---- TODO 5: registry (the researcher subagent gets exactly these) ----
SOURCE_TOOLS = [arxiv_search, hf_daily_papers, hf_search_papers, web_search, web_fetch]


if __name__ == "__main__":
    for name, fn, args in [
        ("arxiv_search", arxiv_search, {"query": "world model", "max_results": 3}),
        ("hf_daily_papers", hf_daily_papers, {"limit": 20}),
        ("hf_search_papers", hf_search_papers, {"query": "world model", "limit": 3}),
        ("web_search", web_search, {"query": "survey paper on world models", "num_results": 2}),
        ("web_fetch", web_fetch, {"url": "https://arxiv.org/abs/1803.10122"}),
    ]:
        try:
            print(f"== {name}\n{fn.invoke(args)[:400]}\n")
        except NotImplementedError as exc:
            print(f"== {name}: not implemented yet ({exc})\n")
