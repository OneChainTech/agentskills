# Neural Document Intelligence & RAG System

An advanced document analysis system that transforms raw PDFs/Images into structured Markdown using Multimodal LLMs, enables high-precision Multi-turn Hybrid RAG (Retrieval-Augmented Generation) with Reranking, and provides a visual interactive laboratory interface.

## 🌟 Key Features

*   **Multimodal OCR to Markdown**: Utilizes Vision-Language Models (VLM) to perform 1:1 lossless transcription of documents into Markdown, preserving tables, charts, and layout structures.
*   **Full-Element Visual Grounding**: 
    *   **Table (Red)**: Precise detection of tabular data.
    *   **Figure (Purple)**: Identification of diagrams, flowcharts, and architectural maps.
    *   **Text (Blue)**: Highlighting of key semantic text blocks.
*   **Advanced Multi-turn RAG Architecture**: 
    *   **RAG-Fusion Strategy**: Automatically generates 4 multi-view query variations to broaden search scope and eliminate blind spots.
    *   **Reciprocal Rank Fusion (RRF)**: Merges results from parallel retrievals (Vector + Keyword) using weighted rank fusion for robust candidate selection.
    *   **Stage 1 (Hybrid Retrieval)**: Ensemble search (ChromaDB + BM25) executed in parallel for all query variations.
    *   **Stage 2 (Reranking)**: Employs `BAAI/bge-reranker-v2-m3` to re-order the top 20 fused candidates.
*   **Interactive Neural Lab UI**: A developer-focused web interface for document ingestion, real-time visual telemetry, and contextual Q&A. Includes robust error handling and status feedback.
*   **Memory-First Indexing**: Uses ephemeral in-memory vector stores for fast, session-based document interaction.

## 🏗 System Architecture

The system operates in four main stages:
1.  **Ingestion**: PDF conversion to high-res images using `pypdfium2`.
2.  **Cognitive Processing**: VLM-based OCR extraction (Markdown + Full-element Bounding Boxes).
3.  **Indexing**: Hybrid Dense/Sparse vectorization with Ephemeral ChromaDB.
4.  **Synthesis**: 
    *   **Multi-Query Generation**: LLM-based query expansion (1 Original + 4 Variations).
    *   **RAG-Fusion**: Parallel Hybrid Retrieval followed by Reciprocal Rank Fusion (RRF).
    *   **Reranking**: Cross-Encoder scoring of the best fused candidates.
    *   **Generation**: Context-injected answer generation.

*(See `architecture.canvas` for a visual diagram)*

## 🛠 Tech Stack

*   **Backend**: Python 3.12+, FastAPI
*   **Frontend**: HTML5, TailwindCSS, Lucide Icons
*   **AI/LLM**:
    *   **OCR/VLM**: Qwen3-VL-32B (via SiliconFlow)
    *   **Reasoning/Rewrite**: DeepSeek-V3 / GLM-4.7
    *   **Embeddings**: BAAI/bge-m3
    *   **Reranker**: BAAI/bge-reranker-v2-m3
*   **RAG**: LangChain, ChromaDB (Ephemeral), Rank-BM25
*   **PDF Processing**: `pypdfium2`, `pillow`

## 🚀 Getting Started

### Prerequisites
*   Python 3.12+
*   `uv` package manager (recommended)

### Installation

1.  **Clone and Enter Directory**:
    ```bash
    cd ocr
    ```

2.  **Install Dependencies**:
    ```bash
    uv sync
    ```

3.  **Environment Configuration**:
    Create a `.env` file in the `ocr` directory:
    ```ini
    DEEPSEEK_API_KEY=sk-your-key-here
    DEEPSEEK_BASE_URL=https://api.siliconflow.cn/v1
    OCR_MODEL_ID=Qwen/Qwen3-VL-32B-Instruct
    BASE_MODEL_ID=Pro/zai-org/GLM-4.7
    EMBEDDING_MODEL_ID=BAAI/bge-m3
    ```

### Running the System

Start the FastAPI server:

```bash
uv run server.py
```

Access the **Neural Lab** interface at: `http://localhost:8000`

## 📂 Project Structure

```
ocr/
├── engine/          # Core OCR logic (Support for Table/Figure/Text detection)
├── utils/           # PDF to Image conversion
├── retrieval.py     # Hybrid RAG + Rerank + Query Rewriting implementation
├── server.py        # FastAPI application & endpoints
├── web/             # Frontend UI assets (Chat history state management)
└── data/            # Temporary storage for uploads/images (GitIgnored)
```

## 📝 License

MIT
