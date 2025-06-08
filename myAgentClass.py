# Import necessary components from the 'agents' library
import asyncio
from contextlib import AsyncExitStack # Import AsyncExitStack
from pprint import pprint
from agents import Agent, Handoff, ItemHelpers, RunContextWrapper, Runner, gen_trace_id, handoff, trace
from agents.mcp import MCPServerSse, MCPServerStdio
from agents.model_settings import ModelSettings
from typing import List, Optional
from pydantic import BaseModel

from pytypes import gmail_output, calendar_output

def on_handoff_current(ctx: RunContextWrapper[None]):
        print("Handoff called")

# A simple structure to hold agent configuration
class AgentConfig:
    def __init__(self, name: str, instructions: str, mcp_url: Optional[str] = None, model_settings: Optional[ModelSettings] = None, output_type: Optional[BaseModel] = None):
        self.name = name
        self.instructions = instructions
        self.mcp_url = mcp_url
        # Provide a default ModelSettings if none is given, adjust as needed
        self.model_settings = model_settings or ModelSettings()
        self.output_type = output_type

class HierarchicalAgentRunner:
    """
    Manages the configuration and invocation of a main agent with potential handoffs.
    Agent instances are created dynamically during each invocation.
    """

    def __init__(self, main_agent_config: AgentConfig, handoff_configs: List[AgentConfig], web_search: bool = False):
        self.main_agent_config = main_agent_config
        self.handoff_configs = handoff_configs
        self.web_search = web_search
        # We don't store agent instances here


    async def invoke(self, messages: List[dict], integrations: List[str]):
        """
        Creates the agent hierarchy with necessary MCP servers and runs the workflow (non-streaming).
        """
        trace_id = gen_trace_id()
        # Use the main agent's name for the overall workflow trace
        with trace(workflow_name=f"{self.main_agent_config.name} Workflow", trace_id=trace_id):
            async with AsyncExitStack() as stack:
                handoff_agents = []
                # Create handoff agents and their MCP servers if needed
                for config in self.handoff_configs:
                    if not self.web_search and config.name == "Search Agent":
                        continue
                    if config.name.split(" ")[0] not in integrations:
                        print(f"Skipping {config.name} because it is not in the integrations list")
                        continue
                    mcp_servers = []
                    if config.name == "Apple Agent":
                        try:
                            server = await stack.enter_async_context(MCPServerStdio(
                                name = f"{config.name} Server",
                                params = {
                                    "command": "bunx",
                                    "args": ["@dhravya/apple-mcp@latest"]
                                }
                            ))
                            mcp_servers = [server]
                        except Exception as e:
                            print(f"[Error][Invoke] Failed to enter context for {config.name} Server: {e}")
                            raise  # Re-raise the exception for non-streaming case
                    elif config.name == "Whatsapp Agent":
                        try:
                            server = await stack.enter_async_context(MCPServerStdio(
                                name = f"{config.name} Server",
                                params = {
                                    "command": "/Users/penguin/Desktop/projects/mcp_ai_tests/aipa-python-server/.venv/bin/uv",
                                    "args": [
                                        "--directory",
                                        "/Users/penguin/Desktop/projects/mcp_ai_tests/whatsapp-mcp/whatsapp-mcp-server",
                                        "run",
                                        "main.py"
                                    ]
                                }
                            ))
                            mcp_servers = [server]

                        except Exception as e:
                            print(f"[Error][Invoke] Failed to enter context for {config.name} Server: {e}")
                            raise  # Re-raise the exception for non-streaming case
                    elif config.mcp_url:
                        try:
                            server = await stack.enter_async_context(MCPServerSse(
                                name=f"{config.name} Server",
                                params={"url": config.mcp_url},
                            ))
                            mcp_servers = [server]
                        except Exception as e:
                            print(f"[Error][Invoke] Failed to enter context for {config.name} Server: {e}")
                            # Handle error appropriately for non-streaming, maybe raise?
                            raise  # Re-raise the exception for non-streaming case

                    # Create the handoff Agent instance
                    agent = Agent(
                        name=config.name,
                        instructions=config.instructions,
                        mcp_servers=mcp_servers,
                        model_settings=config.model_settings,
                        output_type=config.output_type,
                        # model="o3-mini"
                    )
                    handoffObject = handoff(
                        agent = agent,
                        on_handoff = on_handoff_current
                    )
                    handoff_agents.append(handoffObject)

                # Create the main agent instance, potentially with its own MCP server
                main_agent_mcp_servers = []
                if self.main_agent_config.mcp_url:
                    try:
                         main_server = await stack.enter_async_context(MCPServerSse(
                             name=f"{self.main_agent_config.name} Server",
                             params={"url": self.main_agent_config.mcp_url},
                         ))
                         main_agent_mcp_servers = [main_server]
                    except Exception as e:
                         print(f"[Error][Invoke] Failed to enter context for {self.main_agent_config.name} Server: {e}")
                         raise # Re-raise the exception

                main_agent = Agent(
                    name=self.main_agent_config.name,
                    instructions=self.main_agent_config.instructions,
                    mcp_servers=main_agent_mcp_servers,
                    handoffs=handoff_agents,
                    model_settings=self.main_agent_config.model_settings,
                    # model="o3-mini"
                )

                # Run the workflow with the dynamically constructed main agent
                result = await Runner.run(starting_agent=main_agent, input=messages)
                pprint(result)
                return result

async def main():
    # 1. Define Configurations for all agents
    main_config = AgentConfig(
        name="Task Coordinator",
        instructions="You are a helpful assistant. Determine if a task is for Gmail, Calendar, Slack, Whatsapp, or Notion and delegate.",
        # model_settings=ModelSettings(tool_choice=None) # Main agent might not need tools directly
        # mcp_url= Optional URL if the main agent needs its own tools
    )

    gmail_config = AgentConfig(
        name="Gmail Agent",
        instructions="You are a helpful assistant that can handle gmail tasks.",
        mcp_url="https://mcp.composio.dev/gmail/enough-miniature-terabyte-vtIXTm", # Replace with your actual URL
        output_type=gmail_output
        # model_settings=ModelSettings(tool_choice="required") # Example
    )

    # # Example: Add a Calendar Agent config
    # calendar_config = AgentConfig(
    #     name="Calendar Agent",
    #     instructions="You handle calendar scheduling and querying.",
    #     mcp_url="YOUR_CALENDAR_MCP_URL_HERE", # Replace with your actual URL
    # )

    # 2. Create the Runner with the configurations
    agent_runner = HierarchicalAgentRunner(
        main_agent_config=main_config,
        handoff_configs=[gmail_config] # List all handoff configs
    )

    # 3. Interaction Loop
    messages = []
    while True:
        try:
            user_input = input("User: ")
            if user_input.lower() == "exit":
                break
            messages.append({"role": "user", "content": user_input, "type": "message"})
            pprint(f"Sending messages: {messages}")
            # Invoke the runner, which handles dynamic agent creation
            result = await agent_runner.invoke(messages)
            print("\nAssistant Response:")
            pprint(result.final_output)
            # Update message history for conversation context
            messages = result.to_input_list()
            pprint(messages)
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\nAn error occurred: {e}")
            # Optionally reset messages or handle error differently
            # messages = []


if __name__ == "__main__":
    asyncio.run(main())


    
    
        