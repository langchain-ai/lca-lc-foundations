from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.tools import tool
from langchain.messages import (
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage
    )
from typing import Literal
from dotenv import load_dotenv
import os
load_dotenv()

model=os.getenv("OPENAI_MODEL_NAME")
print(f"Model - {model}")


## Chat client
# client=init_chat_model(model=model,)
# response=client.invoke("what is 10+10")
# print(response.content)



#Tool Creation

@tool(name_or_callable="Calculator",description="Perform ADD,SUBRACT,MULTIPLY,DIVIDE operations")
def calculator(operation:Literal["add","sub","mul","div"],number_1:int,number_2:int):

    if operation=="add":
        return number_1+number_2
    elif operation=="sub":
        return number_1-number_2
    elif operation=="mul":
        return number_1*number_2
    elif operation=="div":
        return number_1/number_2
    else:
        return "Invalid operation!"


#Agent
system_prompt=SystemMessage("""You are an arithmetic assitant. Use your tools to perform the maths operations.""")
question = HumanMessage(content="What is the addtion of 100 and 200?")

agent=create_agent(model=model,
                   tools=[calculator],
                   system_prompt=system_prompt
                   )

response=agent.invoke({"messages": [question]})
print(response['messages'][-1])

