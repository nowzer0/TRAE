# TRAE

Official implementation of **TRAE: Trustworthy Automated ESG Annotation via
Multi-Agent Consensus and Confidence Assessment** (ICDM 2026).

TRAE is the annotation pipeline used to construct
[ESG-EN](https://huggingface.co/datasets/nowzero/ESG-EN). Given English
sentences, it records the responses of three annotators and assigns one of four
labels:

- `E`: Environmental
- `S`: Social
- `G`: Governance
- `I`: ESG-irrelevant

## Pipeline

1. **Relevance assessment:** three annotators decide whether a sentence is
   ESG-related.
2. **ESG classification:** the annotators assign an `E`, `S`, `G`, or `I`
   label with confidence, evidence, and a short rationale.
3. **Debate and judgment:** cases outside the highest-confidence route are
   reviewed through three agent claims and a judge decision.

The default release setting reproduces the ESG-EN Silver+ selection rule:
three matching votes with every supporting confidence at least `0.90`. A
Step 1 `No` decision becomes `I`; an accepted Step 2 decision becomes its
agreed label; remaining rows use the human label supplied with `--expert_csv`.
Step 3 responses are retained as audit traces.

This repository contains the dataset-construction pipeline, prompts, provider
adapters, and a deterministic dry run. Experimental ablations, classifier
training, and tier-comparison scripts are excluded.

## Installation

Python 3.10 or newer is required.

```bash
git clone https://github.com/nowzer0/TRAE.git
cd TRAE

python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Quick start

The input must be a UTF-8 CSV containing a `sentence` column. An `id` column is
recommended and is generated from row order when absent. The optional `year`,
`report`, `sector`, `industry`, and `company` columns are preserved.

```bash
export GEMINI_API_KEY="your-api-key"

python run_annotation.py \
  --input examples/sample_input.csv \
  --out_dir runs/sample \
  --provider gemini \
  --model gemini-2.5-flash-lite
```

The default values for `--consensus` and `--confidence` are `3` and `0.90`.
They can be changed when applying TRAE to another dataset:

```bash
python run_annotation.py \
  --input examples/sample_input.csv \
  --out_dir runs/custom \
  --consensus 2 \
  --confidence 0.80 \
  --provider openai \
  --model YOUR_MODEL
```

`--consensus` accepts `2` or `3`, and `--confidence` accepts a value from `0`
to `1`. Step 3 routing follows the released audit procedure and therefore
always excludes only Step 2 cases with `3/3` agreement and all three confidence
scores at least `0.90`.

To use different models for annotators A, B, C, and the judge, edit
[`examples/agents_mixed.example.json`](examples/agents_mixed.example.json) and
pass it with `--agent_config`. API keys are read from environment variables and
must not be written into the JSON file.

```bash
python run_annotation.py \
  --input examples/sample_input.csv \
  --out_dir runs/mixed \
  --agent_config examples/agents_mixed.example.json
```

To verify the complete pipeline without making API calls:

```bash
python run_annotation.py \
  --input examples/sample_input.csv \
  --out_dir runs/dry-run \
  --dry_run
```

## Human fallback

`--expert_csv` accepts a CSV containing `id` and one of `expert_label`,
`final_label`, or `label`. Human labels are used only for rows that do not pass
the configured Step 1 or Step 2 rule.

```csv
id,expert_label
1,I
2,E
```

## Outputs

| File | Contents |
|---|---|
| `step1_A/B/C.csv` | Relevance response from each annotator |
| `step1_aggregate.csv` | Step 1 votes, confidence, acceptance, and route |
| `step2_A/B/C.csv` | ESG-label response from each annotator |
| `step2_aggregate.csv` | Step 2 votes, confidence, acceptance, and route |
| `step3_debate_raw.csv` | Agent claims and complete judge response |
| `step3_final.csv` | Judge label, confidence, and acceptance |
| `final_annotations.csv` | Final record for every input sentence |
| `expert_review_queue.csv` | Rows that still require a human label |
| `summary.json` | Completion counts grouped by label source |

The released agent responses and normalized route decisions are available in
the [ESG-EN dataset repository](https://huggingface.co/datasets/nowzero/ESG-EN).
The source sustainability reports are not distributed with ESG-EN.

## Reproducibility

Language-model APIs and hosted model versions can change over time. Preserve
the raw response columns, exact model identifiers, package environment,
execution date, and code revision for each run.

## Citation

If you use TRAE or ESG-EN, please cite:

```bibtex
@inproceedings{lee2026trae,
  title     = {TRAE: Trustworthy Automated ESG Annotation via Multi-Agent Consensus and Confidence Assessment},
  author    = {Lee, Jaeyoung and Kim, Misuk},
  booktitle = {Proceedings of the 2026 IEEE International Conference on Data Mining (ICDM)},
  year      = {2026}
}
```

## License

TRAE source code is licensed under the
[Apache License 2.0](LICENSE). ESG-EN is distributed separately under the
[CC BY-NC 4.0 license](https://creativecommons.org/licenses/by-nc/4.0/).
