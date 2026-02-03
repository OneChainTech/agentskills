# MyManus 🤖

MyManus 是一个全能型自主编程智能体，深度集成了 **LangGraph** 的循环推理能力与 **多沙箱支持**（E2B / OpenSandbox）的安全执行环境。

它不仅能编写和运行 Python 代码，还能像人类一样操作远程 Linux 桌面、浏览网页、分析复杂数据，并即时生成交互式可视化报告（HTML/Plotly/Three.js）。

## 🌟 核心特性

*   **🧠 深度推理 (LangGraph Brain):**
    *   采用 ReAct 循环架构，支持自我反思（Self-Correction）和多步规划。
    *   内置长期记忆（MemorySaver），确保在复杂任务中保持上下文连贯。
    *   **Human-in-the-Loop (HITL):** 在执行关键操作（如代码运行、Shell 命令）前自动暂停，请求用户确认，确保安全可控。
*   **🛡️ 多沙箱支持 (Multi-Sandbox):**
    *   **E2B Code Interpreter**: 云端 Firecracker MicroVM 隔离环境（需 API Key）。
    *   **OpenSandbox**: 本地 Docker 部署的开源沙箱方案（免费，推荐开发使用）。
*   **🎨 交互式前端 (Real-time UI):**
    *   **实时可视化:** 自动渲染 Agent 生成的 HTML 文件、图表和数据报告。
    *   **SSE 流式响应:** 毫秒级延迟，实时展示 Agent 的思考过程和工具调用。
    *   **Security Check:** 现代化的确认交互界面，提供代码预览和执行审批功能。
*   **⚡️ 现代工程化:**
    *   基于 Python 3.12+ 和 `uv` 极速包管理。
    *   FastAPI 异步后端 + Tailwind CSS 现代前端。

## 🏗️ 技术架构与核心组件

系统基于 **Python 3.12** 构建，采用 **DeepAgents** 多智能体框架，结合 **LangGraph** 状态管理和多沙箱支持。

### 1. 交互层 (Client Layer)
*   **Web Console (`web/index.html`)**: 基于 Tailwind CSS 的现代前端，支持 SSE 流式接收、HTML 产物渲染 (`iframe`) 和 **HITL 确认交互**。
*   **CLI (`main.py`)**: 基于 `Rich` 库的终端交互界面。

### 2. 服务层 (Server Layer) - Python 3.12
*   **FastAPI Backend (`server.py`)**:
    *   `POST /api/run`: 接收任务请求（支持 `thread_id` 以恢复会话）。
    *   `POST /api/upload`: 处理文件上传。
    *   `event_generator()`: SSE 消息流生成器。
*   **Manus Agent (`agent.py`)**:
    *   **Framework**: 基于 **DeepAgents** 框架构建的多智能体系统。
    *   **Main Agent**: 负责意图识别、任务拆分和路由。
    *   **Subagents**:
        *   **CodeWriter**: 专注于代码编写和文件创建。
        *   **CodeReviewer**: 专注于代码审查、安全检查和质量保证。
    *   **LangGraph Core**: 负责状态管理、记忆 (MemorySaver) 和事件流分发。
    *   **HumanInTheLoopMiddleware**: 拦截关键操作（如 `visualize_file`），触发人工确认。

### 3. 沙箱适配层 (Sandbox Adapter Layer)
*   **统一接口 (`sandbox_interface.py`)**: 定义 `BaseSandbox` 抽象基类。
*   **E2B 适配器 (`sandbox_adapter_e2b.py`)**: 适配 E2B Code Interpreter API。
*   **OpenSandbox 适配器 (`sandbox_adapter_opensandbox.py`)**: 适配 OpenSandbox API。
*   **工具集 (`tools.py`)**: 提供统一的工具接口（run_code, run_shell_command, visualize_file 等）。

### 4. 基础设施 (Infrastructure)
*   **E2B Cloud Sandboxes**:
    *   基于 **Firecracker MicroVM** 的隔离环境。
    *   预装 Python 3.12+, Node.js, pip 等常用工具。
*   **OpenSandbox**:
    *   基于 **Docker** 的本地沙箱环境。
    *   支持 Code Interpreter 功能，完全免费。

## 📂 项目结构

```text
mymanus/
├── agent.py                      # 🧠 智能体核心 (DeepAgents, LangGraph, Subagents)
├── sandbox_interface.py          # 🛡️ 沙箱抽象接口 (BaseSandbox)
├── sandbox_adapter_e2b.py        # 🔌 E2B 沙箱适配器
├── sandbox_adapter_opensandbox.py # 🔌 OpenSandbox 沙箱适配器
├── tools.py                      # 🛠️ 工具集 (run_code, visualize_file 等)
├── server.py                     # 🌐 后端服务 (FastAPI, 核心方法: lifespan, run_task)
├── main.py                       # 💻 CLI 入口
├── start-opensandbox.sh          # 🚀 OpenSandbox 启动脚本
├── architecture.canvas           # 📐 技术架构可视化图 (JSON Canvas)
├── web/                          # 🎨 前端资源 (Tailwind CSS, SSE, HITL UI)
└── downloads/                    # 📂 产物下载区
```

