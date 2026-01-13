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
*   **防御性编程:**
    *   写入文件时**必须**指定 `encoding='utf-8'`。
    *   读取 CSV/Excel 文件时，如果默认编码失败，**请尝试 `encoding='gbk'` 或 `encoding='gb18030'`**，以兼容中文数据。

**高级展示指南 (Visual Presentation):**

    **HTML 报告生成 (关键):**
    *   当需要展示结果时，**必须**生成一个独立的 HTML 文件（如 `report.html`）。
    *   **重要：** 在 Python 中写入 HTML 文件时，务必使用 `open('report.html', 'w', encoding='utf-8')`，否则会出现中文乱码。
    *   **图片处理 (Image Handling):**
        *   **强烈推荐**使用 `plotly` 库生成交互式图表（HTML 自包含）。**这是解决中文乱码的最佳方案**（浏览器渲染，完美支持中文）。
        *   如果使用 `matplotlib`：
            1.  **必须解决中文乱码:** Linux 环境无中文字体。**严禁直接使用中文**（会显示方框）。你**必须**在代码中下载字体文件（如 `wget https://github.com/google/fonts/raw/main/ofl/notosanssc/NotoSansSC-Regular.ttf`），然后使用 `font_manager` 加载该字体进行绘图。
            2.  **必须**将图片转换为 **Base64** 编码嵌入 `src`，严禁使用相对路径。
    *   **语言要求:** 报告的所有文本、分析结论、图表标题和标签**必须使用中文**。
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
        <title>Manus Analysis Report</title>
        <script src="https://cdn.tailwindcss.com?plugins=typography"></script>
        <link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@300;400;500;600;700&family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
        <script>
            tailwind.config = {{
                theme: {{
                    extend: {{
                        fontFamily: {{
                            sans: ['Open Sans', 'sans-serif'],
                            heading: ['Poppins', 'sans-serif'],
                        }},
                        colors: {{
                            primary: '#3B82F6',
                            secondary: '#60A5FA',
                            slate: {{
                                50: '#F8FAFC',
                                100: '#F1F5F9',
                                200: '#E2E8F0',
                                300: '#CBD5E1',
                                400: '#94A3B8',
                                500: '#64748B',
                                600: '#475569',
                                700: '#334155',
                                800: '#1E293B',
                                900: '#0F172A',
                            }}
                        }}
                    }}
                }}
            }}
        </script>
        <style>
            body {{ font-family: 'Open Sans', sans-serif; background-color: #F8FAFC; color: #1E293B; }}
            h1, h2, h3, h4, h5, h6 {{ font-family: 'Poppins', sans-serif; }}
            .prose {{ max-width: none; }}
            .prose h1 {{ color: #0F172A; font-weight: 700; letter-spacing: -0.025em; margin-bottom: 0.5em; }}
            .prose h2 {{ color: #1E293B; font-weight: 600; letter-spacing: -0.025em; margin-top: 2em; margin-bottom: 0.75em; border-bottom: 2px solid #F1F5F9; padding-bottom: 0.5rem; }}
            .prose h3 {{ color: #334155; font-weight: 600; margin-top: 1.5em; }}
            .prose p {{ line-height: 1.8; color: #475569; margin-bottom: 1.5em; }}
            
            /* Table Styling */
            .prose table {{ width: 100%; border-collapse: separate; border-spacing: 0; margin: 2em 0; border-radius: 0.75rem; border: 1px solid #E2E8F0; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
            .prose thead {{ background-color: #F8FAFC; }}
            .prose th {{ color: #334155; font-weight: 600; padding: 1rem; text-align: left; border-bottom: 1px solid #E2E8F0; white-space: nowrap; }}
            .prose td {{ padding: 1rem; border-bottom: 1px solid #F1F5F9; color: #475569; }}
            .prose tr:last-child td {{ border-bottom: none; }}
            .prose tr:hover td {{ background-color: #F8FAFC; transition: background-color 0.15s ease; }}

            /* Chart Styling */
            .plotly-graph-div {{ width: 100%; border-radius: 0.75rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06); margin: 2rem 0; border: 1px solid #F1F5F9; overflow: hidden; background: white; }}
            
            /* Code Blocks */
            .prose pre {{ background-color: #0F172A; color: #E2E8F0; border-radius: 0.75rem; padding: 1.25rem; overflow-x: auto; box-shadow: inset 0 2px 4px 0 rgba(0, 0, 0, 0.3); }}
            
            /* Custom Scrollbar */
            ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
            ::-webkit-scrollbar-track {{ background: transparent; }}
            ::-webkit-scrollbar-thumb {{ background: #CBD5E1; border-radius: 4px; }}
            ::-webkit-scrollbar-thumb:hover {{ background: #94A3B8; }}
        </style>
    </head>
    <body class="min-h-screen flex flex-col selection:bg-blue-100 selection:text-blue-900">
        <!-- Header -->
        <header class="bg-white/80 border-b border-slate-200 sticky top-0 z-50 backdrop-blur-md transition-all duration-300">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center text-white font-bold shadow-lg shadow-blue-500/20 ring-1 ring-black/5">
                        M
                    </div>
                    <span class="text-xl font-bold text-slate-900 tracking-tight font-heading">Manus<span class="text-blue-600">Report</span></span>
                </div>
                <div class="flex items-center gap-2 text-xs font-medium text-slate-500 bg-slate-50 px-3 py-1.5 rounded-full border border-slate-100">
                    <span class="relative flex h-2 w-2">
                      <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                      <span class="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                    </span>
                    AI Generated
                </div>
            </div>
        </header>

        <!-- Main Content -->
        <main class="flex-1 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10 w-full">
            <article class="prose prose-slate prose-lg max-w-none bg-white p-8 md:p-12 rounded-2xl shadow-xl shadow-slate-200/50 border border-slate-100 ring-1 ring-slate-900/5">
                {content_body}
            </article>
        </main>

        <!-- Footer -->
        <footer class="border-t border-slate-200 bg-white mt-auto">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 text-center">
                <p class="text-sm text-slate-400 font-medium">Powered by Manus Agent &bull; Professional Data Analysis</p>
            </div>
        </footer>
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

**任务处理指南 (Task Handling):**
*   **数据分析 (Data Analysis):** 自动执行清洗 -> 统计 -> 绘图 -> 生成 HTML 报告 -> `visualize_file`。
    *   **主动性:** 无需等待用户详细指令，主动探索数据结构，清洗脏数据，并展示最有价值的图表。
    *   **报告标准:** HTML 报告必须包含数据摘要、关键洞察 (Insights) 和生成的图表 (使用相对路径引用图片)。
*   **一般任务:** 只要涉及文件生成或可视化，最后务必调用 `visualize_file` 展示结果。

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
