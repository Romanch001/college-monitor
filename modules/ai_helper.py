"""
ai_helper.py — All Gemini-powered intelligence (100% free)
Functions:
  summarise_diff       — plain-English summary of page changes
  summarise_pdf        — bullet-point PDF summary
  score_importance     — rate change 1-10, decide if worth alerting
  extract_deadlines    — pull out dates/deadlines from text
  translate_text       — detect & translate Marathi/Hindi → English
  parse_timetable      — extract structured timetable from PDF
"""
import os, json, base64, requests

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent"
)

def _key():
    v = os.environ.get("GEMINI_API_KEY", "").strip()
    return v or None

def _call(contents, system, max_tokens=600, json_mode=False):
    key = _key()
    if not key:
        return None
    try:
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.2,
                **({"responseMimeType": "application/json"} if json_mode else {}),
            },
        }
        r = requests.post(GEMINI_URL, params={"key": key}, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"  [ai] Gemini error: {e}")
        return None

def _pdf_part(pdf_bytes):
    return {"inline_data": {"mime_type": "application/pdf",
                            "data": base64.standard_b64encode(pdf_bytes).decode()}}

# ── Summarise diff ───────────────────────────────────────────────
def summarise_diff(page_name, section_diffs):
    if not _key(): return None
    lines = []
    for s, d in section_diffs.items():
        if d.get("added"):   lines.append(f"[{s}] ADDED: "   + " | ".join(d["added"][:8]))
        if d.get("removed"): lines.append(f"[{s}] REMOVED: " + " | ".join(d["removed"][:8]))
    if not lines: return None
    sys = ("Summarise college website changes in 2-4 plain English sentences. "
           "Be student-friendly. No markdown.")
    txt = f"Page: '{page_name}' (COEP Technetu)\n\n" + "\n".join(lines)
    return _call([{"role":"user","parts":[{"text":txt}]}], sys, 300)

# ── Summarise PDF ────────────────────────────────────────────────
def summarise_pdf(pdf_bytes, filename):
    if not _key(): return None
    sys = ("Summarise this college document in 3-5 bullet points. "
           "Cover: topic, key dates/deadlines, who it concerns, action required. "
           "Use • bullets. Be concise.")
    contents = [{"role":"user","parts":[
        _pdf_part(pdf_bytes),
        {"text": f"Document '{filename}' from COEP Technetu. Summarise in bullets."}
    ]}]
    return _call(contents, sys, 400)

# ── Importance scorer ────────────────────────────────────────────
def score_importance(page_name, section_diffs, keywords_found):
    """Returns dict: {score: 1-10, reason: str, should_alert: bool}"""
    if not _key():
        return {"score": 5, "reason": "AI scoring unavailable", "should_alert": True}
    lines = []
    for s, d in section_diffs.items():
        if d.get("added"):   lines.append(f"[{s}] ADDED: "   + " | ".join(d["added"][:6]))
        if d.get("removed"): lines.append(f"[{s}] REMOVED: " + " | ".join(d["removed"][:6]))
    sys = (
        "You score college website changes for a student. "
        "Return ONLY valid JSON: {\"score\": <1-10>, \"reason\": \"<15 words max>\", \"should_alert\": <true/false>}. "
        "10=exam/result/urgent deadline. 7=new notice/circular. 4=minor update. 1=footer/nav change. "
        "should_alert=true if score>=6."
    )
    kw_str = ", ".join(keywords_found) if keywords_found else "none"
    txt = f"Page: {page_name}\nKeywords found: {kw_str}\nChanges:\n" + "\n".join(lines)
    raw = _call([{"role":"user","parts":[{"text":txt}]}], sys, 150, json_mode=True)
    if not raw: return {"score": 5, "reason": "scoring failed", "should_alert": True}
    try:
        return json.loads(raw)
    except Exception:
        return {"score": 5, "reason": raw[:60], "should_alert": True}

# ── Deadline extractor ───────────────────────────────────────────
def extract_deadlines(text, page_name):
    """Returns list of {date_str, description, type, urgency}"""
    if not _key(): return []
    sys = (
        "Extract ALL dates and deadlines from this college website text. "
        "Return ONLY valid JSON array: "
        "[{\"date_str\":\"DD Mon YYYY or as written\", "
        "\"description\":\"what is due\", "
        "\"type\":\"exam|result|fee|admission|event|other\", "
        "\"urgency\":\"high|medium|low\"}]. "
        "Empty array [] if no dates found. No other text."
    )
    txt = f"Page: {page_name}\n\n{text[:3000]}"
    raw = _call([{"role":"user","parts":[{"text":txt}]}], sys, 600, json_mode=True)
    if not raw: return []
    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except Exception:
        return []

# ── Translate text ───────────────────────────────────────────────
def translate_text(text):
    """Detect Marathi/Hindi and translate to English. Returns translated text or None."""
    if not _key(): return None
    if not text or len(text.strip()) < 20: return None
    sys = (
        "Detect the language of the text. "
        "If it is Marathi or Hindi, translate it to English and return ONLY the translation. "
        "If it is already English, return exactly: ENGLISH_ALREADY. "
        "No explanation, no preamble."
    )
    raw = _call([{"role":"user","parts":[{"text":text[:1000]}]}], sys, 500)
    if not raw or raw.strip() == "ENGLISH_ALREADY": return None
    return raw

# ── Parse timetable PDF ──────────────────────────────────────────
def parse_timetable(pdf_bytes, filename):
    """Extract structured timetable from a PDF. Returns formatted string or None."""
    if not _key(): return None
    sys = (
        "Extract the timetable/schedule from this document. "
        "Format it as a clean text table with Day | Time | Subject | Room columns. "
        "If it's not a timetable, return: NOT_A_TIMETABLE."
    )
    contents = [{"role":"user","parts":[
        _pdf_part(pdf_bytes),
        {"text": f"Extract timetable from '{filename}'. Format as table."}
    ]}]
    raw = _call(contents, sys, 800)
    if not raw or "NOT_A_TIMETABLE" in raw: return None
    return raw
