from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.mining_inputs import MiningInputSave


DefinitionScope = Literal["input-value", "input-risk", "output-risk", "output-culture"]


class MiningTaskStart(BaseModel):
    task_type: str = "rule_based_first_phase"
    definition_scope: DefinitionScope | None = None
    input_id: int | None = None
    input: MiningInputSave | None = None


class MiningTaskRerunRequest(BaseModel):
    comment: str = ""


class MiningTaskSaveHistoryRequest(BaseModel):
    title: str = Field(default="", max_length=200)
