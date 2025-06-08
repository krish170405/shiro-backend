import asyncio
import json # Import json
from fastapi import FastAPI, HTTPException # Add HTTPException
from fastapi.responses import StreamingResponse # Import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from contextlib import AsyncExitStack # Import AsyncExitStack here
import datetime
import pytz # For timezone handling

# Import necessary components from your agent class file
# Add ItemHelpers to parse message content
from myAgentClass import AgentConfig, HierarchicalAgentRunner, ModelSettings, ItemHelpers, Agent, handoff, on_handoff_current # Add Agent, handoff, on_handoff_current
from agents.mcp import MCPServerSse # Import MCPServerSse here
from agents import Runner, trace, gen_trace_id

from pytypes import calendar_output, gmail_output, notion_output, slack_output, whatsapp_output # Import Runner, trace, gen_trace_id here

# --- Agent Configuration (Copied or adapted from myAgentClass.py) ---
# You might want to load this from a config file or environment variables in a real app
# Get current time in IST
ist_timezone = pytz.timezone('Asia/Kolkata')
current_time_ist = datetime.datetime.now(ist_timezone)
ist_time_str = current_time_ist.strftime("%Y-%m-%d %H:%M:%S %Z")

main_config = AgentConfig(
    name="Task Coordinator",
    instructions=f"You are Shiro, a highly efficient personal assistant. Current date and time in IST: {ist_time_str}. Carefully analyze each user request to determine if it requires Gmail, Slack, Notion, Whatsapp, or Calendar functionality. When appropriate, delegate to the specialized agent without hesitation.",
    # model_settings=ModelSettings(tool_choice=None) # Main agent might not need tools directly
)

gmail_config = AgentConfig(
    name="Gmail Agent",
    instructions=f"You are a helpful assistant that can handle gmail tasks. Current date and time in IST: {ist_time_str}. 1) Before sending an email, first create a draft, show it to the user and ask for confirmation. If the user confirms, send the email by calling the required tool. 2) If the user would like to summarise their emails, fetch them according to the user's query and summarise them concisely before showing it to the user.",
    mcp_url="https://mcp.composio.dev/gmail/enough-miniature-terabyte-vtIXTm",
    output_type=gmail_output,
    model_settings=ModelSettings(tool_choice="required")
)

slack_config = AgentConfig(
    name="Slack Agent",
    instructions="You are a helpful assistant that can handle slack tasks. 1) Before sending a message, first create a draft, show it to the user and ask for confirmation. If the user confirms, send the message.",
    mcp_url="https://mcp.composio.dev/slack/enough-miniature-terabyte-vtIXTm",
    output_type=slack_output,
    model_settings=ModelSettings(tool_choice="required")
)

calendar_config = AgentConfig(
    name="Calendar Agent",
    instructions=f"You handle calendar scheduling and querying. Current date and time in IST: {ist_time_str}. All schedules should be in IST. 1) When asked to schedule an event, first confirm the date, time and attendees. If the user confirms, schedule the event.",
    mcp_url="https://mcp.composio.dev/googlecalendar/enough-miniature-terabyte-vtIXTm",
    output_type=calendar_output,
    model_settings=ModelSettings(tool_choice="required")
)

search_config = AgentConfig(
    name="Search Agent",
    instructions="You can search the web for up to date information and answer questions which require the latest information.",
    mcp_url="https://mcp.composio.dev/perplexityai/enough-miniature-terabyte-vtIXTm",
)

notion_config = AgentConfig(
    name="Notion Agent",
    instructions="You can create, read, update and delete notes in Notion. Be concise in your responses.",
    mcp_url="https://mcp.composio.dev/notion/scruffy-huge-nest-ixAj3E",
    output_type=notion_output,
    model_settings=ModelSettings(tool_choice="required"))

whatsapp_config = AgentConfig(
    name="Whatsapp Agent",
    instructions="You can send and receive messages from whatsapp.",
    # mcp_url="https://mcp.composio.dev/whatsapp/enough-miniature-terabyte-vtIXTm",
    output_type=whatsapp_output,
    model_settings=ModelSettings(tool_choice="required"))

apple_config = AgentConfig(
    name="Apple Agent",
    instructions="You can use apple services like imessage and notes.",
    mcp_url="https://mcp.composio.dev/whatsapp/enough-miniature-terabyte-vtIXTm",
)

