# Contributing Notes

This repository contains a protein-focused AI research assistant that combines:

- local PyTorch Q3 and Q8 prediction tools,
- a FastAPI serving layer,
- Google ADK agent orchestration,
- UniProt retrieval tools,
- MCP-based BigQuery access.

## Project Areas

- `Protein_agent/`: ADK agent, prompt, prediction tools, UniProt tools, and internal schemas
- `serving/`: FastAPI application and inference code
- `protein_model/`: shared model and preprocessing code
- `protein_bq_mcp_server/`: MCP server for read-only BigQuery access
- `scripts/`: training and analysis utilities

## Development Guidelines

- Keep prediction-tool outputs stable and structured.
- Treat retrieved UniProt and BigQuery facts separately from model predictions.
- Keep README and project-history documents aligned with the actual implemented scope.
- Prefer small, testable changes over broad refactors.

## Environment

Use a Python environment that includes the packages listed in `requirements.txt`.

For agent and BigQuery workflows, make sure local credentials and model artifacts are available before running the ADK setup.
