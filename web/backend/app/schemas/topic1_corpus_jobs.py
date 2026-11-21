from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CorpusRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=100000)


class CorpusJobStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    tool: Literal["refinement", "detox", "detection"]
    operation: Literal["refinemodel_clean", "preprocess", "detox", "evaluate", "score"]
    source_name: str = Field(min_length=1, max_length=200)
    records: list[CorpusRecord] = Field(min_length=1, max_length=500)
    model_alias: str = Field(default="", max_length=80)
    confirmed: Literal[True]

    @model_validator(mode="after")
    def validate_scope(self):
        allowed = {"refinement": {"refinemodel_clean"}, "detox": {"preprocess", "detox", "evaluate"}, "detection": {"score"}}
        if self.operation not in allowed[self.tool]:
            raise ValueError("Tool and operation do not match")
        if any(not row.text.strip() or not row.id.strip() for row in self.records):
            raise ValueError("Empty text or ID")
        if len({row.id for row in self.records}) != len(self.records):
            raise ValueError("Duplicate source IDs")
        if sum(len(row.text.encode('utf-8')) for row in self.records) > 2 * 1024 * 1024:
            raise ValueError("Input exceeds 2 MiB")
        if self.tool == "detection" and not self.model_alias:
            raise ValueError("Detection model must be selected")
        if self.tool != "detection" and self.model_alias:
            raise ValueError("Model alias only applies to detection")
        return self
