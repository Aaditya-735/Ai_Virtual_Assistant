#!/usr/bin/env python3
"""
model.py — Decision-making layer for Jarvis (fixed multi-target extraction + leftover cleaning)
"""

import re
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Dict

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("jarvis_model")

# Patterns for explicit functions. Note: open/close capture following sequence (to include "and firefox")
FUNC_KEYWORDS = {
    # capture everything after 'open' up to sentence end (will be split by 'and' / commas later)
    "open": [r"\bopen\b\s+([a-z0-9_.\-\s,]+)$", r"\bopen\b\s+([a-z0-9_.\-\s,]+)(?=\s+and\b|\s+then\b|$)"],
    "close": [r"\bclose\b\s+([a-z0-9_.\-\s,]+)$", r"\bclose\b\s+([a-z0-9_.\-\s,]+)(?=\s+and\b|\s+then\b|$)"],
    "play": [r"\bplay\b\s+(.+)$"],
    "generate image": [r"\bgenerate (?:an )?image(?: of)?\b\s*(.+)$", r"\bcreate (?:an )?image(?: of)?\b\s*(.+)$"],
    "reminder": [r"\b(remind me|set a reminder)\b(.+)$", r"\bremind me\b(?: to)?\b(.+)$"],
    "system": [r"\b(mute|unmute|volume up|volume down|shutdown|restart)\b"],
    "content": [r"\b(write|generate|compose|create)\b(?: an?| a)?\s*(email|application|script|code|essay|message|post|blog|report)?\b(.*)$"],
    "google search": [r"\bgoogle search\b\s+(.+)$", r"\bsearch on google\b\s+(.+)$"],
    "youtube search": [r"\byoutube search\b\s+(.+)$", r"\bsearch on youtube\b\s+(.+)$"],
    "exit": [r"\b(exit|quit|bye|goodbye)\b"],
}

REALTIME_KEYWORDS = [
    r"\bnews\b", r"\blatest\b", r"\bupdate\b", r"\bheadline\b", r"\bstock\b", r"\bprice\b", r"\bweather\b"
]

EXECUTOR = ThreadPoolExecutor(max_workers=4)


def _find_all_function_matches(prompt: str) -> List[Dict]:
    """
    Extract matches with spans using the original prompt and case-insensitive regex.
    Returns list of {'func','matched_text','span','value'} sorted by start index.
    """
    s = prompt
    matches = []
    for func, patterns in FUNC_KEYWORDS.items():
        for pat in patterns:
            # finditer on original prompt with IGNORECASE
            for m in re.finditer(pat, s, flags=re.IGNORECASE):
                span = m.span()
                text_matched = s[span[0]:span[1]]
                # get best non-empty capture group if present
                value = ""
                if m.groups():
                    # pick last non-empty group
                    for g in reversed(m.groups()):
                        if g and str(g).strip():
                            value = str(g).strip()
                            break
                matches.append({"func": func, "matched_text": text_matched, "span": span, "value": value})
    # sort by start index
    matches = sorted(matches, key=lambda x: x["span"][0])
    # dedupe overlapping matches: keep first non-overlapping
    filtered = []
    last_end = -1
    for m in matches:
        if m["span"][0] >= last_end:
            filtered.append(m)
            last_end = m["span"][1]
    return filtered


def _split_targets(text: str) -> List[str]:
    """Split a phrase like 'chrome and firefox, edge' into ['chrome','firefox','edge']"""
    # split on ' and ' or commas, keep words
    parts = re.split(r"\s*(?:and|,|then)\s*", text, flags=re.IGNORECASE)
    cleaned = []
    for p in parts:
        p2 = p.strip()
        if p2:
            # strip leading/trailing conjunctions/punctuation
            p2 = re.sub(r"^[\s\-,:;]+|[\s\-,:;]+$", "", p2)
            if p2:
                cleaned.append(p2)
    return cleaned


