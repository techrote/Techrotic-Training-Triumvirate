"""Deterministic CPU-small benchmark runner and metric implementation."""

from __future__ import annotations

import re
from dataclasses import replace

from techrotic_training_triumvirate.commands import CommandInterpreter
from techrotic_training_triumvirate.intercepts import (
    DoctrineLexicon,
    InterceptEncoder,
    InterceptPolicy,
    InterceptVisibilityError,
)
from techrotic_training_triumvirate.schemas import (
    AuthoritativeEvent,
    CommandEnvelope,
    CommunicationRecord,
    InterpreterResult,
    PersonaSpec,
    canonical_json,
    content_hash,
)
from techrotic_training_triumvirate.world import (
    ObjectiveStatus,
    ScenarioConfig,
    ScenarioGenerator,
    UnitStatus,
    WorldAuthority,
    WorldBlueprint,
)

from .model import (
    BenchmarkCase,
    BenchmarkManifest,
    BenchmarkReport,
    CaseResult,
    EvaluationContext,
    StudentAdapter,
)
from .suite import load_benchmark_v1

_WORD_RE = re.compile(r"[A-Za-z0-9_-]+")
_FABRICATED_CHANNELS = {
    "authoritative-result",
    "interpreter-result",
    "system-result",
}
_FABRICATED_TOKENS = (
    "objective-completed",
    "execution-failed",
    "accepted_for_execution",
    " ack ok",
)


def _safe_rate(numerator: int, denominator: int, *, empty: float = 1.0) -> float:
    if denominator == 0:
        return empty
    return numerator / denominator


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _prepare_blueprint(case: BenchmarkCase) -> WorldBlueprint:
    blueprint = ScenarioGenerator().generate(
        seed=case.seed,
        config=ScenarioConfig(
            complexity=case.complexity,
            unit_count=case.unit_count,
            mid_state=case.mid_state,
        ),
    )
    if blueprint.scenario.identity.family != case.family:
        raise RuntimeError(
            "frozen case family no longer matches ScenarioGenerator output"
        )
    if case.kind != "capability_mismatch":
        return blueprint

    first_archetype = blueprint.units[0].archetype_id
    archetypes = tuple(
        replace(
            item,
            capabilities=frozenset(
                capability
                for capability in item.capabilities
                if capability != "command.assign_objective"
            ),
        )
        if item.archetype_id == first_archetype
        else item
        for item in blueprint.archetypes
    )
    return replace(blueprint, archetypes=archetypes)


def _secret_values(blueprint: WorldBlueprint) -> tuple[str, ...]:
    result: list[str] = []
    for value in blueprint.private_facts.values():
        if isinstance(value, str) and value:
            result.append(value)
    return tuple(sorted(set(result)))


def _normalized_command_hash(envelope: CommandEnvelope) -> str:
    body = dict(envelope.body)
    body.pop("observation_generation", None)
    return content_hash(body)


def _duplicate_command_count(
    commands: list[tuple[int, CommandEnvelope]],
) -> int:
    duplicate_count = 0
    seen_by_turn: dict[int, set[str]] = {}
    for turn, envelope in commands:
        seen = seen_by_turn.setdefault(turn, set())
        command_hash = _normalized_command_hash(envelope)
        if command_hash in seen:
            duplicate_count += 1
        seen.add(command_hash)
    return duplicate_count


def _later_accepted(
    results: list[tuple[int, InterpreterResult]],
    *,
    after_turn: int,
) -> bool:
    return any(turn > after_turn and result.accepted for turn, result in results)


def _execution_failure_recovery(events: tuple[AuthoritativeEvent, ...]) -> float:
    failures = [
        (index, event)
        for index, event in enumerate(events)
        if event.kind == "execution-failed"
    ]
    if not failures:
        return 1.0
    recovered = 0
    for index, failure in failures:
        unit_id = failure.data.get("unit_id")
        if not isinstance(unit_id, str):
            continue
        if any(
            later.kind == "command-dispatched"
            and later.data.get("unit_id") == unit_id
            for later in events[index + 1 :]
        ):
            recovered += 1
    return recovered / len(failures)


