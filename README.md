# Protein Secondary Structure Prediction with LSTM Networks

A deep learning project that predicts protein secondary structures from amino acid sequences using bidirectional LSTM networks, served via a production-grade FastAPI container with Q3 and Q8 prediction, batch inference, and input validation.

##  Overview

Protein secondary structure prediction is a fundamental problem in bioinformatics that helps understand protein function and facilitates 3D structure determination. This project implements a neural network approach to classify each amino acid in a protein sequence into secondary structure states:

**Q3 (3-class):**
- **H** — Alpha helix
- **E** — Beta strand (extended)
- **C** — Coil/loop

**Q8 (8-class):**
- **H** — Alpha helix
- **E** — Beta strand
- **C** — Coil/loop (random coil)
- **B** — Beta bridge
- **G** — 3-10 helix
- **I** — Pi helix
- **S** — Bend
- **T** — Turn

##  Features

- **Bidirectional LSTM Architecture**: Captures sequential dependencies in both directions
- **PyTorch Implementation**: Efficient training with GPU acceleration (MPS support for Apple Silicon)
- **Comprehensive Evaluation**: Multiple metrics and visualizations
- **Modular Design**: Clean separation of preprocessing, model, and visualization components
- **Flexible Configuration**: Support for both 3-class (Q3) and 8-class (Q8) prediction
- **FastAPI Serving**: Production-grade REST API with Pydantic input validation
- **Dockerized**: Ready-to-deploy container with CPU-optimized PyTorch
- **Batch Inference**: Predict multiple sequences in a single request

## 📊 Performance

Our model achieves the following performance on standard test sets:

| Dataset | Q3 Accuracy | Q8 Accuracy |
|---------|-------------|-------------|
| CB513   | 76.2%       | 62.1%       |
| TS115   | 75.8%       | 61.7%       |
| CASP12  | 74.9%       | 60.3%       |

*Results may vary based on training parameters and random initialization*

## 🛠️ Installation

### Prerequisites

- Python 3.8+
- PyTorch 1.9+
- Apple Silicon Mac (for MPS acceleration) or CUDA-compatible GPU
- Docker (for containerized serving)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/Mubarak-11/Protein_Secondary_Strucuture_Prediction.git
cd protein-struct-proj
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Download the dataset:
```bash
# Dataset files should be placed in the dataset/ directory
# - training_secondary_structure_train.csv
# - validation_secondary_structure_valid.csv
# - test_secondary_structure_*.csv
```

## 📁 Project Structure

```
protein_struct_proj/
├── protein_model/                   # Shared model package (training + serving)
│   ├── __init__.py
│   ├── architecture.py              # lstm_model class (bidirectional LSTM)
│   ├── data_utils.py                # proteinDataset, pad_mask
│   └── preprocess_training.py       # preprocess_proteins (vocab creation)
├── scripts/                         # Training code
│   ├── __init__.py
│   ├── train.py                     # Train Q3/Q8 models with early stopping
│   ├── plots.py                     # Evaluation visualizations
│   └── queries/                     # BigQuery analysis SQL
│       ├── amino_acid_freq.sql
│       ├── batch_input_view.sql
│       ├── longest_sequence.sql
│       └── q8_class_balance.sql
├── serving/                         # FastAPI serving application
│   ├── __init__.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app with 5 endpoints
│   │   ├── model.py                 # Q3/Q8 model loaders + inference
│   │   ├── preprocess.py            # Inference preprocess (encode/decode)
│   │   └── schemas.py               # Pydantic request/response schemas
│   └── artifacts/
│       ├── vocab.json               # Amino acid + label vocabularies
│       ├── best_model_state_for_label3.pth  # Q3 weights
│       └── best_model_state_for_label8.pth  # Q8 weights
├── dataset/                         # Training/validation/test CSVs
├── Dockerfile                       # Production container
├── requirements.txt                 # Python dependencies
└── README.md                        # This file
```

## 🎯 Quick Start

### Training a Model

```bash
python -m scripts.train
```

This will:
1. Load and preprocess the training data
2. Initialize a bidirectional LSTM model
3. Train for 20 epochs with early stopping
4. Save the best model checkpoint
5. Generate training/validation loss plots

### Serving (Docker)

```bash
docker build -t protein-serving .
docker run -d -p 8000:8000 protein-serving
```

### Serving (Local)

