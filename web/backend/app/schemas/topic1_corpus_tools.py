"""Shared contracts for Project 1 training-corpus tools.

The data-input BFF and the governance assistant intentionally share this DTO.
This keeps delivery/runtime facts canonical while allowing each surface to
present them for its own workflow.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Topic1CorpusToolKey = Literal[
    "scarcity_evaluation",
    "data_denoising",
    "data_detoxification",
    "data_selection",
]

Topic1CorpusWorkflowStage = Literal["assessment", "correction", "delivery"]


class Topic1ToolServiceStatus(BaseModel):
    connection: Literal["not_configured", "unreachable", "online"]
    readiness: Literal["unknown", "missing_resources", "unverified", "declared_ready", "demo"]
    message: str
    checked_at: str


class Topic1CorpusToolDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_key: Topic1CorpusToolKey
    display_name: str
    implementation_name: str
    purpose: str
    workflow_stage: Topic1CorpusWorkflowStage
    delivery_status: Literal["source_delivered", "pending_source_delivery"]
    runtime_status: Literal[
        "metadata_ready", "source_only", "blocked_missing_artifacts", "pending"
    ]
    execution_mode: Literal[
        "metadata_only", "precomputed_asset", "remote_service", "unavailable"
    ]
    executable: bool
    source_package: str = ""
    source_sha256: str = ""
    source_repository: str = ""
    source_revision: str = ""
    service_status: Topic1ToolServiceStatus | None = None
    input_contract: str
    output_contract: str
    requirements: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    next_action: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_delivery_and_runtime_truth(self) -> "Topic1CorpusToolDescriptor":
        if self.source_repository or self.source_revision:
            if not re.fullmatch(r"Project_1_[A-Za-z0-9_]+", self.source_repository):
                raise ValueError("Invalid Topic 1 repository name")
            if not re.fullmatch(r"[0-9a-f]{40}", self.source_revision):
                raise ValueError("Source revision must be a complete commit ID")
        if self.delivery_status == "source_delivered":
            if not self.source_package.strip():
                raise ValueError("源码已交付的工具必须登记 source_package")
            if (
                "/" in self.source_package
                or "\\" in self.source_package
                or not self.source_package.lower().endswith(".zip")
            ):
                raise ValueError("source_package 必须是纯 ZIP 文件名")
            if not re.fullmatch(r"[0-9a-f]{64}", self.source_sha256):
                raise ValueError("源码已交付的工具必须登记小写 SHA-256")
        if self.execution_mode in {"metadata_only", "unavailable"} and self.executable:
            raise ValueError("仅元信息或不可用模式不能标记为可执行")
        if self.executable and self.blockers:
            raise ValueError("可执行工具不能同时登记阻塞项")
        return self


class Topic1CorpusToolCatalogResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: Literal["topic1_corpus_tool_catalog"] = "topic1_corpus_tool_catalog"
    available: bool = True
    error_code: str = ""
    message: str = ""
    catalog_version: str
    source_snapshot_date: str
    tools: list[Topic1CorpusToolDescriptor]

    @model_validator(mode="after")
    def validate_catalog_membership(self) -> "Topic1CorpusToolCatalogResult":
        if not self.available:
            if self.tools:
                raise ValueError("不可用的工具目录不得携带旧工具数据")
            if not self.error_code or not self.message:
                raise ValueError("不可用的工具目录必须返回稳定错误码和提示")
            return self

        expected = {
            "scarcity_evaluation",
            "data_denoising",
            "data_detoxification",
            "data_selection",
        }
        actual = {tool.tool_key for tool in self.tools}
        if len(actual) != len(self.tools):
            raise ValueError("课题一工具目录包含重复 tool_key")
        if actual != expected:
            raise ValueError("课题一工具目录必须完整登记四项约定工具")
        return self

    def render_content(self) -> str:
        if not self.available:
            return self.message
        delivered = sum(
            tool.delivery_status == "source_delivered" for tool in self.tools
        )
        executable = sum(tool.executable for tool in self.tools)
        return (
            f"课题一训练语料工具共 {len(self.tools)} 项："
            f"已收到源码 {delivered} 项，当前可直接执行 {executable} 项。"
            "源码交付状态与平台运行状态已分开显示。"
        )


class Topic1CorpusToolSourceVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_key: Topic1CorpusToolKey
    source_package: str
    status: Literal["verified", "missing", "hash_mismatch"]
    expected_sha256: str
    actual_sha256: str = ""


class Topic1CorpusToolVerificationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_version: str
    delivered_package_count: int = Field(ge=0)
    verified_package_count: int = Field(ge=0)
    results: list[Topic1CorpusToolSourceVerification] = Field(default_factory=list)
