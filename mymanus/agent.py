import os
import json
import asyncio
import uuid
import re
from typing import AsyncGenerator, Dict, Any, List, Literal

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.types import Command

# Import our tools
from sandbox_e2b import TOOLS, TEMPLATE_CODE_INTERPRETER

# System Prompt
SYSTEM_PROMPT = """你是一个运行在 **E2B 安全沙箱 (Firecracker MicroVM)** 中的全栈编程智能体。你的目标是利用 Python 代码和系统命令，自主、高效地解决用户提出的任何技术问题。

**环境能力:**
*   **OS**: Linux (Debian/Ubuntu based).
*   **Python**: 3.12+ (预装常用库).
*   **Root 权限**: 你拥有沙箱的完全控制权 (sudo not required, or available).
*   **持久化**: `/home/user` 是你的工作目录。

**核心工作流 (Thought Process):**
1.  **分析 (Analyze)**: 理解用户需求。如果是模糊的需求（如“分析这个数据”），先查看数据结构。
2.  **规划 (Plan)**: 决定需要的步骤。是否需要安装库？是否需要编写脚本？
3.  **执行 (Execute)**:
    *   **代码优先**: 能用 Python 解决的，优先用 `run_code`。
    *   **Shell 辅助**: 安装依赖 (`pip install`)、文件管理 (`ls`, `mv`) 使用 `run_shell_command`。
    *   **合并操作**: 尽量在一个工具调用中完成相关联的步骤，减少往返延迟。
4.  **验证 (Verify)**: 检查代码输出或文件是否存在。如果有错误，自我修正并重试。
5.  **交付 (Deliver)**:
    *   **静态网页/图表**: 如果生成了 HTML 文件、图片或图表，**必须**调用 `visualize_file(path='...')`。**严禁**对静态文件使用 `get_public_url`。
    *   **动态 Web 服务**: 如果启动了 Web 服务 (如 Streamlit, Flask, Gradio, FastAPI) 监听端口，**必须**调用 `get_public_url(port=...)`。
    *   **文件下载**: 如果用户需要最终产物 (PDF, Excel, Zip)，使用 `download_file_to_host` 将其保存到宿主机供用户下载。

**HTML 与可视化指南:**
*   **自主设计**: 生成 HTML 报告时，请完全自主编写 HTML/CSS/JS 代码，拒绝死板的预设模板。根据数据特点设计布局（推荐使用现代风格如 Tailwind CDN）。
*   **布局对齐**: 务必使用 Flexbox (e.g., `flex flex-col items-center`) 或 Grid 布局确保图表和文字说明（标题、段落）在页面中居中或整齐对齐，避免元素错位。
*   **编码规范**: 务必在 HTML `<head>` 中添加 `<meta charset="UTF-8">`，确保中文显示正常。
*   **资源引用**: 生成的图表（如 .png, .svg）应保存为独立文件。在 HTML 中请直接使用**相对路径**引用它们（例如 `<img src="chart.png">`），**不要**使用 Base64 编码，以便于利用沙箱的文件服务能力。
*   **动态预览**: 始终记得在生成 HTML 后调用 `visualize_file`。

**UI/UX Pro Max 规范 (必须执行):**
1.  **Bento Grid 布局**: 必须使用 CSS Grid (`grid gap-6`) 将页面划分为卡片区域。
2.  **Glassmorphism 卡片**:
    *   卡片样式: `bg-white/80 dark:bg-slate-900/60 backdrop-blur-xl border border-slate-200 dark:border-white/10 rounded-2xl shadow-sm hover:shadow-md transition-all duration-300`.
3.  **排版**:
    *   字体: `<body class="font-sans antialiased text-slate-900 dark:text-slate-50 bg-slate-50 dark:bg-slate-950">`
    *   标题: 使用 `tracking-tight` (紧凑字间距) 和 `font-bold`。
4.  **图表融合**: 生成 Plotly/Echarts 时，务必将背景设置为**透明**，并隐藏无关的工具栏 (`config={'displayModeBar': 'hover'}`)。
5.  **禁止 Emoji**: 在正式的 UI 元素（按钮、标题、卡片头）中，请使用 SVG 图标代替 Emoji。

**工具使用最佳实践:**
*   **依赖管理**: 不要假设库已安装。如果不确定，先 `pip install`。
*   **文件路径**: 始终使用绝对路径或相对路径，注意当前工作目录。
*   **文件操作**: 读写文本文件时（特别是包含中文时），请显式指定 `encoding='utf-8'`。
*   **Web 服务**: 如果启动 Web 服务，确保绑定到 `0.0.0.0`。
    *   **端口清理**: 启动服务前（如 Gradio/Streamlit），**必须**先检查并杀死占用端口的进程。例如：`fuser -k 7860/tcp` 或 `kill -9 $(lsof -t -i:7860)`，防止端口冲突。
*   **Streamlit 特别指南**:
    *   **启动命令**: 必须使用 `streamlit run app.py --server.address=0.0.0.0 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false`。缺少这些参数会导致连接断开。
    *   **后台运行**: 使用 `run_shell_command` 时，务必设置 `is_background=True` 或在命令末尾加 `&`。
*   **Gradio 特别指南**:
    *   **版本建议**: 强烈推荐使用 `pip install gradio==3.50.2`，因为新版本(4.x)在反向代理下常出现样式丢失(404)或连接错误。
        *   **启动代码**: 必须使用以下配置以避免反向代理下的JSON解析错误：
            ```python
            import gradio as gr
            import os
            
            # 创建Gradio应用
            def greet(name):
                return f"Hello {name}!"
            
            demo = gr.Interface(
                fn=greet,
                inputs=gr.Textbox(placeholder="Enter your name"),
                outputs="text",
                title="Hello World",
                description="A simple Gradio app that says hello"
            )
            
            # 关键：share=False时自动非阻塞，并禁用可能导致问题的功能
            demo.launch(
                server_name="0.0.0.0",
                server_port=7860,
                share=False,             # 必须False：使用E2B代理，且非阻塞模式
                show_error=True,
                enable_queue=False,      # 必须False：禁用队列，避免API调用返回HTML
                favicon_path=None,       # 避免favicon请求问题
                inbrowser=False,
                quiet=True               # 减少日志输出
            )
            # 注意：share=False时，launch()会自动非阻塞，无需blocking参数
            ```
        *   **关键参数说明**:
            - `enable_queue=False`: **必须设置**，禁用队列功能，避免某些API端点返回HTML而非JSON。这是解决JSON解析错误的关键参数。
            - `share=False`: **必须设置**，不使用gradio的公共链接（使用E2B的代理），且会自动非阻塞运行
            - `show_error=True`: 显示详细错误信息便于调试
            - `server_name="0.0.0.0"`: 允许外部访问
        *   **启动方式**: 
            - 如果使用 `run_code` 执行，确保代码最后一行是 `demo.launch(...)`，`share=False`会自动非阻塞
            - 如果使用 `run_shell_command`，使用 `python app.py &` 在后台运行
        *   **故障排除**: 
            - 如果仍然出现JSON解析错误，尝试在启动前设置环境变量：`os.environ['GRADIO_SERVER_NAME'] = '0.0.0.0'`
            - 确保端口7860没有被占用：先执行 `kill -9 $(lsof -t -i:7860) 2>/dev/null || true`
        *   **端口**: 默认端口通常为 `7860`。
        *   **访问**: 运行后必须调用 `get_public_url(port=7860)`。

请始终使用**中文**与用户交流，保持专业、简洁且乐于助人。
"""

