"""
ai_helper.py — AI summaries using Google Gemini (completely free)
Free tier: 1,500 requests/day · No credit card needed
Get your key at: aistudio.google.com → Get API Key
Add as GitHub Secret: GEMINI_API_KEY
"""
import os
import base64
import requests

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent"
)


def _api_key() -> str | None:
    v = os.environ.get("GEMINI_API_KEY", "").strip()
    return v if v else None


def _call(contents: list, system: str, max_tokens: int = 512) -> str | None:
    key = _api_key()
    if not key:
        print("  [ai] GEMINI_API_KEY not set — AI summaries skipped.")
        return None
    try:
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.3,
            },
        }
        resp = requests.post(
            GEMINI_URL,
            params={"key": key},
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"  [ai] Gemini call failed: {e}")
        return None


def summarise_diff(page_name: str, section_diffs: dict) -> str | None:
    """Return a 2-4 sentence plain-English summary of what changed."""
    if not _api_key():
        return None

    lines = []
    for section, diff in section_diffs.items():
        if diff.get("added"):
            lines.append(f"[{section}] ADDED: " + " | ".join(diff["added"][:10]))
        if diff.get("removed"):
            lines.append(f"[{section}] REMOVED: " + " | ".join(diff["removed"][:10]))

    if not lines:
        return None

    system = (
        "You are a helpful assistant summarising changes on a college website. "
        "Be concise, factual, and student-friendly. "
        "Write 2-4 plain English sentences. No bullet points, no markdown."
    )
    user_text = (
        f"Changes detected on the '{page_name}' page of COEP Technetu "
        f"(College of Engineering Pune). Summarise what changed and why it matters to students:\n\n"
        + "\n".join(lines)
    )
    contents = [{"role": "user", "parts": [{"text": user_text}]}]
    return _call(contents, system, max_tokens=300)


def summarise_pdf(pdf_bytes: bytes, filename: str) -> str | None:
    """Send PDF to Gemini and return bullet-point summary."""
    if not _api_key():
        return None

    b64 = base64.standard_b64encode(pdf_bytes).decode()
    system = (
        "You are a helpful assistant summarising college notices and documents. "
        "Be concise and student-friendly. "
        "Output exactly 3-5 bullet points covering: what this document is about, "
        "key dates or deadlines, who it concerns, and any action required. "
        "Use plain text bullets starting with *"
    )
    contents = [
        {
            "role": "user",
            "parts": [
                {
                    "inline_data": {
                        "mime_type": "application/pdf",
                        "data": b64,
                    }
                },
                {
                    "text": (
                        f"This document '{filename}' is from COEP Technetu college. "
                        "Summarise it in 3-5 bullet points."
                    )
                },
            ],
        }
    ]
    return _call(contents, system, max_tokens=400)