## 🚀 快速开始

### 1. 环境准备
确保已安装 Python 3.12+ 和 `uv` 包管理器。

```bash
# 进入项目目录
cd mymanus

# 配置环境变量
cp .env.example .env
```

### 2. 选择沙箱提供商

MyManus 支持两种沙箱：

#### 选项 A: OpenSandbox（推荐，免费，本地部署）

1. **启动 OpenSandbox 服务**（需要 Docker）:
```bash
# 方式 1: 使用启动脚本
./start-opensandbox.sh

# 方式 2: 手动启动
cd ../OpenSandbox/server
uv run python -m src.main
```

2. **配置 `.env`**:
```bash
# 使用 OpenSandbox
SANDBOX_PROVIDER=opensandbox
OPEN_SANDBOX_DOMAIN=127.0.0.1:8082
OPEN_SANDBOX_API_KEY=
```

#### 选项 B: E2B Cloud（付费，云端托管）

1. **获取 API Key**: 访问 [e2b.dev](https://e2b.dev) 注册并获取 API Key。

2. **配置 `.env`**:
```bash
# 使用 E2B
SANDBOX_PROVIDER=e2b
E2B_API_KEY=your_e2b_api_key_here
```

### 3. 安装依赖
```bash
uv sync
```

### 4. 启动
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

### 任务 1: 深度数据洞察
```
生成一份包含 [日期, 地区, 产品类别, 销售额, 利润] 的模拟电商数据（100条），使用 Plotly 绘制一个交互式的柱状图展示各地区销售占比，并保存为 HTML 报告。
```
**展示能力:**
- 🐍 Python 代码执行 (pandas, plotly)
- 📦 自动依赖安装 (pip install)
- 🎨 HTML 可视化生成与自动预览

### 任务 2: 智能文件分析
```
请读取我上传的数据文件，分析数据的基本统计信息（行数、列名、缺失值），并针对数值列绘制分布直方图。最后遵循 UI/UX Pro Max 规范生成一份专业的 HTML 可视化报告。
```
**展示能力:**
- 📂 本地文件上传与处理
- 📊 数据清洗与多维度分析
- 🎨 UI/UX Pro Max 现代化设计规范

### 任务 3: 沙箱工具 SDK 综合演示
```
展示沙箱工具 SDK 的综合使用：1) write_file 创建脚本；2) run_code 执行生成数据；3) list_files 查看文件；4) visualize_file 可视化；5) download_file_to_host 下载到本地。
```
**展示能力:**
- 🛠️ 完整的沙箱文件系统操作
- 💾 自动化产物持久化
- 📥 跨沙箱边界的文件下载

### 任务 4: 多智能体协作 (Multi-Agent)
```
使用多智能体模式：创建一个 Streamlit Hello World 应用。要求：包含文本输入框，输入名字后显示 'Hello, {名字}!'。
```
**展示能力:**
- 🤝 **CodeWriter + CodeReviewer** 自动迭代协作
- 🌐 Web 服务动态托管与端口转发
- 🛡️ 复杂工程任务的质量保证

### 核心特性演示: Human-in-the-Loop (HITL) ✅
**展示能力:**
- 🤝 **代码执行确认:** Agent 在执行 `run_code` 或 `run_shell_command` 前会自动暂停。
- 🔄 **可视化审批 UI:** 前端弹出 "Security Check" 卡片，展示待执行代码。
- 🛡️ **安全可控:** 用户批准后，Agent 继续执行；拒绝则终止任务。

## 🛡️ 安全说明

MyManus 的所有代码均在隔离沙箱中运行，不会影响宿主机系统：
- **E2B**: 基于 Firecracker MicroVM 的强隔离环境
- **OpenSandbox**: 基于 Docker 的容器隔离环境

Human-in-the-Loop 机制进一步增强了安全性，防止意外的命令执行。

## 🔧 OpenSandbox 本地部署指南

OpenSandbox 是阿里巴巴开源的沙箱项目，提供完整的本地部署方案。

### 前置要求
- Docker Desktop (macOS/Windows) 或 Docker Engine (Linux)
- Python 3.10+

### 启动步骤
1. **启动服务**:
   ```bash
   ./start-opensandbox.sh
   ```

2. **验证服务**:
   ```bash
   curl http://127.0.0.1:8082/health
   # 应返回: {"status":"healthy"}
   ```

### 常见问题
- **端口冲突**: 修改 `~/.sandbox.toml` 中的 `port` 配置
- **Docker 未运行**: 启动 Docker Desktop
- **镜像拉取失败**: 配置 Docker 镜像加速器

更多信息请参考: [OpenSandbox GitHub](https://github.com/alibaba/OpenSandbox)