""" Tools for UniProt REST API"""

import requests

UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"


#Helper function to extract all text values
def _get_comment_texts(entry: dict, comment_type: str) -> list[str]:
    """ Extract text values from Uniprot comments of a specific type """
    
    texts = []
    for comment in entry.get("comments", []):
        if comment.get("commentType") != comment_type:
            continue

        for text in comment.get("texts", []):
            value = text.get("value")
            if value:
                texts.append(value)

    return texts


#Helper function to extract GO terms
def _get_go_terms(entry: dict) -> list[dict]:
    """ Extract Gene ontology annoations from Uniprot cross-references """

    go_terms = []

    for ref in entry.get("uniProtKBCrossReferences", []):
        if ref.get("database") != "GO":
            continue

        properties = {
            prop.get("key"): prop.get("value")
            for prop in ref.get("properties", [])
            if prop.get("key") and prop.get("value")
        }

        go_terms.append({
            "id" : ref.get("id", ""),
            "term": properties.get("GoTerm", ""),
            "evidence": properties.get("GoEvidenceType", "")
        })

    return go_terms


#Helper function to grab keywords
def _grab_keywords(entry: dict) -> list[dict]:
    """ Extract Uniprot Keyword annoation """

    keywords = []

    for keyword in entry.get("keywords", []):
        name = keyword.get("name")
        if not name:
            continue

        keywords.append({
            "id": keyword.get("id", ""),
            "category": keyword.get("category", ""),
            "name": name
        })

    return keywords


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
            "protein_name": entry.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}).get("value", ""),
            "gene": entry.get("genes", [{}])[0].get("geneName", {}).get("value", ""),
            "organism": entry.get("organism", {}).get("scientificName", ""),
            "organism_common_name": entry.get("organism", {}).get("commonName", ""),
            "length": entry.get("sequence", {}).get("length", 0),
            "reviewed": "reviewed" in entry.get("entryType", "").lower(),
            "entry_type": entry.get("entryType", ""),
        })

    return {"results": results, "total": data.get("total", 0)}


def get_uniprot_entry(accession: str) -> dict:
    """Get full UniProt entry for a given accession (e.g. 'P68871').

    Returns: protein name, gene, organism, length, function and GO terms (FPC: molecular function/Biological process/cellular component)
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
        "sequence": entry.get("sequence", {}).get("value", ""),
        "function": _get_comment_texts(entry, "FUNCTION"),
        "go_terms": _get_go_terms(entry),
        "keywords": _grab_keywords(entry)
    }
