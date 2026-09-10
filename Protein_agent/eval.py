"""Deterministic end-to-end evaluation harness for ProteinResearchAgent flows.

Why this exists
---------------
Unit tests mock the network, so they cannot catch an agent that calls the right
tools in the wrong order, calls a tool with data the tool cannot use, or produces
a final answer that quietly drops a required section. Those are integration
failures, and they only appear when the real agent runs.

This harness evaluates *behaviour*, not prose quality:

* the expected tool call order is a **golden trace** and is asserted exactly,
* tool outputs are validated **structurally** (payload keys, accession agreement,
  the number of structure links produced),
* the final answer is checked for the **contract sections** it must contain.

There is deliberately no second LLM judging the output. Every check here is a
deterministic assertion, so a run either passes or fails for a reason you can
read in the report -- and the suite costs exactly one model call per flow.

One flow is one row of the evaluation dataset. Adding a scenario means adding an
``AgentFlowScenario`` row, not a new framework.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import parse_qs, urlparse

__all__ = [
    "StructureExpectation",
    "TraceStep",
    "AgentFlowScenario",
    "CheckResult",
    "FlowReport",
    "GOLDEN_FLOWS",
    "HEMOGLOBIN_STRUCTURE_FLOW",
    "collect_trace",
    "tool_names",
    "decode_viewer_payload",
    "check_tool_sequence",
    "check_tool_responses_succeeded",
    "check_structure_payload",
    "check_single_structure_link",
    "check_answer_sections",
    "evaluate_flow",
    "run_flow",
]


# ---------------------------------------------------------------------------
# Scenario definition (the evaluation dataset)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StructureExpectation:
    """The structure handoff a flow is expected to produce."""

    uniprot_id: str
    pdb_id: str


@dataclass(frozen=True)
class TraceStep:
    """One tool call, with the response it returned when the run completed."""

    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    response: Any = None

    @property
    def ok(self) -> bool | None:
        """Tool-reported success flag, or None when the tool did not report one."""

        if isinstance(self.response, Mapping) and "ok" in self.response:
            return bool(self.response["ok"])
        return None


@dataclass(frozen=True)
class AgentFlowScenario:
    """A golden trace: the prompt, the expected tool order, and the contract.

    ``expected_tool_sequence`` is matched as a subsequence of the real trace, so
    a flow is allowed to call extra tools without failing -- it is not allowed to
    skip one or reorder the ones that matter.
    """

    name: str
    user_prompt: str
    expected_tool_sequence: tuple[str, ...]
    required_answer_sections: tuple[str, ...] = ()
    expected_structure: StructureExpectation | None = None
    notes: str = ""


@dataclass(frozen=True)
class CheckResult:
    """One deterministic verdict."""

    name: str
    passed: bool
    detail: str


@dataclass
class FlowReport:
    """The outcome of evaluating one flow."""

    scenario: str
    prompt: str
    steps: list[TraceStep]
    final_answer: str
    checks: list[CheckResult] = field(default_factory=list)
    error: str | None = None

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(check.passed for check in self.checks)

    def render(self) -> str:
        """Render a plain-text report suitable for a terminal or CI log."""

        lines: list[str] = []
        lines.append("=" * 72)
        lines.append(f"AGENT FLOW: {self.scenario}")
        lines.append("=" * 72)
        lines.append(f"prompt: {self.prompt}")
        lines.append("")

        lines.append(f"GOLDEN TRACE -- {len(self.steps)} tool call(s)")
        if not self.steps:
            lines.append("  (no tool calls captured)")
        for index, step in enumerate(self.steps, 1):
            flag = {True: "ok", False: "FAILED", None: "-"}[step.ok]
            arg_keys = ", ".join(sorted(str(key) for key in step.arguments))
            lines.append(f"  {index:>2}. {step.name}({arg_keys})  [{flag}]")
        lines.append("")

        lines.append("CHECKS")
        for check in self.checks:
            lines.append(f"  [{'PASS' if check.passed else 'FAIL'}] {check.name}")
            lines.append(f"         {check.detail}")

        if self.error:
            lines.append("")
            lines.append(f"RUNTIME ERROR: {self.error}")

        lines.append("")
        lines.append(f"VERDICT: {'PASS' if self.passed else 'FAIL'}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Trace capture
# ---------------------------------------------------------------------------


def _parts_of(event: Any) -> Iterable[Any]:
    content = getattr(event, "content", None)
    return getattr(content, "parts", None) or []


def collect_trace(events: Sequence[Any]) -> tuple[list[TraceStep], str]:
    """Turn raw ADK events into an ordered tool trace plus the final answer text.

    Works on any object shaped like an ADK ``Event`` (``.content.parts`` where a
    part exposes ``function_call``, ``function_response`` or ``text``), which
    keeps this function unit-testable without a live model.
    """

    steps: list[TraceStep] = []
    texts: list[str] = []

    for event in events:
        for part in _parts_of(event):
            call = getattr(part, "function_call", None)
            if call is not None:
                steps.append(
                    TraceStep(name=str(call.name), arguments=dict(call.args or {}))
                )
                continue

            response = getattr(part, "function_response", None)
            if response is not None:
                for index in range(len(steps) - 1, -1, -1):
                    if steps[index].name == response.name and steps[index].response is None:
                        steps[index] = TraceStep(
                            name=steps[index].name,
                            arguments=steps[index].arguments,
                            response=response.response,
                        )
                        break
                continue

            text = getattr(part, "text", None)
            if text:
                texts.append(str(text))

    return steps, (texts[-1] if texts else "")


def tool_names(steps: Sequence[TraceStep]) -> list[str]:
    """Return just the tool names, in call order."""

    return [step.name for step in steps]


# ---------------------------------------------------------------------------
# Deterministic checks
# ---------------------------------------------------------------------------


def check_tool_sequence(
    steps: Sequence[TraceStep],
    expected: Sequence[str],
) -> CheckResult:
    """Assert the expected tools were called in order (as a subsequence)."""

    actual = tool_names(steps)
    position = 0
    for name in actual:
        if position < len(expected) and name == expected[position]:
            position += 1

    if position == len(expected):
        return CheckResult(
            name="tool_sequence",
            passed=True,
            detail=f"called in order: {' -> '.join(expected)} (actual: {' -> '.join(actual) or 'none'})",
        )

    missing = list(expected[position:])
    return CheckResult(
        name="tool_sequence",
        passed=False,
        detail=(
            f"expected {' -> '.join(expected)}; got {' -> '.join(actual) or 'none'}; "
            f"missing from position {position + 1}: {missing}"
        ),
    )


def check_tool_responses_succeeded(steps: Sequence[TraceStep]) -> CheckResult:
    """Assert no tool reported a failure envelope."""

    failures = [
        f"{step.name} -> {str(step.response)[:160]}"
        for step in steps
        if step.ok is False
    ]
    if failures:
        return CheckResult(
            name="tool_responses",
            passed=False,
            detail="tool failure envelope(s): " + " | ".join(failures),
        )
    return CheckResult(
        name="tool_responses",
        passed=True,
        detail=f"{len(steps)} tool call(s), none reported ok=False",
    )


def _structure_responses(steps: Sequence[TraceStep]) -> list[TraceStep]:
    return [step for step in steps if step.name == "create_structure_view_link"]


def check_single_structure_link(steps: Sequence[TraceStep]) -> CheckResult:
    """The prompt contract allows exactly one viewer link per protein."""

    count = len(_structure_responses(steps))
    if count == 1:
        return CheckResult(
            name="single_structure_link",
            passed=True,
            detail="exactly one create_structure_view_link call",
        )
    return CheckResult(
        name="single_structure_link",
        passed=False,
        detail=f"expected exactly 1 create_structure_view_link call, got {count}",
    )


def decode_viewer_payload(viewer_url: str) -> dict[str, Any]:
    """Decode the url-safe base64 ``payload`` query parameter of a viewer URL."""

    raw = parse_qs(urlparse(viewer_url).query).get("payload", [""])[0]
    if not raw:
        raise ValueError("viewer URL has no payload parameter")
    padded = raw + "=" * (-len(raw) % 4)
    return json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))


def check_structure_payload(
    steps: Sequence[TraceStep],
    expectation: StructureExpectation,
) -> CheckResult:
    """Validate the structure handoff payload against the golden expectation."""

    responses = _structure_responses(steps)
    if not responses:
        return CheckResult(
            name="structure_payload",
            passed=False,
            detail="create_structure_view_link was never called",
        )

    step = responses[-1]
    result = step.response
    if not isinstance(result, Mapping):
        return CheckResult(
            name="structure_payload",
            passed=False,
            detail=f"unexpected tool response type: {type(result).__name__}",
        )
    if not result.get("ok"):
        return CheckResult(
            name="structure_payload",
            passed=False,
            detail=f"tool returned ok=False: {result.get('error')}",
        )

    problems: list[str] = []
    selected = str(result.get("selected_pdb_id") or "")
    if selected.upper() != expectation.pdb_id.upper():
        problems.append(f"selected_pdb_id={selected!r} expected {expectation.pdb_id!r}")

    viewer_url = str(result.get("viewer_url") or "")
    payload: dict[str, Any] = {}
    try:
        payload = decode_viewer_payload(viewer_url)
    except Exception as exc:  # noqa: BLE001 - report, do not crash the harness
        problems.append(f"viewer_url payload did not decode: {exc}")

    if payload:
        if str(payload.get("pdb_id", "")).upper() != expectation.pdb_id.upper():
            problems.append(f"payload pdb_id={payload.get('pdb_id')!r}")
        if str(payload.get("uniprot_id", "")).upper() != expectation.uniprot_id.upper():
            problems.append(f"payload uniprot_id={payload.get('uniprot_id')!r}")
        for key in ("protein_name", "chains", "view_mode", "source"):
            if key not in payload:
                problems.append(f"payload missing {key!r}")

    if problems:
        return CheckResult(
            name="structure_payload",
            passed=False,
            detail="; ".join(problems),
        )

    chains = payload.get("chains")
    return CheckResult(
        name="structure_payload",
        passed=True,
        detail=(
            f"{expectation.uniprot_id} -> PDB {selected}, "
            f"chains={chains}, keys={sorted(payload)}"
        ),
    )


def check_answer_sections(
    final_answer: str,
    required: Sequence[str],
) -> CheckResult:
    """Assert the final answer still carries the required contract sections.

    Deliberately a substring check, not a rubric: the contract names the sections
    the answer must contain, so their absence is a deterministic failure.
    """

    haystack = (final_answer or "").lower()
    missing = [section for section in required if section.lower() not in haystack]
    if missing:
        return CheckResult(
            name="answer_contract_sections",
            passed=False,
            detail=f"missing required section(s): {missing}",
        )
    return CheckResult(
        name="answer_contract_sections",
        passed=True,
        detail=f"all {len(required)} required section(s) present",
    )


def check_answer_not_empty(final_answer: str) -> CheckResult:
    """An empty answer is the classic silent agent failure."""

    length = len((final_answer or "").strip())
    return CheckResult(
        name="answer_not_empty",
        passed=length > 0,
        detail=f"final answer length: {length} characters",
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def evaluate_flow(scenario: AgentFlowScenario, events: Sequence[Any]) -> FlowReport:
    """Score a single flow's captured events against its golden trace."""

    steps, final_answer = collect_trace(events)
    report = FlowReport(
        scenario=scenario.name,
        prompt=scenario.user_prompt,
        steps=steps,
        final_answer=final_answer,
    )

    report.checks.append(check_tool_sequence(steps, scenario.expected_tool_sequence))
    report.checks.append(check_tool_responses_succeeded(steps))
    report.checks.append(check_answer_not_empty(final_answer))

    if scenario.expected_structure is not None:
        report.checks.append(check_single_structure_link(steps))
        report.checks.append(check_structure_payload(steps, scenario.expected_structure))

    if scenario.required_answer_sections:
        report.checks.append(
            check_answer_sections(final_answer, scenario.required_answer_sections)
        )

    return report


