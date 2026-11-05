from dotenv import load_dotenv

load_dotenv() 

from typing import Dict, Any
from langchain.agents import create_agent
from langchain.tools import tool
from langchain.messages import HumanMessage
#from langgraph.checkpoint.memory import InMemorySaver
from tavily import TavilyClient
from pprint import pprint

tavily_client = TavilyClient()

@tool
def web_search(query: str) -> Dict[str, Any]:

    """Search the web for info"""
    return tavily_client.search(query)

system_prompt = "You are a personal chef who scrubs the internet to help users create recipes and meal plans using the food in their fridge, giving them brief descriptions and then providing links to the recipes."
agent = create_agent(model="gpt-5-nano",
                    tools=[web_search],
                    system_prompt=system_prompt,
                    #checkpointer=InMemorySaver()
)

message = HumanMessage(content="I have bread, cheese, ham pizza, eggs, orange juice, and milk in my fridge.")
config = {"configurable": {"thread_id": "1"}}

response = agent.invoke(
    {"messages" : [message]}, config,
)


#print(response['messages'][-1].content)

pprint(response)