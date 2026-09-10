"""Offline tests for the deterministic agent-flow evaluation harness.

These tests never touch the network or a model: they replay synthetic ADK events
through the harness so the trace matching, payload validation and contract checks
are proven independently of any live run.
"""

from __future__ import annotations

import unittest

from Protein_agent.eval import (
    HEMOGLOBIN_STRUCTURE_FLOW,
    StructureExpectation,
    check_answer_sections,
    check_single_structure_link,
    check_structure_payload,
    check_tool_responses_succeeded,
    check_tool_sequence,
    collect_trace,
    decode_viewer_payload,
    evaluate_flow,
    flow_names,
    tool_names,
)
from protein_structure_view.links import build_studio_url, decode_payload, encode_payload

P68871_PAYLOAD = {
    "protein_name": "Hemoglobin subunit beta",
    "uniprot_id": "P68871",
    "pdb_id": "2HHB",
    "chains": ["A", "B", "C", "D"],
    "focus_residues": [],
    "view_mode": "Function",
    "summary": "Human hemoglobin subunit beta, involved in oxygen transport.",
    "source": {
        "database": "RCSB PDB",
        "url": "https://www.rcsb.org/structure/2HHB",
        "experimental_method": "X-ray",
        "resolution": 1.74,
    },
}

GOOD_ANSWER = (
    "UniProt accession P68871 (Hemoglobin subunit beta). "
    "Function: oxygen transport. Accession verified as reviewed. "
    "Uncertainty: prediction confidence is a model score. "
    "Confidence summary: 55.3%."
)


# --- minimal ADK-shaped stand-ins -------------------------------------------


class _Call:
    def __init__(self, name, args):
        self.name = name
        self.args = args


class _Response:
    def __init__(self, name, response):
        self.name = name
        self.response = response


class _Part:
    def __init__(self, *, call=None, response=None, text=None):
        self.function_call = call
        self.function_response = response
        self.text = text


class _Content:
    def __init__(self, parts):
        self.parts = parts


class _Event:
    def __init__(self, parts):
        self.content = _Content(parts)


def _call(name, args=None):
    return _Event([_Part(call=_Call(name, args or {}))])


def _response(name, payload):
    return _Event([_Part(response=_Response(name, payload))])


def _text(value):
    return _Event([_Part(text=value)])


def golden_events(structure_response=None):
    """The expected happy-path event stream for the hemoglobin capstone flow."""

    if structure_response is None:
        structure_response = {
            "ok": True,
            "selected_pdb_id": "2HHB",
            "viewer_url": build_studio_url(P68871_PAYLOAD),
            "payload": P68871_PAYLOAD,
        }
    return [
        _call("get_uniprot_entry", {"accession": "P68871"}),
        _response("get_uniprot_entry", {"ok": True, "accession": "P68871", "length": 147}),
        _call("predict_q3", {"seq": "MVHLTPEEK"}),
        _response("predict_q3", {"ok": True, "prediction": "HHHHHHCCC", "confidence": 0.553}),
        _call("create_structure_view_link", {"accession": "P68871"}),
        _response("create_structure_view_link", structure_response),
        _text(GOOD_ANSWER),
    ]


class TraceCollectionTests(unittest.TestCase):
    def test_collect_trace_pairs_calls_with_their_responses_in_order(self) -> None:
        steps, answer = collect_trace(golden_events())

        self.assertEqual(
            tool_names(steps),
            ["get_uniprot_entry", "predict_q3", "create_structure_view_link"],
        )
        self.assertEqual(steps[0].response["accession"], "P68871")
        self.assertEqual(steps[1].response["confidence"], 0.553)
        self.assertTrue(steps[2].response["ok"])
        self.assertEqual(answer, GOOD_ANSWER)

    def test_collect_trace_handles_missing_response_and_empty_stream(self) -> None:
        steps, answer = collect_trace([_call("get_uniprot_entry", {"accession": "P68871"})])
        self.assertEqual(len(steps), 1)
        self.assertIsNone(steps[0].response)
        self.assertIsNone(steps[0].ok)
        self.assertEqual(answer, "")

        steps, answer = collect_trace([])
        self.assertEqual(steps, [])
        self.assertEqual(answer, "")


