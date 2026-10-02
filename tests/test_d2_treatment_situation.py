"""D2-117 replaces the retired treatment record with neutral task volume."""
import json
from datetime import date
import pytest
from contracts.d2_dialogue_result import D2DialogueResult, DiscussionVolume
from pydantic import ValidationError
from core.response_plan_materialization import resolve_d2_operations
from core.response_text_renderer import render_response_text
from core.response_ui_projection import project_response_ui
from tests.test_d2_single_request import _sources


def result(volume=None):
    return D2DialogueResult.model_validate({"outcome":"dialogue","blocks":[{
        "request_id":"r1","kind":"price","target":{"type":"service","id":"service_one"},"volume":volume,
    }]})


def resolve(task):
    sources=_sources()
    payload=sources.model_dump()
    for offer in payload["material_authority"]["bundle"]["offers"]:
        offer["applies_to_extents"]=["one_tooth","few_teeth","full_arch"]
    sources=type(sources).model_validate(payload)
    return resolve_d2_operations(task.blocks,sources,as_of=date(2026,9,18)),sources


@pytest.mark.parametrize("value", [None, {"extent":"unknown"},
    {"extent":"one_tooth","tooth_count":1},
    {"extent":"few_teeth","tooth_count":3,"jaw":"lower"},
    {"extent":"full_arch","tooth_count":6,"jaw":"upper"}])
def test_volume_is_frozen_on_the_task_without_patient_fields(value):
    task=result(value)
    outcome,_=resolve(task)
    part=outcome.resolved.d2_request_parts[0]
    assert part.discussion_scope.volume == task.blocks[0].volume
    assert part.discussion_scope.service_id == "service_one"
    assert "d2_treatment_situation" not in outcome.resolved.model_dump()
    assert "subject_id" not in part.model_dump()


@pytest.mark.parametrize("count", [0,-1,True,1.5,"3"])
def test_count_requires_a_positive_strict_integer(count):
    with pytest.raises(ValidationError):
        result({"extent":"few_teeth","tooth_count":count})


@pytest.mark.parametrize("extent,count", [("unknown",3),("one_tooth",3),("few_teeth",1)])
def test_contradictory_volume_is_rejected(extent,count):
    with pytest.raises(ValidationError):
        result({"extent":extent,"tooth_count":count})


@pytest.mark.parametrize("field", ["scope_commitment","continuity","subject_id","situation_owner_id"])
def test_old_patient_controls_are_rejected_not_renamed(field):
    with pytest.raises(ValidationError):
        DiscussionVolume.model_validate({"extent":"one_tooth",field:"same"})


def test_each_operation_can_express_its_own_discussed_volume():
    first=result({"extent":"one_tooth","tooth_count":1}).blocks[0]
    second=first.model_copy(update={"request_id":"r2","volume":DiscussionVolume(extent="few_teeth",tooth_count=3)})
    task=D2DialogueResult(outcome="dialogue",blocks=(first,second))
    outcome,_=resolve(task)
    assert [p.discussion_scope.volume.tooth_count for p in outcome.resolved.d2_request_parts] == [1,3]
    assert outcome.resolved.d2_request_parts[1].status == "deferred"


def test_completed_volume_prices_and_ui_do_not_change_when_sources_change():
    outcome,sources=resolve(result({"extent":"few_teeth","tooth_count":3}))
    frozen=outcome.resolved.model_dump_json()
    sources.material_authority.bundle.offers.clear()
    assert outcome.resolved.model_dump_json() == frozen
    assert render_response_text(outcome.resolved) == outcome.rendered_text
    assert project_response_ui(outcome.resolved) == outcome.ui_projection
