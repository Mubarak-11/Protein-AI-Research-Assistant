#Faciliate API contract(REQUEST/RESPONSE)

from typing import Dict, Union, Optional
from pydantic import BaseModel, Field, field_validator

from .preprocess import VALID_AA

class PredictRequest(BaseModel):

    sequence: str = Field(..., min_length=1, max_length=512)

    @field_validator("sequence")
    @classmethod
    def validate_amino_acids(cls, v):
        v = v.strip().upper()
        invalid = set(v) - VALID_AA
        if invalid:
            raise ValueError(f"Invalid amino acid(s): {', '.join(sorted(invalid))}")
        return v

class PredictResponse(BaseModel):

    sequence: str
    prediction: str
    confidence: float

class BatchPredictRequest(BaseModel):
    sequences: list[str] = Field(..., min_length=1, max_length=100)

class BatchPredictResponse(BaseModel):
    results: list[dict]
    