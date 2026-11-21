from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "Project 5 LLM Content Safety Governance API"
    database_url: str = "sqlite+aiosqlite:///./content_governance.db"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    benchmark_base_url: str = "http://127.0.0.1:6006"
    cultural_gen_base_url: str = "http://127.0.0.1:6322"
    cultural_gen_data_base_url: str = "http://127.0.0.1:6323"
    cultural_assessment_root: str = ""
    cultural_assessment_console_base_url: str = "http://127.0.0.1:8877"
    cultural_assessment_console_v2_base_url: str = "http://127.0.0.1:8878"
    cultural_corpus_runs_dir: str = ""
    cultural_corpus_generator_base_url: str = "http://127.0.0.1:8766"
    cultural_corpus_generator_root: str = ""
    cultural_corpus_generation_config: str = ""
    cultural_corpus_generation_python: str = ""
    cultural_corpus_generation_api_key_env: str = "DEEPSEEK_API_KEY"
    predictions_snapshot_dir: str = ""
    topic4_input_workflow_base_url: str = "http://127.0.0.1:8081"
    topic4_input_workflow_timeout_seconds: float = 30.0
    # Explicitly opt in: no discovery of developer-local repositories or models.
    topic1_refinement_base_url: str = ""
    topic1_refinement_api_key: SecretStr = SecretStr("")
    topic1_detox_base_url: str = ""
    topic1_detection_base_url: str = ""
    topic1_corpus_tools_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    # Admin-managed aliases only. Browser/LLM never supplies model paths or URLs.
    topic1_detection_models: dict[str, dict[str, str]] = {}
    topic2_autobench_base_url: str = "http://127.0.0.1:8766"
    topic2_autobench_api_token: str = ""
    topic2_autobench_health_timeout_seconds: float = 2.0
    benchmark_artifact_root: str = "benchmark-artifacts"
    # Benchmark management import (#151). The admin credential is independent of
    # any other secret; unset or blank makes the admin endpoints fail closed.
    benchmark_admin_token: SecretStr | None = None
    # Recorded as uploaded_by; never derived from the credential.
    benchmark_admin_label: str = "benchmark-admin"
    benchmark_delivery_staging_root: str = "benchmark-delivery-staging"
    # An uploaded/validating delivery untouched this long is abandoned and may be
    # taken over by a retry of the same package; keep it above the longest validation.
    benchmark_delivery_stale_seconds: int = 900
    benchmark_delivery_max_package_bytes: int = 64 * 1024 * 1024
    benchmark_delivery_max_entries: int = 64
    benchmark_delivery_max_entry_bytes: int = 256 * 1024 * 1024
    benchmark_delivery_max_total_bytes: int = 512 * 1024 * 1024
    benchmark_delivery_max_compression_ratio: float = 200.0
    benchmark_demo_budget_max: int = 5
    topic2_autobench_source_repo: str = (
        "Project_2_Flywheel_on_Anomaly_Detection_Tracking_Correction"
    )
    topic2_autobench_source_commit: str = "a28a32c"
    topic2_filterguard_base_url: str = "http://127.0.0.1:6211"
    topic2_filterguard_timeout_seconds: float = 10.0
    topic2_filterguard_method: str = "keyword"
    # Remote Activation Probe (neuron showcase) served by Topic 2 on AutoDL.
    topic2_activation_probe_base_url: str = (
        "https://u165979-8749-15195365.westc.seetacloud.com:8443"
    )
    topic2_activation_probe_proxy_url: str = ""
    topic2_activation_probe_timeout_seconds: float = 60.0
    topic2_activation_probe_max_batch: int = 30
    # New Activation Probe per-text cap; over-long text fails the whole batch.
    topic2_activation_probe_max_text_chars: int = 32768
    # Default risk-detect method for input module: activation_probe | keyword
    topic2_risk_detect_method: str = "activation_probe"
    # Optional stable upstream service/build/model version. Empty means the
    # executor identity is frozen as a provisional fingerprint.
    topic2_risk_detect_version: str = ""
    topic3_difficulty_base_url: str = "http://127.0.0.1:6331"
    topic3_difficulty_health_timeout_seconds: float = 2.0
    topic3_difficulty_timeout_seconds: float = 300.0
    topic3_difficulty_poll_interval_seconds: float = 2.0
    topic3_difficulty_source_repo: str = (
        "Project_3_Dynamic_Difficulty_Question_Generation_Tool"
    )
    topic3_difficulty_source_commit: str = "3afa6e7"
    topic3_difficulty_vllm_api_base: str = "http://127.0.0.1:6332/v1"
    topic3_difficulty_vllm_api_key_env: str = ""
    topic3_risk_benchmark_source_repo: str = (
        "Project_3_Dynamic_Risk_Benchmark_Generation"
    )
    topic3_risk_benchmark_source_commit: str = "42c8b5e"
    topic3_risk_benchmark_default_final_dir: str = ""
    topic3_risk_benchmark_project_root: str = ""
    topic3_risk_benchmark_python: str = ""
    topic3_risk_agent_url: str = "http://127.0.0.1:6351/chat"
    topic3_risk_qwen_api_base: str = "http://127.0.0.1:6352/v1"
    topic3_risk_timeout_seconds: float = 900.0
    topic3_risk_health_timeout_seconds: float = 5.0
    topic3_risk_workers: int = 1
    topic3_cultural_source_repo: str = (
        "Project_3_Cultural_Diversity_Corpus_Generation_Tool"
    )
    topic3_cultural_source_commit: str = ""
    topic3_cultural_timeout_seconds: float = 900.0
    topic3_cultural_poll_interval_seconds: float = 2.0
    topic1_value_qa_source_repo: str = "Project_1_Sample_evaluation_Generation"
    topic1_value_qa_source_commit: str = "9826945"
    topic1_value_qa_project_root: str = ""
    topic1_value_qa_python: str = ""
    # Hard ceiling for large (~30 rows); slow LLM / online retrieval may need the full window.
    topic1_value_qa_timeout_seconds: float = 7200.0
    topic1_value_qa_health_timeout_seconds: float = 5.0
    topic1_value_qa_llm_health_timeout_seconds: float = 2.0
    topic1_value_qa_llm_api_base: str = ""
    topic1_value_qa_llm_model: str = ""
    # Legacy / expert-path default only. Standard value_qa no longer hard-binds
    # mid-autumn; run-time retrieval is resolved from topic disk hit or online.
    topic1_value_qa_default_corpus_jsonl: str = "data/corpus/baidu/中秋节.jsonl"
    topic1_value_qa_default_samples_path: str = ""
    topic1_value_qa_default_marks_path: str = ""
    topic1_value_qa_default_qc_index_path: str = ""
    topic1_value_qa_default_qc_samples_path: str = ""
    topic1_value_qa_default_qc_scores_path: str = ""
    topic1_value_qa_default_qc_summary_path: str = ""
    topic1_value_qa_default_trace_predictions_path: str = ""
    topic1_value_qa_default_trace_low_issues_path: str = ""
    topic1_value_qa_prompt_snapshot: str = "value_qa-v4-20260707_103918"
    topic1_value_qa_auto_ensure: bool = True
    compliance_edit_base_url: str = "http://127.0.0.1:6311"
    compliance_edit_timeout_seconds: float = 60.0
    output_guardrail_detect_timeout_seconds: float = 60.0
    # Governance assistant: exactly one provider active at a time. "stub" is the
    # deterministic test/dev seam, not a production model provider.
    governance_assistant_provider: Literal["qwen", "deepseek", "stub"] = "qwen"
    governance_assistant_timeout_seconds: float = 60.0
    # Wall-clock budget for one governance turn's skill selection and planning
    # calls together. Independent of the per-read inactivity timeout above:
    # a provider keepalive must not extend the turn past this deadline.
    governance_planner_turn_budget_seconds: float = 70.0
    governance_assistant_qwen_base_url: str = "http://127.0.0.1:6332/v1"
    governance_assistant_qwen_model: str = "Qwen3.5-9B"
    governance_assistant_deepseek_base_url: str = "https://api.deepseek.com"
    governance_assistant_deepseek_model: str = "deepseek-v4-pro"
    governance_assistant_deepseek_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "DEEPSEEK_API_KEY",
            "GOVERNANCE_ASSISTANT_DEEPSEEK_API_KEY",
        ),
    )
    # Governance risk re-detection (#55): server-side hard cap per confirmed run
    # and the wait window for the existing online secondary-detection service.
    governance_risk_rescan_timeout_seconds: float = 120.0
    # Governance follow-up suggestion ranking (#65). "deterministic" keeps the
    # server order and never touches the network; "model" lets the configured
    # assistant provider reorder/rewrite candidates (server re-validates).
    governance_suggestion_ranker: Literal["deterministic", "model"] = "deterministic"
    # Anonymized product-funnel sink (#67 / #83). Independent of Skill Runtime
    # mode (owned by #84); when False, emit helpers become no-ops.
    governance_product_metrics_enabled: bool = True
    # Gradual Skill Runtime rollout (#67 / #84). "off" keeps Phase 1 free-capability
    # interpret → confirm; "on" routes new turns through propose_governance_plan
    # and never falls back to free capability interpret on reject/no_match.
    governance_skill_runtime_mode: Literal["off", "on"] = "on"

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
