from pathlib import Path
from typing import Any, Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[1]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TemplateIdentity(StrictModel):
    work_id: str | None = None
    evidence_id: str | None = None
    verification_id: str | None = None
    rework_id: str | None = None
    project_id: str
    created_at: str
    work_type: str | None = None


class WorkContractTemplate(StrictModel):
    schema_version: str
    record_type: Literal["work_contract"]
    status: Literal["draft"]
    identity: TemplateIdentity
    intent: dict[str, Any]
    inputs: dict[str, Any]
    boundaries: dict[str, Any]
    outputs: dict[str, Any]
    evidence_and_verification: dict[str, Any]
    continuation: dict[str, Any]


class EvidenceRecordTemplate(StrictModel):
    schema_version: str
    record_type: Literal["evidence_record"]
    status: Literal["draft"]
    identity: TemplateIdentity
    sources: dict[str, Any]
    observations: dict[str, Any]
    limits: dict[str, Any]


class VerificationRecordTemplate(StrictModel):
    schema_version: str
    record_type: Literal["verification_record"]
    status: Literal["draft"]
    identity: TemplateIdentity
    checks: list[dict[str, Any]]
    unverified_surfaces: list[Any]
    residual_risk: list[Any]
    next_action: str


class ReworkRecordTemplate(StrictModel):
    schema_version: str
    record_type: Literal["rework_record"]
    status: Literal["draft"]
    identity: TemplateIdentity
    rework: dict[str, Any]
    closure: dict[str, Any]


class ProjectStorageMapTemplate(StrictModel):
    schema_version: str
    record_type: Literal["project_storage_map"]
    status: Literal["draft"]
    project: dict[str, Any]
    canonical_records: dict[str, Any]
    overlays: list[dict[str, Any]]
    rules: dict[str, Any]


class ProjectGraph(StrictModel):
    ecosystem_id: str
    project_id: str
    offer_id: str
    channel_id: str
    campaign_id: str
    owner_agent: str
    human_owner: str
    status: str
    memo: str


class ContentRef(StrictModel):
    content_id: str
    project_id: str
    offer_id: str
    channel_id: str
    content_type: str
    status: str
    body_ref: str
    asset_refs: list[str]
    evidence_refs: list[str]
    reaction_refs: list[str]


class EvidencePacket(StrictModel):
    packet_id: str
    schema_version: str
    project_graph: ProjectGraph
    evidence_type: str
    claim: str
    evidence_refs: list[str]
    confidence: str
    used_for: str
    content_ref: ContentRef
    memo: str


class HandoffPacket(StrictModel):
    packet_id: str
    schema_version: str
    from_agent: str = Field(alias="from")
    to: str
    project_graph: ProjectGraph
    task: str
    content_ref: ContentRef
    required_context: list[str]
    expected_output: str
    gate_required: bool
    memo: str


class ReworkPacket(StrictModel):
    packet_id: str
    schema_version: str
    from_agent: str = Field(alias="from")
    to: str
    project_graph: ProjectGraph
    reason: str
    evidence_refs: list[str]
    requested_change: str
    severity: str
    content_ref: ContentRef
    memo: str


def load_yaml(relative_path: str) -> dict[str, Any]:
    raw_data: object = yaml.safe_load((ROOT / relative_path).read_text(encoding="utf-8"))
    assert isinstance(raw_data, dict), relative_path
    return cast(dict[str, Any], raw_data)


def test_templates_validate_with_pydantic_models() -> None:
    cases: tuple[tuple[str, type[BaseModel]], ...] = (
        ("templates/work-contract.yaml", WorkContractTemplate),
        ("templates/evidence-record.yaml", EvidenceRecordTemplate),
        ("templates/verification-record.yaml", VerificationRecordTemplate),
        ("templates/rework-record.yaml", ReworkRecordTemplate),
        ("templates/project-storage-map.yaml", ProjectStorageMapTemplate),
    )

    for relative_path, model in cases:
        model.model_validate(load_yaml(relative_path))


def test_archive_packets_validate_with_pydantic_models() -> None:
    cases: tuple[tuple[str, type[BaseModel]], ...] = (
        ("archive/packets/evidence-packet.yaml", EvidencePacket),
        ("archive/packets/handoff-packet.yaml", HandoffPacket),
        ("archive/packets/rework-packet.yaml", ReworkPacket),
    )

    for relative_path, model in cases:
        model.model_validate(load_yaml(relative_path))
