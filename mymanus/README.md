# MyManus

一个由 **LLM (DeepSeek / Qwen)** 和 **E2B Firecracker MicroVMs** 驱动的高性能 Python 编程智能体。

Manus 旨在成为一个“代码优先”的自主智能体。它通过在安全的、有状态的沙箱中编写和执行 Python 代码来解决问题，而不仅仅是生成文本。

## 🌟 核心特性

*   **⚡️ LangChain 1.0 架构：** 现代化的智能体架构，具备强大的规划与执行能力。
*   **🔒 安全的 E2B 沙箱：** 代码在隔离的 Firecracker MicroVM 中运行。文件和变量在整个会话期间持久保存，支持复杂的多步任务。
*   **🧠 多模型支持：** 支持 DeepSeek V3、Qwen 2.5/3 等兼容 OpenAI 格式的高级推理模型。
*   **🖥️ 增强型 Web 控制台：**
    *   **可视化工作流：** 实时展示智能体的思考过程、工具调用和执行结果。
    *   **实时预览：** 自动渲染生成的 HTML、图表 (Matplotlib/Plotly) 和数据。
    *   **中文优化：** 针对中文图表显示进行了专门优化，完美支持 Plotly 交互式图表。
    *   **交互体验：** 支持深色模式 (Dark Mode)、执行步骤复制、呼吸灯运行状态提示。
*   **🛠️ CLI 模式：** 专为开发者设计的终端交互界面。

## 🚀 前置要求

1.  **Python 3.12+** (强烈推荐使用 [uv](https://github.com/astral-sh/uv) 进行包管理)
2.  **E2B API Key**: 在 [e2b.dev](https://e2b.dev) 注册获取免费密钥（用于沙箱环境）。
3.  **LLM API Key**: 兼容 OpenAI 格式的提供商（如 SiliconFlow, DeepSeek, Together AI）。

## 🛠️ 安装与配置

1.  **克隆项目：**
    ```bash
    git clone <repository-url>
    cd mymanus
    ```

2.  **配置环境：**
    复制示例配置文件：
    ```bash
    cp .env.example .env
    ```
    编辑 `.env` 文件填入你的密钥：
    ```ini
    DEEPSEEK_API_KEY=sk-your-key
    DEEPSEEK_BASE_URL=https://api.siliconflow.cn/v1
    # 推荐使用 DeepSeek V3 或 Qwen 2.5 Coder
    MODEL_ID=Qwen/Qwen2.5-Coder-32B-Instruct
    E2B_API_KEY=e2b_...
    ```

3.  **安装依赖：**
    使用 `uv` 快速同步依赖：
    ```bash
    uv sync
    ```

## 🎮 使用指南

### 1. Web 控制台 (推荐)

体验完整的可视化交互功能。

启动服务：
```bash
uv run server.py
```
> 💡 提示：服务启动后，浏览器访问 **[http://localhost:8000](http://localhost:8000)**

**特色功能：**
*   **文件上传：** 直接将 CSV/Excel/PDF 拖入输入框，智能体可直接读取并分析。
*   **全流程数据分析：** 点击 "Quick Start" 中的数据分析任务，体验从清洗、分析到生成 HTML 图表报告的全自动化流程。
*   **中文图表支持：** 智能体已配置为优先使用 Plotly 或下载中文字体，确保生成的图表不出现乱码。

### 2. CLI 命令行模式

适合快速测试或无头环境运行。

启动 CLI：
```bash
uv run main.py
```

## 📂 项目结构

*   `agent.py`: `ManusAgent` 核心类。处理 LLM 交互循环、工具调度、Prompt 工程及上下文管理。
*   `sandbox_e2b.py`: **MCP Server** 实现。负责连接 E2B 沙箱，提供 `run_code`, `run_shell`, `upload_file` 等原子工具。
*   `server.py`: FastAPI 后端服务。处理 HTTP 请求，管理 WebSocket/SSE 流式输出。
*   `web/`: 前端单页应用 (SPA)。基于 HTML5 + Tailwind CSS + Vanilla JS 构建，轻量且高性能。
*   `uploads/`: 临时存储用户上传文件的目录。

## 🛡️ 安全说明

MyManus 具备执行任意代码的能力。
*   **隔离性：** 所有代码均在 E2B 的 Firecracker MicroVM 中运行，与宿主机完全隔离，确保安全。
*   **人工监督：** 虽然沙箱是安全的，但建议在处理敏感数据时保持关注。

## 📄 许可证

MIT License