# --- Multi-Agent Prompts ---

CODE_WRITER_PROMPT = """你是一个专业的代码编写智能体。你的职责是：

**核心能力：**
1. 根据任务需求编写清晰、功能完整的代码
2. 遵循最佳实践和编码规范
3. 根据代码审查反馈改进代码
4. 编写必要的配置文件和依赖声明

**重要指令：**
- **必须**使用 `write_file` 工具将所有代码写入文件。
- **不要**仅仅在回复中展示代码块，除非你已经调用了 `write_file`。
- 如果你不调用 `write_file`，文件将不会被保存，任务将失败。

**编码标准：**
- 使用清晰的变量和函数命名
- 添加适当的注释和文档字符串
- 遵循 PEP 8 (Python) 或相应语言的规范
- 处理常见的错误情况
- 使用 UTF-8 编码处理中文

**工作流程：**
1. 分析任务需求，规划需要创建的文件
2. 使用 write_file 工具创建代码文件
3. 如果收到审查反馈，仔细阅读并改进代码
4. 确保所有文件都已创建并保存

**可用工具：**
- write_file: 创建或覆盖文件
- read_file: 读取文件内容
- list_files: 列出目录中的文件

请始终使用中文回复，保持专业和高效。
"""

CODE_REVIEWER_PROMPT = """你是一个专业的代码审查智能体。你的职责是：

**审查重点：**
1. **代码质量**: 可读性、可维护性、代码组织
2. **功能完整性**: 是否满足任务需求，是否有遗漏
3. **最佳实践**: 是否遵循语言和框架的最佳实践
4. **错误处理**: 是否处理了常见的错误情况
5. **安全性**: 是否存在明显的安全隐患
6. **文档**: 是否有必要的注释和文档字符串

**审查标准：**
- ✓ **通过 (approved)**: 代码质量良好，满足需求，可以使用
- ✗ **需要改进 (needs_improvement)**: 存在明显问题，需要修改

**反馈格式：**
你必须返回 JSON 格式的审查结果：
```json
{
  "status": "approved" 或 "needs_improvement",
  "comments": ["评论1", "评论2"],
  "suggestions": ["建议1", "建议2"]
}
```

**审查流程：**
1. **首先**使用 `list_files` 工具列出 /home/user 目录，确认实际存在哪些文件
2. 使用 `read_file` 工具读取所有相关文件
3. 仔细分析代码质量和功能完整性
4. 列出具体的问题和改进建议
5. 返回结构化的审查结果

**注意事项：**
- 提供具体、可操作的建议，而不是泛泛而谈
- 如果代码基本满足需求，不要过于苛刻
- 关注重要问题，忽略微小的风格差异

请始终使用中文回复，保持专业和建设性。
"""

