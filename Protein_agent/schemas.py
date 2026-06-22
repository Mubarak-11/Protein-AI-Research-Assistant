from pydantic import BaseModel

class ResiduePrediction(BaseModel):
    position: int
    amino_acid: str
    structure: str

class PredictionResult(BaseModel):
    sequence: str
    prediction: str
    confidence: float
    per_residue: list[ResiduePrediction]