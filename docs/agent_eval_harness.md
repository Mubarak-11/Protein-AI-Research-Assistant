# Agent Evaluation Harness

A deterministic, end-to-end evaluation harness for `ProteinResearchAgent` flows.

This document explains what the harness is, why it is built the way it is, and how to
extend it. It is deliberately small: one flow is one row of the evaluation dataset.

| Piece | Path | Role |
|---|---|---|
| Harness logic | `Protein_agent/eval.py` | Scenarios, trace capture, checks, reporting |
| CLI runner | `scripts/reliability/run_agent_flow.py` | Thin wrapper: run a flow, print the report, set the exit code |
| Offline tests | `tests/test_eval_harness.py` | Replays synthetic events so the checks are proven without a model |

There are now **56 unit tests**, of which 21 cover the harness logic and run entirely
offline. The harness itself costs one model call per flow, because the live run is the
thing under test.

---

## 1. The problem it solves

The unit suite mocks the network. That makes it fast and reliable, and it also means it
**cannot** catch a class of failure that only appears against the real agent:

- the agent calls the right tools in the wrong order,
- the agent calls a tool with data the tool cannot consume,
- a tool silently returns an error envelope and the answer is quietly degraded,
- the agent produces an empty or contract-violating final answer,
- a documented handoff contract is not actually honoured end to end.

Both real defects found in this project were of that kind, and **both passed the unit
suite at the time**:

1. **The structure tool rejected its own agent's data.** `get_uniprot_entry` returns a
   compact normalized entry. The agent's natural move — fetch the entry, then hand that
   same entry to `create_structure_view_link` — made the tool report
   *"No PDB structure candidate was available for this protein."* Accession-only calls
   worked, so the failure hid.
2. **The viewer never implemented the payload contract.** Its own documentation listed
   payload support as a future target, so the viewer rendered a default preset and
   silently ignored the protein the agent selected.

Neither is visible from a mocked test. Both are obvious from a trace.

---

## 2. Design: golden trace + assertions, no judge model

The core idea is that **behaviour is asserted, not judged**.

```
prompt ──► real ADK agent ──► event stream ──► trace ──► deterministic checks ──► PASS/FAIL
                                  │
                                  └── also: the golden trace itself, for humans and for diffs
```

An `AgentFlowScenario` is the dataset row:

```python
AgentFlowScenario(
    name="hemoglobin_structure_handoff",
    user_prompt="Use UniProt accession P68871 …",
    expected_tool_sequence=("get_uniprot_entry", "predict_q3", "create_structure_view_link"),
    required_answer_sections=("accession", "function", "uncertainty", "confidence"),
    expected_structure=StructureExpectation(uniprot_id="P68871", pdb_id="2HHB"),
)
```

The checks applied to every run:

| Check | Asserts | Why it is deterministic |
|---|---|---|
| `tool_sequence` | Expected tools were called **in order** (matched as a subsequence, so extra tools are allowed) | Compares two lists of names |
| `tool_responses` | No tool returned an `ok=False` envelope | Reads a boolean the tools already set |
| `answer_not_empty` | The agent did not silently return nothing | Length of the final text |
| `single_structure_link` | Exactly one viewer link was produced | Counts calls to one tool |
| `structure_payload` | The handoff payload decodes and carries the right accession, PDB ID, chains and source | Base64-decodes and compares fields |
| `answer_contract_sections` | The answer still contains the sections the prompt contract requires | Substring presence |

### Why no second LLM as judge

An LLM judge would be the wrong tool here, and this is a deliberate choice:

- **It would be circular.** The failure modes above are structural — a missing tool call,
  a wrong PDB ID, a broken payload. A judge model is not needed to notice that tool 3 was
  never called, and asking one to notice introduces a new source of variance.
- **It would not be reproducible.** The same trace should score the same on every run,
  on every machine. String comparison and field comparison are.
- **It would cost more than the thing being tested.** A rubric call per flow can cost as
  much as the agent run itself, for a weaker signal.
- **It would hide regressions.** A judge returning "looks good" is not a failing test.

The same reasoning applies to pulling in an external evaluation platform. A trace-shaped
harness that runs from a shell command, asserts exact facts and exits non-zero is enough
for this project, and it stays readable.