class ToolSequenceTests(unittest.TestCase):
    def test_expected_order_passes(self) -> None:
        steps, _ = collect_trace(golden_events())
        result = check_tool_sequence(steps, HEMOGLOBIN_STRUCTURE_FLOW.expected_tool_sequence)
        self.assertTrue(result.passed, result.detail)

    def test_extra_tools_are_allowed_but_missing_ones_fail(self) -> None:
        steps, _ = collect_trace(
            [
                _call("search_uniprot", {"query": "hemoglobin"}),
                *_call_and_response("get_uniprot_entry"),
                *_call_and_response("predict_q3"),
                # create_structure_view_link never called
            ]
        )
        result = check_tool_sequence(steps, HEMOGLOBIN_STRUCTURE_FLOW.expected_tool_sequence)
        self.assertFalse(result.passed)
        self.assertIn("create_structure_view_link", result.detail)

    def test_wrong_order_fails(self) -> None:
        events = [
            *_call_and_response("get_uniprot_entry"),
            *_call_and_response("create_structure_view_link"),
            *_call_and_response("predict_q3"),
        ]
        steps, _ = collect_trace(events)
        result = check_tool_sequence(steps, HEMOGLOBIN_STRUCTURE_FLOW.expected_tool_sequence)
        self.assertFalse(result.passed)


def _call_and_response(name):
    return [_call(name, {}), _response(name, {"ok": True})]


class ToolResponseTests(unittest.TestCase):
    def test_clean_responses_pass(self) -> None:
        steps, _ = collect_trace(golden_events())
        self.assertTrue(check_tool_responses_succeeded(steps).passed)

    def test_failure_envelope_fails_and_names_the_tool(self) -> None:
        broken = {
            "ok": False,
            "error": "Structure view link could not be created: No PDB structure candidate was available for this protein.",
        }
        steps, _ = collect_trace(golden_events(structure_response=broken))
        result = check_tool_responses_succeeded(steps)
        self.assertFalse(result.passed)
        self.assertIn("create_structure_view_link", result.detail)


class StructurePayloadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.expectation = StructureExpectation(uniprot_id="P68871", pdb_id="2HHB")

    def test_good_handoff_passes(self) -> None:
        steps, _ = collect_trace(golden_events())
        result = check_structure_payload(steps, self.expectation)
        self.assertTrue(result.passed, result.detail)
        self.assertIn("2HHB", result.detail)

    def test_wrong_pdb_fails(self) -> None:
        wrong = dict(P68871_PAYLOAD, pdb_id="1GFL")
        steps, _ = collect_trace(
            golden_events(
                structure_response={
                    "ok": True,
                    "selected_pdb_id": "1GFL",
                    "viewer_url": build_studio_url(wrong),
                    "payload": wrong,
                }
            )
        )
        result = check_structure_payload(steps, self.expectation)
        self.assertFalse(result.passed)
        self.assertIn("selected_pdb_id", result.detail)

    def test_payload_missing_keys_fails(self) -> None:
        thin = {"pdb_id": "2HHB", "uniprot_id": "P68871"}
        steps, _ = collect_trace(
            golden_events(
                structure_response={
                    "ok": True,
                    "selected_pdb_id": "2HHB",
                    "viewer_url": build_studio_url(thin),
                    "payload": thin,
                }
            )
        )
        result = check_structure_payload(steps, self.expectation)
        self.assertFalse(result.passed)
        for key in ("protein_name", "chains", "view_mode", "source"):
            self.assertIn(key, result.detail)

    def test_missing_structure_call_fails(self) -> None:
        steps, _ = collect_trace([*_call_and_response("get_uniprot_entry")])
        result = check_structure_payload(steps, self.expectation)
        self.assertFalse(result.passed)
        self.assertIn("never called", result.detail)

    def test_single_link_check_counts_calls(self) -> None:
        steps, _ = collect_trace(golden_events())
        self.assertTrue(check_single_structure_link(steps).passed)

        doubled, _ = collect_trace(golden_events() + [_call("create_structure_view_link", {})])
        result = check_single_structure_link(doubled)
        self.assertFalse(result.passed)
        self.assertIn("expected exactly 1", result.detail)


