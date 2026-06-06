"""
Model loading and inference for protein secondary structure prediction
"""

import numpy as np
import torch
import torch.nn as nn
from pathlib import Path
import logging
import os
import time
import sys

from protein_model.architecture import lstm_model     #import model
from .preprocess import MODEL_CONFIG     


logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

Device = torch.device("cpu")


#lets load the q3 model weights now
def load_q3_model_weights(weight_path: str) -> torch.nn.Module:

    #unpack config into model constructor
    # checkpoint was trained with bidir=False and 4 output classes (includes PAD)
    model = lstm_model(
        vocab_size = MODEL_CONFIG["vocab_size"],
        num_tags = 4,
        pad_id = MODEL_CONFIG["pad_id"],
        hidden = MODEL_CONFIG["hidden"],
        embed_dim = MODEL_CONFIG["embed_dim"],
        bidir = False
    )

    #load the trained weights into this model instance
    state = torch.load(weight_path, map_location= Device, weights_only = False)
    model.load_state_dict(state)

    model.eval()    #enter eval

    return model.to(Device)     #return model (and put the model on the GPU)

#load q8 model weights now
def load_q8_model_weights(weight_path: str) -> torch.nn.Module:

    #unpack config into model constructor
    # checkpoint was trained with bidir=False and 4 output classes (includes PAD)
    model = lstm_model(
        vocab_size = MODEL_CONFIG["vocab_size"],
        num_tags = 9,
        pad_id = MODEL_CONFIG["pad_id"],
        hidden = MODEL_CONFIG["hidden"],
        embed_dim = MODEL_CONFIG["embed_dim"],
        bidir = True
    )

    #load the trained weights into this model instance
    state = torch.load(weight_path, map_location= Device, weights_only = False)
    model.load_state_dict(state)

    model.eval()    #enter eval

    return model.to(Device)


#Now lets setup the inference to make the predictions
@torch.inference_mode()
def predict(model: torch.nn.Module, x: torch.Tensor) -> tuple[torch.Tensor, float]:

    logits = model(x)   # [1, seq_len, 3]

    probs = torch.softmax(logits, dim= -1)  #[1, seq_len, 3]
    pred = logits.argmax(dim = -1)  # [1, seq_len]

    confidence = probs.max(dim = -1).values.mean().item() #average confidence

    return pred, confidence

#Now for warmup to catch errors/inital testing
def warmup(model: torch.nn.Module, n_features: int) -> None:

    fake = torch.zeros((1, n_features), dtype = torch.long, device = Device)
    predict(model, fake)