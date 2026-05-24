# Đánh giá ảo giác của LLM trong tác vụ hỏi đáp Lịch sử Việt Nam

Mã nguồn và dữ liệu đi kèm khóa luận tốt nghiệp **"Xây dựng bộ chuẩn đánh giá và áp dụng phương pháp học tăng cường nhằm giảm thiểu ảo giác của mô hình ngôn ngữ lớn trong tác vụ hỏi đáp Lịch sử"** — Hồ Tú Minh, Trường Đại học Công nghệ, ĐHQGHN, 2026.

## Tổng quan

Khóa luận có ba đóng góp chính:

1. **Taxonomy ảo giác Lịch sử** — phân loại 10 dạng lỗi đặc thù theo 3 nhóm: thời gian, nhân quả, bằng chứng và hành vi trả lời.
2. **Benchmark hỏi đáp mở Lịch sử Việt Nam (ShortQA)** — 409 câu hỏi tổng hợp từ đề thi chính thức, kèm rubric đánh giá 4 khía cạnh (Helpfulness, Safety, Factuality, Reasoning) trên thang 1–5.
3. **Thực nghiệm TruthRL** — khảo sát ban đầu việc dùng GRPO + LoRA để giảm ảo giác hành vi abstention trên SQuAD 2.0.

## Cấu trúc thư mục

```
.
├── README.md
├── requirements.txt
├── .gitignore
│
├── shortqa/                       # [Đóng góp 2] Benchmark ShortQA
│   ├── shortQA_benchmark.csv      # 409 câu: question, grade, difficulty
│   ├── evaluation_results.csv     # Câu trả lời + điểm rubric (Llama & Phi)
│   ├── rubric.md                  # Rubric đánh giá 4 khía cạnh
│   └── run_benchmark.py           # Chạy 2 LLM zero-shot trên benchmark
│
├── taxonomy/                      # [Đóng góp 1] Taxonomy ảo giác Lịch sử
│   ├── taxonomy.py                # Sơ đồ tròn 10 loại
│   └── taxonomy_table.py          # Bảng mô tả chi tiết + ví dụ
│
└── truthrl/                       # [Đóng góp 3] Pipeline TruthRL
    ├── README.md
    ├── data/                      # Sinh từ src/data.py
    │   ├── train.jsonl
    │   └── eval.jsonl
    ├── output/                    # Kết quả eval
    │   └── adapter_results.jsonl
    └── src/
        ├── config.py
        ├── data.py                # Build train/eval/test từ SQuAD 2.0
        ├── verifier.py            # Gemini verifier (reward khi train)
        ├── reward.py              # Hàm reward 3 mức
        ├── train.py               # GRPO + LoRA
        ├── judges.py              # Groq judges (abstention + correctness)
        ├── eval.py                # Inference + judging trên test set
        └── metrics.py             # Hallucination, Truthfulness, F1
```

## Cài đặt

```bash
pip install -r requirements.txt
```

Python ≥ 3.10. Phần TruthRL cần GPU ≥ 8GB VRAM cho Llama 3.2 3B.

## Hướng dẫn sử dụng

### Đóng góp 1 — Taxonomy ảo giác Lịch sử

Chi tiết taxonomy và ví dụ tại folder `taxonomy`

### Đóng góp 2 — Benchmark ShortQA Lịch sử Việt Nam

Bộ dữ liệu ở `data/shortQA_benchmark.csv`:

| Cột | Kiểu | Mô tả |
|-----|------|-------|
| `question` | string | Câu hỏi Lịch sử Việt Nam |
| `grade` | int | Khối lớp: 10, 11, 12 |
| `difficulty` | int | `1`, `2`, `3`, tương ứng với `nhận biết`, `thông hiểu`, `vận dụng` |

Chạy 2 mô hình sinh câu trả lời ở chế độ zero-shot:

```bash
python shortqa/run_benchmark.py --input shortqa/shortQA_benchmark.csv                       # cả 2 mô hình, output: benchmark_outputs.csv
python run_benchmark.py --model llama         # chỉ Llama 3.2 3B Instruct
python run_benchmark.py --model phi           # chỉ Phi-4-mini Instruct
```

Sau đó chấm điểm thủ công theo rubric 4 khía cạnh (1–5). Kết quả đã chấm sẵn lưu ở `data/evaluation_results.csv` — định dạng `"<điểm>, <nhận xét>"` cho mỗi ô rubric.

### Đóng góp 3 — Thực nghiệm TruthRL

Pipeline 4 lệnh trong thư mục `truthrl/`:

```bash
cd truthrl

# Cấu hình API keys
export HF_TOKEN=...
export GEMINI_API_KEY=...    # verifier khi train
export GROQ_API_KEY=...      # judges khi eval

# 1. Build datasets từ SQuAD 2.0
python data.py
#  → train.jsonl (2000)  + eval.jsonl (300)  + test.jsonl (2317)

# 2. GRPO + LoRA, 160 step
python train.py

# 3. Đánh giá trên test set (7 chủ đề lịch sử)
python eval.py                 # adapter sau training
python eval.py --no-adapter    # baseline (prompt only)

# 4. Tính metrics
python metrics.py
```
