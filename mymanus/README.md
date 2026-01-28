# MyManus 🤖

MyManus 是一个全能型自主编程智能体，深度集成了 **LangGraph** 的循环推理能力与 **E2B Sandboxes** 的安全执行环境。

它不仅能编写和运行 Python 代码，还能像人类一样操作远程 Linux 桌面、浏览网页、分析复杂数据，并即时生成交互式可视化报告（HTML/Plotly/Three.js）。

## 🌟 核心特性

*   **🧠 深度推理 (LangGraph Brain):**
    *   采用 ReAct 循环架构，支持自我反思（Self-Correction）和多步规划。
    *   内置长期记忆（MemorySaver），确保在复杂任务中保持上下文连贯。
    *   **Human-in-the-Loop (HITL):** 在执行关键操作（如代码运行、Shell 命令）前自动暂停，请求用户确认，确保安全可控。
*   **🛡️ 安全沙箱 (E2B Code Interpreter):**
    *   **Code Interpreter:** 安全执行 Python 3.12+ 代码、Shell 命令，支持 `pip` 安装任意库。
*   **🎨 交互式前端 (Real-time UI):**
    *   **实时可视化:** 自动渲染 Agent 生成的 HTML 文件、图表和数据报告。
    *   **SSE 流式响应:** 毫秒级延迟，实时展示 Agent 的思考过程和工具调用。
    *   **Security Check:** 现代化的确认交互界面，提供代码预览和执行审批功能。
*   **⚡️ 现代工程化:**
    *   基于 Python 3.12+ 和 `uv` 极速包管理。
    *   FastAPI 异步后端 + Tailwind CSS 现代前端。

## 🏗️ 技术架构与核心组件

系统基于 **Python 3.12** 构建，采用分层微服务架构：

### 1. 交互层 (Client Layer)
*   **Web Console (`web/index.html`)**: 基于 Tailwind CSS 的现代前端，支持 SSE 流式接收、HTML 产物渲染 (`iframe`) 和 **HITL 确认交互**。
*   **CLI (`main.py`)**: 基于 `Rich` 库的终端交互界面。

### 2. 服务层 (Server Layer) - Python 3.12
*   **FastAPI Backend (`server.py`)**:
    *   `POST /api/run`: 接收任务请求（支持 `thread_id` 以恢复会话）。
    *   `POST /api/upload`: 处理文件上传。
    *   `event_generator()`: SSE 消息流生成器。
*   **Manus Agent (`agent.py`)**:
    *   **Core**: 集成 `LangGraph` (`create_agent`) 和 `LangChain` (`ChatOpenAI`)。
    *   `run(task, thread_id)`: 异步生成器，驱动 ReAct 循环，支持 **中断与恢复**。
    *   `HumanInTheLoopMiddleware`: 拦截关键工具调用，触发人工确认。
    *   `MemorySaver`: 状态持久化。

### 3. 工具层 (Tool Layer) - `sandbox_e2b.py`
*   **Code Execution**: `run_code` (Python), `run_shell_command` (Bash).
*   **File Ops**: `read_file`, `write_file`, `upload_local_file`, `download_file_to_host`.
*   **Visualization**: `visualize_file` (静态托管), `get_public_url` (动态端口转发).

### 4. 基础设施 (Infrastructure)
*   **E2B Cloud Sandboxes**:
    *   基于 **Firecracker MicroVM** 的隔离环境。
    *   预装 Python 3.12+, Node.js, pip 等常用工具。

## 📂 项目结构

```text
mymanus/
├── agent.py                 # 🧠 智能体核心 (LangGraph, 核心方法: run, create_agent, HITL)
├── sandbox_e2b.py           # 🛠️ 工具集 (核心方法: run_code, visualize_file)
├── server.py                # 🌐 后端服务 (FastAPI, 核心方法: lifespan, run_task)
├── main.py                  # 💻 CLI 入口
├── project_framework.canvas # 📐 技术架构可视化图 (Obsidian Canvas)
├── web/                     # 🎨 前端资源 (Tailwind CSS, SSE, HITL UI)
└── downloads/               # 📂 产物下载区
```

## 🚀 快速开始

### 1. 环境准备
确保已安装 Python 3.12+ 和 `uv` 包管理器。

```bash
# 进入项目目录
cd mymanus

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Key (DEEPSEEK_API_KEY, E2B_API_KEY)
```

### 2. 安装依赖
```bash
uv sync
```

### 3. 启动
**Web 模式 (推荐):**
```bash
uv run server.py
# 访问: http://localhost:8000
```

**CLI 模式:**
```bash
uv run main.py
```

## 💡 示例任务

以下是一些展示 MyManus 核心能力的示例任务，你可以直接在 Web Console 或 CLI 中尝试：

### 任务 1: 数据分析与可视化
```
分析 iris 数据集，生成一个包含散点图和统计摘要的交互式 HTML 报告
```
**展示能力:**
- 🐍 Python 代码执行 (pandas, plotly)
- 📦 自动依赖安装 (pip install)
- 🎨 HTML 可视化生成
- 🖼️ 自动触发前端预览

### 任务 2: Web 应用快速原型
```
创建一个 Gradio 应用，实现图片风格迁移功能，使用预训练模型
```
**展示能力:**
- 🌐 Web 服务托管 (Gradio 3.50.2)
- 🔌 动态端口转发 (get_public_url)
- 🛡️ 沙箱隔离环境
- 🔄 端口冲突自动处理

### 任务 3: 数据爬取与报告生成
```
爬取 GitHub Trending 页面，提取前 10 个项目信息，生成 Bento Grid 风格的 HTML 报告
```
**展示能力:**
- 🕷️ Shell 命令执行 (curl, wget)
- 🧠 多步骤规划与执行
- 🎨 UI/UX Pro Max 设计规范
- 📄 文件下载到宿主机

### 任务 4: 交互式数据探索 (Human-in-the-Loop) ✅
```
执行任意需要代码运行的任务
```
**展示能力:**
- 🤝 **代码执行确认:** Agent 在执行 `run_code` 或 `run_shell_command` 前会自动暂停。
- 🔄 **可视化审批 UI:** 前端弹出 "Security Check" 卡片，展示待执行代码。
- 🛡️ **安全可控:** 用户批准后，Agent 继续执行；拒绝则终止任务。

## 🛡️ 安全说明

MyManus 的所有代码均在 E2B 提供的隔离沙箱中运行，不会影响宿主机系统。Human-in-the-Loop 机制进一步增强了安全性，防止意外的命令执行。