"""Run GRPO + LoRA training on train.jsonl."""

import torch
from datasets import load_dataset
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import GRPOConfig, GRPOTrainer

from config import ADAPTER_DIR, MODEL_ID, TRAIN_PATH
from reward import truthrl_reward

MAX_STEPS = 160
NUM_GENERATIONS = 4
BATCH_SIZE = 4


def main():
    ds = load_dataset("json", data_files=TRAIN_PATH, split="train")
    ds = ds.map(lambda ex: {"prompt": [{"role": "user", "content": ex["prompt"]}]})

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.bfloat16,
        device_map={"": 0},
        attn_implementation="eager",
    )

    lora_config = LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    )

    cfg = GRPOConfig(
        output_dir=ADAPTER_DIR,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=1,
        num_generations=NUM_GENERATIONS,
        max_completion_length=384,
        gradient_checkpointing=True,
        top_entropy_quantile=1.0,
        repetition_penalty=1.1,
        max_steps=MAX_STEPS,
        learning_rate=1e-6,
        logging_steps=10,
        save_strategy="steps",
        save_steps=40,
        save_total_limit=5,
        report_to=[],
        bf16=True,
        temperature=1.0,
        top_p=1.0,
    )

    trainer = GRPOTrainer(
        model=model,
        args=cfg,
        train_dataset=ds,
        reward_funcs=truthrl_reward,
        peft_config=lora_config,
        processing_class=tokenizer,
    )
    trainer.train()
    trainer.save_model(f"{ADAPTER_DIR}/final")


if __name__ == "__main__":
    main()
