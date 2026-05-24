"""Gemini-based verifier used inside the reward function during training."""

import os
import time

from google import genai

from config import VERIFIER_PROMPT

GEMINI_MODEL = "gemini-2.5-flash"
MAX_RETRIES = 3

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


def judge_one(question, ref, pred):
    """Return True / False / None (None = verifier failed)."""
    content = VERIFIER_PROMPT.format(question=question, ref=ref, pred=pred)
    for attempt in range(MAX_RETRIES):
        try:
            resp = _get_client().models.generate_content(
                model=GEMINI_MODEL,
                contents=content,
                config={"temperature": 0, "max_output_tokens": 5},
            )
            word = (resp.text or "").lower().strip(" .,\n")
            first = word.split()[0] if word else ""
            if first in ("correct", "incorrect"):
                return first == "correct"
        except Exception:
            time.sleep(2 ** attempt)
    return None


def judge_batch(items):
    """items: list of (question, ref, pred)."""
    return [judge_one(q, r, p) for q, r, p in items]
