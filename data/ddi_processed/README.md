---
license: cc-by-nc-4.0
task_categories:
- text-classification
language:
- en
tags:
- medical
- drug-drug-interaction
- pharmacology
- clinical
- ddi
size_categories:
- 1K<n<10K
---

# DDI Corpus Processed

Drug-Drug Interaction (DDI) detection dataset processed from the [SemEval-2013 DDI Corpus](https://github.com/isegura/DDICorpus).

## Dataset Description

This dataset contains drug-drug interaction examples for 5-class classification:

- **MECHANISM**: Mechanistic description of how drugs interact (e.g., inhibition, induction)
- **EFFECT**: Clinical effect of concurrent use (e.g., increased toxicity, decreased efficacy)
- **ADVISE**: Advisory or cautionary information about concurrent use
- **INT**: General interaction without specific type
- **NONE**: No interaction between the drug pair

## Dataset Statistics

| Split | Total | MECHANISM | EFFECT | ADVISE | INT | NONE |
|-------|-------|-----------|--------|--------|-----|------|
| Train | 5,744 | 1,319 (23%) | 1,687 (29%) | 826 (14%) | 189 (3%) | 1,723 (30%) |
| Test | 1,398 | 302 (22%) | 360 (26%) | 221 (16%) | 96 (7%) | 419 (30%) |

## Data Format

Each example contains:
- `sentence`: The original sentence containing drug mentions
- `drug1`: First drug entity
- `drug2`: Second drug entity
- `relation`: Interaction type (MECHANISM, EFFECT, ADVISE, INT, or NONE)
- `source_file`: Original XML source file
- `sentence_id`: Original sentence ID
- `pair_id`: Original pair ID

## Usage

```python
from datasets import load_dataset

dataset = load_dataset("MaziyarPanahi/DDI-Corpus-Processed")
```

## Citation

If you use this dataset, please cite:

```bibtex
@article{herrero2013ddi,
  title={The DDI corpus: An annotated corpus with pharmacological substances and drug--drug interactions},
  author={Herrero-Zazo, Mar{\'\i}a and Segura-Bedmar, Isabel and Mart{\'\i}nez, Paloma and Declerck, Thierry},
  journal={Journal of Biomedical Informatics},
  volume={46},
  number={5},
  pages={914--920},
  year={2013}
}
```

## License

CC BY-NC 4.0 (following original DDI Corpus license)