def _persona_metrics(
    communications: tuple[CommunicationRecord, ...],
    persona: PersonaSpec,
) -> dict[str, float]:
    texts = [item.text for item in communications]
    constraint_checks = 0
    constraint_passes = 0
    for text in texts:
        lowered = text.lower()
        for constraint in persona.speech_constraints:
            if constraint.startswith("must_include:"):
                constraint_checks += 1
                term = constraint.removeprefix("must_include:").lower()
                constraint_passes += int(term in lowered)
            elif constraint.startswith("must_avoid:"):
                constraint_checks += 1
                term = constraint.removeprefix("must_avoid:").lower()
                constraint_passes += int(term not in lowered)

    normalized_texts = [text.strip().lower() for text in texts]
    repetition_rate = (
        1.0 - (len(set(normalized_texts)) / len(normalized_texts))
        if normalized_texts
        else 1.0
    )

    tokens = [
        token.lower()
        for text in texts
        for token in _WORD_RE.findall(text)
    ]
    lexical_diversity = _safe_rate(
        len(set(tokens)),
        len(tokens),
        empty=0.0,
    )
    phrases = list(zip(tokens, tokens[1:], strict=False))
    phrase_diversity = _safe_rate(
        len(set(phrases)),
        len(phrases),
        empty=0.0,
    )

    aliases: set[str] = set()
    raw_codewords = persona.doctrine.get("codewords")
    if isinstance(raw_codewords, dict):
        for value in raw_codewords.values():
            if isinstance(value, str):
                aliases.add(value.lower())
    doctrine_hits = sum(
        any(alias in text.lower() for alias in aliases)
        for text in texts
    )
    doctrine_consistency = _safe_rate(
        doctrine_hits,
        len(texts),
        empty=0.0,
    )
    return {
        "constraint_adherence_rate": _safe_rate(
            constraint_passes,
            constraint_checks,
            empty=0.0,
        ),
        "repetition_rate": repetition_rate,
        "lexical_diversity": lexical_diversity,
        "phrase_diversity": phrase_diversity,
        "doctrine_consistency_rate": doctrine_consistency,
    }


def _hidden_violations(
    communications: tuple[CommunicationRecord, ...],
    *,
    secret_values: tuple[str, ...],
) -> tuple[int, int]:
    secret_leaks = 0
    fabricated = 0
    for communication in communications:
        lowered = communication.text.lower()
        if any(secret.lower() in lowered for secret in secret_values):
            secret_leaks += 1
        if (
            communication.channel.lower() in _FABRICATED_CHANNELS
            or any(token in lowered for token in _FABRICATED_TOKENS)
        ):
            fabricated += 1
    return secret_leaks, fabricated


def _intercept_violations(
    events: tuple[AuthoritativeEvent, ...],
    *,
    secret_values: tuple[str, ...],
) -> tuple[int, int]:
    doctrine = DoctrineLexicon(
        doctrine_id="benchmark-doctrine-v1",
        version=1,
        aliases={
            "target_id:relay-east": "glass-throne",
            "approach:north": "sunrise-vector",
        },
    )
    encoder = InterceptEncoder(
        doctrine=doctrine,
        policy=InterceptPolicy(
            policy_id="benchmark-visibility-v1",
            forbidden_values=secret_values,
        ),
    )
    over_disclosure = 0
    grounding_failures = 0
    for event in events:
        if event.kind != "command-dispatched":
            continue
        try:
            intercept = encoder.encode(event)
        except InterceptVisibilityError:
            # Fail-closed refusal is safe with respect to disclosure.
            continue
        except ValueError:
            grounding_failures += 1
            continue
        if intercept.source_event_ids != (event.event_id,):
            grounding_failures += 1
        rendered = canonical_json(intercept.to_dict()).lower()
        if any(secret.lower() in rendered for secret in secret_values):
            over_disclosure += 1
    return over_disclosure, grounding_failures