# --- FastAPI App Setup ---
app = FastAPI()

# Instantiate the agent runner globally - it now only holds configs
agent_runner_configs = HierarchicalAgentRunner(
    main_agent_config=main_config,
    # handoff_configs=[gmail_config, slack_config, calendar_config, search_config]
    handoff_configs=[gmail_config, slack_config, calendar_config, search_config, whatsapp_config, notion_config]
)

# --- API Models ---
class InvokeRequest(BaseModel):
    messages: List[Dict[str, Any]] # Standard message format
    integrations: List[str] = [] # List of integrations to use

# Define the response model for the non-streaming endpoint
class InvokeResponse(BaseModel):
    messages: List[Dict[str, Any]] # Return the updated message list

# --- Helper function to format SSE data ---
def format_sse(data: str, event: Optional[str] = None) -> str:
    """Formats data for Server-Sent Events."""
    msg = f"data: {data}\n\n"
    if event is not None:
        msg = f"event: {event}\n{msg}"
    return msg

# --- API Endpoint (Non-Streaming) ---
@app.post("/invoke", response_model=InvokeResponse)
async def invoke_agent_standard(request: InvokeRequest):
    """
    Receives messages, invokes the agent hierarchy non-streamed,
    and returns the final updated message list.
    """
    try:
        # Use the standard invoke method (which now handles its own context)
        result = await agent_runner_configs.invoke(request.messages, request.integrations) # Use the instance holding configs
        updated_messages = result.to_input_list()
        return InvokeResponse(messages=updated_messages)
    except Exception as e:
        # Basic error handling
        print(f"Error during non-streaming agent invocation: {e}")
        # Raise HTTPException for standard JSON error response
        raise HTTPException(status_code=500, detail=str(e))