def run_flow(scenario: AgentFlowScenario, *, model: str | None = None) -> FlowReport:
    """Run one flow against the real ADK agent and evaluate it.

    Imports ADK lazily so the rest of this module stays usable offline in tests.
    """

    try:
        import asyncio

        from google.adk.runners import InMemoryRunner

        from .agent import root_agent
    except Exception as exc:  # noqa: BLE001 - surface a readable blocked state
        report = FlowReport(
            scenario=scenario.name,
            prompt=scenario.user_prompt,
            steps=[],
            final_answer="",
            error=f"ADK runtime unavailable: {exc}",
        )
        return report

    if model:
        root_agent.model = model

    runner = InMemoryRunner(agent=root_agent)
    try:
        events = asyncio.run(runner.run_debug(scenario.user_prompt, quiet=True))
    except Exception as exc:  # noqa: BLE001 - network/credentials/DB can all fail here
        report = FlowReport(
            scenario=scenario.name,
            prompt=scenario.user_prompt,
            steps=[],
            final_answer="",
            error=f"agent run failed: {type(exc).__name__}: {exc}",
        )
        return report

    return evaluate_flow(scenario, events)


# ---------------------------------------------------------------------------
# The evaluation dataset: golden flows
# ---------------------------------------------------------------------------


HEMOGLOBIN_STRUCTURE_FLOW = AgentFlowScenario(
    name="hemoglobin_structure_handoff",
    user_prompt=(
        "Use UniProt accession P68871 (human hemoglobin subunit beta). "
        "Verify the entry with the UniProt tools, predict its Q3 secondary structure, "
        "and then hand me the interactive 3D structure view link."
    ),
    expected_tool_sequence=("get_uniprot_entry", "predict_q3", "create_structure_view_link"),
    required_answer_sections=("accession", "function", "uncertainty", "confidence"),
    expected_structure=StructureExpectation(uniprot_id="P68871", pdb_id="2HHB"),
    notes=(
        "Capstone flow. Regression guard for the compact-UniProt-entry handoff bug: "
        "the agent passes its own fetched entry back into the structure tool."
    ),
)


GOLDEN_FLOWS: tuple[AgentFlowScenario, ...] = (HEMOGLOBIN_STRUCTURE_FLOW,)


def flow_names() -> set[str]:
    """Return the stable flow names used by the CLI and tests."""

    return {scenario.name for scenario in GOLDEN_FLOWS}
