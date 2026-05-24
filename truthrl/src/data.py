"""Build train.jsonl, eval.jsonl, test.jsonl from SQuAD v2.

- train + eval: drawn from SQuAD train, excluding test topics, balanced 50/50.
- test: drawn from SQuAD validation, restricted to 7 history topics.
"""

import json
import random

from datasets import load_dataset

from config import (EVAL_PATH, MIN_BALANCE, MIN_PER_CLASS, N_EVAL, N_TRAIN,
                    SEED, TEST_PATH, TEST_TITLES, TRUTHRL_PROMPT)


def to_record(ex):
    answers = list(set(ex["answers"]["text"]))
    return {
        "id": ex["id"],
        "title": ex["title"],
        "question": ex["question"],
        "context": ex["context"],
        "prompt": TRUTHRL_PROMPT.format(context=ex["context"], question=ex["question"]),
        "answers": answers,
        "is_unanswerable": len(answers) == 0,
    }


def write_jsonl(path, records):
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def build_train_eval(train_path, eval_path):
    """Pool SQuAD train minus test topics; balanced sample; disjoint split."""
    random.seed(SEED)
    train = load_dataset("rajpurkar/squad_v2")["train"]
    test_set = set(TEST_TITLES)

    by_title = {}
    for ex in train:
        if ex["title"] in test_set:
            continue
        d = by_title.setdefault(ex["title"], {"ans": [], "unans": []})
        key = "ans" if len(ex["answers"]["text"]) > 0 else "unans"
        d[key].append(ex)

    selected = [
        t for t, d in by_title.items()
        if len(d["ans"]) >= MIN_PER_CLASS
        and len(d["unans"]) >= MIN_PER_CLASS
        and min(len(d["ans"]), len(d["unans"])) / max(len(d["ans"]), len(d["unans"])) >= MIN_BALANCE
    ]

    pool_ans = [ex for t in selected for ex in by_title[t]["ans"]]
    pool_unans = [ex for t in selected for ex in by_title[t]["unans"]]
    random.shuffle(pool_ans)
    random.shuffle(pool_unans)

    half = (N_TRAIN + N_EVAL) // 2
    assert len(pool_ans) >= half and len(pool_unans) >= half, "Not enough data"

    sel_ans, sel_unans = pool_ans[:half], pool_unans[:half]
    eval_rows = sel_ans[:N_EVAL // 2] + sel_unans[:N_EVAL // 2]
    train_rows = sel_ans[N_EVAL // 2:] + sel_unans[N_EVAL // 2:]
    random.shuffle(eval_rows)
    random.shuffle(train_rows)

    train_recs = [to_record(e) for e in train_rows]
    eval_recs = [to_record(e) for e in eval_rows]
    assert {r["id"] for r in train_recs}.isdisjoint({r["id"] for r in eval_recs})

    write_jsonl(train_path, train_recs)
    write_jsonl(eval_path, eval_recs)
    print(f"train={len(train_recs)} eval={len(eval_recs)} topics={len(selected)}")


def build_test(test_path):
    """Test = SQuAD validation filtered to TEST_TITLES (7 history topics)."""
    val = load_dataset("rajpurkar/squad_v2")["validation"]
    test_set = set(TEST_TITLES)
    rows = [to_record(ex) for ex in val if ex["title"] in test_set]
    write_jsonl(test_path, rows)
    print(f"test={len(rows)}")


if __name__ == "__main__":
    from config import TRAIN_PATH
    build_train_eval(TRAIN_PATH, EVAL_PATH)
    build_test(TEST_PATH)
