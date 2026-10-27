from pydantic import BaseModel, Field


class MiningInputSave(BaseModel):
    definition_type: str = "value"
    policy_text: str = ""
    sample_text: str = ""
    uploaded_document_ids: list[int] = Field(default_factory=list)
    web_links: list[str] = Field(default_factory=list)
    lookup_names: list[str] = Field(default_factory=list)
    mining_demand: str = "level3"
    level1: str | None = None
    level2: str | None = None


class MiningInputOut(MiningInputSave):
    id: int
    status: str
