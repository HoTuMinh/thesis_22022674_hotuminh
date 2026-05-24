"""Run benchmark: inference + abstention/correctness judging.

Usage:
    python eval.py                          # eval trained adapter
    python eval.py --no-adapter             # baseline (prompt only)
    python eval.py --output baseline.jsonl --no-adapter
"""

import argparse
import glob
import json
import os
import re

import torch
from peft import PeftModel
from tqdm import tqdm
from transformers import AutoModelForCausalLM, AutoTokenizer

from config import (ADAPTER_RESULTS, BASELINE_RESULTS, MAX_NEW_TOKENS,
                    MODEL_ID, TEST_PATH, TRUTHRL_PROMPT)
from judges import judge_abstention, judge_correctness

BOXED_RE = re.compile(r"\\boxed\{(.*?)\}", re.DOTALL)


def parse_boxed(text):
    m = BOXED_RE.search(text)
    if m:
        return m.group(1).strip()
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def find_adapter_path():
    cfg = glob.glob("/kaggle/input/**/adapter_config.json", recursive=True)
    if not cfg:
        cfg = glob.glob("**/adapter_config.json", recursive=True)
    assert cfg, "adapter_config.json not found"
    return os.path.dirname(cfg[0])


def load_model(use_adapter):
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, torch_dtype=torch.bfloat16,
        device_map={"": 0}, attn_implementation="sdpa",
    )
    if use_adapter:
        model = PeftModel.from_pretrained(model, find_adapter_path())

    model.generation_config.temperature = None
    model.generation_config.top_p = None
    model.generation_config.do_sample = False
    model.eval()
    return model, tokenizer


@torch.no_grad()
def run_inference(model, tokenizer, sample):
    user_msg = TRUTHRL_PROMPT.format(context=sample["context"], question=sample["question"])
    prompt = tokenizer.apply_chat_template(
        [{"role": "user", "content": user_msg}],
        tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt",
                       truncation=True, max_length=2048).to(model.device)
    outputs = model.generate(
        **inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False,
        pad_token_id=tokenizer.eos_token_id,
    )
    raw = tokenizer.decode(
        outputs[0][inputs["input_ids"].shape[1]:],
        skip_special_tokens=True).strip()
    return raw, parse_boxed(raw)


def load_test():
    return [json.loads(l) for l in open(TEST_PATH)]


def resume(save_file):
    """Keep only completed rows; return set of completed ids."""
    if not os.path.exists(save_file):
        return set()
    good = []
    for line in open(save_file):
        r = json.loads(line)
        ok = r["judge_abstained"] is not None and (
            r["is_unanswerable"] or r["is_correct"] is not None)
        if ok:
            good.append(line)
    with open(save_file, "w") as f:
        f.writelines(good)
    return {json.loads(l)["id"] for l in good}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-adapter", action="store_true",
                        help="Run baseline (no LoRA adapter)")
    parser.add_argument("--output", default=None,
                        help="Output JSONL path")
    args = parser.parse_args()

    use_adapter = not args.no_adapter
    save_file = args.output or (ADAPTER_RESULTS if use_adapter else BASELINE_RESULTS)

    samples = load_test()
    done = resume(save_file)
    remaining = [s for s in samples if s["id"] not in done]
    print(f"remaining={len(remaining)}/{len(samples)} | adapter={use_adapter}")

    model, tokenizer = load_model(use_adapter)

    with open(save_file, "a") as f:
        for s in tqdm(remaining):
            raw, parsed = run_inference(model, tokenizer, s)
            is_unans = s["is_unanswerable"]
            ref = None if is_unans else s["answers"]
            judge_abst = judge_abstention(s["question"], ref, is_unans, parsed)
            is_correct = judge_correctness(s["question"], ref, parsed)
            f.write(json.dumps({
                "id": s["id"], "title": s["title"], "question": s["question"],
                "ground_truth": s["answers"], "is_unanswerable": is_unans,
                "raw_model_response": raw, "parsed_model_answer": parsed,
                "judge_abstained": judge_abst, "is_correct": is_correct,
            }, ensure_ascii=False) + "\n")
            f.flush(); os.fsync(f.fileno())


if __name__ == "__main__":
    main()
