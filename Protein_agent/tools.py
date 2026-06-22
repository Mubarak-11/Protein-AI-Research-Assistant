""" Tools for protein agent"""

import torch
import torch.nn as nn
import os
import logging

from pathlib import Path

#import our API
from serving.app.model import load_q3_model_weights, load_q8_model_weights, predict
from serving.app.preprocess import encode_sequence, decode_labels_q3, decode_labels_q8

_AGENT_DIR = Path(__file__).resolve().parent    #agent/
ARTIFACT_DIR = _AGENT_DIR.parent / "serving" / "artifacts"

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

#Lazy load  models
_q3_model: nn.Module | None = None
_q8_model: nn.Module | None = None

def _get_q3_model() -> nn.Module:
    global _q3_model
    if _q3_model is None:
        
        logger.info(f" Loading Q3 Model Weight")
        _q3_model = load_q3_model_weights(str(ARTIFACT_DIR / "best_model_state_for_label3.pth"))

    return _q3_model


def _get_q8_model() -> nn.Module:
    global _q8_model
    if _q8_model is None:
        
        logger.info(f" Loading Q8 Model Weight")
        _q8_model = load_q8_model_weights(str(ARTIFACT_DIR / "best_model_state_for_label8.pth"))

    return _q8_model
        

#Q3 prediction
def predict_q3(seq:str) -> dict:
    """Predict 3-class secondary structure (H=helix, E=strand, C=coil) for a protein sequence"""

    try:

        #encode sequence
        tensor = encode_sequence(seq, max_len = 512)

        #tensor -> predict -> (label_ids, confidence)
        pred_ids, confidence = predict(_get_q3_model(), tensor)

        #decode labels, label_ids -> List of "H/E/C"
        labels = decode_labels_q3(pred_ids)

        #join list into a single prediction string
        prediction_str = "".join(labels)

        #return
        return {"sequence": seq, 
                "prediction": prediction_str, 
                "confidence": confidence, 
                }
    
    except Exception as e:
        raise ValueError(f"Q3 Prediction failed {e}")


def predict_q8(seq: str) -> dict:
    """Predict 8-class secondary structure (B/C/E/G/H/I/S/T) for a protein sequence"""
    
    try:

        #encode sequence
        tensor = encode_sequence(seq, max_len = 512)

        #tensor -> predict -> (label_ids, confidence)
        pred_ids, confidence = predict(_get_q8_model(), tensor)

        #decode labels, label_ids -> List of "H/E/C"
        labels = decode_labels_q8(pred_ids)

        #join list into a single prediction string
        prediction_str = "".join(labels)

        #return
        return {"sequence": seq, 
                "prediction": prediction_str, 
                "confidence": confidence, 
                }
    
    except Exception as e:
        raise ValueError( f"Q8 Prediction failed: {e}")
    
def batch_predict_q3(seqs: list[str]) -> dict:
    """Batch predict Q3 for up to 100 sequences"""

    try:

        results = []

        for seq in seqs:
            #encode sequence
            tensor = encode_sequence(seq, max_len = 512)

            #tensor -> predict -> (label_ids, confidence)
            pred_ids, confidence = predict(_get_q3_model(), tensor)

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
        raise ValueError(f"Q3 Batch Prediction failed {e}")


def batch_predict_q8(seqs: list[str]) -> dict:
    """Batch predict Q8 for up to 100 sequences"""
    
    try:

        results = []

        for seq in seqs:
            #encode sequence
            tensor = encode_sequence(seq, max_len = 512)

            #tensor -> predict -> (label_ids, confidence)
            pred_ids, confidence = predict(_get_q8_model(), tensor)

            #decode labels, label_ids -> List of "H/E/C"
            labels = decode_labels_q8(pred_ids)

            results.append({
                "sequence": seq,
                "prediction": "".join(labels),
                "confidence": confidence
            })

        #return
        return {"results": results}
    
    except Exception as e:
        raise ValueError(f"Q8 Batch Prediction failed {e}")
    

