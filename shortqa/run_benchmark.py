"""
Chạy benchmark hỏi đáp Lịch sử Việt Nam (409 câu) trên Llama 3.2 3B Instruct
và Phi-4-mini Instruct trong thiết lập zero-shot open QA.

Sử dụng:
    # Chạy cả 2 mô hình, lưu vào results.csv
    python run_benchmark.py

    # Chỉ chạy 1 mô hình
    python run_benchmark.py --model llama
    python run_benchmark.py --model phi

    # Đường dẫn tùy chỉnh
    python run_benchmark.py --input data/shortQA_benchmark.csv --output out.csv

    # Test nhanh trên N câu đầu
    python run_benchmark.py --limit 10

Cấu hình sinh:
    - Greedy decoding (do_sample=False)
    - max_new_tokens=512
    - System prompt + general instruction prompt như mô tả ở Mục 3.4.2

Yêu cầu GPU. Sau khi script kết thúc, cần chấm điểm thủ công theo rubric
4 khía cạnh (Helpfulness, Safety, Factuality, Reasoning), thang 1-5.
"""

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
import torch
from tqdm import tqdm
from transformers import AutoModelForCausalLM, AutoTokenizer

# ---------------------------------------------------------------------------
# Cấu hình mô hình
# ---------------------------------------------------------------------------
MODEL_REGISTRY = {
    "llama": {
        "hf_id": "meta-llama/Llama-3.2-3B-Instruct",
        "answer_col": "answer_llama-3.2-3b",
    },
    "phi": {
        "hf_id": "microsoft/Phi-4-mini-instruct",
        "answer_col": "answer_phi-4-mini",
    },
}

# Prompt giữ nguyên theo Mục 3.4.2 của khóa luận
SYSTEM_PROMPT = (
    "Bạn là một chuyên gia Lịch Sử với kiến thức sâu rộng về Lịch Sử Việt Nam"
)

INSTRUCTION_PROMPT = (
    "Bạn sẽ được giao nhiệm vụ trả lời các câu hỏi mở về các sự kiện Lịch Sử.\n"
    "Hãy cung cấp tóm tắt ngắn gọn về bằng chứng, sau đó là lý luận của bạn,\n"
    "rồi đưa ra câu trả lời rõ ràng và ngắn gọn.\n"
    "Giữ cho phần tóm tắt và lý luận của bạn ngắn gọn nhất có thể.\n"
    "Dựa câu trả lời nghiêm ngặt trên kiến thức Lịch Sử đã được thiết lập."
)

MAX_NEW_TOKENS = 512


# ---------------------------------------------------------------------------
def load_model(hf_id: str):
    """Nạp tokenizer và model với precision phù hợp."""
    print(f"[Loading] {hf_id} ...")
    tokenizer = AutoTokenizer.from_pretrained(hf_id, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        hf_id,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        device_map="auto",
        trust_remote_code=True,
    )
    model.eval()
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
    return tokenizer, model


def build_prompt(tokenizer, question: str) -> str:
    """Ghép system + instruction + question theo chat template của mô hình."""
    user_content = f"{INSTRUCTION_PROMPT}\n\nCâu hỏi: {question}"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    return tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )


@torch.no_grad()
def generate_answer(tokenizer, model, question: str) -> str:
    """Sinh câu trả lời bằng greedy decoding."""
    prompt = build_prompt(tokenizer, question)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    output = model.generate(
        **inputs,
        max_new_tokens=MAX_NEW_TOKENS,
        do_sample=False,
        pad_token_id=tokenizer.pad_token_id,
    )
    new_tokens = output[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


def run_model(model_key: str, questions: list[str]) -> list[str]:
    """Chạy 1 mô hình trên toàn bộ danh sách câu hỏi."""
    cfg = MODEL_REGISTRY[model_key]
    tokenizer, model = load_model(cfg["hf_id"])

    answers = []
    for q in tqdm(questions, desc=f"Inference [{model_key}]"):
        try:
            ans = generate_answer(tokenizer, model, q)
        except Exception as e:  # noqa: BLE001
            ans = f"[ERROR] {e}"
        answers.append(ans)

    # Giải phóng bộ nhớ GPU trước khi nạp model kế tiếp
    del model, tokenizer
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return answers


# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", default="data/shortQA_benchmark.csv",
        help="Đường dẫn CSV benchmark (cột: question, grade, difficulty)",
    )
    parser.add_argument(
        "--output", default="benchmark_outputs.csv",
        help="Đường dẫn CSV kết quả",
    )
    parser.add_argument(
        "--model", choices=["llama", "phi", "both"], default="both",
        help="Mô hình để chạy",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Chạy trên N câu đầu (debug)",
    )
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        sys.exit(f"[ERROR] Không thấy file {in_path}")

    df = pd.read_csv(in_path)
    if "question" not in df.columns:
        sys.exit("[ERROR] CSV thiếu cột `question`")

    if args.limit is not None:
        df = df.head(args.limit).copy()
    print(f"[Info] Loaded {len(df)} câu hỏi từ {in_path}")

    models_to_run = ["llama", "phi"] if args.model == "both" else [args.model]
    for m in models_to_run:
        col = MODEL_REGISTRY[m]["answer_col"]
        df[col] = run_model(m, df["question"].tolist())
        # Ghi tạm sau mỗi mô hình để tránh mất kết quả nếu lỗi giữa chừng
        df.to_csv(args.output, index=False)
        print(f"[Info] Đã lưu tạm sau khi chạy {m}: {args.output}")

    print(f"\n[Done] Kết quả lưu tại: {args.output}")
    print("Bước tiếp theo: chấm điểm thủ công theo rubric 4 khía cạnh (1-5).")


if __name__ == "__main__":
    main()
