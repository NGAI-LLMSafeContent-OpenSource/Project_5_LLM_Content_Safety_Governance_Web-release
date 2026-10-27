"""Read-only registry for versioned Agent Skills governance packages.

A governance skill is a reviewed, versioned package owned by the repository:

    releases/<version>/<skill-name>/
        SKILL.md            # Agent Skills instructions (procedural knowledge)
        contract.yaml       # platform machine contract (server-enforced limits)
        references/*.md     # material explicitly linked from SKILL.md
        scenarios/*.yaml    # deterministic trigger/rejection contract cases

The registry is an explicit allow-list. It never discovers production skills by
walking arbitrary directories: only packages registered in ``_REGISTRY`` are
listed or activated. Discovery exposes metadata only; the full instructions are
loaded only after the server accepts a single registered skill.

Two layers stay separate on purpose:

* ``SKILL.md`` teaches the planner how to understand, clarify and plan. It can
  never grant execution rights or widen the machine contract.
* ``contract.yaml`` is parsed by a strict Schema (unknown fields are rejected)
  and is the only source of allowed capabilities, steps, branches, confirmation
  points, immutable scope and result Schema.

A well-formed package must also pass governance-skill admission (ADR-0012):
only genuine cross-capability orchestration becomes a governance skill — one run
composes at least two distinct capabilities and a later call depends on earlier
output or follows a declared branch condition. Same-capability prepare/confirm/
execute/export phases are a capability lifecycle, not a skill; read-only browse
and search stay plain governance capabilities.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.services.governance_capabilities import resolve_capability
from app.services.governance_hashing import canonical_digest, canonical_text, text_digest


RELEASES_ROOT = Path(__file__).resolve().parents[1] / "governance_skills" / "releases"

_SEMVER_PATTERN = re.compile(
    r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
_MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_FRONTMATTER_KEYS = {"name", "description", "metadata"}
_METADATA_KEYS = {"domain", "version"}
_EXTERNAL_LINK_PREFIXES = ("http://", "https://", "mailto:", "#")
_MIN_DISTINCT_CAPABILITIES = 2


class SkillRegistryError(ValueError):
    """A stable rejection raised when a package is missing or malformed."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class SkillStepContract(BaseModel):
    """One ordered capability step the machine contract allows."""

    model_config = ConfigDict(extra="forbid")

    step_id: str
    capability: str
    capability_version: str
    action: Literal["prepare", "execute"]
    parameters_schema: str
    automatic: bool
    requires_confirmation: bool
    completion_condition: str
    # Gate-only annotation: expresses the cross-capability dependency but is
    # excluded from outward projections (prompts, catalog, persisted plans) so
    # those payloads stay stable for packages that do not use it.
    depends_on: list[str] = Field(default_factory=list, exclude=True)


class SkillExecutionEstimate(BaseModel):
    """Server-side cost/time estimate used to freeze the confirmation scope."""

    model_config = ConfigDict(extra="forbid")

    cost_units_per_sample: int = Field(ge=0)
    estimated_seconds_per_sample: int = Field(ge=0)