class PayloadRoundTripTests(unittest.TestCase):
    def test_harness_decodes_what_the_agent_encodes(self) -> None:
        url = build_studio_url(P68871_PAYLOAD)
        self.assertEqual(decode_viewer_payload(url), decode_payload(encode_payload(P68871_PAYLOAD)))
        self.assertEqual(decode_viewer_payload(url)["pdb_id"], "2HHB")

    def test_missing_payload_parameter_raises(self) -> None:
        with self.assertRaises(ValueError):
            decode_viewer_payload("http://127.0.0.1:8765/protein-sculpture-studio.html")


class AnswerContractTests(unittest.TestCase):
    def test_required_sections_present(self) -> None:
        self.assertTrue(
            check_answer_sections(GOOD_ANSWER, HEMOGLOBIN_STRUCTURE_FLOW.required_answer_sections).passed
        )

    def test_missing_section_is_named(self) -> None:
        result = check_answer_sections(
            "UniProt accession P68871 with a function description.",
            HEMOGLOBIN_STRUCTURE_FLOW.required_answer_sections,
        )
        self.assertFalse(result.passed)
        self.assertIn("uncertainty", result.detail)
        self.assertIn("confidence", result.detail)

    def test_empty_answer_fails_the_contract(self) -> None:
        self.assertFalse(
            check_answer_sections("", HEMOGLOBIN_STRUCTURE_FLOW.required_answer_sections).passed
        )


class FlowEvaluationTests(unittest.TestCase):
    def test_golden_events_pass_every_check(self) -> None:
        report = evaluate_flow(HEMOGLOBIN_STRUCTURE_FLOW, golden_events())

        self.assertTrue(report.passed, report.render())
        check_names = {check.name for check in report.checks}
        self.assertEqual(
            check_names,
            {
                "tool_sequence",
                "tool_responses",
                "answer_not_empty",
                "single_structure_link",
                "structure_payload",
                "answer_contract_sections",
            },
        )
        self.assertIn("VERDICT: PASS", report.render())

    def test_regression_compact_entry_bug_is_caught(self) -> None:
        """The bug that broke the capstone: the structure tool refused its own agent's data."""

        broken = {
            "ok": False,
            "error": "Structure view link could not be created: No PDB structure candidate was available for this protein.",
        }
        report = evaluate_flow(
            HEMOGLOBIN_STRUCTURE_FLOW, golden_events(structure_response=broken)
        )

        self.assertFalse(report.passed)
        failed = {check.name for check in report.checks if not check.passed}
        self.assertIn("tool_responses", failed)
        self.assertIn("structure_payload", failed)
        self.assertIn("VERDICT: FAIL", report.render())

    def test_empty_answer_is_reported_as_a_failure(self) -> None:
        events = golden_events()[:-1]  # drop the final text event
        report = evaluate_flow(HEMOGLOBIN_STRUCTURE_FLOW, events)

        self.assertFalse(report.passed)
        names = {check.name for check in report.checks if not check.passed}
        self.assertIn("answer_not_empty", names)
        self.assertIn("answer_contract_sections", names)


class GoldenFlowRegistryTests(unittest.TestCase):
    def test_registry_exposes_the_capstone_flow(self) -> None:
        self.assertIn("hemoglobin_structure_handoff", flow_names())
        self.assertEqual(
            HEMOGLOBIN_STRUCTURE_FLOW.expected_structure,
            StructureExpectation(uniprot_id="P68871", pdb_id="2HHB"),
        )


if __name__ == "__main__":
    unittest.main()
