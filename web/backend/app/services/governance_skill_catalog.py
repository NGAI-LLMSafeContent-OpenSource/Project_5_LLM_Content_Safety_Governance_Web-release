"""Read-only projection of the registered governance skill catalog (#65).

The catalog is an operator-facing, boundary-first view of every registered Agent
Skill: metadata plus the machine-contract limits the server will enforce. It is
assembled entirely from the read-only registry, so it can never widen what a
skill is allowed to do, and skills from every domain stay visible.
"""

from __future__ import annotations

from app.schemas.governance import (
    GovernanceSkillBoundary,
    GovernanceSkillBoundaryStep,
    GovernanceSkillCatalogResult,
    GovernanceSkillEntry,
)
from app.services.governance_skill_registry import (
    ActivatedGovernanceSkill,
    GovernanceSkillDescriptor,
    SkillRegistryError,
    activate_registered_skill,
    list_skill_descriptors,
)


def _boundary(activated: ActivatedGovernanceSkill) -> GovernanceSkillBoundary:
    contract = activated.contract
    return GovernanceSkillBoundary(
        branches=list(contract.branches),
        entrypoints=list(contract.entrypoints),
        executor_capability=contract.executor_capability,
        result_schema=contract.result_schema,
        immutable_scope_fields=list(contract.immutable_scope_fields),
        cost_units_per_sample=contract.execution_estimate.cost_units_per_sample,
        estimated_seconds_per_sample=(
            contract.execution_estimate.estimated_seconds_per_sample
        ),
        confirmation_required=any(
            step.requires_confirmation for step in contract.steps
        ),
        steps=[
            GovernanceSkillBoundaryStep(
                step_id=step.step_id,
                capability=step.capability,
                capability_version=step.capability_version,
                action=step.action,
                automatic=step.automatic,
                requires_confirmation=step.requires_confirmation,
                completion_condition=step.completion_condition,
            )
            for step in contract.steps
        ],
    )


def _entry(descriptor: GovernanceSkillDescriptor) -> GovernanceSkillEntry | None:
    """Read one skill's contract; an unreadable package is skipped, not fatal."""

    try:
        activated = activate_registered_skill(descriptor.skill_key, descriptor.version)
    except SkillRegistryError:
        return None
    return GovernanceSkillEntry(
        skill_key=descriptor.skill_key,
        version=descriptor.version,
        name=descriptor.name,
        description=descriptor.description,
        domain=descriptor.domain,
        skill_content_digest=descriptor.skill_content_digest,
        contract_digest=descriptor.contract_digest,
        boundary=_boundary(activated),
    )


def build_skill_catalog(domain: str | None = None) -> dict:
    """Return every registered skill; the requested domain is ordered first.

    ``domain`` only reorders the list; it never hides skills from other domains,
    so the persistent entry can still explain cross-domain boundaries.
    """

    entries = [
        entry
        for descriptor in list_skill_descriptors()
        if (entry := _entry(descriptor)) is not None
    ]
    domains = sorted({entry.domain for entry in entries})
    if domain is not None:
        ordered = [entry for entry in entries if entry.domain == domain] + [
            entry for entry in entries if entry.domain != domain
        ]
    else:
        ordered = entries
    return GovernanceSkillCatalogResult(
        domain=domain or "",
        domains=domains,
        skills=ordered,
    ).model_dump(mode="json")
