from __future__ import annotations

import json
import os
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable

import pandas as pd

VALID_LABELS = {"E", "S", "G", "I"}
VALID_RELEVANCE = {"Yes", "No"}


def ensure_dir(path: str | Path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def save_csv(df: pd.DataFrame, path: str | Path) -> None:
    path = Path(path)
    if path.parent:
        ensure_dir(path.parent)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def parse_json(text: Any) -> dict[str, Any]:
    if isinstance(text, dict):
        return text
    if text is None:
        return {}
    raw = str(text).strip()
    try:
        return json.loads(raw)
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except Exception:
        return {}


def complete_json_with_retry(
    client,
    messages: list[dict[str, str]],
    *,
    role: str | None = None,
    max_retries: int = 5,
    backoff_sec: float = 0.5,
    validate: Callable[[dict[str, Any]], bool] | None = None,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        raw = None
        try:
            raw = client.complete(messages, role=role)
        except Exception as exc:
            last_error = exc

        obj = parse_json(raw)
        if obj and (validate(obj) if validate else True):
            return obj

        if attempt < max_retries:
            time.sleep(backoff_sec * (2**attempt))

    if last_error:
        raise last_error
    raise ValueError("LLM response was not valid JSON after retries.")


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "y", "t"}


def norm_rel(value: Any) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip().lower()
    if text in {"yes", "y", "true", "1"}:
        return "Yes"
    if text in {"no", "n", "false", "0"}:
        return "No"
    return None


def norm_label(value: Any) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip().upper()
    if "," in text:
        text = text.split(",", 1)[0].strip()
    if text in {"NONE", "IRRELEVANT"}:
        text = "I"
    return text if text in VALID_LABELS else None


def vote_acceptance(
    votes: list[dict[str, Any]],
    *,
    label_key: str,
    conf_key: str,
    tau: float,
    min_votes: int = 2,
) -> dict[str, Any]:
    labels = [vote.get(label_key) for vote in votes]
    labels = [label for label in labels if label is not None]
    if not labels:
        return {
            "final": None,
            "accepted": False,
            "support_count": 0,
            "support_conf_min": 0.0,
            "agreement": "0/3",
        }

    counts = Counter(labels)
    final, support_count = counts.most_common(1)[0]
    supporter_confs = [
        as_float(vote.get(conf_key), 0.0)
        for vote in votes
        if vote.get(label_key) == final
    ]
    support_conf_min = min(supporter_confs) if supporter_confs else 0.0
    accepted = support_count >= min_votes and support_conf_min >= tau
    agreement = f"{support_count}/{len(votes)}"

    return {
        "final": final,
        "accepted": bool(accepted),
        "support_count": int(support_count),
        "support_conf_min": float(support_conf_min),
        "agreement": agreement,
    }


def metadata_from_row(row: pd.Series, index: int | None = None) -> dict[str, Any]:
    return {
        "id": row.get("id", index),
        "year": row.get("year"),
        "report": row.get("report"),
        "sector": row.get("sector"),
        "industry": row.get("industry"),
        "company": row.get("company"),
        "sentence": row.get("sentence"),
        "label": row.get("label"),
    }


def read_input_csv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "sentence" not in df.columns:
        raise ValueError("Input CSV must contain a 'sentence' column.")
    if "id" not in df.columns:
        df = df.copy()
        df["id"] = range(len(df))
    return df


def read_optional_csv(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path) if os.path.exists(path) else pd.DataFrame()
