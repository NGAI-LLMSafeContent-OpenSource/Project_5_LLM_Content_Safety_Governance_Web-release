#!/usr/bin/env python
"""Run Project 5 culture-aware output guardrail over generated responses."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_candidate_path() -> Path:
    return (
        Path("/mnt/d/repos/LLMSafeContent")
        / "Project_3_Cultural_Diversity_Corpus_Generation_Tool"
        / "framework_v3"
        / "runs"
        / "topic5_cultural_scene_seed_20260821_smoke10"
        / "candidate_responses"
        / "deepseek-v4-pro-0813"
        / "responses.jsonl"
    )


async def _run(args: argparse.Namespace) -> dict:
    sys.path.insert(0, str(_backend_root()))
    from app.services.output_guardrail_culture_service import run_culture_guardrail_batch

    return await run_culture_guardrail_batch(
        str(Path(args.candidate_responses_path).expanduser().resolve()),
        limit=args.limit,
        model_id=args.model_id,
        language=args.language,
        generate_neutral_candidate=args.generate_neutral_candidate,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run culture-aware output guardrail smoke from a candidate responses JSONL."
    )
    parser.add_argument(
        "--candidate-responses-path",
        default=str(_default_candidate_path()),
        help="Path to the second-step responses.jsonl file.",
    )
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--model-id", default="qwen3.5-9b")
    parser.add_argument("--language", default="zh")
    parser.add_argument(
        "--generate-neutral-candidate",
        action="store_true",
        help="Generate neutral model answer B with DeepSeek instead of using expected_neutral_answer fallback.",
    )
    args = parser.parse_args()
    result = asyncio.run(_run(args))
    print(
        json.dumps(
            {
                "batch_id": result["batch_id"],
                "status": result["status"],
                "sample_count": result["sample_count"],
                "manifest_path": result["manifest_path"],
                "results_path": result["results_path"],
                "summary": result["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