# --- API Endpoint (Streaming) ---
@app.post("/invoke_streamed")
async def invoke_agent_streamed(request: InvokeRequest):
    """
    Receives messages, dynamically builds the agent hierarchy within the stream context,
    and streams results using SSE.
    """
    async def stream_generator():
        """Async generator that manages server lifecycles and yields agent events."""
        trace_id = gen_trace_id()
        # Use the main agent's config name for trace
        main_conf = agent_runner_configs.main_agent_config
        handoff_confs = agent_runner_configs.handoff_configs

        # *** Manage context within the generator ***
        with trace(workflow_name=f"{main_conf.name} Workflow (Streamed)", trace_id=trace_id):
            async with AsyncExitStack() as stack:
                try:
                    # --- Dynamically build agent hierarchy inside the stack ---
                    handoff_agents = []
                    for config in handoff_confs:
                        mcp_servers = []
                        if config.mcp_url:
                            try:
                                server = await stack.enter_async_context(MCPServerSse(
                                    name=f"{config.name} Server (Stream)", # Unique name
                                    params={"url": config.mcp_url},
                                ))
                                print(f"[Stream] Context entered for {config.name} Server.")
                                mcp_servers = [server]
                            except Exception as e:
                                print(f"[Error][Stream] Failed context for {config.name} Server: {e}")
                                # Send error event and stop if server fails? Or try to continue?
                                # Sending error and stopping is safer if tools are required.
                                error_payload = json.dumps({"error": f"Failed to initialize tool server for {config.name}", "detail": str(e)})
                                yield format_sse(data=error_payload, event="error")
                                return # Stop the generator

                        # Create the handoff Agent instance
                        agent = Agent(
                            name=config.name,
                            instructions=config.instructions,
                            mcp_servers=mcp_servers,
                            model_settings=config.model_settings,
                            # model="o3-mini"
                        )
                        handoffObject = handoff(
                            agent=agent,
                            on_handoff=on_handoff_current # Make sure this function is accessible
                        )
                        handoff_agents.append(handoffObject)

                    # Create the main agent instance
                    main_agent_mcp_servers = []
                    if main_conf.mcp_url:
                         try:
                             main_server = await stack.enter_async_context(MCPServerSse(
                                 name=f"{main_conf.name} Server (Stream)", # Unique name
                                 params={"url": main_conf.mcp_url},
                             ))
                             print(f"[Stream] Context entered for {main_conf.name} Server.")
                             main_agent_mcp_servers = [main_server]
                         except Exception as e:
                            print(f"[Error][Stream] Failed context for {main_conf.name} Server: {e}")
                            error_payload = json.dumps({"error": f"Failed to initialize tool server for {main_conf.name}", "detail": str(e)})
                            yield format_sse(data=error_payload, event="error")
                            return # Stop the generator

                    main_agent = Agent(
                        name=main_conf.name,
                        instructions=main_conf.instructions,
                        mcp_servers=main_agent_mcp_servers,
                        handoffs=handoff_agents,
                        model_settings=main_conf.model_settings,
                        # model="o3-mini"
                    )
                    # --- Agent hierarchy built ---

                    print("[Stream] Calling Runner.run_streamed...")
                    # Call run_streamed with the newly created agent hierarchy
                    result = Runner.run_streamed(starting_agent=main_agent, input=request.messages)
                    print("[Stream] Runner.run_streamed returned, starting event iteration.")

                    # Iterate through the events provided by the agent run
                    async for event in result.stream_events():
                        event_type = event.type
                        data_payload = {}

                        # --- Filter and format events based on type ---
                        if event.type == "raw_response_event":
                            # Often too noisy for direct client consumption, skip by default
                            # You could potentially extract token deltas here if needed
                            # print(f"Raw delta: {event.delta}") # Uncomment for debugging
                            continue
                        elif event.type == "agent_updated_stream_event":
                            # Send agent update info
                            data_payload = {"agent_name": event.new_agent.name}
                            print(f"Stream: Agent updated: {event.new_agent.name}") # Log server-side
                        elif event.type == "run_item_stream_event":
                            # Handle specific item types within the run
                            item = event.item
                            if item.type == "tool_call_item":
                                event_type = "tool_call" # Use a more specific event name
                                data_payload = {
                                    "tool_name": item.name,
                                    "tool_args": item.args,
                                    "tool_call_id": item.tool_call_id,
                                }
                                print("Stream: -- Tool was called") # Log server-side
                            elif item.type == "tool_call_output_item":
                                 event_type = "tool_output"
                                 data_payload = {
                                    "tool_call_id": item.tool_call_id,
                                    "output": item.output, # Output could be large/complex
                                 }
                                 print(f"Stream: -- Tool output received for call {item.tool_call_id}") # Log server-side
                            elif item.type == "message_output_item":
                                 event_type = "message_output"
                                 # Use ItemHelpers to safely extract text content
                                 content = ItemHelpers.text_message_output(item)
                                 data_payload = {"content": content}
                                 print(f"Stream: -- Message output chunk:\n {content}") # Log server-side
                            else:
                                 # Ignore other item types like 'action_item' if not needed
                                 continue
                        else:
                             # Ignore other top-level event types if not needed
                             continue

                        # --- Send event if data was generated ---
                        if data_payload:
                            # Convert the Python dict to a JSON string
                            json_data = json.dumps(data_payload)
                            # Format as an SSE message and yield it
                            yield format_sse(data=json_data, event=event_type)

                    # --- Send a final "done" event (optional) ---
                    # Useful for the client to know the stream is finished successfully
                    yield format_sse(data=json.dumps({"status": "complete"}), event="done")
                    print("[Stream] Event stream finished.")

                except Exception as e:
                    # --- Handle errors during streaming ---
                    print(f"Error during agent streaming: {e}") # Log the error server-side
                    # Send an error event via SSE to the client
                    error_payload = json.dumps({"error": str(e), "detail": "An error occurred during processing."})
                    yield format_sse(data=error_payload, event="error")
                    # You could also raise HTTPException here, but sending an error event
                    # might be more informative for the client if the stream partially worked.
                    # from fastapi import HTTPException
                    # raise HTTPException(status_code=500, detail=str(e))

            # AsyncExitStack automatically cleans up servers here when generator ends
            print("[Stream] Stream generator finished and contexts exited.")

    # Return the StreamingResponse, passing the async generator and specifying the media type
    return StreamingResponse(stream_generator(), media_type="text/event-stream")

# --- Optional: Run directly with uvicorn for local testing ---
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
# You would typically run this using: uvicorn main:app --reload
