from pydantic import BaseModel


class ReviewRequest(BaseModel):
    comment: str = ""


class CandidateUpdate(BaseModel):
    name: str
    level1: str
    level2: str
    level3: str
    definition: str
    source: str = ""
    formula: str = ""
    rationale: str = ""
    evidence_text: str = ""
