"""Groq-based abstention + correctness judges for evaluation."""

import os
import time

from groq import Groq

from config import JUDGE_ABSTENTION_PROMPT, JUDGE_CORRECTNESS_PROMPT

GROQ_MODEL = "llama-3.1-8b-instant"
MAX_RETRIES = 3

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ["GROQ_API_KEY"])
    return _client


def _call(content):
    for attempt in range(MAX_RETRIES):
        try:
            resp = _get_client().chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": content}],
                temperature=0, max_tokens=5,
            )
            return (resp.choices[0].message.content or "").lower().strip(" .,\n")
        except Exception:
            time.sleep(2 ** attempt)
    return None


def _binary(out, yes_word, no_word):
    if out is None:
        return None
    first = out.split()[0] if out else ""
    if first not in (yes_word, no_word):
        return None
    return first == yes_word


def judge_abstention(question, ref_answer, is_unanswerable, model_answer):
    ref_str = "[" + "; ".join(set(ref_answer)) + "]" if ref_answer else "[]"
    out = _call(JUDGE_ABSTENTION_PROMPT.format(
        question=question, ref_answer=ref_str,
        abstention_label=is_unanswerable, model_answer=model_answer))
    return _binary(out, "yes", "no")


def judge_correctness(question, ref_answer, model_answer):
    if not ref_answer:
        return None
    out = _call(JUDGE_CORRECTNESS_PROMPT.format(
        question=question, ref_answer="\n".join(set(ref_answer)),
        model_answer=model_answer))
    return _binary(out, "correct", "incorrect")