```bash
uvicorn serving.app.main:app --reload
```

##  API Endpoints

### Health Check
```bash
curl http://localhost:8000/health
# {"status":"healthy","q3_loaded":true,"q8_loaded":true}
```

### Q3 Prediction (3-class: H/E/C)
```bash
curl -X POST http://localhost:8000/predict/q3 \
  -H "Content-Type: application/json" \
  -d '{"sequence": "MVLSPADKTNVKAAW"}'
```

### Q8 Prediction (8-class: B/C/E/G/H/I/S/T)
```bash
curl -X POST http://localhost:8000/predict/q8 \
  -H "Content-Type: application/json" \
  -d '{"sequence": "MVLSPADKTNVKAAW"}'
```

### Batch Prediction
```bash
curl -X POST http://localhost:8000/predict/batch_q3 \
  -H "Content-Type: application/json" \
  -d '{"sequences": ["MVLSPADKTNVKAAW", "ACDEFGHIKLMNP"]}'
```

### Input validation
All prediction endpoints enforce `min_length=1`, `max_length=512`, and reject invalid amino acids before they reach the model.

## 📚 Detailed Usage

### Model Architecture

The core model is a bidirectional LSTM with the following components:
- **Embedding Layer**: Converts amino acid indices to dense vectors
- **Bidirectional LSTM**: Processes sequences in both directions
- **Layer Normalization**: Stabilizes training
- **Dropout**: Prevents overfitting
- **Linear Layer**: Maps to output classes

### Training Configuration

Key hyperparameters (configurable in `scripts/train.py`):
- `hidden`: LSTM hidden dimension (default: 20)
- `embed_dim`: Embedding dimension (default: 20)
- `bidir`: Use bidirectional LSTM (default: True)
- `n_epochs`: Maximum training epochs (default: 20)
- `batch_size`: Training batch size (default: 16)
- `lr`: Learning rate (default: 0.01)

### Evaluation Metrics

The model is evaluated using:
- **Q3 Accuracy**: 3-class secondary structure accuracy
- **Q8 Accuracy**: 8-class secondary structure accuracy
- **Per-class Precision/Recall/F1**: Detailed performance metrics
- **Confusion Matrix**: Error analysis

### Generating Visualizations

```bash
python -m scripts.plots best_model_state_for_label3.pth dataset/test_secondary_structure_cb513.csv
```

## 🔬 Advanced Features

### Custom Dataset Support

To use your own protein data:
1. Format your CSV with columns: `seq` (amino acid sequence), `sst3` and `sst8` (secondary structure)
2. Place in the `dataset/` directory
3. Update file paths in `scripts/train.py`

### GPU Acceleration

The code automatically detects and uses available hardware:
- **MPS**: Apple Metal Performance Shaders (Apple Silicon)
- **CUDA**: NVIDIA GPUs
- **CPU**: Fallback for systems without GPU acceleration

## 📈 Model Performance Analysis

### Visualization Tools

The `scripts/plots.py` module provides comprehensive visualization:
1. **Prediction Comparison**: Side-by-side true vs. predicted structures
2. **Confusion Matrix**: Detailed error analysis
3. **Length Performance**: Accuracy vs. sequence length
4. **Class Metrics**: Per-class precision, recall, F1-score

### Error Analysis

Common failure modes and solutions:
- **Short sequences**: May lack sufficient context
- **Rare amino acids**: Limited training examples
- **Boundary regions**: Transitions between secondary structures

## 🤝 Contributing

Contributions are welcome. To contribute:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🙏 Acknowledgments

- **Dataset**: CB513, TS115, and CASP12 benchmark datasets
- **PyTorch**: Deep learning framework
- **Scikit-learn**: Machine learning evaluation metrics

## 📚 References

1. Jones, D. T. (1999). Protein secondary structure prediction based on position-specific scoring matrices. *Journal of Molecular Biology*, 292(2), 195-202.
2. Hou, J., Adhikari, B., & Cheng, J. (2018). DeepSF: deep convolutional neural network for mapping protein sequences to folds. *Bioinformatics*, 34(8), 1295-1303.
3. Heffernan, R., Yang, Y., Paliwal, K. K., & Zhou, Y. (2017). Capturing non-local interactions in protein sequences using deep learning. *Scientific Reports*, 7(1), 1-11.

---

⭐ If you find this project useful, please consider giving it a star!
