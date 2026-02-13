# NeuralDocs Lab - 高精度文档智能分析与 RAG 系统

这是一个基于 FastAPI 开发的先进文档分析系统，通过多模态大模型（VLM）将原始 PDF/图像转换为结构化的 Markdown，并实现高精度的多轮混合检索增强生成（RAG）。

## 🌟 核心特性

*   **多模态 OCR 转 Markdown**：利用 VLM 进行 1:1 无损识别，完美保留表格、图表描述及布局结构。
*   **高精度视觉溯源**：解析过程保留原子块坐标（Bounding Boxes），检索结果支持在原始页面上高亮显示。
*   **先进 RAG 架构**：
    *   **混合检索**：结合向量搜索（ChromaDB）与关键词搜索（BM25），通过加权融合（RRF）提升召回率。
    *   **查询改写**：基于对话历史自动重写提问，支持高质量的多轮对话。
    *   **重排（Reranking）**：集成 `BAAI/bge-reranker-v2-m3` 对候选文档进行二次精排。
*   **性能深度优化**：
    *   **图像处理**：智能压缩与降采样策略，兼顾识别精度与传输速度。
    *   **并发处理**：多线程并行解析页面，大幅缩短大型文档的处理时间。
    *   **实时反馈**：通过 SSE（Server-Sent Events）实现逐页解析进度的实时推送。
*   **现代 SaaS 交互界面**：
    *   **双视图模式**：支持“可视化坐标框”与“Markdown 源码”快速切换。
    *   **历史管理**：支持历史记录的存储、回放、重建索引及管理。
    *   **推荐问题**：针对领域知识提供一键快捷提问。

## 🏗 系统架构

系统运行分为四个主要阶段：
1.  **摄入（Ingestion）**：使用 `pypdfium2` 进行高分辨率图像渲染。
2.  **认知处理（Cognitive Processing）**：VLM 提取带坐标标签的 Markdown。
3.  **索引构建（Indexing）**：在内存中构建混合索引（Chroma Ephemeral + Rank-BM25）。
4.  **合成回复（Synthesis）**：通过查询改写、召回、重排及上下文注入，生成最终答案。

## 📂 目录结构

```text
ocr/
├── engine/          # 核心 OCR 逻辑与 VLM API 集成
├── utils/           # PDF 处理与图像预处理工具
├── retrieval.py     # 混合检索、重排及 RAG 调度逻辑
├── server.py        # FastAPI 路由、SSE 及生命周期管理
├── web/             # 现代化前端 UI
├── data/            # 运行时数据（上传文件、图片、历史记录）
└── ocrdata/         # 示例测试文档
```

## 🚀 快速开始

### 环境准备
*   Python 3.12+
*   `uv` 包管理器（推荐）

### 安装与运行

1.  **安装依赖**:
    ```bash
    cd ocr
    uv sync
    ```

2.  **配置环境变量**:
    在 `ocr/` 目录下创建 `.env` 文件:
    ```ini
    DEEPSEEK_API_KEY=sk-your-key-here
    DEEPSEEK_BASE_URL=https://api.siliconflow.cn/v1
    OCR_MODEL_ID=deepseek-ai/DeepSeek-OCR
    BASE_MODEL_ID=Pro/zai-org/GLM-4.7
    EMBEDDING_MODEL_ID=BAAI/bge-m3
    ```

3.  **启动服务**:
    ```bash
    uv run server.py
    ```
    访问: `http://localhost:8000`

## 📝 许可证

MIT
