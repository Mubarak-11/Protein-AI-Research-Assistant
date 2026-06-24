from pydantic import BaseModel

class StructureRegion(BaseModel):
    start: int
    end: int
    structure: str


class PredictionResult(BaseModel):
    sequence: str
    prediction: str
    confidence: float
    regions: list[StructureRegion]


class BatchPredictionResult(BaseModel):
    results: list[PredictionResult]


#For uniprot too
class GoTerm(BaseModel):
    id: str
    term: str
    evidence: str

class KeywordAnnotation(BaseModel):
    id: str
    category: str
    name: str

class UniProtSearchResult(BaseModel):
    accession: str
    name: str
    protein_name: str
    gene: str
    organism: str
    organism_common_name: str
    length: int
    reviewed: bool
    entry_type: str

class UniProtSearchResponse(BaseModel):
    results: list[UniProtSearchResult]
    total: int

class UniProtEntryResponse(BaseModel):
    accession: str
    name: str
    protein_name: str
    gene: str
    organism: str
    length: int
    sequence: str
    function: list[str]
    go_terms: list[GoTerm]
    keywords: list[KeywordAnnotation]