class ManusAgent:
    def __init__(self):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        base_url = os.getenv("DEEPSEEK_BASE_URL")
        self.model_id = os.getenv("MODEL_ID", "deepseek-ai/DeepSeek-V3")
        
        if not api_key:
            print("[Warning] DEEPSEEK_API_KEY not found.")
            self.model = None
        else:
            self.model = ChatOpenAI(
                api_key=api_key, 
                base_url=base_url,
                model=self.model_id,
                streaming=True,
                max_retries=20,
                timeout=300
            )
            
        self.tools = TOOLS
        
        # Use create_agent from langchain with middleware
        if self.model:
            self.graph = create_agent(
                model=self.model,
                tools=self.tools,
                system_prompt=SYSTEM_PROMPT,
                checkpointer=MemorySaver(),
                middleware=[
                    HumanInTheLoopMiddleware(
                        interrupt_on={
                            "visualize_file": True
                        },
                        description_prefix="[Approval Required]"
                    )
                ]
            )
        else:
            self.graph = None

        self.sandbox = None

    async def close(self):
        """Clean up resources."""
        if self.sandbox:
            await self.sandbox.kill()
            self.sandbox = None

    async def run(
        self,
        task: str = None,
        thread_id: str = None,
        mode: Literal["single", "multi"] = "single",
        max_iterations: int = 3
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Executes the agent loop.

        Args:
            task: Task description
            thread_id: Thread ID for resumption
            mode: "single" for single agent, "multi" for multi-agent collaboration
            max_iterations: Max iterations for multi-agent mode

        Returns:
            AsyncGenerator of events
        """
        if mode == "single":
            async for event in self._run_single(task, thread_id):
                yield event
        else:
            async for event in self._run_multi(task, max_iterations):
                yield event

    async def _run_single(self, task: str = None, thread_id: str = None) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Executes the agent loop.
        If thread_id is provided, it resumes that thread.
        """
        if not self.graph:
            yield {"type": "error", "message": "Agent not initialized (check API Key)."}
            return

        # Generate a new thread_id if not provided
        if not thread_id:
            thread_id = str(uuid.uuid4())
        
        # Initialize Sandbox if needed
        from e2b_code_interpreter import AsyncSandbox
        
        try:
            # Check if sandbox is healthy
            is_healthy = False
            if self.sandbox:
                try:
                    is_healthy = await self.sandbox.is_running()
                except:
                    is_healthy = False

            if not is_healthy:
                yield {"type": "status", "message": "Initializing E2B Sandbox..."}
                self.sandbox = await AsyncSandbox.create(TEMPLATE_CODE_INTERPRETER)
                yield {"type": "system", "message": f"Sandbox created: {self.sandbox.sandbox_id}"}
            else:
                yield {"type": "system", "message": f"Reusing sandbox: {self.sandbox.sandbox_id}"}
                
            # Config with sandbox
            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "sandbox": self.sandbox
                },
                "recursion_limit": 100
            }

            # Initialize turn count based on existing message history
            state = self.graph.get_state(config)
            existing_messages = state.values.get("messages", [])
            # Each pair of Human+AI is one turn, plus the current one
            current_turn = len([m for m in existing_messages if hasattr(m, 'content') and m.content]) // 2
            
            # Input format:
            # If new task: {"messages": [HumanMessage(content=task)]}
            # If resumption: Command(resume={"decisions": [{"type": "approve"}]})
            inputs = None
            if task:
                inputs = {"messages": [HumanMessage(content=task)]}
            else:
                # Assuming resumption implies approval for now
                # We need to wrap it in a dict because HumanInTheLoopMiddleware expects "decisions" key
                # "approve" is the correct type, not "accept"
                inputs = Command(resume={"decisions": [{"type": "approve"}]})
            
            # Use astream_events to pipe results to frontend
            async for event in self.graph.astream_events(inputs, config=config, version="v2"):
                kind = event["event"]
                
                if kind == "on_chat_model_start":
                    current_turn += 1
                    yield {"type": "status", "message": f"Thinking (Turn {current_turn})..."}

                elif kind == "on_chat_model_stream":
                    content = event["data"]["chunk"].content
                    if content:
                        yield {"type": "thought", "content": content}

                elif kind == "on_chat_model_end":
                    output = event["data"].get("output")
                    if output:
                        tool_calls = getattr(output, "tool_calls", [])
                        if tool_calls:
                            yield {
                                "type": "step_summary",
                                "thought": output.content,
                                "tool_calls": [
                                    {"name": tc["name"], "args": tc["args"]} 
                                    for tc in tool_calls
                                ]
                            }
                        elif output.content:
                            yield {
                                "type": "answer",
                                "content": output.content
                            }
                        
                elif kind == "on_tool_start":
                    yield {"type": "status", "message": f"Calling tool: {event['name']}"}
                    
                elif kind == "on_tool_end":
                    output = event["data"].get("output")
                    
                    # Try to extract content string
                    content_str = ""
                    if isinstance(output, ToolMessage):
                        content_str = output.content
                    else:
                        content_str = str(output)

                    # Try to detect if it's a visualization payload
                    is_preview = False
                    try:
                        # Heuristic: only try parsing if it looks like JSON object
                        if content_str.strip().startswith("{"):
                            data = json.loads(content_str)
                            if data.get("type") == "file_preview":
                                yield {
                                    "type": "preview", 
                                    "mime": data["mime"], 
                                    "content": data["content"], 
                                    "path": data["path"]
                                }
                                yield {"type": "output", "content": f"(File '{data['path']}' sent to preview)"}
                                is_preview = True
                    except:
                        pass
                    
                    # If not a preview, just output the content
                    if not is_preview:
                        yield {"type": "output", "content": content_str}

            # Check if we are paused (interrupted)
            state = self.graph.get_state(config)
            if state.next:
                # We are paused.
                # Check what the next step is
                # For HumanInTheLoopMiddleware, the interruption details might be in state
                # But since we configured interrupt_on for tools, seeing pending tool calls is enough
                
                # Check for pending tool calls in the last message
                if state.values.get("messages"):
                    last_message = state.values["messages"][-1]
                    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                        tool_calls = last_message.tool_calls
                        
                        # Format tool calls for display with refined terminal-like style
                        tools_html = ""
                        for tc in tool_calls:
                            # Extract snippet
                            args = tc.get("args", {})
                            content = args.get("code") or args.get("command") or json.dumps(args)
                            snippet = str(content)[:400] + "..." if len(str(content)) > 400 else str(content)
                            
                            tools_html += f"""
                            <div class="relative group/card rounded-xl border border-slate-200 bg-white/80 overflow-hidden transition-all duration-300 hover:border-amber-400 hover:shadow-lg hover:shadow-amber-500/20 cursor-pointer backdrop-blur-sm">
                                
                                <div class="flex items-start justify-between px-4 py-3 border-b border-slate-200 bg-slate-50/80 relative z-10">
                                    <div class="flex items-center gap-3">
                                        <div class="w-2 h-2 rounded-full bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)]"></div>
                                        <span class="text-[11px] font-bold tracking-widest uppercase text-amber-600 font-mono">{tc['name']}</span>
                                    </div>
                                    <div class="flex gap-1.5">
                                        <div class="w-2.5 h-2.5 rounded-full bg-slate-300 group-hover/card:bg-amber-400/40 transition-colors"></div>
                                        <div class="w-2.5 h-2.5 rounded-full bg-slate-300 group-hover/card:bg-amber-400/40 transition-colors"></div>
                                        <div class="w-2.5 h-2.5 rounded-full bg-slate-300 group-hover/card:bg-amber-400/40 transition-colors"></div>
                                    </div>
                                </div>
                                <div class="p-4 relative z-10">
                                    <pre class="text-[11px] font-mono text-slate-700 break-words whitespace-pre-wrap leading-relaxed selection:bg-amber-500/30">{snippet}</pre>
                                </div>
                                <!-- Bottom Accent Line -->
                                <div class="absolute bottom-0 left-0 w-full h-0.5 bg-gradient-to-r from-transparent via-amber-500/60 to-transparent opacity-0 group-hover/card:opacity-100 transition-opacity duration-500"></div>
                            </div>
                            """

                        # Generate a preview for the UI with high-end frontend design
                        # IMPORTANT: Must include Tailwind and Fonts because iframe is isolated
                        preview_html = f"""
                        <!DOCTYPE html>
                        <html lang="en">
                        <head>
                            <meta charset="UTF-8">
                            <meta name="viewport" content="width=device-width, initial-scale=1.0">
                            <script src="https://cdn.tailwindcss.com"></script>
                            <script>
                                tailwind.config = {{
                                    darkMode: 'class',
                                    theme: {{
                                        extend: {{
                                            fontFamily: {{
                                                sans: ['Inter', 'sans-serif'],
                                                mono: ['JetBrains Mono', 'monospace'],
                                            }}
                                        }}
                                    }}
                                }}
                            </script>
                            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
                            <style>
                                /* Custom Scrollbar - Light Mode */
                                ::-webkit-scrollbar {{
                                    width: 6px;
                                }}
                                ::-webkit-scrollbar-track {{
                                    background: rgba(226, 232, 240, 0.3);
                                    border-radius: 10px;
                                }}
                                ::-webkit-scrollbar-thumb {{
                                    background: rgba(245, 158, 11, 0.4);
                                    border-radius: 10px;
                                    transition: background 0.2s;
                                }}
                                ::-webkit-scrollbar-thumb:hover {{
                                    background: rgba(245, 158, 11, 0.6);
                                }}

                                /* Glassmorphism - Light Mode */
                                .glass-card {{
                                    background: rgba(255, 255, 255, 0.85);
                                    backdrop-filter: blur(20px);
                                    -webkit-backdrop-filter: blur(20px);
                                }}

                                /* Reduced Motion Support */
                                @media (prefers-reduced-motion: reduce) {{
                                    *, *::before, *::after {{
                                        transition-duration: 0.01ms !important;
                                    }}
                                }}
                            </style>
                        </head>
                        <body class="bg-slate-50 h-screen w-screen overflow-hidden flex items-center justify-center p-4 md:p-8 font-sans text-slate-900">

                            <!-- Main Container -->
                            <div class="w-full max-w-6xl h-full max-h-[700px] relative group mx-auto flex flex-col shadow-2xl">
                                
                                <div class="relative w-full h-full glass-card rounded-3xl border border-slate-200 overflow-hidden grid grid-cols-1 md:grid-cols-12 shadow-2xl shadow-slate-200/50">

                                    <!-- Left Panel: Context & Header -->
                                    <div class="md:col-span-4 bg-gradient-to-br from-white via-slate-50 to-slate-100 p-10 flex flex-col justify-center border-b md:border-b-0 md:border-r border-slate-200 relative overflow-hidden shrink-0">
                                        
                                        <div class="relative z-10 flex flex-col h-full justify-center">
                                            <!-- Icon Container -->
                                            <div class="relative w-16 h-16 rounded-2xl bg-amber-500/10 border-2 border-amber-500/20 flex items-center justify-center mb-8 shrink-0">
                                                <svg class="w-8 h-8 text-amber-600 relative z-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                                                    <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
                                                </svg>
                                            </div>

                                            <h3 class="text-3xl font-bold text-slate-900 tracking-tight mb-4">Security Check</h3>
                                            <p class="text-sm text-slate-600 leading-relaxed mb-auto">
                                                The agent requires your approval to execute the following actions in the secure sandbox environment.
                                            </p>

                                            <!-- Status Badge -->
                                            <div class="flex items-center gap-3 px-4 py-3 rounded-xl bg-slate-100 border border-slate-200 text-[11px] font-mono text-slate-600 uppercase tracking-wider mt-8 shadow-sm">
                                                <span class="relative flex h-2.5 w-2.5">
                                                    <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
                                                </span>
                                                System Standing By
                                            </div>
                                        </div>
                                    </div>
                                    
                                    <!-- Right Panel: List & Actions -->
                                    <div class="md:col-span-8 bg-white/60 flex flex-col h-full overflow-hidden backdrop-blur-sm">
                                        <!-- Header -->
                                        <div class="px-6 py-4 border-b border-slate-200 bg-white/80">
                                            <div class="flex items-center justify-between">
                                                <div>
                                                    <h4 class="text-xs font-bold text-amber-600 uppercase tracking-wider mb-1">Pending Operations</h4>
                                                    <p class="text-[10px] text-slate-500">Review and approve the following actions</p>
                                                </div>
                                                <div class="px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 shadow-sm">
                                                    <span class="text-[10px] font-bold text-amber-700 font-mono">{len(tool_calls)} ACTIONS</span>
                                                </div>
                                            </div>
                                        </div>

                                        <!-- Scrollable Tool List -->
                                        <div class="flex-1 p-6 overflow-y-auto custom-scrollbar space-y-4 bg-gradient-to-b from-slate-50/50 to-blue-50/30 min-h-0">
                                            {tools_html}
                                        </div>

                                        <!-- Footer -->
                                        <div class="p-6 bg-white/90 border-t border-slate-200 flex gap-4 shrink-0 z-20 backdrop-blur-md shadow-[0_-10px_40px_rgba(0,0,0,0.05)]">
                                            <button onclick="confirmExecution('{thread_id}')" class="flex-1 relative group/btn px-6 py-4 rounded-xl text-sm font-bold uppercase tracking-widest text-white overflow-hidden transition-all active:scale-[0.97] shadow-xl shadow-amber-600/30 hover:shadow-amber-600/50 border-2 border-amber-500/40 hover:border-amber-500/60">
                                                <div class="absolute inset-0 bg-gradient-to-r from-amber-600 via-orange-600 to-amber-600 bg-[length:200%_auto] transition-all duration-700 group-hover/btn:bg-right"></div>
                                                <div class="absolute inset-0 bg-gradient-to-t from-black/10 to-transparent"></div>
                                                <div class="relative flex items-center justify-center gap-3">
                                                    <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                                                        <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
                                                    </svg>
                                                    <span>Approve & Execute</span>
                                                    <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                                                        <path stroke-linecap="round" stroke-linejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                                                    </svg>
                                                </div>
                                            </button>
                                        </div>
                                    </div>
                                    
                                </div>
                            </div>
                            
                            <script>
                                window.confirmExecution = (tid) => {{
                                    window.parent.postMessage({{ type: 'manus_confirm', thread_id: tid, action: 'approve' }}, '*');
                                }};
                            </script>
                        </body>
                        </html>
                        """
                        
                        yield {
                            "type": "preview",
                            "mime": "text/html",
                            "content": preview_html,
                            "path": "Security Check"
                        }
            else:
                yield {"type": "success", "message": "Task completed."}

        except Exception as e:
            yield {"type": "error", "message": f"Agent Error: {str(e)}"}
            import traceback
            traceback.print_exc()

    async def _run_multi(
        self,
        task: str,
        max_iterations: int = 3
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Multi-agent collaboration mode (Code Writer + Code Reviewer)"""

        if not self.model:
            yield {"type": "error", "message": "Agent not initialized (check API Key)."}
            return

        # Initialize sandbox
        from e2b_code_interpreter import AsyncSandbox

        try:
            is_healthy = False
            if self.sandbox:
                try:
                    is_healthy = await self.sandbox.is_running()
                except:
                    is_healthy = False

            if not is_healthy:
                yield {"type": "status", "message": "初始化 E2B Sandbox..."}
                self.sandbox = await AsyncSandbox.create(TEMPLATE_CODE_INTERPRETER)
                yield {"type": "system", "message": f"Sandbox created: {self.sandbox.sandbox_id}"}
            else:
                yield {"type": "system", "message": f"Reusing sandbox: {self.sandbox.sandbox.sandbox_id}"}

        except Exception as e:
            yield {"type": "error", "message": f"Sandbox initialization failed: {str(e)}"}
            return

        # Create file tools for multi-agent mode
        files_created = []

        @tool
        async def write_file(path: str, content: str) -> str:
            """在沙箱中创建或覆盖文件。必须提供文件路径(path)和文件内容(content)。"""
            try:
                full_path = f"/home/user/{path}" if not path.startswith("/") else path
                await asyncio.wait_for(
                    self.sandbox.files.write(full_path, content),
                    timeout=30.0
                )
                clean_path = path
                if clean_path.startswith("./"):
                    clean_path = clean_path[2:]
                elif clean_path.startswith("/home/user/"):
                    clean_path = clean_path.replace("/home/user/", "")
                if clean_path not in files_created:
                    files_created.append(clean_path)
                return f"✓ 文件已创建: {clean_path}"
            except asyncio.TimeoutError:
                return f"✗ 写入文件超时 ({path}): 写入操作超过 30 秒"
            except Exception as e:
                return f"✗ 写入文件失败 ({path}): {type(e).__name__}: {str(e)}"

        @tool
        async def read_file(path: str) -> str:
            """读取文件内容。参数: path (文件路径)"""
            try:
                full_path = f"/home/user/{path}" if not path.startswith("/") else path
                try:
                    content = await asyncio.wait_for(
                        self.sandbox.files.read(full_path),
                        timeout=10.0
                    )
                    return f"=== {path} ===\n{content}"
                except asyncio.TimeoutError:
                    return f"✗ 读取文件超时 ({path}): 文件读取超过 10 秒"
            except FileNotFoundError:
                return f"✗ 文件不存在 ({path}): 请使用 list_files 确认文件是否存在"
            except Exception as e:
                return f"✗ 读取文件失败 ({path}): {type(e).__name__}: {str(e)}"

        @tool
        async def list_files(directory: str = "/home/user") -> str:
            """列出目录中的文件。参数: directory (目录路径，默认 /home/user)"""
            try:
                try:
                    files = await asyncio.wait_for(
                        self.sandbox.files.list(directory),
                        timeout=10.0
                    )
                    if not files:
                        return f"目录 {directory} 为空"
                    return "\n".join([f"- {f.name} ({'dir' if f.type == 'dir' else 'file'})" for f in files])
                except asyncio.TimeoutError:
                    return f"✗ 列出文件超时 ({directory}): 操作超过 10 秒"
            except Exception as e:
                return f"✗ 列出文件失败 ({directory}): {type(e).__name__}: {str(e)}"

        # Create Code Writer and Code Reviewer agents
        code_writer = create_agent(
            model=self.model,
            tools=[write_file, read_file, list_files],
            system_prompt=CODE_WRITER_PROMPT
        )

        code_reviewer = create_agent(
            model=self.model,
            tools=[read_file, list_files],
            system_prompt=CODE_REVIEWER_PROMPT
        )

        yield {"type": "status", "message": "🎯 开始多智能体协作"}
        yield {"type": "system", "message": f"任务: {task}"}

        # Iteration loop
        for iteration in range(1, max_iterations + 1):
            yield {"type": "status", "message": f"Thinking (Turn {iteration})"}

            # Phase 1: Code Writing
            yield {"type": "status", "message": "Calling tool: CodeWriter"}
            yield {"type": "status", "message": "📝 Code Writer 正在编写代码..."}

            try:
                feedback = None
                if iteration > 1:
                    # Get feedback from previous iteration
                    pass

                if feedback:
                    input_text = f"""任务: {task}\n\n代码审查反馈:\n{feedback}\n\n请根据反馈改进代码。"""
                else:
                    input_text = f"""任务: {task}\n\n请编写完整的代码实现。"""

                config = {"configurable": {"thread_id": str(uuid.uuid4())}}
                result = await code_writer.ainvoke({"messages": [("user", input_text)]}, config)

                output = ""
                if "messages" in result:
                    for msg in reversed(result["messages"]):
                        if msg.type == "ai":
                            output = msg.content
                            break

                # Extract files from output
                for line in output.split("\n"):
                    if "文件已创建:" in line:
                        path = line.split("文件已创建:")[-1].strip()
                        if path.startswith("./"):
                            path = path[2:]
                        elif path.startswith("/home/user/"):
                            path = path.replace("/home/user/", "")
                        if path and path not in files_created:
                            files_created.append(path)

                yield {"type": "output", "content": "✓ Code Writer 完成"}
                yield {"type": "output", "content": f"创建的文件: {', '.join(files_created) if files_created else '(无)'}"}

            except Exception as e:
                yield {"type": "error", "message": f"Code Writer 错误: {str(e)}"}
                break

            # Phase 2: Code Review
            yield {"type": "status", "message": "Calling tool: CodeReviewer"}
            yield {"type": "status", "message": "🔍 Code Reviewer 正在审查代码..."}

            try:
                # List actual files in sandbox
                files_to_review = set(files_created)
                try:
                    files_list = await asyncio.wait_for(
                        self.sandbox.files.list("/home/user"),
                        timeout=15.0
                    )
                    for f in files_list:
                        if f.type != 'dir' and not f.name.startswith('.'):
                            files_to_review.add(f.name)
                except Exception:
                    pass

                files_to_review = sorted(list(files_to_review))
                yield {"type": "status", "message": f"📂 准备审查文件: {', '.join(files_to_review) if files_to_review else '无'}"}

                review_input = f"""
原始任务: {task}

需要审查的文件列表:
{chr(10).join([f'- {f}' for f in files_to_review]) if files_to_review else '(无文件)'}

**重要指令**:
1. **首先**使用 `list_files("/home/user")` 工具确认实际存在哪些文件。
2. 你必须**逐个**使用 `read_file` 工具读取文件内容。
3. 不要假设文件内容，必须基于 `read_file` 的返回结果进行审查。
4. 如果文件读取失败或超时，请在评论中指出具体错误信息。
5. 审查完成后，返回 JSON 格式的审查结果。

请开始审查...
"""
                config = {"configurable": {"thread_id": str(uuid.uuid4())}}
                result = await code_reviewer.ainvoke({"messages": [("user", review_input)]}, config)

                output = ""
                if "messages" in result:
                    for msg in reversed(result["messages"]):
                        if msg.type == "ai":
                            output = msg.content
                            break

                # Parse review result
                review_result = self._parse_review_result(output)
                feedback_status = review_result.get("status", "needs_improvement")
                feedback_comments = review_result.get("comments", [])
                feedback_suggestions = review_result.get("suggestions", [])

                yield {"type": "output", "content": "✓ Code Reviewer 完成"}
                yield {"type": "output", "content": f"审查状态: {feedback_status}"}
                if feedback_comments:
                    yield {"type": "output", "content": f"评论: {chr(10).join(feedback_comments)}"}
                if feedback_suggestions:
                    yield {"type": "output", "content": f"建议: {chr(10).join(feedback_suggestions)}"}

                if feedback_status == "approved":
                    yield {"type": "status", "message": "✅ 代码审查通过！"}
                    yield {"type": "answer", "content": f"🎉 多智能体任务完成！共经过 {iteration} 轮迭代。"}

                    # Try to run the application
                    entry_point = self._find_entry_point(files_created)
                    if entry_point:
                        async for event in self._execute_application(entry_point, task):
                            yield event
                    break
                else:
                    if iteration < max_iterations:
                        yield {"type": "status", "message": "⚠️ 需要改进，准备下一轮迭代..."}
                    else:
                        yield {"type": "status", "message": "⚠️ 达到最大迭代次数，停止迭代。"}
                        yield {"type": "answer", "content": f"已完成 {max_iterations} 轮迭代。最终审查状态: {feedback_status}"}
                        break

            except Exception as e:
                yield {"type": "error", "message": f"Code Reviewer 错误: {str(e)}"}
                break

    def _parse_review_result(self, output: str) -> Dict[str, Any]:
        """Parse code review result from LLM output"""
        try:
            # Try to extract JSON block
            json_block = re.search(r"```json\s*([\s\S]*?)\s*```", output)
            if json_block:
                return json.loads(json_block.group(1).strip())

            # Try to find JSON object
            possible_json = re.search(r"\{[\s\S]*\}", output)
            if possible_json:
                return json.loads(possible_json.group(0))
        except Exception:
            pass

        # Fallback parsing
        status = "needs_improvement"
        if "approved" in output.lower() or "通过" in output:
            status = "approved"

        comments = []
        suggestions = []
        lines = output.split("\n")
        section = "comments"

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if "建议" in line or "suggestion" in line.lower():
                section = "suggestions"
                continue
            if "评论" in line or "comment" in line.lower():
                section = "comments"
                continue
            if line.startswith("-") or line.startswith("•") or line[0].isdigit():
                content = line.lstrip("-•0123456789. ").strip()
                if section == "suggestions":
                    suggestions.append(content)
                else:
                    comments.append(content)

        return {
            "status": status,
            "comments": comments if comments else ["审查完成"],
            "suggestions": suggestions
        }

    def _find_entry_point(self, files: List[str]) -> str | None:
        """Find the main entry point file"""
        priority_names = ["main.py", "app.py", "streamlit_app.py", "run.py", "server.py"]
        for name in priority_names:
            if name in files:
                return name

        py_files = [f for f in files if f.endswith(".py")]
        if py_files:
            candidates = [f for f in py_files if "test" not in f]
            if not candidates:
                candidates = py_files
            if len(candidates) == 1:
                return candidates[0]
            return min(candidates, key=len)

        return None

    async def _execute_application(self, entry_point: str, task: str):
        """Execute the created application"""
        try:
            # Install requirements.txt if exists
            try:
                req_content = await self.sandbox.files.read("/home/user/requirements.txt")
                if req_content:
                    yield {"type": "status", "message": "📦 检测到 requirements.txt，正在安装依赖..."}
                    req_cmd = "pip install -r /home/user/requirements.txt"
                    install_result = await self.sandbox.commands.run(req_cmd, timeout=300)
                    if install_result.exit_code != 0:
                        yield {"type": "error", "message": f"依赖安装失败: {install_result.stderr}"}
                    else:
                        yield {"type": "output", "content": "✓ 依赖安装完成"}
            except:
                pass

            full_path = f"/home/user/{entry_point}" if not entry_point.startswith("/") else entry_point

            # Detect app type
            is_streamlit = "streamlit" in entry_point.lower() or "streamlit" in task.lower()
            is_gradio = "gradio" in entry_point.lower() or "gradio" in task.lower() or entry_point == "app.py"

            if is_streamlit:
                yield {"type": "status", "message": "📦 正在安装 Streamlit..."}
                await self.sandbox.commands.run("pip install streamlit -q")
                cmd = f"streamlit run {full_path} --server.address=0.0.0.0 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false"
                port = 8501
                app_type = "Streamlit App"
            elif is_gradio:
                yield {"type": "status", "message": "📦 正在安装 Gradio..."}
                await self.sandbox.commands.run("pip install gradio==3.50.2 -q")
                # Gradio with share=False runs non-blocking
                yield {"type": "status", "message": f"🚀 正在启动 Gradio 应用: {entry_point}"}
                cmd = f"python3 {full_path}"
                port = 7860
                app_type = "Gradio App"
            else:
                cmd = f"python3 {full_path}"
                port = 8000
                app_type = "Web App"

            is_web = is_streamlit or is_gradio or "app.py" in entry_point or "main.py" in entry_point

            if is_web:
                yield {"type": "status", "message": f"启动 {app_type} 服务中..."}
                process = await self.sandbox.commands.run(cmd, background=True)

                # Wait a bit for the service to start
                await asyncio.sleep(5)

                try:
                    host = self.sandbox.get_host(port)
                    url = f"https://{host}"
                    yield {"type": "status", "message": f"🔗 正在暴露服务: {url}"}
                    yield {"type": "file_preview", "path": f"{app_type} (Port {port})", "mime": "url", "content": url}
                except Exception as e:
                    yield {"type": "error", "message": f"无法获取公共链接: {str(e)}"}
            else:
                result = await self.sandbox.commands.run(cmd, timeout=60)
                output = []
                if result.stdout:
                    output.append(f"STDOUT:\n{result.stdout}")
                if result.stderr:
                    output.append(f"STDERR:\n{result.stderr}")
                yield {"type": "output", "content": "\n".join(output) if output else "(无输出)"}

        except Exception as e:
            yield {"type": "error", "message": f"运行失败: {str(e)}"}

if __name__ == "__main__":
    agent = ManusAgent()
    async def main():
        async for msg in agent.run("Print hello"):
            print(msg)
    asyncio.run(main())
