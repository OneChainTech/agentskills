import os
import json
import traceback
import sys
from typing import AsyncGenerator, Dict, Any, List
from contextlib import AsyncExitStack

from openai import AsyncOpenAI
from rich.console import Console

# MCP Imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

console = Console()

SYSTEM_PROMPT = """你现在拥有一个名为 E2B Firecracker Sandbox 的安全执行环境 (MCP Server)。
当你遇到需要进行数学计算、数据分析、文件处理或验证代码逻辑的任务时，请优先使用工具在沙盒中编写并运行代码，而不是仅凭记忆推断。
该环境是一个基于 Firecracker MicroVM 的强隔离环境，文件和变量在会话期间会保留。
如果运行报错，请利用报错信息进行自我修复并重新运行。
请始终使用中文回答用户的提问。

你还有以下特殊能力：
1. `visualize_file(path)`: 当你生成了 HTML、图片或其他可视化文件时，请调用此工具将其展示给用户。不要直接读取文件内容输出到对话中。
2. `get_public_url(port)`: 如果你启动了一个 Web 服务（如 Streamlit, Flask），调用此工具获取外部访问链接，并展示给用户。
"""

class ManusAgent:
    def __init__(self):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        base_url = os.getenv("DEEPSEEK_BASE_URL")
        self.model_id = os.getenv("MODEL_ID", "deepseek-ai/DeepSeek-V3")
        
        if not api_key:
            console.print("[yellow]Warning: DEEPSEEK_API_KEY not found. Agent will fail if LLM is needed.[/yellow]")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def run(self, task: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Executes the agent loop with MCP integration.
        """
        if not self.client:
            yield {"type": "error", "message": "DeepSeek API Key is missing."}
            return

        yield {"type": "system", "message": "Manus Agent initialized (MCP Mode)."}
        
        # Define MCP Server Parameters (Our new E2B Firecracker sandbox)
        server_params = StdioServerParameters(
            command="uv", # Use uv to run python to ensure venv context
            args=["run", "-q", "python", "sandbox_e2b.py"],
            env=os.environ
        )

        async with AsyncExitStack() as stack:
            yield {"type": "status", "message": "Connecting to E2B Firecracker MCP Server..."}
            
            try:
                # Connect to MCP Server
                read_stream, write_stream = await stack.enter_async_context(stdio_client(server_params))
                session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
                await session.initialize()
                
                # Handshake: List Tools
                yield {"type": "status", "message": "Discovering tools..."}
                mcp_tools_response = await session.list_tools()
                mcp_tools = mcp_tools_response.tools
                
                # Convert MCP tools to OpenAI Tool format
                openai_tools = []
                for tool in mcp_tools:
                    openai_tools.append({
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.inputSchema
                        }
                    })
                
                yield {"type": "system", "message": f"Found {len(mcp_tools)} tools: {[t.name for t in mcp_tools]}"}

            except Exception as e:
                yield {"type": "error", "message": f"MCP Connection Failed: {e}"}
                return

            # Start Conversation
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": task}
            ]

            max_turns = 10
            current_turn = 0

            while current_turn < max_turns:
                current_turn += 1
                yield {"type": "status", "message": f"Thinking (Turn {current_turn})..."}

                try:
                    response = await self.client.chat.completions.create(
                        model=self.model_id,
                        messages=messages,
                        tools=openai_tools,
                        tool_choice="auto"
                    )
                except Exception as e:
                    yield {"type": "error", "message": f"LLM API Error: {str(e)}"}
                    return

                message = response.choices[0].message
                messages.append(message)

                if message.tool_calls:
                    for tool_call in message.tool_calls:
                        yield {"type": "status", "message": f"Calling tool: {tool_call.function.name}"}
                        
                        args = json.loads(tool_call.function.arguments)
                        
                        # Extract code for display if available
                        if "code" in args:
                            yield {"type": "code", "content": args["code"]}

                        # Execute Tool via MCP
                        try:
                            result = await session.call_tool(tool_call.function.name, arguments=args)
                            
                            # MCP results can be text or artifacts. We assume text for now.
                            output_text = ""
                            if result.content:
                                for content in result.content:
                                    if content.type == "text":
                                        output_text += content.text
                            
                            if not output_text:
                                output_text = "(No output)"

                            # SPECIAL HANDLING FOR VISUALIZATION
                            if tool_call.function.name == "visualize_file":
                                try:
                                    # DEBUG: Log the raw output length and snippet to confirm data reception
                                    preview_snippet = output_text[:100] + "..." if len(output_text) > 100 else output_text
                                    yield {"type": "status", "message": f"DEBUG: Tool returned {len(output_text)} chars. Snippet: {preview_snippet}"}
                                    
                                    data = json.loads(output_text)
                                    if data.get("type") == "file_preview":
                                        # Yield preview event for frontend
                                        yield {"type": "preview", "mime": data["mime"], "content": data["content"], "path": data["path"]}
                                        # Replace output text for LLM history so it doesn't get flooded with base64/html
                                        output_text = f"(File '{data['path']}' sent to user preview. Content length: {len(data['content'])})"
                                    else:
                                        yield {"type": "status", "message": f"visualize_file returned unknown JSON structure."}
                                except json.JSONDecodeError as e:
                                    yield {"type": "error", "message": f"JSON Parse Error: {str(e)}. Raw output might contain invalid chars."}
                                except Exception as e:
                                    yield {"type": "error", "message": f"Error processing visualization: {str(e)}"}
                                    
                            # SPECIAL HANDLING FOR PUBLIC URL
                            if tool_call.function.name == "get_public_url":
                                if output_text.startswith("https://"):
                                     yield {"type": "preview", "mime": "url", "content": output_text, "path": "Exposed Port"}

                            yield {"type": "output", "content": output_text}

                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": output_text
                            })

                        except Exception as e:
                            error_msg = f"Tool Execution Error: {str(e)}"
                            yield {"type": "error", "message": error_msg}
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": error_msg
                            })
                else:
                    # Final Answer
                    content = message.content
                    if content:
                        yield {"type": "answer", "content": content}
                    yield {"type": "success", "message": "Task completed."}
                    return
            
            yield {"type": "error", "message": "Max turns reached."}
