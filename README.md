
# TRAE

[![Conference](https://img.shields.io/badge/ICDM-2026%20Applied-blue)](https://www3.cs.stonybrook.edu/~icdm2026/)
[![Dataset](https://img.shields.io/badge/Hugging%20Face-ESG--EN-yellow)](https://huggingface.co/datasets/nowzero/ESG-EN)
[![License](https://img.shields.io/badge/License-Apache%202.0-green)](LICENSE)

**Official implementation of our ICDM 2026 paper:**

**TRAE: Trustworthy Automated ESG Annotation via Multi-Agent Consensus and Confidence Assessment**

TRAE is a multi-agent framework for trustworthy ESG annotation that combines consensus-based decisions, confidence assessment, and agent debate with judge-based evaluation.

This repository provides the official **TRAE annotation pipeline**, including agent prompts, provider adapters, confidence-based routing, and reproducible execution scripts.

The pipeline was used to construct [ESG-EN](https://huggingface.co/datasets/nowzero/ESG-EN), a publicly released English ESG annotation dataset.

## 📦 Resources

| Resource | Description | Link |
|---|---|---|
| **TRAE** | Multi-agent ESG annotation framework and source code. | This repository |
| **ESG-EN** | English ESG dataset constructed using TRAE. | [🤗 Dataset](https://huggingface.co/datasets/nowzero/ESG-EN) |

## 🔍 TRAE Pipeline

TRAE assigns English sentences to four categories:

- **E:** Environmental
- **S:** Social
- **G:** Governance
- **I:** ESG-irrelevant

The annotation process consists of three stages:

1. **Relevance Assessment:** Three independent annotators determine whether a sentence is ESG-related.
2. **ESG Classification:** Annotators assign ESG labels with confidence scores, supporting evidence, and brief rationales.
3. **Debate and Judgment:** Cases outside the highest-confidence route undergo agent debate and judge-based assessment.

### Confidence-Based Annotation

The default configuration reproduces the **ESG-EN Silver+ selection rule**:

- All three annotators must agree on the decision.
- Each supporting confidence score must be at least **0.90**.
- Accepted Step 1 negative decisions are assigned `I`.
- Accepted Step 2 decisions receive the agreed ESG label.
- Remaining cases use human expert labels supplied through `--expert_csv`.

Step 3 debate and judgment responses are preserved as audit traces.

The repository includes the dataset-construction pipeline, prompts, provider adapters, and a deterministic dry run. Experimental ablations, classifier training, and tier-comparison scripts are not included.

## 🚀 Quick Start

### Installation

Python 3.10 or newer is required.

```bash
git clone https://github.com/nowzer0/TRAE.git
cd TRAE

python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Prepare Input Data

TRAE accepts a UTF-8 CSV file containing a `sentence` column.

An `id` column is recommended. If omitted, IDs are generated from row order.

Optional metadata columns are preserved:

- `year`
- `report`
- `sector`
- `industry`
- `company`

### Run Annotation

Set your API key and execute the annotation pipeline:

```bash
export GEMINI_API_KEY="your-api-key"

python run_annotation.py \
  --input examples/sample_input.csv \
  --out_dir runs/sample \
  --provider gemini \
  --model gemini-2.5-flash-lite
```

### Custom Consensus and Confidence

The default thresholds are:

| Parameter | Default | Description |
|---|---|---|
| `--consensus` | `3` | Number of matching annotator votes required |
| `--confidence` | `0.90` | Minimum confidence threshold |

These thresholds can be adjusted for other datasets:

```bash
python run_annotation.py \
  --input examples/sample_input.csv \
  --out_dir runs/custom \
  --consensus 2 \
  --confidence 0.80 \
  --provider openai \
  --model YOUR_MODEL
```

`--consensus` accepts `2` or `3`, and `--confidence` accepts values between `0` and `1`.

**Note:** Step 3 routing follows the released audit procedure. It excludes only Step 2 cases with unanimous (`3/3`) agreement and confidence scores of at least `0.90` from all three annotators.

### Multi-Model Configuration

Different models can be assigned to annotators A, B, C, and the judge.

Edit [`examples/agents_mixed.example.json`](examples/agents_mixed.example.json) and provide the configuration file:

```bash
python run_annotation.py \
  --input examples/sample_input.csv \
  --out_dir runs/mixed \
  --agent_config examples/agents_mixed.example.json
```

API keys are read from environment variables and should never be stored in the configuration file.

### Dry Run

To verify the complete pipeline without making external API calls:

```bash
python run_annotation.py \
  --input examples/sample_input.csv \
  --out_dir runs/dry-run \
  --dry_run
```

## 👤 Human Expert Fallback

For cases that do not satisfy the configured Step 1 or Step 2 acceptance rule, TRAE supports human expert labels through `--expert_csv`.

The CSV file must contain an `id` column and one of the following label columns:

- `expert_label`
- `final_label`
- `label`

Example:

```csv
id,expert_label
1,I
2,E
```

Human labels are applied only to cases that fail the configured automatic acceptance criteria.

## 📁 Outputs

TRAE generates intermediate annotation records, consensus decisions, debate traces, and final annotations.

| File | Description |
|---|---|
| `step1_A/B/C.csv` | Relevance assessment responses from each annotator |
| `step1_aggregate.csv` | Step 1 votes, confidence scores, and routing decisions |
| `step2_A/B/C.csv` | ESG classification responses from each annotator |
| `step2_aggregate.csv` | Step 2 votes, confidence scores, and routing decisions |
| `step3_debate_raw.csv` | Agent debate claims and complete judge responses |
| `step3_final.csv` | Judge decisions, confidence scores, and acceptance results |
| `final_annotations.csv` | Final annotation records |
| `expert_review_queue.csv` | Cases requiring human expert labels |
| `summary.json` | Annotation completion statistics grouped by label source |

The released agent responses and normalized routing decisions are available in the [ESG-EN dataset repository](https://huggingface.co/datasets/nowzero/ESG-EN).

Source sustainability reports are not redistributed with ESG-EN.

## 🔬 Reproducibility

Language-model APIs and hosted model versions may change over time, potentially affecting annotation results.

For reproducibility, we recommend preserving:

- Raw agent responses and judge decisions
- Exact model identifiers
- Package and dependency versions
- Execution dates
- Source code revision

## 📄 License

TRAE source code is released under the [Apache License 2.0](LICENSE).

The ESG-EN dataset is distributed separately under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/), subject to applicable third-party data terms.

## 📝 Citation

If you use TRAE or ESG-EN, please cite our paper:

```bibtex
@inproceedings{lee2026trae,
  title     = {{TRAE}: Trustworthy Automated {ESG} Annotation via Multi-Agent Consensus and Confidence Assessment},
  author    = {Lee, Jaeyoung and Kim, Misuk},
  booktitle = {Proceedings of the 2026 IEEE International Conference on Data Mining (ICDM)},
  year      = {2026}
}
```

*The citation will be updated with the official publication details when available.*