If a future flow genuinely needs a subjective quality signal, the right shape is a new
**deterministic** check (for example: does the answer cite the accession it retrieved),
not a judge model.

---

## 3. Running it

```bash
# list the evaluation dataset
python -m scripts.reliability.run_agent_flow --list

# run the capstone flow against the real agent
python -m scripts.reliability.run_agent_flow --env-file /path/to/.env

# override the model for a run
python -m scripts.reliability.run_agent_flow --model gemini-2.5-flash
```

Requirements for a live run: ADK credentials, network access to UniProt, PostgreSQL with
the retrieval corpus, and the local model artifacts. The harness is a **demo/eval tool,
not a unit test** — it needs those services, so it lives in `scripts/` and not in
`tests/`.

Exit codes make it usable as a gate:

| Code | Meaning |
|---|---|
| `0` | Flow ran and every check passed |
| `1` | Flow ran and at least one check failed |
| `2` | Flow could not run (missing credentials, network, or services) |

Crucially, a flow that cannot run is reported as **BLOCKED**, never as a pass. A harness
that cannot tell "passed" from "did not execute" is worse than no harness.

---

## 4. Verified result

Live run against the real agent, `gemini-2.5-flash`:

```text
GOLDEN TRACE -- 3 tool call(s)
   1. get_uniprot_entry(accession)                                          [ok]
   2. predict_q3(seq)                                                       [-]
   3. create_structure_view_link(accession, protein_name, summary, uniprot_entry) [ok]

CHECKS
  [PASS] tool_sequence            called in order: get_uniprot_entry -> predict_q3 -> create_structure_view_link
  [PASS] tool_responses           3 tool call(s), none reported ok=False
  [PASS] answer_not_empty         final answer length: 5605 characters
  [PASS] single_structure_link    exactly one create_structure_view_link call
  [PASS] structure_payload        P68871 -> PDB 2HHB, chains=['A', 'B', 'C', 'D']
  [PASS] answer_contract_sections all 4 required section(s) present

VERDICT: PASS
```

Note the third call: the agent passed `uniprot_entry` **back** into the structure tool.
That is precisely the input shape that used to break, so this flow is a standing
regression guard for defect #1 rather than a happy-path demo.

---

## 5. Extending the dataset

Adding coverage means adding a row, not a framework.

**A new golden flow** — append an `AgentFlowScenario` to `GOLDEN_FLOWS` in
`Protein_agent/eval.py`:

```python
INVALID_ACCESSION_FLOW = AgentFlowScenario(
    name="invalid_accession_graceful_failure",
    user_prompt="Summarize UniProt accession NOT_A_REAL_ACCESSION.",
    expected_tool_sequence=("get_uniprot_entry",),
    required_answer_sections=("uncertainty", "missing information"),
    expected_structure=None,
)
```

**Reuse the existing reliability scenarios.** `Protein_agent/reliability.py` already
defines six failure-oriented scenarios (ambiguous query, invalid accession, no result,
wrong-organism temptation, long-sequence limit, tool/API failure). They currently assert
the prompt contract; the natural next step is to give each one an expected tool sequence
so the prompt contract is checked against real behaviour, not just prompt text.

**Stronger per-flow checks.** The payload check currently validates structure. A sequence
flow could assert that `predict_q3` was never called for a sequence longer than 512
residues — a guardrail that today is only enforced by prompt wording.

**CI wiring.** `run_agent_flow` returns 0/1/2, so a pipeline step can run the live flow on
a schedule and fail the build on regression. Because the checks are deterministic, a red
build means a real change in behaviour, not a flaky judge.

---

## 6. Relationship to the other test layers

| Layer | Location | Needs network | Catches |
|---|---|---|---|
| Unit tests | `tests/` | No | Logic, parsing, payload encoding, error envelopes |
| Reliability contract | `Protein_agent/reliability.py` | No | Prompt/answer contract wording |
| **This harness** | `Protein_agent/eval.py` + `scripts/reliability/` | **Yes** | **Live tool order, tool inputs, handoff integrity** |

The layers are complementary: the unit tests pin the parts, and the harness pins the
behaviour of the assembled system.
