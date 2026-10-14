from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from tqdm.auto import tqdm

from .config import ROLES, RuntimeConfig, Thresholds
from .llm_client import LLMClient
from .prompts import (
    ARGUE_USER,
    DEBATE_SYSTEM,
    JUDGE_SYSTEM,
    JUDGE_USER,
    LABEL_SYSTEM,
    LABEL_USER,
    RELEVANCE_SYSTEM,
    RELEVANCE_USER,
)
from .utils import (
    as_bool,
    as_float,
    complete_json_with_retry,
    ensure_dir,
    metadata_from_row,
    norm_label,
    norm_rel,
    read_input_csv,
    read_optional_csv,
    save_csv,
    vote_acceptance,
)


BASE_COLUMNS = ["id", "year", "report", "sector", "industry", "company", "sentence", "label"]


def _safe_base(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in BASE_COLUMNS:
        if col not in out.columns:
            out[col] = None
    return out[BASE_COLUMNS]


def _print_agents(runtime: RuntimeConfig) -> None:
    print("Agents:")
    for role in (*ROLES, "judge"):
        agent = runtime.agent(role)
        print(f"  {role}: {agent.provider}/{agent.model}")


def _validate_relevance(obj: dict[str, Any]) -> bool:
    return norm_rel(obj.get("relevance")) is not None and 0.0 <= as_float(obj.get("confidence")) <= 1.0


def _validate_label(obj: dict[str, Any]) -> bool:
    return norm_label(obj.get("label")) is not None and 0.0 <= as_float(obj.get("confidence")) <= 1.0


def _validate_judge(obj: dict[str, Any]) -> bool:
    return norm_label(obj.get("final_label")) is not None


def run_step1(
    input_csv: str | Path,
    out_dir: str | Path,
    runtime: RuntimeConfig,
    thresholds: Thresholds,
) -> pd.DataFrame:
    out_dir = Path(out_dir)
    ensure_dir(out_dir)
    df = read_input_csv(input_csv)
    client = LLMClient(runtime)

    print(f"Step 1 relevance assessment: {len(df)} rows")
    _print_agents(runtime)

    per_role: dict[str, pd.DataFrame] = {}
    for role in ROLES:
        records = []
        for idx, row in tqdm(df.iterrows(), total=len(df), desc=f"step1 {role}"):
            sentence = str(row.get("sentence", ""))
            messages = [
                {"role": "system", "content": RELEVANCE_SYSTEM},
                {
                    "role": "user",
                    "content": RELEVANCE_USER.format(role=role, sentence=sentence),
                },
            ]
            try:
                obj = complete_json_with_retry(
                    client,
                    messages,
                    role=role,
                    max_retries=5,
                    validate=_validate_relevance,
                )
            except Exception as exc:
                obj = {
                    "relevance": None,
                    "confidence": 0.0,
                    "keywords": [],
                    "rationale": f"ERROR: {exc}",
                }

            rec = metadata_from_row(row, idx)
            rec.update(
                {
                    f"rel_{role}": norm_rel(obj.get("relevance")),
                    f"conf_{role}": as_float(obj.get("confidence")),
                    f"keywords_{role}": "|".join(obj.get("keywords", []))
                    if isinstance(obj.get("keywords"), list)
                    else str(obj.get("keywords", "")),
                    f"rationale_{role}": obj.get("rationale"),
                    f"raw_{role}": json.dumps(obj, ensure_ascii=False),
                }
            )
            records.append(rec)

        per_role[role] = pd.DataFrame(records)
        save_csv(per_role[role], out_dir / f"step1_{role}.csv")

    combined = per_role[ROLES[0]][BASE_COLUMNS].copy()
    for role in ROLES:
        drop_cols = [col for col in BASE_COLUMNS if col != "id"]
        combined = combined.merge(per_role[role].drop(columns=drop_cols), on="id", how="left")
    save_csv(combined, out_dir / "step1_all.csv")

    agg_records = []
    for _, row in tqdm(combined.iterrows(), total=len(combined), desc="step1 aggregate"):
        votes = [
            {"label": norm_rel(row.get(f"rel_{role}")), "confidence": as_float(row.get(f"conf_{role}"))}
            for role in ROLES
        ]
        result = vote_acceptance(
            votes,
            label_key="label",
            conf_key="confidence",
            tau=thresholds.tau_rel,
            min_votes=thresholds.min_votes,
        )
        rel_final = result["final"]
        route = "auto_irrelevant" if result["accepted"] and rel_final == "No" else "step2"
        rec = {col: row.get(col) for col in BASE_COLUMNS}
        rec.update(
            {
                "rel_votes": ";".join(vote["label"] or "NA" for vote in votes),
                "rel_final": rel_final,
                "rel_accepted": result["accepted"],
                "rel_agreement": result["agreement"],
                "rel_support_count": result["support_count"],
                "rel_support_conf_min": result["support_conf_min"],
                "route_after_step1": route,
            }
        )
        agg_records.append(rec)

    agg = pd.DataFrame(agg_records)
    save_csv(agg, out_dir / "step1_aggregate.csv")
    print(f"Step 1 saved to {out_dir}")
    return agg


def run_step2(
    input_csv: str | Path,
    out_dir: str | Path,
    runtime: RuntimeConfig,
    thresholds: Thresholds,
) -> pd.DataFrame:
    out_dir = Path(out_dir)
    ensure_dir(out_dir)
    df = read_input_csv(input_csv)
    step1_path = out_dir / "step1_aggregate.csv"
    if not step1_path.exists():
        raise FileNotFoundError("Step 1 output is required before running Step 2.")
    step1 = pd.read_csv(step1_path)
    candidate_ids = set(
        step1.loc[step1["route_after_step1"] == "step2", "id"].astype(str)
    )
    candidates = df[df["id"].astype(str).isin(candidate_ids)].copy()
    save_csv(candidates, out_dir / "step2_candidates.csv")

    print(f"Step 2 ESG factor labeling: {len(candidates)} rows")
    client = LLMClient(runtime)
    per_role: dict[str, pd.DataFrame] = {}

    for role in ROLES:
        records = []
        for idx, row in tqdm(candidates.iterrows(), total=len(candidates), desc=f"step2 {role}"):
            sentence = str(row.get("sentence", ""))
            messages = [
                {"role": "system", "content": LABEL_SYSTEM},
                {
                    "role": "user",
                    "content": LABEL_USER.format(role=role, sentence=sentence),
                },
            ]
            try:
                obj = complete_json_with_retry(
                    client,
                    messages,
                    role=role,
                    max_retries=5,
                    validate=_validate_label,
                )
            except Exception as exc:
                obj = {
                    "label": None,
                    "confidence": 0.0,
                    "span": "",
                    "rationale": f"ERROR: {exc}",
                }

            rec = metadata_from_row(row, idx)
            rec.update(
                {
                    f"lab_{role}": norm_label(obj.get("label")),
                    f"conf_{role}": as_float(obj.get("confidence")),
                    f"span_{role}": obj.get("span"),
                    f"rationale_{role}": obj.get("rationale"),
                    f"raw_{role}": json.dumps(obj, ensure_ascii=False),
                }
            )
            records.append(rec)

        per_role[role] = pd.DataFrame(records)
        if per_role[role].empty:
            per_role[role] = pd.DataFrame(
                columns=BASE_COLUMNS
                + [
                    f"lab_{role}",
                    f"conf_{role}",
                    f"span_{role}",
                    f"rationale_{role}",
                    f"raw_{role}",
                ]
            )
        save_csv(per_role[role], out_dir / f"step2_{role}.csv")

    combined = _safe_base(candidates)
    for role in ROLES:
        drop_cols = [col for col in BASE_COLUMNS if col != "id" and col in per_role[role].columns]
        combined = combined.merge(per_role[role].drop(columns=drop_cols), on="id", how="left")
    save_csv(combined, out_dir / "step2_all.csv")

    agg_records = []
    for _, row in tqdm(combined.iterrows(), total=len(combined), desc="step2 aggregate"):
        votes = [
            {"label": norm_label(row.get(f"lab_{role}")), "confidence": as_float(row.get(f"conf_{role}"))}
            for role in ROLES
        ]
        result = vote_acceptance(
            votes,
            label_key="label",
            conf_key="confidence",
            tau=thresholds.tau_lab,
            min_votes=thresholds.min_votes,
        )
        rec = {col: row.get(col) for col in BASE_COLUMNS}
        rec.update(
            {
                "lab_votes": ";".join(vote["label"] or "NA" for vote in votes),
                "lab_final_initial": result["final"],
                "lab_accepted": result["accepted"],
                "lab_agreement": result["agreement"],
                "lab_support_count": result["support_count"],
                "lab_support_conf_min": result["support_conf_min"],
                "need_debate": not result["accepted"],
            }
        )
        agg_records.append(rec)

    agg = pd.DataFrame(
        agg_records,
        columns=BASE_COLUMNS
        + [
            "lab_votes",
            "lab_final_initial",
            "lab_accepted",
            "lab_agreement",
            "lab_support_count",
            "lab_support_conf_min",
            "need_debate",
        ],
    )
    save_csv(agg, out_dir / "step2_aggregate.csv")
    print(f"Step 2 saved to {out_dir}")
    return agg


def run_step3(
    out_dir: str | Path,
    runtime: RuntimeConfig,
) -> pd.DataFrame:
    out_dir = Path(out_dir)
    step2_all = pd.read_csv(out_dir / "step2_all.csv")
    step2_agg = pd.read_csv(out_dir / "step2_aggregate.csv")
    if step2_agg.empty:
        debate_df = pd.DataFrame(
            columns=["id", "sentence", "claims_json", "verdict_json"]
        )
        final_df = pd.DataFrame(
            columns=[
                "id",
                "sentence",
                "lab_final",
                "judge_rationale",
            ]
        )
        save_csv(debate_df, out_dir / "step3_debate_raw.csv")
        save_csv(final_df, out_dir / "step3_final.csv")
        print(f"Step 3 debate and judge: 0 rows")
        return final_df

    df = step2_all.merge(
        step2_agg[["id", "need_debate", "lab_final_initial"]],
        on="id",
        how="left",
    )
    target = df[df["need_debate"].map(as_bool)].copy()
    print(f"Step 3 debate and judge: {len(target)} rows")

    client = LLMClient(runtime)
    debate_records = []
    final_records = []

    for _, row in tqdm(target.iterrows(), total=len(target), desc="step3 debate+judge"):
        sentence = str(row.get("sentence", ""))
        claims = []
        for role in ROLES:
            label = row.get(f"lab_{role}")
            span = row.get(f"span_{role}")
            rationale = row.get(f"rationale_{role}")
            messages = [
                {"role": "system", "content": DEBATE_SYSTEM},
                {
                    "role": "user",
                    "content": ARGUE_USER.format(
                        role=role,
                        label=label,
                        span=span,
                        rationale=rationale,
                        sentence=sentence,
                    ),
                },
            ]
            try:
                claim = complete_json_with_retry(client, messages, role=role, max_retries=5)
            except Exception as exc:
                claim = {"claim": "", "error": str(exc)}
            claim.update(
                {
                    "role": role,
                    "initial_label": label,
                    "initial_span": span,
                    "initial_rationale": rationale,
                }
            )
            claims.append(claim)

        claims_json = json.dumps(claims, ensure_ascii=False)
        judge_messages = [
            {"role": "system", "content": JUDGE_SYSTEM},
            {
                "role": "user",
                "content": JUDGE_USER.format(sentence=sentence, claims=claims_json),
            },
        ]
        try:
            verdict = complete_json_with_retry(
                client,
                judge_messages,
                role="judge",
                max_retries=5,
                validate=_validate_judge,
            )
        except Exception as exc:
            verdict = {"final_label": None, "rationale": f"ERROR: {exc}"}

        final_label = norm_label(verdict.get("final_label"))

        debate_records.append(
            {
                "id": row.get("id"),
                "sentence": sentence,
                "claims_json": claims_json,
                "verdict_json": json.dumps(verdict, ensure_ascii=False),
            }
        )
        final_records.append(
            {
                "id": row.get("id"),
                "sentence": sentence,
                "lab_final": final_label,
                "judge_rationale": verdict.get("rationale") or verdict.get("notes"),
            }
        )

    debate_df = pd.DataFrame(debate_records)
    final_df = pd.DataFrame(final_records)
    save_csv(debate_df, out_dir / "step3_debate_raw.csv")
    save_csv(final_df, out_dir / "step3_final.csv")
    print(f"Step 3 saved to {out_dir}")
    return final_df


def _index_by_id(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "id" not in df.columns:
        return pd.DataFrame()
    out = df.copy()
    out["_id_key"] = out["id"].astype(str)
    return out.set_index("_id_key", drop=False)


def build_final_dataset(
    input_csv: str | Path,
    out_dir: str | Path,
) -> pd.DataFrame:
    out_dir = Path(out_dir)
    df = read_input_csv(input_csv)
    step1 = _index_by_id(read_optional_csv(out_dir / "step1_aggregate.csv"))
    step2 = _index_by_id(read_optional_csv(out_dir / "step2_aggregate.csv"))
    step3 = _index_by_id(read_optional_csv(out_dir / "step3_final.csv"))

    final_records = []
    for idx, row in df.iterrows():
        rec = metadata_from_row(row, idx)
        row_id = str(rec["id"])
        final_label = None
        confidence = None
        label_source = "unresolved"
        processing_path = "unresolved"

        s1 = step1.loc[row_id] if not step1.empty and row_id in step1.index else None
        s2 = step2.loc[row_id] if not step2.empty and row_id in step2.index else None
        s3 = step3.loc[row_id] if not step3.empty and row_id in step3.index else None

        if s1 is not None and as_bool(s1.get("rel_accepted")) and s1.get("rel_final") == "No":
            final_label = "I"
            confidence = as_float(s1.get("rel_support_conf_min"))
            label_source = "step1_auto_irrelevant"
            processing_path = "Step1: accepted No -> I"
        elif s2 is not None and as_bool(s2.get("lab_accepted")):
            final_label = norm_label(s2.get("lab_final_initial"))
            confidence = as_float(s2.get("lab_support_conf_min"))
            label_source = "step2_auto_label"
            processing_path = "Step1: routed -> Step2: accepted"
        elif s3 is not None and norm_label(s3.get("lab_final")) is not None:
            final_label = norm_label(s3.get("lab_final"))
            label_source = "step3_judge"
            processing_path = "Step1: routed -> Step2: unresolved -> Step3: judge"

        rec.update(
            {
                "final_label": final_label,
                "confidence": confidence,
                "label_source": label_source,
                "processing_path": processing_path,
                "unresolved": final_label is None,
            }
        )
        final_records.append(rec)

    final_df = pd.DataFrame(final_records)
    unresolved_df = final_df[final_df["unresolved"] == True].copy()
    save_csv(final_df, out_dir / "final_annotations.csv")
    save_csv(unresolved_df, out_dir / "unresolved_annotations.csv")

    summary = {
        "total": int(len(final_df)),
        "completed": int(final_df["final_label"].notna().sum()),
        "unresolved": int(unresolved_df.shape[0]),
        "by_source": final_df["label_source"].value_counts(dropna=False).to_dict(),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Final annotations saved to {out_dir / 'final_annotations.csv'}")
    print(f"Unresolved annotations saved to {out_dir / 'unresolved_annotations.csv'}")
    return final_df


def run_pipeline(
    input_csv: str | Path,
    out_dir: str | Path,
    runtime: RuntimeConfig,
    thresholds: Thresholds,
) -> pd.DataFrame:
    run_step1(input_csv, out_dir, runtime, thresholds)
    run_step2(input_csv, out_dir, runtime, thresholds)
    run_step3(out_dir, runtime)
    return build_final_dataset(input_csv, out_dir)
