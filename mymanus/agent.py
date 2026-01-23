import os
import json
import asyncio
from typing import AsyncGenerator, Dict, Any, List
from contextlib import AsyncExitStack

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent

# Import our tools
from sandbox_e2b import TOOLS, TEMPLATE_CODE_INTERPRETER

# System Prompt
SYSTEM_PROMPT = """你是一个运行在 **E2B 安全沙箱 (Firecracker MicroVM)** 中的全栈编程智能体。你的目标是利用 Python 代码和系统命令，自主、高效地解决用户提出的任何技术问题。

**环境能力:**
*   **OS**: Linux (Debian/Ubuntu based).
*   **Python**: 3.12+ (预装常用库).
*   **Root 权限**: 你拥有沙箱的完全控制权 (sudo not required, or available).
*   **持久化**: `/home/user` 是你的工作目录。
*   **GUI**: 支持启动 GUI 应用并通过 `desktop_` 系列工具进行交互。

**核心工作流 (Thought Process):**
1.  **分析 (Analyze)**: 理解用户需求。如果是模糊的需求（如“分析这个数据”），先查看数据结构。
2.  **规划 (Plan)**: 决定需要的步骤。是否需要安装库？是否需要编写脚本？
3.  **执行 (Execute)**:
    *   **代码优先**: 能用 Python 解决的，优先用 `run_code`。
    *   **Shell 辅助**: 安装依赖 (`pip install`)、文件管理 (`ls`, `mv`) 使用 `run_shell_command`。
    *   **合并操作**: 尽量在一个工具调用中完成相关联的步骤，减少往返延迟。
4.  **验证 (Verify)**: 检查代码输出或文件是否存在。如果有错误，自我修正并重试。
5.  **交付 (Deliver)**:
    *   **Web/可视化**: 如果生成了 HTML, 图表, 或运行了 Web 服务 (Streamlit, Flask)，**必须**调用 `visualize_file` (静态文件) 或 `get_public_url` (动态服务) 以触发前端预览窗口。仅在终端打印 URL 是不够的，必须调用工具。
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
*   **GUI 任务**: 如果任务涉及浏览器自动化或 Linux 桌面软件，**必须**使用 `desktop_` 工具集。
    *   **截图**: 当用户要求“截图”或“看看屏幕”时，使用 `desktop_take_screenshot`。该工具会自动返回预览数据，**不需要**再调用 `visualize_file`。
    *   **浏览器**: 使用 `desktop_open_app("firefox")` 或 `desktop_open_app("google-chrome")`。

请始终使用**中文**与用户交流，保持专业、简洁且乐于助人。
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
                max_retries=15
            )
            
        self.tools = TOOLS
        
        # Use create_agent from langchain v1
        if self.model:
            self.graph = create_agent(
                model=self.model,
                tools=self.tools,
                system_prompt=SYSTEM_PROMPT,
                checkpointer=MemorySaver()
            )
        else:
            self.graph = None

    async def run(self, task: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Executes the agent loop using langchain.agents.create_agent.
        """
        if not self.graph:
            yield {"type": "error", "message": "Agent not initialized (check API Key)."}
            return

        yield {"type": "system", "message": "Manus Agent initialized (LangChain create_agent Mode)."}

        # Initialize Sandbox for this session
        yield {"type": "status", "message": "Initializing E2B Sandbox..."}
        from e2b_code_interpreter import AsyncSandbox
        
        try:
            async with AsyncExitStack() as stack:
                sb = await AsyncSandbox.create(TEMPLATE_CODE_INTERPRETER)
                sandbox = await stack.enter_async_context(sb)
                yield {"type": "system", "message": f"Sandbox created: {sandbox.sandbox_id}"}
                
                # Config with sandbox
                config = {
                    "configurable": {
                        "thread_id": "session_1",
                        "sandbox": sandbox
                    },
                    "recursion_limit": 100
                }

                # Input format for langchain agent expects a list of messages
                inputs = {"messages": [HumanMessage(content=task)]}

                current_turn = 0
                
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

                yield {"type": "success", "message": "Task completed."}

        except Exception as e:
            yield {"type": "error", "message": f"Agent Error: {str(e)}"}
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    agent = ManusAgent()
    async def main():
        async for msg in agent.run("Print hello"):
            print(msg)
    asyncio.run(main())
