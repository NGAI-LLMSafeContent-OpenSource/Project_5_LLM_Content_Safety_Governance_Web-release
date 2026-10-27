from pydantic import BaseModel, Field


class Topic1MiningOptions(BaseModel):
    task_type: str = "topic1_indicator_mining"
    subject_area: str = "topic1"
    use_predefined_framework: bool = True
    include_policy_analysis: bool = True


class Topic1MatchedPath(BaseModel):
    level1: str
    level2: str
    level3: str
    name: str
    confidence: float
    hits: list[str] = Field(default_factory=list)
    matched_keywords: list[str] = Field(default_factory=list)
    evidence_snippets: list[str] = Field(default_factory=list)


class Topic1CandidateIndicator(BaseModel):
    definition_type: str
    name: str
    level1: str
    level2: str
    level3: str
    definition: str
    source: str
    formula: str = ""
    rationale: str = ""
    evidence_text: str = ""
    confidence: float = 0.0


class Topic1MiningStats(BaseModel):
    input_text_count: int = 0
    matched_path_count: int = 0
    candidate_count: int = 0
    dropped_duplicate_count: int = 0


class Topic1TaskArtifact(BaseModel):
    artifact_type: str
    content: dict | list


class Topic1TaskArtifactsResponse(BaseModel):
    task_id: str
    artifacts: list[Topic1TaskArtifact] = Field(default_factory=list)