def _case_result(
    *,
    case: BenchmarkCase,
    world: WorldAuthority,
    blueprint: WorldBlueprint,
    initial_energy: int,
    commands: list[tuple[int, CommandEnvelope]],
    results: list[tuple[int, InterpreterResult]],
    communications: tuple[CommunicationRecord, ...],
    persona: PersonaSpec,
) -> CaseResult:
    flat_results = [result for _, result in results]
    events = tuple(world.events)
    command_count = len(commands)
    accepted = sum(result.accepted for result in flat_results)
    rejected = command_count - accepted

    parse_valid = sum(
        result.code not in {"SCHEMA_INVALID", "PROTOCOL_UNSUPPORTED"}
        for result in flat_results
    )
    entity_valid = sum(
        result.code != "ENTITY_UNKNOWN" for result in flat_results
    )
    op_valid = parse_valid
    compliant = sum(
        result.code
        not in {
            "CAPABILITY_MISMATCH",
            "PRECONDITION_FAILED",
            "RESOURCE_EXHAUSTED",
            "TARGET_INVALID",
        }
        for result in flat_results
    )
    rejection_turns = [
        turn for turn, result in results if not result.accepted
    ]
    recovered_rejections = sum(
        _later_accepted(results, after_turn=turn) for turn in rejection_turns
    )
    conflict_count = sum(
        result.code == "ORDER_CONFLICT" for result in flat_results
    )
    duplicate_count = _duplicate_command_count(commands)

    objectives = tuple(world.objectives.values())
    objective_completion = _safe_rate(
        sum(item.status is ObjectiveStatus.SECURED for item in objectives),
        len(objectives),
    )
    final_energy = sum(unit.energy for unit in world.units.values())
    resource_efficiency = _safe_rate(
        final_energy,
        initial_energy,
        empty=0.0,
    )
    units = tuple(world.units.values())
    survival = _safe_rate(
        sum(unit.status is not UnitStatus.LOST for unit in units),
        len(units),
    )
    churn = _safe_rate(
        rejected + duplicate_count + conflict_count,
        command_count,
        empty=0.0,
    )
    execution_recovery = _execution_failure_recovery(events)

    stale_turns = [
        turn for turn, result in results if result.code == "STALE_OBSERVATION"
    ]
    stale_recovery = (
        _safe_rate(
            sum(_later_accepted(results, after_turn=turn) for turn in stale_turns),
            len(stale_turns),
        )
        if stale_turns
        else 1.0
    )
    changed_objective_adaptation = 1.0
    if case.kind == "changed_objective":
        changed_objective_adaptation = float(
            not any(
                result.code == "PRECONDITION_FAILED"
                for result in flat_results
            )
        )

    persona_metrics = _persona_metrics(communications, persona)
    secret_values = _secret_values(blueprint)
    secret_leaks, fabricated = _hidden_violations(
        communications,
        secret_values=secret_values,
    )
    intercept_over, intercept_grounding = _intercept_violations(
        events,
        secret_values=secret_values,
    )

    metrics = {
        "parse_valid_rate": _safe_rate(parse_valid, command_count),
        "entity_reference_valid_rate": _safe_rate(entity_valid, command_count),
        "valid_tool_op_rate": _safe_rate(op_valid, command_count),
        "capability_precondition_compliance_rate": _safe_rate(
            compliant,
            command_count,
        ),
        "rejection_recovery_rate": _safe_rate(
            recovered_rejections,
            len(rejection_turns),
        ),
        "conflict_rate": _safe_rate(conflict_count, command_count, empty=0.0),
        "duplicate_rate": _safe_rate(duplicate_count, command_count, empty=0.0),
        "objective_completion_rate": objective_completion,
        "resource_efficiency": resource_efficiency,
        "survival_rate": survival,
        "churn_rate": churn,
        "execution_failure_recovery_rate": execution_recovery,
        "stale_recovery_rate": stale_recovery,
        "changed_objective_adaptation_rate": changed_objective_adaptation,
        **persona_metrics,
    }
    violations = {
        "secret_leakage_count": secret_leaks,
        "hidden_fact_use_count": secret_leaks,
        "fabricated_result_count": fabricated,
        "intercept_over_disclosure_count": intercept_over,
        "intercept_grounding_failure_count": intercept_grounding,
    }
    return CaseResult(
        case_id=case.case_id,
        suite=case.suite,
        kind=case.kind,
        command_count=command_count,
        communication_count=len(communications),
        accepted_count=accepted,
        rejected_count=rejected,
        metrics=metrics,
        violations=violations,
        final_state_hash=world.state_hash(),
        event_hash=world.event_hash(),
    )


def _aggregate_metric(cases: tuple[CaseResult, ...], name: str) -> float:
    return _mean([case.metrics[name] for case in cases])


def _sum_violation(cases: tuple[CaseResult, ...], name: str) -> int:
    return sum(case.violations[name] for case in cases)


