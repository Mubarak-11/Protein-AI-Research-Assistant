import os
from google.adk.agents import Agent
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp.client.stdio import StdioServerParameters
from .tools import predict_q3, predict_q8, batch_predict_q3, batch_predict_q8

script_dir = os.path.dirname(os.path.abspath(__file__))
instruction_file_path = os.path.join(script_dir, "agent-prompt.md")

with open(instruction_file_path, "r") as f:
    instruction = f.read()


bq_toolset = McpToolset(
    connection_params = StdioConnectionParams(
        server_params = StdioServerParameters(
            command = "python3",
            args = ["-m", "protein_bq_mcp_server.server"],
        ),
    ),
)

root_agent = Agent(
    name = "ProteinResearchAgent",
    description = "Protein Research Assistant that helps with Protein secondary structure from Amino Acids",
    instruction = instruction,
    model = "gemini-3.1-pro-preview",
    tools= [predict_q3, predict_q8, batch_predict_q3, batch_predict_q8, bq_toolset],
)