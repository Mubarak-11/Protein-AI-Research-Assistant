# Agent Context for opencode

## Python Environment
- Default venv: `source /Users/mubarak/.venvs/ml311/bin/activate && python3`
- This venv has: pandas, torch, scikit-learn, numpy, matplotlib, seaborn
- Use this venv for ALL Python commands — system python3 (3.9) does not have the required packages

## Project: Protein Structure Prediction Serving
- Serving project at: `serving/`
- FastAPI app files in: `serving/app/`
- Model checkpoint: `serving/artifacts/best_model_state_for_label3.pth`
- Vocab: `serving/artifacts/vocab.json`
- Training code in: `scripts/`
- Datasets in: `dataset/`

## How to Run Python
```bash
source /Users/mubarak/.venvs/ml311/bin/activate
cd /path/to/project
python3 script.py
```
