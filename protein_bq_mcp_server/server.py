""" Custom MCP server for querying the protein BigQuery dataset """

import re
import json

import google.cloud.bigquery as bigquery
from mcp.server.fastmcp import FastMCP

#--- BigQuery client pointing at our project and a FASTMCP server instance

#BigQuery setup
client = bigquery.Client(project = "bio-ml-inference")

#create the MCP server
mcp = FastMCP("Protein BigQuery MCP Server")

#Table the LLM can query
TABLE_ID = "protein_data.training_seq"

# Read only SQL validation
# only allow SELECT statements
READ_ONLY_RE = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
BLOCKED_KEYWORDS = re.compile(
    r"\b(DELETE|INSERT|UPDATE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|MERGE)\b",
    re.IGNORECASE,
)

#Guardrails #1: so the LLM can only run Statements.
def _validate_read_only(sql: str) -> None:
    """ Reject any non-SELECT or destructive SQL. """
    
    #ensure we can query the protein_data dataset
    if "protein_data" not in sql and "training_seq" not in sql:
        raise ValueError("Query must reference the protein_data dataset")
    
    if not READ_ONLY_RE.match(sql):
        raise ValueError("Only SELECT queries are allowed.")
    
    if BLOCKED_KEYWORDS.search(sql):
        raise ValueError("Destructive SQL operations are not allowed")
    
#Guardrail #2: Prevents the LLM from asking million of rows. Every query is capped. 
def _add_row_limit(sql: str, max_rows: int = 1000) -> str:
    """ Append LIMIT if not already present. """
    sql_stripped = sql.rstrip().rstrip(";")
    if not re.search(r"\bLIMIT\s+\d+", sql_stripped, re.IGNORECASE):
        sql_stripped += f"  LIMIT {max_rows}"
    
    return sql_stripped

#----MCP Tools ----

#Tool #1:  LLM can use this tool to learn the table schema, queries information schema for column type
@mcp.tool()
def get_table_info() -> str:
    """ Get the schema, column descriptions, and sample rows from the protein training table"""

    """ Use this to understand the table structure before writing queries"""

    schema_sql = f"""
    SELECT column_name, data_type
    FROM `bio-ml-inference.INFORMATION_SCHEMA.COLUMNS`
    WHERE table_name = 'training_seq'
    """

    schema_rows = client.query(schema_sql).result()
    schema_lines = ["Table: training_seq (dataset: protein_data, project: bio-ml-inference), columns: "]

    for row in schema_rows: 
        schema_lines.append(f"  - {row.column_name} ({row.data_type})")

    schema_lines.append("")
    schema_lines.append("Description:")
    schema_lines.append("  - seq: Amino acid sequence (standard 20 residues)")
    schema_lines.append("  - sst3: Q3 secondary structure (H=helix, E=strand, C=coil)")
    schema_lines.append("  - sst8: Q8 secondary structure (B/C/E/G/H/I/S/T)")

    schema_lines.append("")
    schema_lines.append("Sample rows (first 3):")
    sample = client.query(f"SELECT * FROM `bio-ml-inference.{TABLE_ID}` LIMIT 3").result()
    for row in sample:
        schema_lines.append(f"  seq={row.seq[:40]}... | sst3={row.sst3[:40]}... | sst8={row.sst8[:40]}...")

    return "\n".join(schema_lines)

#Tool #2: the core tool that validates SQL is read only, adds a row limit and enforces a $1 max cost cap
@mcp.tool()
def query_protein_data(sql: str) -> str:

    """ Execute a read-only SQL query on the protein dataset.
    
        The table is 'bio-ml-inference.protein_data.training_seq` with columns:
        - seq (STRING): amino acid sequence
        - sst3 (STRING): Q3 structure labels (H/E/C)
        - sst8 (STRING): Q8 structure labels (B/C/E/G/H/I/S/T)

        You can join the table with itself, group by, count, use UNNEST(SPLIT(seq, '')) for per-residue analysis.
        Examples:
        - COUNT(*) for total rows
        - SELECT LENGTH(seq) AS len FROM training_seq for sequence lengths
        - SELECT aa, COUNT(*) FROM training_seq, UNNEST(SPLIT(seq, '')) AS aa GROUP BY aa for amino acid frequency

        Call get_table_info first if you need to understand the schema.
        Always query the `training_seq` table. Use backticks around the table name.

        Args:
            sql: A SELECT SQL query.

    """
    _validate_read_only(sql)
    sql = _add_row_limit(sql)

    try:
        job_config = bigquery.QueryJobConfig(   maximum_bytes_billed = 100_000_000) # 1$ cost cap per query

        query_job = client.query( sql, job_config = job_config)

        rows = list(query_job.result())

        if not rows:
            return "Query returned no results."
        
        #Format as list of dicts (for JSON)
        results = []
        for row in rows:
            results.append(dict(row))

        return json.dumps(results, indent= 2, default = str)
    
    except Exception as e:
        return f"Query error {e}"
    

if __name__ == "__main__":
    mcp.run(transport="stdio")
