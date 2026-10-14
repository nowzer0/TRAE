import json
from pathlib import Path
import subprocess
import sys

import pandas as pd

from trae_esg.config import DEFAULT_THRESHOLDS, build_runtime_config
from trae_esg.pipeline import run_pipeline


def test_dry_run_writes_traceable_routes(tmp_path: Path) -> None:
    source = tmp_path / "input.csv"
    pd.DataFrame(
        [
            {"id": "a", "sentence": "We reduced operational emissions."},
            {"id": "b", "sentence": "The office opened on Monday."},
        ]
    ).to_csv(source, index=False)

    result = run_pipeline(
        source,
        tmp_path / "run",
        build_runtime_config(dry_run=True),
        DEFAULT_THRESHOLDS,
    )

    assert result["id"].astype(str).tolist() == ["a", "b"]
    assert set(result["label_source"]) <= {
        "step1_auto_irrelevant",
        "step2_auto_label",
        "expert_required",
    }
    for name in (
        "step1_aggregate.csv",
        "step2_aggregate.csv",
        "step3_final.csv",
        "final_annotations.csv",
        "summary.json",
    ):
        assert (tmp_path / "run" / name).exists()

    summary = json.loads((tmp_path / "run" / "summary.json").read_text())
    assert summary["total"] == 2


def test_cli_exposes_consensus_and_confidence() -> None:
    result = subprocess.run(
        [sys.executable, "run_annotation.py", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "--consensus {2,3}" in result.stdout
    assert "--confidence CONFIDENCE" in result.stdout
