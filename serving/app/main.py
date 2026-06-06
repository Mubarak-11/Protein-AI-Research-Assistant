# FASTAPI serving for protein secondary structure prediction

import os, logging, time
from pathlib import Path
import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .model import load_q3_model_weights, load_q8_model_weights, predict, warmup
from .preprocess import encode_sequence, decode_labels_q3, decode_labels_q8
from .schemas import PredictRequest, PredictResponse, BatchPredictRequest, BatchPredictResponse

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

CURDIR = Path(__file__).resolve().parent
MODEL_PATH3 = os.getenv("MODEL_PATH3", str(CURDIR.parent / "artifacts" / "best_model_state_for_label3.pth"))
MODEL_PATH8 = os.getenv("MODEL_PATH8", str(CURDIR.parent / "artifacts" / "best_model_state_for_label8.pth"))

#app setup
app = FastAPI(title= "Protein Secondary Strucuture Predicator", version = "1.0")

#load models
model_q3 = load_q3_model_weights(str(MODEL_PATH3))
model_q8 = load_q8_model_weights(str(MODEL_PATH8))

@app.on_event("startup")
def _startup():

    logger.info("Loading Models...")

    #load the model and kick off warmup
    try:
        warmup(model = model_q3, n_features = 20)
        warmup(model = model_q8, n_features = 20)

        logger.info("Models Successfully loaded on startup")

    except Exception as e:
        logger.info(f" Failed to load model: {str(e)}")
        raise


#Endpoints
@app.get("/health")
def health():
    
    q3_ok = model_q3 is not None
    q8_ok = model_q8 is not None

    return {
        "status": "healthy" if q3_ok or q8_ok else "degraded",
        "q3_loaded": q3_ok,
        "q8_loaded": q8_ok
    }

@app.post("/predict/q3", response_model = PredictResponse)
def predict_q3_endpoint(req: PredictRequest):

    try:

        #encode sequence
        tensor = encode_sequence(req.sequence, max_len = 512)

        #tensor -> predict -> (label_ids, confidence)
        pred_ids, confidence = predict(model_q3, tensor)

        #decode labels, label_ids -> List of "H/E/C"
        labels = decode_labels_q3(pred_ids)

        #join list into a single prediction string
        prediction_str = "".join(labels)

        #return
        return {"sequence": req.sequence, 
                "prediction": prediction_str, 
                "confidence": confidence, 
                }
    
    except Exception as e:
        raise HTTPException(status_code = 400, detail = f"classification error: {e}")
    

@app.post("/predict/q8", response_model = PredictResponse)
def predict_q8_endpoint(req: PredictRequest):

    try:

        #encode sequence
        tensor = encode_sequence(req.sequence, max_len = 512)

        #tensor -> predict -> (label_ids, confidence)
        pred_ids, confidence = predict(model_q8, tensor)

        #decode labels, label_ids -> List of "H/E/C"
        labels = decode_labels_q8(pred_ids)

        #join list into a single prediction string
        prediction_str = "".join(labels)

        #return
        return {"sequence": req.sequence, 
                "prediction": prediction_str, 
                "confidence": confidence, 
                }
    
    except Exception as e:
        raise HTTPException(status_code = 400, detail = f"classification error: {e}")
    

@app.post("/predict/batch_q3", response_model = BatchPredictResponse)
def predict_batch_q3(req: BatchPredictRequest):
    
    try:

        results = []

        for seq in req.sequences:
            #encode sequence
            tensor = encode_sequence(seq, max_len = 512)

            #tensor -> predict -> (label_ids, confidence)
            pred_ids, confidence = predict(model_q3, tensor)

            #decode labels, label_ids -> List of "H/E/C"
            labels = decode_labels_q3(pred_ids)

            results.append({
                "sequence": seq,
                "prediction": "".join(labels),
                "confidence": confidence
            })

        #return
        return {"results": results}
    
    except Exception as e:
        raise HTTPException(status_code = 400, detail = f"classification error: {e}")
    

@app.post("/predict/batch_q8", response_model = BatchPredictResponse)
def predict_batch_q8(req: BatchPredictRequest):
    
    try:
        results = []
        for seq in req.sequences:
            #encode sequence
            tensor = encode_sequence(seq, max_len = 512)

            #tensor -> predict -> (label_ids, confidence)
            pred_ids, confidence = predict(model_q8, tensor)

            #decode labels, label_ids -> List of "H/E/C"
            labels = decode_labels_q8(pred_ids)

            #join list into a single prediction string
            prediction_str = "".join(labels)

            results.append({
                "sequence": seq, 
                "prediction": prediction_str, 
                "confidence": confidence,
            })

        #return the result
        return {"results": results}
    
    except Exception as e:
        raise HTTPException(status_code = 400, detail = f"classification error: {e}")
    