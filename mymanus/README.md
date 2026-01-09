# MyManus

A high-performance Python coding agent powered by **DeepSeek V3** and **E2B Firecracker MicroVMs**.

Manus is designed to be a "Code First" autonomous agent. It solves problems by writing and executing Python code in a secure, stateful sandbox, rather than just generating text.

## 🌟 Features

*   **⚡️ LangChain 1.0 Architecture:** Built on the latest agentic frameworks for robust planning and execution.
*   **🔒 Secure E2B Sandboxing:** Code runs inside isolated Firecracker MicroVMs. Files and variables persist throughout the session.
*   **🧠 DeepSeek V3 Integration:** Leveraging state-of-the-art open models for complex reasoning and coding.
*   **🖥️ Modern Web Console:** A beautiful, responsive UI with:
    *   **Light/Dark Mode** support.
    *   **Real-time Timeline** of the agent's thought process.
    *   **Live Previews** for generated HTML, images, and data visualizations.
    *   **Terminal** for raw log inspection.
*   **🛠️ CLI Mode:** A rich command-line interface for quick tasks.

## 🚀 Prerequisites

1.  **Python 3.12+** (Managed via `uv` is recommended)
2.  **E2B API Key**: Get a free key at [e2b.dev](https://e2b.dev).
3.  **DeepSeek API Key**: Or any OpenAI-compatible provider (e.g., SiliconFlow, Together AI).

## 🛠️ Setup

1.  **Clone the project:**
    ```bash
    git clone <repository-url>
    cd mymanus
    ```

2.  **Configure Environment:**
    Create a `.env` file from the example:
    ```bash
    cp .env.example .env
    ```
    Add your API keys:
    ```ini
    DEEPSEEK_API_KEY=sk-your-key
    DEEPSEEK_BASE_URL=https://api.siliconflow.cn/v1
    MODEL_ID=deepseek-ai/DeepSeek-V3
    E2B_API_KEY=e2b_...
    ```

3.  **Install Dependencies:**
    We recommend using `uv` for fast, reliable package management:
    ```bash
    uv sync
    ```

## 🎮 Usage

### Web Console (Recommended)

Experience the full visual capability of Manus.

1.  Start the backend server:
    ```bash
    uv run server.py
    ```
2.  Open **[http://localhost:8000](http://localhost:8000)** in your browser.
3.  Try a task like:
    > "Analyze the Bitcoin price trend for the last 7 days and plot a chart."

### CLI Mode

For quick interactions in your terminal:

```bash
uv run main.py
```

## 📂 Project Structure

*   `agent.py`: Core logic for `ManusAgent`, handling the LLM loop and MCP tool execution.
*   `sandbox_e2b.py`: An **MCP Server** implementation that bridges the agent to the E2B Firecracker sandbox.
*   `server.py`: FastAPI backend that streams agent events to the frontend.
*   `web/`: The frontend application (single-file HTML/JS).
*   `main.py`: CLI entry point.

## 🛡️ Security Note

Manus executes generated code. While E2B provides strong isolation via Firecracker MicroVMs, always review the agent's plan for critical tasks.

## 📄 License

MIT
