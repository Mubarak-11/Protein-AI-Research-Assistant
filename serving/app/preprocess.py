#Protein Sequence preprocessing for inference
#Loads vocab.json once and provides encoding/decoding for the model

import json
import torch
from pathlib import Path


#load vocab once at import time
_vocab_path = Path(__file__).resolve().parent.parent / "artifacts" / "vocab.json"

with open(_vocab_path) as f:
    VOCAB = json.load(f)

PRIME2IDX = VOCAB["prime2idx"]          # {"A": 2, "C": 7, ...}
IDX2LAB3 = VOCAB["idx2lab3"]           # {"1": "H", "2": "E", "3": "C"}
LAB3 = VOCAB["lab3"]                    # {"<PAD>": 0, "H": 1, "E": 2, "C": 3}

LAB8 = VOCAB["lab8"]                    
IDX2LAB8 = VOCAB["idx2lab8"]   

MODEL_CONFIG = VOCAB["model_config"]    # {"hidden": 20, ...}
UNK_ID = PRIME2IDX["<UNK>"]
PAD_ID = PRIME2IDX["<PAD>"]

VALID_AA = {k for k in PRIME2IDX if k not in ("<PAD>", "<UNK>")} #checker for valid Amino Acids

def encode_sequence(sequence: str, max_len: int = 512) -> torch.LongTensor:
    """
    Encode an amino acid string into [1, seq_len] tensor of IDs
    """
    seq = sequence.strip().upper()[:max_len]
    ids = [PRIME2IDX.get(aa, UNK_ID) for aa in seq]

    return torch.tensor([ids], dtype= torch.long) #[1, seq_len]

def decode_labels_q3(label_ids: torch.LongTensor) -> list[str]:
    """
    Decode a [1, seq_len] tensor of label IDS back into H/E/C strings
    """
    ids = label_ids[0].tolist()

    return [IDX2LAB3[str(i)] for i in ids if i != PAD_ID]

def decode_labels_q8(label_ids: torch.LongTensor) -> list[str]:
    """
    Decode a [1, seq_len] tensor of label IDS back into H/E/C strings
    """
    ids = label_ids[0].tolist()

    return [IDX2LAB8[str(i)] for i in ids if i != PAD_ID]
