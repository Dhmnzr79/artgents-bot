"""Deterministic execution schedule for coordinated four-config architecture comparison."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from evals.v5.arch_compare.arch_compare_configs import config_by_id
from evals.v5.arch_compare.arch_compare_contract import CONFIG_IDS
from evals.v5.arch_compare.arch_compare_live_contract import assert_expected_job_counts
from evals.v5.arch_compare.arch_compare_matrix import (
    ArchCompareScenarioSpec,
    parse_scenario_specs,
)


@dataclass(frozen=True, slots=True)
class ArchCompareScenarioConfigJob:
    order_index: int
    scenario_id: str
    config_id: str
    session_id: str
    scenario_index: int
    config_position: int


@dataclass(frozen=True, slots=True)
class ArchCompareTurnConfigJob:
    order_index: int
    scenario_id: str
    turn_id: str
    config_id: str
    session_id: str
    provider_turn: bool
    scenario_index: int
    config_position: int
    turn_index: int


@dataclass(frozen=True, slots=True)
class ArchCompareExecutionSchedule:
    schedule_seed: str
    scenario_config_jobs: tuple[ArchCompareScenarioConfigJob, ...]
    turn_config_jobs: tuple[ArchCompareTurnConfigJob, ...]
    config_order_by_scenario: dict[str, tuple[str, ...]]
    provider_turn_jobs: int
    code_only_turn_jobs: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "schedule_seed": self.schedule_seed,
            "scenario_config_jobs": [asdict(row) for row in self.scenario_config_jobs],
            "turn_config_jobs": [asdict(row) for row in self.turn_config_jobs],
            "config_order_by_scenario": {
                key: list(value) for key, value in self.config_order_by_scenario.items()
            },
            "provider_turn_jobs": self.provider_turn_jobs,
            "code_only_turn_jobs": self.code_only_turn_jobs,
        }


def rotated_config_order(*, scenario_index: int) -> tuple[str, ...]:
    shift = scenario_index % len(CONFIG_IDS)
    return tuple(CONFIG_IDS[shift:] + CONFIG_IDS[:shift])


def session_id_for(*, attempt_id: str, scenario_id: str, config_id: str) -> str:
    return f"arch_compare_live-{attempt_id}-{scenario_id}-{config_id}"


def build_execution_schedule(*, attempt_id: str) -> ArchCompareExecutionSchedule:
    scenarios = parse_scenario_specs()
    scenario_config_jobs: list[ArchCompareScenarioConfigJob] = []
    turn_config_jobs: list[ArchCompareTurnConfigJob] = []
    config_order_by_scenario: dict[str, tuple[str, ...]] = {}
    order_index = 0
    provider_turn_jobs = 0
    code_only_turn_jobs = 0

    for scenario_index, scenario in enumerate(scenarios):
        config_order = rotated_config_order(scenario_index=scenario_index)
        config_order_by_scenario[scenario.scenario_id] = config_order
        for config_position, config_id in enumerate(config_order):
            session = session_id_for(
                attempt_id=attempt_id,
                scenario_id=scenario.scenario_id,
                config_id=config_id,
            )
            scenario_config_jobs.append(
                ArchCompareScenarioConfigJob(
                    order_index=order_index,
                    scenario_id=scenario.scenario_id,
                    config_id=config_id,
                    session_id=session,
                    scenario_index=scenario_index,
                    config_position=config_position,
                )
            )
            order_index += 1
            for turn_index, turn in enumerate(scenario.turns):
                turn_config_jobs.append(
                    ArchCompareTurnConfigJob(
                        order_index=len(turn_config_jobs),
                        scenario_id=scenario.scenario_id,
                        turn_id=turn.turn_id,
                        config_id=config_id,
                        session_id=session,
                        provider_turn=turn.provider_turn,
                        scenario_index=scenario_index,
                        config_position=config_position,
                        turn_index=turn_index,
                    )
                )
                if turn.provider_turn:
                    provider_turn_jobs += 1
                else:
                    code_only_turn_jobs += 1

    schedule = ArchCompareExecutionSchedule(
        schedule_seed=attempt_id,
        scenario_config_jobs=tuple(scenario_config_jobs),
        turn_config_jobs=tuple(turn_config_jobs),
        config_order_by_scenario=config_order_by_scenario,
        provider_turn_jobs=provider_turn_jobs,
        code_only_turn_jobs=code_only_turn_jobs,
    )
    assert_expected_job_counts(
        scenario_config_jobs=len(schedule.scenario_config_jobs),
        turn_config_jobs=len(schedule.turn_config_jobs),
    )
    return schedule


def config_position_balance(schedule: ArchCompareExecutionSchedule) -> dict[str, dict[int, int]]:
    counts: dict[str, dict[int, int]] = {config_id: {0: 0, 1: 0, 2: 0, 3: 0} for config_id in CONFIG_IDS}
    for row in schedule.scenario_config_jobs:
        counts[row.config_id][row.config_position] += 1
    return counts


def scenario_for_id(scenario_id: str) -> ArchCompareScenarioSpec:
    for row in parse_scenario_specs():
        if row.scenario_id == scenario_id:
            return row
    raise KeyError(scenario_id)


def turn_for_job(job: ArchCompareTurnConfigJob):
    scenario = scenario_for_id(job.scenario_id)
    for turn in scenario.turns:
        if turn.turn_id == job.turn_id:
            return turn
    raise KeyError(job.turn_id)


def config_for_job(job: ArchCompareTurnConfigJob):
    return config_by_id(job.config_id)
