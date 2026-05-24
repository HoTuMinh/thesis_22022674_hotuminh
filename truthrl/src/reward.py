"""TruthRL three-way reward.

+1: correct answer (verifier=True)         OR  abstain on unanswerable
 0: abstain on answerable                  OR  verifier failed
-1: wrong answer, hallucination on unans,  OR  missing \\boxed{} format
"""

import re

from verifier import judge_batch

BOXED_RE = re.compile(r"\\boxed\{(.*?)\}", re.DOTALL)
ABSTAIN_PHRASES = ("i don't know", "i dont know", "invalid question")


def _parse_boxed(text):
    m = BOXED_RE.search(text)
    return (m.group(1).strip(), True) if m else ("", False)


def _is_abstain(answer):
    a = answer.lower().strip(" .\"'")
    return any(p in a for p in ABSTAIN_PHRASES)


def truthrl_reward(completions, answers, is_unanswerable, **kwargs):
    """Reward func for GRPOTrainer."""
    rewards = [None] * len(completions)
    api_jobs = []  # (idx, question, ref, pred) needing verifier
    questions = kwargs.get("question", [None] * len(completions))

    for i, comp in enumerate(completions):
        text = comp if isinstance(comp, str) else comp[-1]["content"]
        boxed, found = _parse_boxed(text)
        unans = is_unanswerable[i]

        if not found:
            rewards[i] = -1.0
        elif _is_abstain(boxed):
            rewards[i] = 1.0 if unans else 0.0
        elif unans:
            rewards[i] = -1.0
        else:
            api_jobs.append((i, questions[i], "[" + "; ".join(answers[i]) + "]", boxed))

    if api_jobs:
        verdicts = judge_batch([(q, r, p) for _, q, r, p in api_jobs])
        for (idx, _, _, _), v in zip(api_jobs, verdicts):
            rewards[idx] = 0.0 if v is None else (1.0 if v else -1.0)

    return rewards
