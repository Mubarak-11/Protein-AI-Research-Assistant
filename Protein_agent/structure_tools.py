"""Structure tools for the protein agent: build Structure Studio viewer links."""

from __future__ import annotations
from typing import Any

from protein_structure_view import FocusResidue, create_structure_view
from protein_structure_view.uniprot import fetch_uniprot_structure_entry


def _has_pdb_crossrefs(entry: dict[str, Any] | None) -> bool:
    """Return True when an entry carries enough data to resolve a PDB candidate.

    Agent-normalized entries (e.g. the output of get_uniprot_entry) do not
    include PDB cross-references, so they must not suppress the raw UniProt
    fetch that structure selection depends on.
    """

    if not entry:
        return False
    if entry.get("pdb_crossrefs"):
        return True
    return any(
        isinstance(ref, dict) and ref.get("database") == "PDB"
        for ref in entry.get("uniProtKBCrossReferences", [])
    )


def create_structure_view_link(
        accession: str,
        protein_name: str = "",
        summary: str = "",
        pdb_id: str | None = None,
        uniprot_entry: dict[str, Any] | None = None,
        focus_residues: list[dict[str, Any]] | None = None,
        view_mode: str = "Function",
) -> dict[str, Any]:
    """ Create a Protein structure studio link for an accession or PDB ID.

    Args:
        accession: UniProt accession, e.g. 'P0DP24'. If pdb_id is not given,
            the tool fetches the UniProt entry to resolve PDB candidates.
        protein_name: Display name of the protein, e.g. 'Calmodulin-2'.
        summary: Short biological summary shown in the viewer.
        pdb_id: Optional explicit PDB ID, e.g. '5NIN'. When given, no
            UniProt fetch is needed. If the user asks to use a specific PDB
            ID, pass that exact ID here instead of relying on automatic
            structure selection.
        uniprot_entry: Optional raw UniProt JSON entry carrying
            `uniProtKBCrossReferences`, or a normalized entry carrying
            `pdb_crossrefs`. Entries that carry neither (for example the
            compact output of get_uniprot_entry) are ignored and the raw
            UniProt entry is fetched instead.
        focus_residues: Residues to highlight in the viewer. Pass ONE dict
            per residue anchor: {"chain": "A", "residue_number": 21,
            "label": "EF-hand 1"}. residue_number MUST be a single integer
            (e.g. 21). NEVER pass a range string like "21-32" or "21..32" —
            they are rejected with an error. For a region (e.g. a binding
            loop), pass 1-3 REPRESENTATIVE anchor residues with DISTINCT
            labels (e.g. residue 21 labelled "EF-hand 1 start") — do not pass
            every residue of the region, which floods the viewer with
            duplicate layers.
        view_mode: Viewer coloring mode, e.g. 'Function'.
    """

    try:
        structure_entry = uniprot_entry
        if pdb_id is None and not _has_pdb_crossrefs(structure_entry):
            structure_entry = fetch_uniprot_structure_entry(accession)

        residues = [
            FocusResidue(
                chain=str(item.get("chain", "")),
                residue_number=int(item["residue_number"]),
                label=str(item.get("label", "")),
            )
            for item in focus_residues or []
        ]

        view = create_structure_view(
            protein_name=protein_name or accession,
            uniprot_id=accession,
            uniprot_entry=structure_entry,
            pdb_id=pdb_id,
            summary=summary,
            focus_residues=residues,
            view_mode=view_mode,
        )

        return {"ok": True, **view.to_dict()}

    except Exception as exc:
        return {
            "ok": False,
            "error": f"Structure view link could not be created: {exc}",
        }