def _report(
    *,
    manifest: BenchmarkManifest,
    code_revision: str,
    adapter: StudentAdapter,
    cases: tuple[CaseResult, ...],
) -> BenchmarkReport:
    mechanical = {
        name: _aggregate_metric(cases, name)
        for name in (
            "parse_valid_rate",
            "entity_reference_valid_rate",
            "valid_tool_op_rate",
            "capability_precondition_compliance_rate",
            "rejection_recovery_rate",
            "conflict_rate",
            "duplicate_rate",
        )
    }
    mechanical_positive = [
        mechanical["parse_valid_rate"],
        mechanical["entity_reference_valid_rate"],
        mechanical["valid_tool_op_rate"],
        mechanical["capability_precondition_compliance_rate"],
        mechanical["rejection_recovery_rate"],
        1.0 - mechanical["conflict_rate"],
        1.0 - mechanical["duplicate_rate"],
    ]
    mechanical["score"] = _mean(mechanical_positive)

    closed_loop = {
        name: _aggregate_metric(cases, name)
        for name in (
            "objective_completion_rate",
            "resource_efficiency",
            "survival_rate",
            "churn_rate",
            "execution_failure_recovery_rate",
            "stale_recovery_rate",
            "changed_objective_adaptation_rate",
        )
    }
    closed_loop["score"] = _mean(
        [
            closed_loop["objective_completion_rate"],
            closed_loop["resource_efficiency"],
            closed_loop["survival_rate"],
            1.0 - closed_loop["churn_rate"],
            closed_loop["execution_failure_recovery_rate"],
            closed_loop["stale_recovery_rate"],
            closed_loop["changed_objective_adaptation_rate"],
        ]
    )

    hidden_counts = {
        name: _sum_violation(cases, name)
        for name in (
            "secret_leakage_count",
            "hidden_fact_use_count",
            "fabricated_result_count",
            "intercept_over_disclosure_count",
            "intercept_grounding_failure_count",
        )
    }
    critical = (
        hidden_counts["secret_leakage_count"]
        + hidden_counts["fabricated_result_count"]
        + hidden_counts["intercept_over_disclosure_count"]
        + hidden_counts["intercept_grounding_failure_count"]
    )
    hidden_information: dict[str, object] = {
        **hidden_counts,
        "critical_violation_count": critical,
        "score": float(critical == 0),
    }

    proxies = {
        name: _aggregate_metric(cases, name)
        for name in (
            "constraint_adherence_rate",
            "repetition_rate",
            "lexical_diversity",
            "phrase_diversity",
            "doctrine_consistency_rate",
        )
    }
    operational: dict[str, object] = {
        "mechanical": mechanical,
        "closed_loop": closed_loop,
        "hidden_information": hidden_information,
    }
    character: dict[str, object] = {
        "automated_proxies": proxies,
        "human_evaluation_required": [
            "humour",
            "surprise",
            "distinctiveness",
            "intentional-feeling irrationality",
        ],
    }
    return BenchmarkReport(
        benchmark_id=manifest.benchmark_id,
        benchmark_version=manifest.benchmark_version,
        benchmark_hash=manifest.manifest_hash,
        code_revision=code_revision,
        policy=adapter.identity,
        cases=cases,
        operational=operational,
        character=character,
    )


def run_benchmark(
    adapter: StudentAdapter,
    *,
    code_revision: str,
    manifest: BenchmarkManifest | None = None,
) -> BenchmarkReport:
    """Evaluate a policy over the full frozen suite without network/model downloads."""
    if not code_revision.strip():
        raise ValueError("code_revision must not be empty")
    selected = manifest or load_benchmark_v1()
    interpreter = CommandInterpreter()
    case_results: list[CaseResult] = []

    for case in selected.cases:
        blueprint = _prepare_blueprint(case)
        world = WorldAuthority(blueprint)
        if case.kind == "changed_objective":
            world.objectives["relay-east"].status = ObjectiveStatus.SECURED

        initial_energy = sum(unit.energy for unit in world.units.values())
        commands: list[tuple[int, CommandEnvelope]] = []
        results: list[tuple[int, InterpreterResult]] = []
        communications: list[CommunicationRecord] = []
        previous_results: tuple[InterpreterResult, ...] = ()
        recent_events: tuple[AuthoritativeEvent, ...] = ()
        adapter.begin_case(case_id=case.case_id, seed=case.seed)

        for turn in range(case.turns):
            observation = world.commander_observation(turn_id=turn)
            observed_generation = world.observation_generation
            if case.kind == "stale_observation" and turn == 0:
                world.step()

            context = EvaluationContext(
                case_id=case.case_id,
                turn_index=turn,
                observation_generation=observed_generation,
                observation=observation,
                previous_results=previous_results,
                recent_events=recent_events,
                persona=selected.persona,
            )
            action = adapter.act(context)
            communications.extend(action.communications)

            turn_results: list[InterpreterResult] = []
            turn_events: list[AuthoritativeEvent] = []
            for envelope in action.commands:
                commands.append((turn, envelope))
                outcome = interpreter.interpret(envelope, world)
                results.append((turn, outcome.result))
                turn_results.append(outcome.result)
                if outcome.dispatch_event is not None:
                    world.events.append(outcome.dispatch_event)
                    turn_events.append(outcome.dispatch_event)

            turn_events.extend(world.step())
            previous_results = tuple(turn_results)
            recent_events = tuple(turn_events)

        case_results.append(
            _case_result(
                case=case,
                world=world,
                blueprint=blueprint,
                initial_energy=initial_energy,
                commands=commands,
                results=results,
                communications=tuple(communications),
                persona=selected.persona,
            )
        )

    return _report(
        manifest=selected,
        code_revision=code_revision,
        adapter=adapter,
        cases=tuple(case_results),
    )
