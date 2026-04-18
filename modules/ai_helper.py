"""
ai_helper.py — Claude-powered summaries for page diffs and PDFs
Uses claude-haiku (cheapest model) to keep costs near zero.
Set ANTHROPIC_API_KEY in GitHub Secrets to enable.
"""
import os
import base64
import requests

API_URL = "https://api.anthropic.com/v1/messages"
MODEL   = "claude-haiku-4-5-20251001"   # cheapest, fast, great for summaries


def _api_key() -> str | None:
    return os.environ.get("ANTHROPIC_API_KEY")


def _call(messages: list, system: str, max_tokens: int = 512) -> str | None:
    key = _api_key()
    if not key:
        return None
    try:
        resp = requests.post(
            API_URL,
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": max_tokens,
                "system": system,
                "messages": messages,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"].strip()
    except Exception as e:
        print(f"  [ai_helper] API call failed: {e}")
        return None


# ── Summarise a page diff ────────────────────────────────────────
def summarise_diff(page_name: str, section_diffs: dict) -> str | None:
    """
    section_diffs: {section_label: {added:[...], removed:[...]}}
    Returns a plain-English 3-5 sentence summary.
    """
    if not _api_key():
        return None

    lines = []
    for section, diff in section_diffs.items():
        if diff["added"]:
            lines.append(f"[{section}] ADDED: " + " | ".join(diff["added"][:10]))
        if diff["removed"]:
            lines.append(f"[{section}] REMOVED: " + " | ".join(diff["removed"][:10]))

    if not lines:
        return None

    raw_diff = "\n".join(lines)
    system = (
        "You are a helpful assistant summarising changes detected on a college website. "
        "Be concise, factual, and student-friendly. "
        "Output 2-4 plain English sentences. No bullet points, no markdown."
    )
    user = (
        f"The following changes were detected on the '{page_name}' page of COEP Technetu "
        f"(College of Engineering Pune). Summarise what changed and why it might matter to students:\n\n"
        f"{raw_diff}"
    )
    return _call([{"role": "user", "content": user}], system, max_tokens=300)


# ── Summarise a PDF ──────────────────────────────────────────────
def summarise_pdf(pdf_bytes: bytes, filename: str) -> str | None:
    """Send PDF to Claude and return a short summary."""
    if not _api_key():
        return None

    b64 = base64.standard_b64encode(pdf_bytes).decode()
    system = (
        "You are a helpful assistant summarising college notices and documents. "
        "Be concise and student-friendly. "
        "Output 3-5 bullet points covering: what this document is about, "
        "key dates or deadlines, who it concerns, and any action required. "
        "Use plain text bullets starting with •"
    )
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": b64,
                    },
                },
                {
                    "type": "text",
                    "text": (
                        f"This is a document named '{filename}' from COEP Technetu college. "
                        "Please summarise it in 3-5 bullet points."
                    ),
                },
            ],
        }
    ]
    return _call(messages, system, max_tokens=400)
