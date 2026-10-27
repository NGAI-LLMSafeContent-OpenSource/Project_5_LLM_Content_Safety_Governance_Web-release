"""Offline governance planning gate (Issue #67 / #82, #164).

Loads capability-scenario ``scenarios/*.yaml`` cases and runs them through the
single ``plan_governance_turn`` boundary. Provider parity evidence uses recorded
planning outcomes via ``ReplayGovernancePlanner`` — never a deterministic fake.

The scenarios are planner inputs, not production data, so the caller supplies
their directory; the retired skill packages no longer carry them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Sequence

import yaml

from app.services.governance_planner import (
    GovernancePlanningRequest,
    PlannedCapability,
    PlannedGovernanceTurn,
    plan_governance_turn,
)

ProviderName = Literal["qwen", "deepseek", "deterministic"]


@dataclass(frozen=True)
class OfflineCaseResult:
    case_id: str
    provider: str
    selection_status: str
    selection: PlannedCapability | None
    error_code: str | None


def load_offline_cases(scenarios_dir: Path) -> list[dict[str, Any]]:
    """Load ``valid.yaml`` + ``rejected.yaml`` cases in stable file order."""

    root = Path(scenarios_dir)
    cases: list[dict[str, Any]] = []
    for name in ("valid.yaml", "rejected.yaml"):
        path = root / name
        if not path.is_file():
            raise FileNotFoundError(f"offline scenarios missing: {path}")
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(parsed, dict) or not isinstance(parsed.get("cases"), list):
            raise ValueError(f"offline scenarios invalid: {path}")
        for item in parsed["cases"]:
            if not isinstance(item, dict) or "id" not in item:
                raise ValueError(f"offline scenario case missing id in {path}")
            cases.append(item)
    return cases


def _turn_status(turn: PlannedGovernanceTurn) -> str:
    if turn.capability is not None or turn.skill is not None:
        return "selected"
    if turn.clarification is not None:
        return "needs_clarification"
    return "rejected"


async def run_offline_case(
    case: dict[str, Any],
    planner,
) -> OfflineCaseResult:
    """Run one scenario case through the single planning boundary.

    The planner itself validates a capability selection against the registry, so
    an illegal target is already a stable rejection here; there is no second
    contract gate to keep in sync.
    """

    turn = await plan_governance_turn(
        str(case["goal"]),
        str(case["domain"]),
        planner,
        requested_capability=case.get("requested_capability"),
        requested_skill_key=case.get("requested_skill_key"),
        entrypoint=case.get("entrypoint"),
    )
    return OfflineCaseResult(
        case_id=str(case["id"]),
        provider=planner.name,
        selection_status=_turn_status(turn),
        selection=turn.capability,
        error_code=turn.rejection.code if turn.rejection is not None else None,
    )


async def run_offline_suite(
    planner,
    *,
    scenarios_dir: Path,
    case_ids: Sequence[str] | None = None,
    skip_missing_fixtures: bool = False,
) -> list[OfflineCaseResult]:
    """Run scenarios with one planner.

    When ``planner`` is a ``ReplayGovernancePlanner``, each case is bound before
    execution. Missing replay fixtures are skipped when
    ``skip_missing_fixtures`` is true; otherwise ``FileNotFoundError`` is raised.
    """

    cases = load_offline_cases(scenarios_dir)
    if case_ids is not None:
        wanted = set(case_ids)
        cases = [case for case in cases if case["id"] in wanted]

    results: list[OfflineCaseResult] = []
    for case in cases:
        case_id = str(case["id"])
        if isinstance(planner, ReplayGovernancePlanner):
            if not planner.has_fixture(case_id):
                if skip_missing_fixtures:
                    continue
                raise FileNotFoundError(
                    f"replay fixture missing for {planner.name}/{case_id}.json"
                )
            planner.use_case(case_id)
        results.append(await run_offline_case(case, planner))
    return results


class ReplayGovernancePlanner:
    """Replay one anonymized structured planning outcome per provider case."""

    def __init__(self, name: ProviderName, fixture_root: Path):
        if name not in ("qwen", "deepseek", "deterministic"):
            raise ValueError(f"unsupported replay provider name: {name}")
        self.name = name
        self._root = Path(fixture_root) / name
        self._case_id: str | None = None
        self._cache: dict[str, dict[str, Any]] = {}

    def has_fixture(self, case_id: str) -> bool:
        return (self._root / f"{case_id}.json").is_file()

    def use_case(self, case_id: str) -> None:
        self._case_id = case_id

    def _load(self) -> dict[str, Any]:
        if self._case_id is None:
            raise RuntimeError("ReplayGovernancePlanner.use_case() required")
        if self._case_id in self._cache:
            return self._cache[self._case_id]
        path = self._root / f"{self._case_id}.json"
        if not path.is_file():
            raise FileNotFoundError(f"replay fixture missing: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"replay fixture must be an object: {path}")
        outcome = data.get("outcome")
        if not isinstance(outcome, dict):
            raise ValueError(
                f"replay fixture {self.name}/{self._case_id} missing outcome dict"
            )
        self._cache[self._case_id] = outcome
        return outcome

    async def plan(self, request: GovernancePlanningRequest) -> dict[str, Any]:
        del request  # replay is keyed by case_id
        return self._load()
