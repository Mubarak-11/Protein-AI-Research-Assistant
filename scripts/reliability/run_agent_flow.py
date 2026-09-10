"""Run a golden agent flow end to end and report deterministic pass/fail checks.

Thin wrapper around ``Protein_agent.eval``. One flow = one row of the evaluation
dataset; see ``docs/agent_eval_harness.md`` for the design.

Usage:
    python -m scripts.reliability.run_agent_flow --list
    python -m scripts.reliability.run_agent_flow
    python -m scripts.reliability.run_agent_flow --flow hemoglobin_structure_handoff
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from Protein_agent.eval import (
    GOLDEN_FLOWS,
    decode_viewer_payload,
    run_flow,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_BLOCKED = 2


def _load_env(env_file: str | None) -> str | None:
    """Load a .env file when one is available, without hard-failing if absent."""

    candidate = Path(env_file) if env_file else PROJECT_ROOT / ".env"
    if not candidate.is_file():
        return None
    try:
        from dotenv import load_dotenv
    except ImportError:
        return None
    load_dotenv(candidate, override=False)
    return str(candidate)


def _print_flows() -> None:
    print(f"{len(GOLDEN_FLOWS)} golden flow(s) in the evaluation dataset:\n")
    for scenario in GOLDEN_FLOWS:
        print(f"  {scenario.name}")
        print(f"    prompt   : {scenario.user_prompt}")
        print(f"    expected : {' -> '.join(scenario.expected_tool_sequence)}")
        if scenario.expected_structure:
            print(
                "    structure: "
                f"{scenario.expected_structure.uniprot_id} -> PDB {scenario.expected_structure.pdb_id}"
            )
        if scenario.notes:
            print(f"    notes    : {scenario.notes}")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--flow",
        default=GOLDEN_FLOWS[0].name,
        help="Golden flow name to run (see --list).",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("PROTEIN_AGENT_MODEL"),
        help="Override the ADK model for this run (default: PROTEIN_AGENT_MODEL).",
    )
    parser.add_argument(
        "--env-file",
        default=None,
        help="Path to a .env file holding credentials (default: <project root>/.env).",
    )
    parser.add_argument("--list", action="store_true", help="List the golden flows and exit.")
    args = parser.parse_args()

    if args.list:
        _print_flows()
        return EXIT_PASS

    scenario = next((s for s in GOLDEN_FLOWS if s.name == args.flow), None)
    if scenario is None:
        known = ", ".join(sorted(s.name for s in GOLDEN_FLOWS))
        print(f"Unknown flow {args.flow!r}. Known flows: {known}", file=sys.stderr)
        return EXIT_BLOCKED

    loaded = _load_env(args.env_file)
    print(f"env file : {loaded or '(none found - relying on the current environment)'}")
    print("running the real agent; this needs credentials, network and local services")
    print()

    report = run_flow(scenario, model=args.model)
    print(report.render())

    if report.error:
        print()
        print("BLOCKED: the flow could not run, so it was not evaluated.")
        return EXIT_BLOCKED

    for step in report.steps:
        if step.name != "create_structure_view_link" or not isinstance(step.response, dict):
            continue
        url = str(step.response.get("viewer_url") or "")
        if not url:
            continue
        print()
        print("STRUCTURE VIEWER HANDOFF")
        print(f"  url     : {url}")
        try:
            print(f"  payload : {decode_viewer_payload(url)}")
        except Exception as exc:  # noqa: BLE001 - report only
            print(f"  payload : could not decode ({exc})")

    return EXIT_PASS if report.passed else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main())
