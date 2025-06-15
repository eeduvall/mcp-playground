import gradio as gr
import os

from huggingface_hub import Agent
from smolagents import InferenceClientModel, CodeAgent, ToolCollection, MCPClient

mcp_client = None
try:
    mcp_client = MCPClient(
        {"url": "http://localhost:7860/gradio_api/mcp/sse"} # This is the MCP Server we created in the previous section
    )
    tools = mcp_client.get_tools()

    model = InferenceClientModel(token=os.getenv("HUGGINGFACE_API_TOKEN"))
    agent = Agent(
            model="Qwen/Qwen2.5-72B-Instruct",
            provider="nebius",
            servers=[
                {
                    "command": "npx",
                    "args": [
                    "mcp-remote",
                    "http://localhost:7860/gradio_api/mcp/sse"  # Your Gradio MCP server
                ]
            }
        ],
    )

    demo = gr.ChatInterface(
        fn=lambda message, history: str(agent.run(message)),
        type="messages",
        examples=["Prime factorization of 68"],
        title="Agent with MCP Tools",
        description="This is a simple agent that uses MCP tools to answer questions.",
    )

    demo.launch()
finally:
    mcp_client.disconnect()