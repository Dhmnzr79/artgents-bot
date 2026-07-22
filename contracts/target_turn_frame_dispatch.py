"""TurnFrame dispatch unions (S41, offline/unwired)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from contracts.target_response_policy import TargetResponsePolicyRequest
from contracts.target_response_spec import TargetResponseSpec
from core.target_response_verifier import TargetVerifiedComposedResponse


TargetTurnFrameTerminalMode = Literal[
    "clarify",
    "defer",
    "medical_handoff_nonmaterializable",
]


@dataclass(frozen=True, slots=True)
class TargetTurnFrameMaterializeDispatch:
    kind: Literal["materialize"]
    policy_request: TargetResponsePolicyRequest


@dataclass(frozen=True, slots=True)
class TargetTurnFrameTerminalDispatch:
    kind: Literal["terminal"]
    terminal_mode: TargetTurnFrameTerminalMode
    spec: TargetResponseSpec


@dataclass(frozen=True, slots=True)
class TargetTurnFrameBoundMaterializeResponse:
    kind: Literal["materialize"]
    dispatch: TargetTurnFrameMaterializeDispatch
    verified: TargetVerifiedComposedResponse


@dataclass(frozen=True, slots=True)
class TargetTurnFrameBoundTerminalResponse:
    kind: Literal["terminal"]
    dispatch: TargetTurnFrameTerminalDispatch
