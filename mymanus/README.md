# MyManus

一个由 **LangChain deepagents** 和 **E2B Firecracker MicroVMs** 驱动的高性能自动编程智能体。

MyManus 致力于成为一个“深度思考”的编程助手。它不仅能编写代码，还能在安全的、有状态的沙箱环境中执行代码、分析结果并根据反馈自我迭代。

## 🌟 核心特性

*   **🧠 Deep Agents 架构：** 采用了最新的 `deepagents` 库，提供比标准 ReAct 更深度的推理链条和任务规划能力。
*   **⚡️ LangGraph 1.0 驱动：** 核心编排基于状态机，确保长任务执行的稳定性和可观测性。
*   **🔒 安全的 E2B 沙箱：** 所有的 Python 代码和 Shell 命令都在隔离的 Firecracker VM 中运行，保护宿主机安全。
*   **🎨 UI/UX Pro Max 设计：** 生成的 HTML 报告采用“瑞士现代主义 2.0”风格，内置专业排版、交互式 Plotly 图表和现代审美。
*   **🖥️ 极简可视化控制台：**
    *   **自动展示：** 智能体生成任何可视化文件后，无需显式指令即可自动启动静态服务并预览。
    *   **步骤摘要：** 自动过滤流式输出噪音，仅展示关键动作标题和执行结果。
    *   **文件直传：** 输入框下方集成便捷的文件上传按钮，支持直接分析本地数据集。

## 🚀 前置要求

1.  **Python 3.12+** (推荐使用 `uv`)
2.  **E2B API Key**: [e2b.dev](https://e2b.dev)
3.  **LLM API Key**: 支持 OpenAI 兼容接口的供应商（如 SiliconFlow, DeepSeek）。

## 🛠️ 安装与配置

1.  **准备环境：**
    ```bash
    git clone <repository-url>
    cd mymanus
    cp .env.example .env
    ```
2.  **安装依赖：**
    ```bash
    uv sync
    ```

## 🎮 使用指南

### Web 控制台
```bash
uv run server.py
```
访问 `http://localhost:8000`。您可以直接点击 **Quick Start** 示例任务，或上传自己的数据文件。

### CLI 模式
```bash
uv run main.py
```

## 📂 项目结构

*   `agent.py`: 基于 `deepagents` 的智能体逻辑，注入了专业 UI 模板。
*   `sandbox_e2b.py`: 原生 E2B 工具集，采用 URL 模式确保复杂应用的预览。
*   `server.py`: FastAPI 后端，处理 SSE 流和文件上传。
*   `architecture.canvas`: 可视化架构图。

## 🛡️ 安全说明

MyManus 具备在沙箱中执行任意代码的能力。虽然 E2B 提供了极高的隔离性，但仍建议您在运行任务时对智能体的行为保持关注。