def _normalize_targets_from_matches(matches: List[Dict], original_prompt: str) -> List[str]:
    tasks = []
    for m in matches:
        func = m["func"]
        value = m.get("value", "").strip()
        matched_text = m.get("matched_text", "").strip()

        if func in ("open", "close"):
            # Prefer captured 'value' which may contain multiple items; fallback to matched_text minus leading keyword
            body = value or re.sub(r"(?i)^\s*(open|close)\b", "", matched_text).strip()
            targets = _split_targets(body)
            for t in targets:
                tasks.append(f"{func} {t}")
        elif func == "play":
            body = value or re.sub(r"(?i)^\s*play\b", "", matched_text).strip()
            for t in _split_targets(body):
                tasks.append(f"play {t}")
        elif func == "generate image":
            v = value or re.sub(r"(?i).*generate (?:an )?image(?: of)?\s*", "", matched_text).strip()
            if v:
                for p in _split_targets(v):
                    tasks.append(f"generate image {p}")
        elif func == "reminder":
            # crude but better: use captured value or matched_text remainder
            body = value or re.sub(r"(?i)^\s*(remind me|set a reminder)\b", "", matched_text).strip()
            body = body.strip()
            tasks.append(f"reminder {body}")
        elif func == "system":
            tasks.append(f"system {matched_text}")
        elif func == "content":
            topic = value or re.sub(r"(?i)^(write|generate|compose|create)\b", "", matched_text).strip()
            tasks.append(f"content {topic or 'unspecified'}")
        elif func == "google search":
            q = value or re.sub(r"(?i).*google (search )?(for )?", "", matched_text).strip()
            tasks.append(f"google search {q or original_prompt}")
        elif func == "youtube search":
            q = value or re.sub(r"(?i).*youtube (search )?(for )?", "", matched_text).strip()
            tasks.append(f"youtube search {q or original_prompt}")
        elif func == "exit":
            tasks.append("exit")
        else:
            tasks.append(f"{func} {value or matched_text}")
    return tasks


def _clean_leftover(leftover: str) -> str:
    """Trim leftover and remove leading/trailing conjunctions like 'and', 'then'."""
    if not leftover:
        return ""
    # collapse whitespace
    s = " ".join(leftover.split())
    # remove leading/trailing conjunctions and separators
    s = re.sub(r"^(?:and|then|,|\s)+", "", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:and|then|,|\s)+$", "", s, flags=re.IGNORECASE)
    return s.strip()


def _classify_leftover(leftover: str) -> Optional[str]:
    if not leftover or not leftover.strip():
        return None
    s = leftover.strip()
    s_l = s.lower()
    for rk in REALTIME_KEYWORDS:
        if re.search(rk, s_l, flags=re.IGNORECASE):
            return f"realtime {s}"
    # treat date/time terms as general per your spec
    if re.search(r"\b(time|date|day|month|year|today|tomorrow|yesterday)\b", s_l, flags=re.IGNORECASE):
        return f"general {s}"
    return f"general {s}"


def classify_prompt(prompt: str) -> List[str]:
    prompt = (prompt or "").strip()
    if not prompt:
        return ["unknown"]

    matches = _find_all_function_matches(prompt)
    tasks_from_matches = _normalize_targets_from_matches(matches, prompt)

    # build leftover by removing matched spans from original prompt
    if matches:
        parts = []
        last = 0
        for m in matches:
            start, end = m["span"]
            parts.append(prompt[last:start])
            last = end
        parts.append(prompt[last:])
        leftover_raw = " ".join(p.strip() for p in parts if p and p.strip())
    else:
        leftover_raw = prompt

    leftover = _clean_leftover(leftover_raw)
    leftover_task = _classify_leftover(leftover)
    tasks = tasks_from_matches.copy()
    if leftover_task:
        if leftover_task.lower().strip() not in [t.lower().strip() for t in tasks]:
            tasks.append(leftover_task)

    # ----- New filter: avoid duplicate 'general' entries that repeat image generation -----
    # If there's an explicit "generate image ..." task, remove any 'general ...' tasks
    # that contain 'generate image' (these are leftovers that duplicate intent).
    has_explicit_generate = any(
        isinstance(t, str) and t.lower().strip().startswith("generate image") for t in tasks
    )
    if has_explicit_generate:
        filtered = []
        for t in tasks:
            tl = t.lower().strip()
            # skip general entries that just repeat an image-generation phrase
            if tl.startswith("general") and "generate image" in tl:
                continue
            filtered.append(t)
        tasks = filtered
    # -------------------------------------------------------------------------------

    # final dedupe & normalization
    final = []
    seen = set()
    for t in tasks:
        t_clean = " ".join(t.split())
        tl = t_clean.lower()
        if tl not in seen:
            final.append(t_clean)
            seen.add(tl)
    return final or ["general "]



def dispatch_background(task: str, context: Optional[Dict] = None):
    def worker(t, ctx):
        logger.info("Background worker executing task: %s | ctx=%s", t, ctx)
        return {"status": "ok", "task": t}
    EXECUTOR.submit(worker, task, context or {})


def repl():
    logger.info("Starting REPL (type 'exit' to quit).")
    try:
        while True:
            try:
                s = input(">>> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not s:
                print(json.dumps(["unknown"], ensure_ascii=False))
                continue
            tasks = classify_prompt(s)
            print(json.dumps(tasks, ensure_ascii=False))
            if any(t.lower().strip() == "exit" for t in tasks):
                break
            for t in tasks:
                if t.split()[0].lower() in ("open", "close", "play", "generate", "reminder", "system", "google", "youtube"):
                    dispatch_background(t, context={"prompt": s})
    finally:
        EXECUTOR.shutdown(wait=False)
        logger.info("REPL terminated.")


if __name__ == "__main__":
    repl()

