from pydantic import BaseModel, ConfigDict, Field


class LiveBatchStartRequest(BaseModel):
    pack_id: str = "demo-zh-8"
    max_samples: int | None = None


class CultureGuardrailBatchRequest(BaseModel):
    candidate_responses_path: str = ""
    limit: int | None = None
    model_id: str = "qwen3.5-9b"
    language: str = "zh"
    generate_neutral_candidate: bool = False


class ComplianceEditRequest(BaseModel):
    text: str
    request_id: str = ""
    pre_safety_label: str = "unsafe"
    language: str = "zh"


class DemoPackOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    pack_id: str
    title: str
    model_id: str = ""
    language: str = "zh"
    sample_count: int = 0


class LiveBatchStartOut(BaseModel):
    job_id: str
    status: str = "pending"
    pack_id: str
    sample_count: int


class LiveProgressOut(BaseModel):
    detect_done: int = 0
    detect_total: int = 0
    rewrite_done: int = 0
    rewrite_total: int = 0


class LiveSampleOut(BaseModel):
    id: str
    prompt: str = ""
    response: str = ""
    detect_status: str = "pending"
    pred_safe_type: str | None = None
    pred_risk_level: str | None = None
    pred_category: str | None = None
    pred_category_code: str | None = None
    risk_evidence: list = Field(default_factory=list)
    rewrite_status: str = "pending"
    disposition: str = ""
    edited_text: str = ""
    post_safety_label: str = ""
    error: str | None = None


class LiveBatchJobOut(BaseModel):
    job_id: str
    pack_id: str
    status: str
    source: str = "live"
    progress: LiveProgressOut
    samples: list[LiveSampleOut] = Field(default_factory=list)
