"""Typed requirement for whether a turn must run Medical Boundary classification (PERF-2).

See TASK.md § FINAL_SAFE_MEDICAL_BOUNDARY_BYPASS and
docs/evidence/performance/FINAL_SAFE_MEDICAL_BOUNDARY_BYPASS_SEAM_AUDIT.md. Governance
correction (@ bfcc59c) narrowed this from five candidate values to exactly two: pure
free-text price lookup and exact FAQ are documented as deferred future capabilities but are
not returnable values of this type, and the structured-capability short-circuit
(clinic_contact/service_availability) is not modeled here at all -- its own call site already
returns before this type would ever be consulted.
"""

from __future__ import annotations

from typing import Literal

TargetMedicalBoundaryRequirement = Literal[
    "required",
    "bypass_governed_ui",
]
