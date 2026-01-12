# MyManus

一个由 **DeepSeek V3** 和 **E2B Firecracker MicroVMs** 驱动的高性能 Python 编程智能体。

Manus 旨在成为一个“代码优先”的自主智能体。它通过在安全的、有状态的沙箱中编写和执行 Python 代码来解决问题，而不仅仅是生成文本。

## 🌟 特性

*   **⚡️ LangChain 1.0 架构：** 基于最新的智能体框架构建，具有强大的规划和执行能力。
*   **🔒 安全的 E2B 沙箱：** 代码在隔离的 Firecracker MicroVM 中运行。文件和变量在整个会话期间持久保存。
*   **🧠 DeepSeek V3 集成：** 利用最先进的开源模型进行复杂的推理和编码。
*   **🖥️ 现代 Web 控制台：** 一个美观、响应迅速的 UI，具有：
    *   支持 **亮色/暗色模式**。
    *   智能体思维过程的 **实时时间轴**。
    *   生成的 HTML、图片和数据可视化的 **实时预览**。
    *   用于查看原始日志的 **终端**。
*   **🛠️ CLI 模式：** 用于快速任务的丰富命令行界面。

## 🚀先決条件

1.  **Python 3.12+** (推荐使用 `uv` 管理)
2.  **E2B API Key**: 在 [e2b.dev](https://e2b.dev) 获取免费密钥。
3.  **DeepSeek API Key**: 或任何兼容 OpenAI 的提供商（例如 SiliconFlow, Together AI）。

## 🛠️ 安装与配置

1.  **克隆项目：**
    ```bash
    git clone <repository-url>
    cd mymanus
    ```

2.  **配置环境：**
    从示例创建 `.env` 文件：
    ```bash
    cp .env.example .env
    ```
    添加你的 API 密钥：
    ```ini
    DEEPSEEK_API_KEY=sk-your-key
    DEEPSEEK_BASE_URL=https://api.siliconflow.cn/v1
    MODEL_ID=deepseek-ai/DeepSeek-V3
    E2B_API_KEY=e2b_...
    ```

3.  **安装依赖：**
    我们推荐使用 `uv` 进行快速、可靠的包管理：
    ```bash
    uv sync
    ```

## 🎮 使用方法

### Web 控制台 (推荐)

体验 Manus 的完整可视化功能。

1.  启动后端服务器：
    ```bash
    uv run server.py
    ```
2.  在浏览器中打开 **[http://localhost:8000](http://localhost:8000)**。
3.  尝试一个任务，例如：
    > "分析比特币过去 7 天的价格趋势并绘制图表。"

### CLI 模式

用于终端中的快速交互：

```bash
uv run main.py
```

## 📂 项目结构

*   `agent.py`: `ManusAgent` 的核心逻辑，处理 LLM 循环和 MCP 工具执行。
*   `sandbox_e2b.py`: 一个 **MCP 服务器** 实现，连接智能体和 E2B Firecracker 沙箱。
*   `server.py`: FastAPI 后端，将智能体事件流式传输到前端。
*   `web/`: 前端应用程序（单文件 HTML/JS）。
*   `main.py`: CLI 入口点。

## 🛡️ 安全说明

Manus 会执行生成的代码。虽然 E2B 通过 Firecracker MicroVM 提供了强大的隔离，但对于关键任务，请务必审查智能体的计划。

## 📄 许可证

MIT