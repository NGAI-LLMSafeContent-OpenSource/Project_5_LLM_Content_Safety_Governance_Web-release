from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


PRIVATE_DYNBENCH_REPOSITORY = (
    "Project_2_Flywheel_on_Anomaly_Detection_Tracking_Correction"
)

Readiness = Literal["ready", "missing", "offline", "invalid"]
ShowcaseMode = Literal["dynamic", "prerun", "static-only"]
LifecycleCaseId = Literal["cbrne", "explicit-harmful-injection"]


class ShowcaseStatus(BaseModel):
    static_assets: Readiness
    prerun: Readiness
    dynbench: Readiness
    mode: ShowcaseMode


class LifecycleCase(BaseModel):
    id: LifecycleCaseId
    title: str
    file: str
    case_count: int = Field(ge=0)


class DatasetStats(BaseModel):
    total: int = Field(ge=0)
    labels: dict[str, int] = Field(default_factory=dict)
    l2_categories: dict[str, int] = Field(default_factory=dict)
    source_benchmarks: dict[str, int] = Field(default_factory=dict)
    seed_types: dict[str, int] = Field(default_factory=dict)


class CbrneStats(BaseModel):
    full: DatasetStats
    filtered: DatasetStats


class PrerunMetadata(BaseModel):
    run_id: str
    created_at: datetime
    repository: Literal[
        "Project_2_Flywheel_on_Anomaly_Detection_Tracking_Correction"
    ]
    commit: str
    moderators: list[str]
    budget: int = Field(ge=1, le=40)
    sampling_seed: int
    attack_strategies: list[str]
    metrics: dict[str, float | int]
    report_file: str
    lifecycle_file: str
    lifecycle_available: bool = True

    @field_validator("commit")
    @classmethod
    def validate_commit(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("commit must not be empty")
        return normalized


class PrerunSummary(BaseModel):
    metadata: PrerunMetadata
    report: str
    lifecycle: list[dict[str, Any]]


class ImportResult(BaseModel):
    run_id: str
    output_dir: Path
    files: list[str]
    lifecycle_available: bool


class ShowcaseStatusResponse(ShowcaseStatus):
    dynbench_webui_url: str | None = None


class ShowcaseOverview(BaseModel):
    title: str
    cbrne_full_total: int = Field(ge=0)
    cbrne_filtered_total: int = Field(ge=0)
    lifecycle_case_total: int = Field(ge=0)
    lifecycle_cases: list[LifecycleCase]
    workflow: list[str]
    status: ShowcaseStatusResponse


class PrerunResponse(BaseModel):
    metadata: PrerunMetadata
    lifecycle: list[dict[str, Any]]


class PrerunReportResponse(BaseModel):
    report: str
