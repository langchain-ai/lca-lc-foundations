from dotenv import load_dotenv

load_dotenv()

from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient(
    #add MCP setup here from online tools

)

tools = await client.get_tools()

from langchain.agents import create_agent
from langchain.tools import tool


create_agent(
)
