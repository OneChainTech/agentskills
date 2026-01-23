# MyManus 🤖

MyManus 是一个全能型自主编程智能体，深度集成了 **LangGraph** 的循环推理能力与 **E2B Sandboxes** 的安全执行环境。

它不仅能编写和运行 Python 代码，还能像人类一样操作远程 Linux 桌面、浏览网页、分析复杂数据，并即时生成交互式可视化报告（HTML/Plotly/Three.js）。

## 🌟 核心特性

*   **🧠 深度推理 (LangGraph Brain):**
    *   采用 ReAct 循环架构，支持自我反思（Self-Correction）和多步规划。
    *   内置长期记忆（MemorySaver），确保在复杂任务中保持上下文连贯。
*   **🛡️ 双模沙箱 (E2B Firecracker MicroVM):**
    *   **Code Interpreter:** 安全执行 Python 3.12+ 代码、Shell 命令，支持 `pip` 安装任意库。
    *   **Desktop Sandbox:** 内置全功能 Linux 桌面 (X11)，支持启动浏览器 (Firefox/Chrome)、屏幕截图、鼠标键盘自动化控制。
*   **🎨 交互式前端 (Real-time UI):**
    *   **实时可视化:** 自动渲染 Agent 生成的 HTML 文件、图表和数据报告。
    *   **桌面流:** 通过 WebRTC/VNC 实时查看和控制沙箱内的桌面环境。
    *   **SSE 流式响应:** 毫秒级延迟，实时展示 Agent 的思考过程和工具调用。
*   **⚡️ 现代工程化:**
    *   基于 Python 3.12+ 和 `uv` 极速包管理。
    *   FastAPI 异步后端 + Tailwind CSS 现代前端。

## 🏗️ 技术架构

系统采用分层架构设计：

1.  **交互层 (Frontend):** 
    *   基于 HTML5/Tailwind 的 Web 控制台。
    *   负责处理用户输入、文件上传、桌面流渲染及产物预览 (`iframe`)。
2.  **编排层 (Agent Server):** 
    *   FastAPI 服务端，托管 `ManusAgent`。
    *   管理 LangGraph 状态机，分发工具调用，处理 SSE 消息流。
3.  **执行层 (Infrastructure):** 
    *   **E2B Cloud Sandboxes:** 提供隔离的云端微虚拟机。
    *   分离的代码执行环境与图形化桌面环境。

## 📂 项目结构

```text
mymanus/
├── agent.py                 # 🧠 智能体核心 (LangGraph 状态机定义)
├── sandbox_e2b.py           # 🛠️ 工具层 (代码执行, 文件操作, 桌面控制)
├── server.py                # 🌐 后端服务 (FastAPI, SSE, HTTP接口)
├── main.py                  # 💻 CLI 命令行入口
├── project_framework.canvas # 📐 技术架构可视化图 (Obsidian Canvas)
├── web/                     # 🎨 前端静态资源
│   ├── index.html           # 主控制台
│   └── desktop.html         # 桌面流调试视图
├── uploads/                 # 📂 用户上传文件暂存区
└── downloads/               # 📂 智能体生成产物下载区
```

## 🚀 快速开始

### 1. 环境准备
确保已安装 Python 3.12+ 和 `uv` 包管理器。

```bash
# 进入项目目录
cd mymanus

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API Key:
# DEEPSEEK_API_KEY=sk-...
# E2B_API_KEY=e2b_...
```

### 2. 安装依赖
```bash
uv sync
```

### 3. 启动 Web 控制台 (推荐)
启动后端服务并访问浏览器界面：
```bash
uv run server.py
```
👉 访问: `http://localhost:8000`

### 4. 命令行模式 (CLI)
如果你更喜欢终端交互：
```bash
uv run main.py
```

## 🎮 能力展示 (Use Cases)

在 Web 控制台中，你可以尝试以下任务：

*   **📊 深度数据洞察:** "分析上传的 CSV 文件，清洗数据并用 Plotly 绘制交互式旭日图。"
*   **🌐 3D 交互网页:** "用 Three.js 写一个赛博朋克风格的 3D 旋转立方体页面。"
*   **🖥️ 浏览器自动化:** "打开 Firefox 访问 Hacker News，滚动浏览并截图保存。"
*   **🤖 全栈应用开发:** "写一个贪吃蛇游戏，生成 HTML 并直接预览。"

## 🛡️ 安全说明

MyManus 的所有代码均在 E2B 提供的隔离沙箱中运行，不会影响宿主机系统。虽然沙箱是安全的，但请避免在 Prompt 中提供敏感的生产环境凭证（如数据库密码），因为这些文本会被发送给 LLM 提供商。
