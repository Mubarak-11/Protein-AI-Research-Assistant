# Protein Secondary Structure Prediction

A deep learning project that predicts protein secondary structures from amino acid sequences using bidirectional LSTM networks, served via a production-grade FastAPI container.

**Q3 prediction** (H: alpha helix, E: beta strand, C: coil) and **Q8 prediction** (8-class DSSP-style) with batch inference support.

## Project Structure

```
protein_struct_proj/
├── protein_model/                   # Shared model package
│   ├── architecture.py              # lstm_model class (bidirectional LSTM)
│   ├── data_utils.py                # proteinDataset, pad_mask
│   └── preprocess_training.py       # preprocess_proteins (vocab creation)
├── scripts/                         # Training code
│   ├── train.py                     # Train Q3/Q8 models
│   ├── plots.py                     # Evaluation visualizations
│   └── queries/                     # BigQuery analysis SQL
├── serving/                         # FastAPI serving application
│   ├── app/
│   │   ├── main.py                  # FastAPI app with all endpoints
│   │   ├── model.py                 # Model loaders + inference
│   │   ├── preprocess.py            # Inference preprocess (encode/decode)
│   │   └── schemas.py               # Pydantic request/response schemas
│   └── artifacts/
│       ├── vocab.json               # Amino acid + label vocabularies
│       ├── best_model_state_for_label3.pth  # Q3 weights
│       └── best_model_state_for_label8.pth  # Q8 weights
├── dataset/                         # Training/validation/test CSVs
├── Dockerfile                       # Production container
└── requirements.txt                 # Python dependencies
```

## Quick Start — Training

```bash
pip install -r requirements.txt
python -m scripts.train
```

## Quick Start — Serving (Docker)

```bash
docker build -t protein-serving .
docker run -d -p 8000:8000 protein-serving
```

## API Endpoints

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

Input validation enforces `min_length=1`, `max_length=512`, and rejects invalid amino acids before they reach the model.

## Performance

| Dataset | Q3 Accuracy | Q8 Accuracy |
|---------|-------------|-------------|
| CB513   | 76.2%       | 62.1%       |
| TS115   | 75.8%       | 61.7%       |
| CASP12  | 74.9%       | 60.3%       |

## License

MIT
