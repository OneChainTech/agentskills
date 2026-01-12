import os
import json
from typing import AsyncGenerator, Dict, Any, List
from contextlib import AsyncExitStack

from openai import AsyncOpenAI
from rich.console import Console

# MCP Imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

console = Console()

SYSTEM_PROMPT = '''你是一个拥有超强执行能力的智能体 (Manus Agent)，运行在 E2B Firecracker 安全沙箱环境中。

**核心原则：代码优先 (Code First)**
遇到问题优先编写 Python 代码解决。

**高级展示指南 (Visual Presentation):**

    **HTML 报告生成 (关键):**
    *   当需要展示结果时，**必须**生成一个独立的 HTML 文件（如 `report.html`）。
    *   **美观度要求 (Manus Premium Style):**
        *   请使用下面的 HTML 骨架。
        *   利用 Tailwind Typography 插件 (`prose`)，你只需要在 `<article>` 标签内填充标准的 HTML 标签 (h1, p, table, img) 即可自动获得完美的排版。
    *   **交互式支持 (Interactive):**
        *   **强烈推荐**使用 `plotly` 库生成交互式图表。
        *   如果是 Plotly，请使用 `fig.to_html(full_html=False, include_plotlyjs='cdn')` 获取 HTML 片段并嵌入到 `{content_body}` 中。
        *   允许在 `{content_body}` 中包含 `<script>` 标签来实现自定义交互逻辑（如按钮、动态过滤器等）。

    **HTML 骨架模板 (请直接复制使用):**
    ```python
    html_template = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.tailwindcss.com?plugins=typography"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
        <style>
            body {{ font-family: 'Inter', sans-serif; background-color: #f8fafc; }}
            h1, h2, h3 {{ letter-spacing: -0.025em; }}
            .prose pre {{ background-color: #1e293b; color: #e2e8f0; border-radius: 0.5rem; }}
            /* 确保 Plotly 图表容器宽度自适应 */
            .plotly-graph-div {{ width: 100%; }}
        </style>
    </head>
    <body class="min-h-screen p-8 flex justify-center bg-slate-50 text-slate-900">
        <article class="prose prose-slate prose-lg max-w-4xl w-full bg-white p-12 rounded-2xl shadow-[0_20px_50px_-12px_rgba(0,0,0,0.1)] border border-slate-100">
            <!-- 你的内容在这里: 标题, 文本, 图片, 表格, 交互组件 -->
            {content_body}
        </article>
    </body>
    </html>
    """
    ```

2.  **图片嵌入 (CRITICAL - UPDATED):**
    *   **不要**使用 Base64 编码图片。这会浪费大量的 Token。
    *   **必须**使用相对路径引用图片。
    *   `visualize_file` 工具会自动启动一个静态服务器并将 HTML 作为一个网页 URL 返回，浏览器会自动加载相对路径的图片。
    *   **正确示例:** `<img src="chart.png" class="..." />`
    *   **错误示例:** `<img src="data:image/png;base64,..." />`

3.  **展示:**
    *   生成 HTML 后，**立即**调用 `visualize_file('report.html')`。

**任务处理指南:**
*   **数据任务:** 生成包含 Markdown 表格的 HTML 报告。
*   **可视化任务:** 生成嵌入 Base64 图片的 HTML 报告。
*   **联网任务:** 生成包含链接列表的 HTML 报告。

**自我修正:**
*   如果代码报错，分析原因并重试。

请始终使用中文与用户交流。
'''

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

            max_turns = 15
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
