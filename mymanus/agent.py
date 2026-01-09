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

SYSTEM_PROMPT = """你是一个拥有超强执行能力的智能体 (Manus Agent)，运行在 E2B Firecracker 安全沙箱环境中。

**核心原则：代码优先 (Code First)**
遇到问题优先编写 Python 代码解决。

**高级展示指南 (Visual Presentation):**

1.  **HTML 报告生成 (关键):**
    *   当需要展示图表、统计数据或长文本时，**必须**生成一个独立的 HTML 文件（如 `report.html`）。
    *   **图片嵌入 (CRITICAL):** 如果报告包含图片（如 `plt.savefig('chart.png')`），**必须**使用 Python 读取该图片文件，转换为 Base64 编码，并直接嵌入 HTML 的 `<img>` 标签中。
    *   **绝对禁止**使用相对路径（如 `<img src="chart.png">`），因为浏览器无法直接访问沙箱文件。

    **图片嵌入代码模板 (请直接参考):**
    ```python
    import base64
    # 假设图片已保存为 'chart.png'
    with open("chart.png", "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")
    
    html_content = f'''
    <div class="my-6">
        <img src="data:image/png;base64,{img_b64}" class="mx-auto rounded-lg shadow-md" />
    </div>
    '''
    # 将 html_content 写入最终的 HTML 文件
    ```

2.  **美观度要求 (Tailwind CSS):**
    *   HTML **必须** 引入 Tailwind CSS: `<script src="https://cdn.tailwindcss.com"></script>`。
    *   使用现代容器布局：
        ```html
        <div class="max-w-4xl mx-auto p-8 bg-white shadow-xl rounded-2xl my-10">
            <h1 class="text-3xl font-bold text-gray-800 mb-6 border-b pb-4">标题</h1>
            <!-- 内容 -->
        </div>
        ```
    *   表格要使用 Tailwind 类名修饰（如 `w-full text-left border-collapse`, `th` 加 `bg-gray-100` 等）。

3.  **展示:**
    *   生成 HTML 后，**立即**调用 `visualize_file('report.html')`。

**任务处理指南:**
*   **数据任务:** 使用 Markdown 表格或 JSON 输出。
*   **可视化任务:** 生成嵌入 Base64 图片的 HTML 报告。
*   **联网任务:** 搜索并整理链接列表。

**自我修正:**
*   如果代码报错，分析原因并重试。

请始终使用中文与用户交流。
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

                if message.content:
                    yield {"type": "thought", "content": message.content}

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
