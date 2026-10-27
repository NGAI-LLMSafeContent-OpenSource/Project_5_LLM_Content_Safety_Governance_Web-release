"""Executor identity resolution for governance capability calls.

A frozen execution scope must record *which* executor a capability will actually
use, not just an abstract capability version. The same resolver is called when a
plan is frozen and again before execution, so any observable change invalidates
the original confirmation.

Topic-2 risk detection has two real adapter methods:

* ``activation_probe`` — the remote neuron showcase (``/v1/moderate``);
* ``keyword`` — the local FilterGuard (``/predict/keyword``).

``adapter_method`` reflects the method that will really run. Upstreams that
expose a stable service/build/model version produce a ``verified`` identity;
otherwise a ``provisional`` fingerprint is derived from the method, the
normalized base URL, available upstream info and semantically relevant local
configuration. URLs are never a version on their own, and secrets, auth headers
and proxy credentials never enter the metadata or the digest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from app.core.config import get_settings
from app.schemas.governance import ExecutorIdentity, RISK_RESCAN_CAPABILITY
from app.services.input_risk_detection_service import (
    METHOD_ACTIVATION_PROBE,
    resolve_input_risk_method,
)
from app.services.governance_capabilities import CapabilityDef
from app.services.governance_hashing import canonical_digest


@dataclass(frozen=True)
class ExecutorObservation:
    """Raw, server-owned observation used to build an executor identity."""

    adapter_method: str
    api_contract_version: str
    base_url: str = ""
    stable_version: str = ""
    extra: dict[str, str] = field(default_factory=dict)


def _safe_base_url(raw: str) -> str:
    """Keep only scheme, host, port and path; drop userinfo, query, fragment."""

    if not raw or not raw.strip():
        return ""
    parts = urlsplit(raw.strip())
    host = parts.hostname or ""
    if not host:
        return ""
    port = f":{parts.port}" if parts.port else ""
    path = parts.path.rstrip("/")
    return f"{parts.scheme}://{host}{port}{path}"


def observe_executor(
    capability: CapabilityDef, parameters: dict[str, Any]
) -> ExecutorObservation:
    """Default observation from real settings and available upstream info.

    Overridden in tests through this single seam. It never performs network I/O,
    so an unavailable ``/v1/info`` cannot block plan freezing; it simply yields a
    ``provisional`` identity until an operator records a stable upstream version
    in configuration.
    """

    settings = get_settings()
    stable_version = (settings.topic2_risk_detect_version or "").strip()

    # Input-risk re-detection pins an explicitly named evaluator through
    # parameters; omission resolves to the registered server default, so the
    # frozen identity always matches the method the run really executes.
    if capability.key == RISK_RESCAN_CAPABILITY:
        requested = (
            parameters.get("evaluator") if isinstance(parameters, dict) else None
        )
        method = resolve_input_risk_method(
            str(requested) if requested is not None else None
        )
        if method == METHOD_ACTIVATION_PROBE:
            return ExecutorObservation(
                adapter_method="activation_probe",
                api_contract_version="topic2.activation_probe.v1",
                base_url=_safe_base_url(settings.topic2_activation_probe_base_url),
                stable_version=stable_version,
                extra={
                    "max_batch": str(int(settings.topic2_activation_probe_max_batch)),
                    "max_text_chars": str(
                        int(settings.topic2_activation_probe_max_text_chars)
                    ),
                    # Never record the proxy URL itself; only whether one is set.
                    "proxy_configured": (
                        "true"
                        if (settings.topic2_activation_probe_proxy_url or "").strip()
                        else "false"
                    ),
                },
            )
        return ExecutorObservation(
            adapter_method="keyword",
            api_contract_version="topic2.filterguard.keyword.v1",
            base_url=_safe_base_url(settings.topic2_filterguard_base_url),
            stable_version=stable_version,
            extra={
                "filterguard_method": settings.topic2_filterguard_method or "keyword",
                "timeout_seconds": f"{float(settings.topic2_filterguard_timeout_seconds):g}",
            },
        )

    return ExecutorObservation(
        adapter_method=capability.key,
        api_contract_version=f"{capability.key}.{capability.version}",
        stable_version=stable_version,
    )


def resolve_executor_identity(
    capability: CapabilityDef, parameters: dict[str, Any]
) -> ExecutorIdentity:
    """Build a stable executor identity from one server-owned observation."""

    observation = observe_executor(capability, parameters)
    fingerprint_input = {
        "capability": capability.key,
        "capability_version": capability.version,
        "adapter_method": observation.adapter_method,
        "api_contract_version": observation.api_contract_version,
        "base_url": observation.base_url,
        "stable_version": observation.stable_version,
        "extra": observation.extra,
    }
    observed_metadata = {
        "adapter_method": observation.adapter_method,
        "api_contract_version": observation.api_contract_version,
        "base_url": observation.base_url,
        **observation.extra,
    }
    if observation.stable_version:
        observed_metadata["stable_version"] = observation.stable_version
    return ExecutorIdentity(
        capability=capability.key,
        capability_version=capability.version,
        adapter_method=observation.adapter_method,
        api_contract_version=observation.api_contract_version,
        implementation_fingerprint=canonical_digest(fingerprint_input),
        version_assurance=(
            "verified" if observation.stable_version else "provisional"
        ),
        observed_metadata=observed_metadata,
    )
