# RAG Knowledge Base Application

A full-stack RAG (Retrieval-Augmented Generation) application featuring a modern Web UI, a FastAPI backend, and a robust hybrid search engine powered by SiliconFlow's LLM and embedding APIs.

## 🌟 Features

*   **Hybrid Search**: Combines semantic vector search (FAISS + BAAI/bge-m3) with keyword search (BM25) for high-recall retrieval.
*   **Intelligent Reranking**: Uses Cross-Encoder (BAAI/bge-reranker-v2-m3) to re-score and filter results for maximum relevance.
*   **Modern Web UI**: Clean, responsive interface for file uploads and chat interactions.
*   **File Ingestion**: Supports drag-and-drop upload for `.txt`, `.md`, and `.csv` files.
*   **High-Performance Backend**: Built with FastAPI and LangChain.

## 🏗 Architecture

The system is composed of three main layers:

1.  **Frontend (Web UI)**:
    *   Single-page application (HTML/Tailwind/JS).
    *   Handles file uploads and chat interface.
    *   Communicates with backend via REST API.

2.  **API Layer (FastAPI)**:
    *   `POST /upload`: Ingests documents into the knowledge base.
    *   `POST /chat`: Processes user queries and returns generated answers.
    *   Serves static web assets.

3.  **RAG Engine (LangChain)**:
    *   **Ingestion**: Embeds text using `BAAI/bge-m3` and indexes into FAISS and BM25.
    *   **Retrieval**: EnsembleRetriever (Vector + Keyword).
    *   **Reranking**: `SiliconFlowReranker` custom component.
    *   **Generation**: `Qwen-Coder-30B` via SiliconFlow API.

## 🚀 Getting Started

### Prerequisites

*   Python 3.11+
*   `uv` package manager

### Installation

1.  **Navigate to the project**:
    ```bash
    cd rag
    ```

2.  **Install Dependencies**:
    ```bash
    uv sync
    ```

3.  **Configure Environment**:
    Ensure your `.env` file contains valid SiliconFlow credentials:
    ```ini
    DEEPSEEK_API_KEY=your_key_here
    DEEPSEEK_BASE_URL=https://api.siliconflow.cn/v1
    MODEL_ID=Qwen/Qwen3-Coder-30B-A3B-Instruct
    ```

### Running the Application

Start the backend server (which also serves the frontend):

```bash
uv run server.py
```

The server will start at `http://0.0.0.0:8000`.

### Using the App

1.  Open your browser and go to:
    👉 **http://localhost:8000/web/index.html**

2.  **Upload Documents**: Drag and drop text files into the sidebar.
3.  **Chat**: Ask questions about the uploaded content in the main chat window.

## 📂 Project Structure

```
rag/
├── .env                 # Configuration
├── pyproject.toml       # Dependencies
├── architecture.canvas  # Visual architecture diagram
├── rag_engine.py        # Core RAG logic (Service Class)
├── server.py            # FastAPI backend application
├── verify_rag.py        # Standalone verification script
└── web/                 # Frontend assets
    ├── index.html
    └── app.js
```