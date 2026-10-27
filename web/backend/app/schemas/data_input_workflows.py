from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


WorkflowStatus = Literal["draft", "submitted", "archived"]
WorkflowSource = Literal["wizard", "input_guardrail"]


class DataInputWorkflowSaveRequest(BaseModel):
    workflow_id: str = ""
    title: str = ""
    source: WorkflowSource = "wizard"
    payload: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    asset_refs: dict[str, Any] = Field(default_factory=dict)


class DataInputWorkflowSaveResponse(BaseModel):
    workflowId: str
    status: WorkflowStatus
    savedAt: datetime
    title: str


class DataInputWorkflowDetailResponse(BaseModel):
    workflowId: str
    title: str
    status: WorkflowStatus
    source: str
    payload: dict[str, Any]
    summary: dict[str, Any]
    assetRefs: dict[str, Any]
    createdAt: datetime
    updatedAt: datetime
    submittedAt: datetime | None = None


class DataInputWorkflowListItem(BaseModel):
    workflowId: str
    title: str
    status: WorkflowStatus
    source: str
    summary: dict[str, Any]
    assetRefs: dict[str, Any]
    createdAt: datetime
    updatedAt: datetime
    submittedAt: datetime | None = None


class DataInputWorkflowListResponse(BaseModel):
    items: list[DataInputWorkflowListItem] = Field(default_factory=list)