class SkillMachineContract(BaseModel):
    """Strict machine contract; unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")

    skill_key: str
    version: str
    domain: str
    entrypoints: list[Literal["natural_language", "skill_entry"]]
    branches: list[str]
    executor_capability: str
    result_schema: str
    execution_estimate: SkillExecutionEstimate
    immutable_scope_fields: list[str]
    steps: list[SkillStepContract]


class GovernanceSkillDescriptor(BaseModel):
    """Level-1 discovery object: metadata only, never the full instructions."""

    model_config = ConfigDict(extra="forbid")

    skill_key: str
    version: str
    name: str
    description: str
    domain: str
    skill_content_digest: str
    contract_digest: str


class ActivatedGovernanceSkill(BaseModel):
    """Level-2 object loaded only after the server accepts one registered skill."""

    model_config = ConfigDict(extra="forbid")

    descriptor: GovernanceSkillDescriptor
    instructions_markdown: str
    references: dict[str, str]
    contract: SkillMachineContract


@dataclass(frozen=True)
class _RegisteredRelease:
    skill_key: str
    version: str
    package_dir: Path


# Explicit allow-list. Adding a release is a reviewed repository change.
#
# It is intentionally empty after #169: the two single-capability packages that
# predated ADR-0012 (risk-corpus-rescan, dynbench400-eval) were retired, and
# their work is now direct capability runs of ``risk_corpus_rescan`` v2. An
# empty production registry is a supported state: discovery lists nothing and
# the planner plans capabilities only.
_REGISTRY: tuple[_RegisteredRelease, ...] = ()


@dataclass(frozen=True)
class _CatalogEntry:
    """One validated package, read from disk exactly once."""

    descriptor: GovernanceSkillDescriptor
    instructions_markdown: str
    references: Mapping[str, str]
    contract: SkillMachineContract


# The catalog is validated on first use and then only read, so a package that is
# edited on disk after startup cannot change what the server serves. It is keyed
# by the identity of the allow-list tuple, which also lets tests swap in a
# temporary registry without leaking a stale catalog into later tests.
_CATALOG_OWNER: tuple[_RegisteredRelease, ...] | None = None
_CATALOG: tuple[_CatalogEntry, ...] = ()


def _build_catalog(
    releases: tuple[_RegisteredRelease, ...],
) -> tuple[_CatalogEntry, ...]:
    entries: list[_CatalogEntry] = []
    for release in releases:
        descriptor, _raw, body, references, contract = validate_skill_package(
            release.package_dir,
            expected_skill_key=release.skill_key,
            expected_version=release.version,
        )
        entries.append(
            _CatalogEntry(
                descriptor=descriptor,
                instructions_markdown=body,
                references=dict(references),
                contract=contract,
            )
        )
    return tuple(entries)


def _catalog() -> tuple[_CatalogEntry, ...]:
    """Validate every registered package once, then serve the frozen snapshot."""

    global _CATALOG_OWNER, _CATALOG
    if _CATALOG_OWNER is not _REGISTRY:
        ordered = tuple(
            sorted(_REGISTRY, key=lambda item: (item.skill_key, item.version))
        )
        _CATALOG = _build_catalog(ordered)
        _CATALOG_OWNER = _REGISTRY
    return _CATALOG


def _split_frontmatter(raw: str, *, skill_key: str) -> tuple[dict[str, Any], str]:
    lines = raw.split("\n")
    if not lines or lines[0].strip() != "---":
        raise SkillRegistryError(
            "skill_frontmatter_invalid", f"技能 {skill_key} 的 SKILL.md 缺少 YAML frontmatter"
        )
    closing = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            closing = index
            break
    if closing is None:
        raise SkillRegistryError(
            "skill_frontmatter_invalid", f"技能 {skill_key} 的 SKILL.md frontmatter 未闭合"
        )
    try:
        data = yaml.safe_load("\n".join(lines[1:closing])) or {}
    except yaml.YAMLError as exc:
        raise SkillRegistryError(
            "skill_frontmatter_invalid", f"技能 {skill_key} 的 frontmatter 无法解析：{exc}"
        ) from exc
    if not isinstance(data, dict):
        raise SkillRegistryError(
            "skill_frontmatter_invalid", f"技能 {skill_key} 的 frontmatter 必须是映射"
        )
    body = "\n".join(lines[closing + 1 :])
    return data, body


def _referenced_paths(body: str):
    for match in _MARKDOWN_LINK_PATTERN.finditer(body):
        target = match.group(1).strip().strip("<>").strip()
        if not target or target.startswith(_EXTERNAL_LINK_PREFIXES):
            continue
        yield target


def _load_references(
    package_dir: Path, body: str, *, skill_key: str
) -> dict[str, str]:
    root = package_dir.resolve()
    references: dict[str, str] = {}
    for target in _referenced_paths(body):
        candidate = (package_dir / target).resolve()
        if root not in candidate.parents and candidate != root:
            raise SkillRegistryError(
                "skill_reference_invalid",
                f"技能 {skill_key} 引用了包目录之外的路径：{target}",
            )
        if not candidate.is_file():
            raise SkillRegistryError(
                "skill_reference_missing",
                f"技能 {skill_key} 引用的文件不存在：{target}",
            )
        references[target] = canonical_text(candidate.read_text("utf-8"))
    return references


def _load_scenarios(package_dir: Path, *, skill_key: str) -> None:
    scenarios_dir = package_dir / "scenarios"
    for name in ("valid.yaml", "rejected.yaml"):
        path = scenarios_dir / name
        if not path.is_file():
            raise SkillRegistryError(
                "skill_scenarios_missing",
                f"技能 {skill_key} 缺少场景文件 scenarios/{name}",
            )
        try:
            parsed = yaml.safe_load(path.read_text("utf-8"))
        except yaml.YAMLError as exc:
            raise SkillRegistryError(
                "skill_scenarios_invalid",
                f"技能 {skill_key} 的场景文件无法解析：{exc}",
            ) from exc
        if not isinstance(parsed, dict) or not isinstance(parsed.get("cases"), list):
            raise SkillRegistryError(
                "skill_scenarios_invalid",
                f"技能 {skill_key} 的场景文件必须是含非空 cases 列表的映射",
            )


def _load_contract(contract_path: Path, *, skill_key: str) -> SkillMachineContract:
    if not contract_path.is_file():
        raise SkillRegistryError(
            "skill_contract_missing", f"技能 {skill_key} 缺少 contract.yaml"
        )
    try:
        raw = yaml.safe_load(contract_path.read_text("utf-8"))
    except yaml.YAMLError as exc:
        raise SkillRegistryError(
            "skill_contract_invalid", f"技能 {skill_key} 的 contract.yaml 无法解析：{exc}"
        ) from exc
    try:
        return SkillMachineContract.model_validate(raw)
    except ValidationError as exc:
        raise SkillRegistryError(
            "skill_contract_invalid", f"技能 {skill_key} 的契约不符合严格 Schema：{exc}"
        ) from exc


def _validate_contract_integrity(contract: SkillMachineContract, *, skill_key: str) -> None:
    if not contract.branches:
        raise SkillRegistryError("skill_contract_invalid", f"技能 {skill_key} 未登记任何分支")
    if not contract.steps:
        raise SkillRegistryError("skill_contract_invalid", f"技能 {skill_key} 未登记任何步骤")
    if contract.executor_capability not in {step.capability for step in contract.steps}:
        raise SkillRegistryError(
            "skill_contract_invalid",
            f"技能 {skill_key} 的执行器能力未出现在任何登记步骤中",
        )
    step_ids = [step.step_id for step in contract.steps]
    if len(set(step_ids)) != len(step_ids):
        raise SkillRegistryError(
            "skill_contract_invalid", f"技能 {skill_key} 的步骤 step_id 存在重复"
        )
    known_steps = set(step_ids)
    for step in contract.steps:
        if step.step_id in step.depends_on:
            raise SkillRegistryError(
                "skill_contract_invalid",
                f"技能 {skill_key} 的步骤 {step.step_id} 不能依赖自身",
            )
        unknown = sorted(set(step.depends_on) - known_steps)
        if unknown:
            raise SkillRegistryError(
                "skill_contract_invalid",
                f"技能 {skill_key} 的步骤 {step.step_id} 依赖未登记的步骤：{unknown}",
            )


def _reject_admission(skill_key: str, reason: str) -> SkillRegistryError:
    return SkillRegistryError(
        "skill_admission_rejected",
        f"技能 {skill_key} 未通过治理技能准入（ADR-0012）：{reason}",
    )


def _contract_digest_payload(contract: SkillMachineContract) -> dict[str, Any]:
    """Include gate-only step annotations that ``model_dump`` excludes.

    ``depends_on`` expresses the cross-capability dependency but is excluded
    from outward projections to keep prompts, catalog payloads and persisted
    plans stable. It still participates in drift detection, so it is re-added
    only when a package actually uses it; a package without a dependency keeps
    its previously reviewed digest.
    """

    if not any(step.depends_on for step in contract.steps):
        return contract.model_dump()
    payload = contract.model_dump()
    payload["steps"] = [
        step.model_dump() | {"depends_on": list(step.depends_on)}
        for step in contract.steps
    ]
    return payload


def _enforce_skill_admission(contract: SkillMachineContract, *, skill_key: str) -> None:
    """Admit only genuine cross-capability orchestration (ADR-0012).

    A governance skill must compose at least two *distinct* governance
    capabilities, and a later invocation must depend on earlier output
    (``depends_on``) or follow a declared branch condition. Prepare, confirm,
    execute and export phases of one capability are its lifecycle, not a skill.
    Read-only detection reuses the capability registry: every execution
    capability declares ``requires_confirmation``, browse/search ones never do.
    Confirmation rules mirror plan-time validation so a listed skill can always
    be planned.
    """

    distinct_capabilities = {step.capability for step in contract.steps}
    if len(distinct_capabilities) < _MIN_DISTINCT_CAPABILITIES:
        raise _reject_admission(
            skill_key,
            f"治理技能必须跨至少 {_MIN_DISTINCT_CAPABILITIES} 个彼此不同的治理能力，"
            f"当前只涉及 {len(distinct_capabilities)} 个：{sorted(distinct_capabilities)}；"
            "同一能力的准备、确认、执行与导出属于能力生命周期，不是治理技能",
        )
    has_dependency = any(step.depends_on for step in contract.steps)
    has_branch_condition = len(contract.branches) >= 2
    if not (has_dependency or has_branch_condition):
        raise _reject_admission(
            skill_key,
            "跨能力技能必须让后续调用依赖前序结果（步骤 depends_on）"
            "或存在两个及以上声明的分支条件",
        )
    executor = resolve_capability(contract.domain, contract.executor_capability)
    if executor is None:
        raise SkillRegistryError(
            "skill_contract_invalid",
            f"技能 {skill_key} 的执行器能力 {contract.executor_capability} "
            f"未在 {contract.domain} 业务域的治理能力注册表登记",
        )
    if not executor.requires_confirmation:
        raise _reject_admission(
            skill_key,
            f"执行器能力 {contract.executor_capability} 是只读浏览或检索能力，"
            "纯只读查询应保留为治理能力，不得登记为治理技能",
        )
    if not any(
        step.capability == contract.executor_capability
        and step.action == "execute"
        and step.requires_confirmation
        for step in contract.steps
    ):
        raise _reject_admission(
            skill_key,
            f"执行器能力 {contract.executor_capability} 的执行步骤必须在用户确认后执行",
        )
    for step in contract.steps:
        if not step.requires_confirmation:
            continue
        capability = resolve_capability(contract.domain, step.capability)
        if capability is None or not capability.requires_confirmation:
            raise _reject_admission(
                skill_key,
                f"确认步骤 {step.step_id} 绑定的能力 {step.capability} "
                "不是需确认的执行型能力",
            )


def validate_skill_package(
    package_dir: Path,
    *,
    expected_skill_key: str,
    expected_version: str,
) -> tuple[GovernanceSkillDescriptor, str, str, dict[str, str], SkillMachineContract]:
    """Validate one package and return its descriptor plus loaded content.

    Format validation is deliberately strict so a reviewed package cannot drift
    silently: directory name, frontmatter name, SemVer, contract identity,
    referenced files and scenario files must all agree.
    """

    skill_key = expected_skill_key
    if not _SEMVER_PATTERN.match(expected_version):
        raise SkillRegistryError(
            "skill_version_invalid", f"技能 {skill_key} 的版本不是合法 SemVer：{expected_version}"
        )
    if not package_dir.is_dir():
        raise SkillRegistryError(
            "skill_package_missing", f"技能 {skill_key}@{expected_version} 的包目录不存在"
        )
    if package_dir.name != skill_key:
        raise SkillRegistryError(
            "skill_name_mismatch",
            f"技能目录名 {package_dir.name} 与登记名 {skill_key} 不一致",
        )
    if package_dir.parent.name != expected_version:
        raise SkillRegistryError(
            "skill_version_mismatch",
            f"版本目录 {package_dir.parent.name} 与登记版本 {expected_version} 不一致",
        )

    skill_path = package_dir / "SKILL.md"
    if not skill_path.is_file():
        raise SkillRegistryError(
            "skill_package_invalid", f"技能 {skill_key} 缺少 SKILL.md"
        )
    raw = canonical_text(skill_path.read_text("utf-8"))
    frontmatter, body = _split_frontmatter(raw, skill_key=skill_key)

    unknown_frontmatter = set(frontmatter) - _FRONTMATTER_KEYS
    if unknown_frontmatter:
        raise SkillRegistryError(
            "skill_frontmatter_invalid",
            f"技能 {skill_key} 的 frontmatter 含未知字段：{sorted(unknown_frontmatter)}",
        )
    if frontmatter.get("name") != skill_key:
        raise SkillRegistryError(
            "skill_name_mismatch",
            f"frontmatter name={frontmatter.get('name')!r} 与登记名 {skill_key!r} 不一致",
        )
    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        raise SkillRegistryError(
            "skill_frontmatter_invalid", f"技能 {skill_key} 的 frontmatter 缺少 description"
        )
    metadata = frontmatter.get("metadata")
    if not isinstance(metadata, dict):
        raise SkillRegistryError(
            "skill_frontmatter_invalid", f"技能 {skill_key} 的 frontmatter 缺少 metadata"
        )
    unknown_metadata = set(metadata) - _METADATA_KEYS
    if unknown_metadata:
        raise SkillRegistryError(
            "skill_frontmatter_invalid",
            f"技能 {skill_key} 的 metadata 含未知字段：{sorted(unknown_metadata)}",
        )
    if metadata.get("version") != expected_version:
        raise SkillRegistryError(
            "skill_version_mismatch",
            f"metadata.version={metadata.get('version')!r} 与登记版本 {expected_version!r} 不一致",
        )
    domain = metadata.get("domain")
    if not isinstance(domain, str) or not domain.strip():
        raise SkillRegistryError(
            "skill_frontmatter_invalid", f"技能 {skill_key} 的 metadata 缺少 domain"
        )

    references = _load_references(package_dir, body, skill_key=skill_key)
    _load_scenarios(package_dir, skill_key=skill_key)
    contract = _load_contract(package_dir / "contract.yaml", skill_key=skill_key)

    if contract.skill_key != skill_key:
        raise SkillRegistryError(
            "skill_name_mismatch",
            f"契约 skill_key={contract.skill_key!r} 与登记名 {skill_key!r} 不一致",
        )
    if contract.version != expected_version:
        raise SkillRegistryError(
            "skill_version_mismatch",
            f"契约 version={contract.version!r} 与登记版本 {expected_version!r} 不一致",
        )
    if contract.domain != domain:
        raise SkillRegistryError(
            "skill_contract_invalid",
            f"契约 domain={contract.domain!r} 与 frontmatter domain={domain!r} 不一致",
        )
    _validate_contract_integrity(contract, skill_key=skill_key)
    _enforce_skill_admission(contract, skill_key=skill_key)

    descriptor = GovernanceSkillDescriptor(
        skill_key=skill_key,
        version=expected_version,
        name=skill_key,
        description=description.strip(),
        domain=domain,
        skill_content_digest=text_digest(raw),
        contract_digest=canonical_digest(_contract_digest_payload(contract)),
    )
    return descriptor, raw, body.strip("\n"), references, contract


def list_skill_descriptors(domain: str | None = None) -> list[GovernanceSkillDescriptor]:
    """Return metadata for registered skills in a stable order.

    Discovery never returns full ``SKILL.md`` content, references or scenarios.
    """

    return [
        entry.descriptor
        for entry in _catalog()
        if domain is None or entry.descriptor.domain == domain
    ]


def activate_registered_skill(
    skill_key: str,
    version: str,
    *,
    expected_skill_content_digest: str | None = None,
    expected_contract_digest: str | None = None,
) -> ActivatedGovernanceSkill:
    """Load one registered skill after the server accepts its exact key/version.

    Optional expected digests let a caller pin a reviewed release: a package that
    was modified in place is rejected instead of being silently re-loaded.
    """

    entry = next(
        (
            item
            for item in _catalog()
            if item.descriptor.skill_key == skill_key
            and item.descriptor.version == version
        ),
        None,
    )
    if entry is None:
        raise SkillRegistryError(
            "skill_not_registered", f"未登记治理技能 {skill_key}@{version}"
        )
    descriptor = entry.descriptor
    if (
        expected_skill_content_digest is not None
        and descriptor.skill_content_digest != expected_skill_content_digest
    ):
        raise SkillRegistryError(
            "skill_digest_drift",
            f"技能 {skill_key}@{version} 的 SKILL.md 内容摘要与已评审版本不一致",
        )
    if (
        expected_contract_digest is not None
        and descriptor.contract_digest != expected_contract_digest
    ):
        raise SkillRegistryError(
            "skill_digest_drift",
            f"技能 {skill_key}@{version} 的 contract.yaml 摘要与已评审版本不一致",
        )
    return ActivatedGovernanceSkill(
        descriptor=descriptor,
        instructions_markdown=entry.instructions_markdown,
        references=dict(entry.references),
        contract=entry.contract,
    )
