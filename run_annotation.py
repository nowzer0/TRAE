from __future__ import annotations

import argparse

from dataclasses import replace

from trae_esg.config import DEFAULT_THRESHOLDS, build_runtime_config
from trae_esg.pipeline import run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Run TRAE ESG annotation pipeline")
    parser.add_argument("--input", required=True, help="Input CSV with a sentence column")
    parser.add_argument("--out_dir", required=True, help="Output directory")
    parser.add_argument("--dry_run", action="store_true", help="Run deterministic mock responses")
    parser.add_argument(
        "--consensus",
        type=int,
        choices=(2, 3),
        default=DEFAULT_THRESHOLDS.min_votes,
        help="Number of matching annotator votes required (default: 3)",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=DEFAULT_THRESHOLDS.tau_rel,
        help="Minimum confidence required from every supporting annotator (default: 0.90)",
    )
    parser.add_argument(
        "--judge-confidence",
        type=float,
        default=DEFAULT_THRESHOLDS.tau_j,
        help="Minimum judge confidence required at Step 3 (default: 0.70)",
    )
    parser.add_argument("--expert_csv", default=None, help="CSV containing id and expert_label")

    parser.add_argument("--provider", default="gemini", help="Provider for single-model mode")
    parser.add_argument("--model", default="gemini-2.5-flash-lite", help="Model for single-model mode")
    parser.add_argument("--agent_config", default=None, help="JSON config for A/B/C/judge agents")
    args = parser.parse_args()
    if not 0.0 <= args.confidence <= 1.0:
        parser.error("--confidence must be between 0 and 1")
    if not 0.0 <= args.judge_confidence <= 1.0:
        parser.error("--judge-confidence must be between 0 and 1")

    runtime = build_runtime_config(
        provider=args.provider,
        model=args.model,
        agent_config=args.agent_config,
        dry_run=args.dry_run,
    )
    thresholds = replace(
        DEFAULT_THRESHOLDS,
        tau_rel=args.confidence,
        tau_lab=args.confidence,
        tau_j=args.judge_confidence,
        min_votes=args.consensus,
    )
    run_pipeline(
        args.input,
        args.out_dir,
        runtime,
        thresholds,
        expert_csv=args.expert_csv,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
