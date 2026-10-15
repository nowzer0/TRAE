import json
from pathlib import Path
import subprocess
import sys

import pandas as pd

from trae_esg.config import DEFAULT_THRESHOLDS, build_runtime_config
from trae_esg.llm_client import LLMClient
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
        "step3_judge",
        "unresolved",
    }
    for name in (
        "step1_aggregate.csv",
        "step2_aggregate.csv",
        "step3_final.csv",
        "final_annotations.csv",
        "unresolved_annotations.csv",
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
    assert "--judge-confidence" not in result.stdout
    assert "--expert_csv" not in result.stdout


def test_pipeline_filters_rows_at_each_stage(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "input.csv"
    pd.DataFrame(
        [
            {"id": "step1", "sentence": "The office opened on Monday."},
            {"id": "step2", "sentence": "We reduced operational emissions."},
            {"id": "step3", "sentence": "This ambiguous disclosure needs debate."},
        ]
    ).to_csv(source, index=False)

    def fake_complete(self, messages, role=None):
        system = messages[0]["content"]
        user = messages[-1]["content"]

        if "Judge" in system:
            return json.dumps(
                {
                    "final_label": "G",
                    "judge_confidence": 0.82,
                    "rationale": "The judge resolves the disagreement.",
                }
            )
        if "debater" in system:
            return json.dumps({"claim": f"Claim from {role}."})
        if "assign EXACTLY ONE label" in system:
            label = "E" if "emissions" in user else {"A": "E", "B": "S", "C": "G"}[role]
            return json.dumps(
                {
                    "label": label,
                    "confidence": 0.95,
                    "span": "disclosure",
                    "rationale": "Test classification.",
                }
            )

        relevance = "No" if "opened on Monday" in user else "Yes"
        return json.dumps(
            {
                "relevance": relevance,
                "confidence": 0.95,
                "keywords": ["test"],
                "rationale": "Test relevance decision.",
            }
        )

    monkeypatch.setattr(LLMClient, "complete", fake_complete)
    out_dir = tmp_path / "run"
    result = run_pipeline(
        source,
        out_dir,
        build_runtime_config(),
        DEFAULT_THRESHOLDS,
    )

    assert len(pd.read_csv(out_dir / "step1_aggregate.csv")) == 3
    assert pd.read_csv(out_dir / "step2_candidates.csv")["id"].tolist() == [
        "step2",
        "step3",
    ]
    assert pd.read_csv(out_dir / "step3_final.csv")["id"].tolist() == ["step3"]
    step3 = pd.read_csv(out_dir / "step3_final.csv")
    assert step3["judge_confidence"].tolist() == [0.82]
    assert result.set_index("id")["label_source"].to_dict() == {
        "step1": "step1_auto_irrelevant",
        "step2": "step2_auto_label",
        "step3": "step3_judge",
    }
    assert json.loads((out_dir / "summary.json").read_text())["unresolved"] == 0
