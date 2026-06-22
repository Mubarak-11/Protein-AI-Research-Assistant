""" Tools for UniProt REST API"""

import requests

UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"


def search_uniprot(query: str, max_results: int = 5) -> dict:
    """Search UniProt for proteins by name, gene, organism, or sequence.

    Returns matched proteins with accession, name, organism, length.
    Examples: 'human hemoglobin', 'HBB', 'MVLSPADKTNVKAAW'
    """
    url = f"{UNIPROT_BASE}/search"
    params = {"query": query, "size": min(max_results, 10), "format": "json"}
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for entry in data.get("results", []):
        results.append({
            "accession": entry["primaryAccession"],
            "name": entry.get("uniProtkbId", ""),
            "protein": entry.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}).get("value", ""),
            "organism": entry.get("organism", {}).get("scientificName", ""),
            "length": entry.get("sequence", {}).get("length", 0),
        })

    return {"results": results, "total": data.get("total", 0)}


def get_uniprot_entry(accession: str) -> dict:
    """Get full UniProt entry for a given accession (e.g. 'P68871').

    Returns: protein name, gene, organism, length
    """
    url = f"{UNIPROT_BASE}/{accession}?format=json"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    entry = resp.json()

    return {
        "accession": entry["primaryAccession"],
        "name": entry.get("uniProtkbId", ""),
        "protein_name": entry.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}).get("value", ""),
        "gene": entry.get("genes", [{}])[0].get("geneName", {}).get("value", ""),
        "organism": entry.get("organism", {}).get("scientificName", ""),
        "length": entry.get("sequence", {}).get("length", 0),
        "sequence": entry.get("sequence", {}).get("value", "")
    }
