# NeuralDocs Lab - 高精度文档智能分析与 RAG 系统

NeuralDocs Lab 是一个基于 FastAPI 开发的先进文档分析系统。它利用多模态大模型（VLM）将原始 PDF 或图像转换为结构化的 **Grounded Markdown**（带坐标标签的 Markdown），并实现了结合向量检索与关键词检索的高精度多轮 RAG 系统。

## 🌟 核心特性

*   **多模态 Grounded OCR**：
    *   利用 VLM（如 DeepSeek-OCR）进行全要素识别。
    *   **1:1 结构还原**：完美保留表格（Markdown 格式）、标题层级、图片描述。
    *   **高精度视觉溯源**：解析过程保留原子块坐标（Bounding Boxes），检索结果可在原始页面上高亮显示。
*   **先进 RAG 架构**：
    *   **混合检索（Hybrid Search）**：集成 `zvec` 向量数据库（Zvec）与 `Rank-BM25` 关键词搜索。
    *   **融合排序（RRF）**：通过 Reciprocal Rank Fusion 算法合并向量与文本检索结果。
    *   **多轮查询改写**：基于对话历史自动重写提问，解决指代不明问题，支持高质量长对话。
    *   **精排（Reranking）**：集成 `BAAI/bge-reranker-v2-m3` 对候选文档进行二次精排，显著提升准确率。
*   **性能深度优化**：
    *   **图像处理**：智能压缩、降采样与 JPEG 优化策略，平衡识别精度与 API 传输速度。
    *   **并发流水线**：多线程并行解析页面，对失败页面提供串行补偿重试机制。
    *   **实时反馈**：通过 SSE（Server-Sent Events）实现逐页解析进度的毫秒级推送。
*   **现代 SaaS 交互界面**：
    *   **双视图模式**：支持“可视化坐标框”与“Markdown 源码”快速切换。
    *   **交互式溯源**：点击回答来源，自动定位并高亮原始 PDF 对应位置。
    *   **历史管理**：完整的会话持久化方案，支持历史记录的加载、重建索引及管理。

## 🏗 系统架构

系统运行分为四个核心阶段：
1.  **摄入（Ingestion）**：使用 `pypdfium2` 进行高清图像渲染（默认 3x 缩放）。
2.  **认知解析（Cognitive Processing）**：VLM 提取带坐标对 `<|ref|>...<|det|>[[x1,y1,x2,y2]]` 的 Markdown。
3.  **混合索引（Indexing）**：基于 `zvec` 构建本地向量索引，同时维护 `BM25` 倒排表。
4.  **合成回复（Synthesis）**：通过查询改写、Ensemble 召回、RRF 融合、Rerank 精排及上下文注入生成最终答案。

## 📂 目录结构

```text
ocr/
├── engine/          # 核心 OCR 逻辑，集成 VLM API 与坐标提取正则表达式
├── utils/           # PDF 渲染（pypdfium2）与图像预处理工具
├── retrieval.py     # 混合检索调度、RRF 算法、SiliconFlow 重排集成
├── server.py        # FastAPI 路由、SSE 事件流、任务状态与历史记录管理
├── web/             # 基于 TailwindCSS 的现代化前端 UI
├── data/            # 运行时持久化数据
│   ├── uploads/     # 原始上传文件
│   ├── images/      # 渲染的逐页图片
│   ├── history/     # 会话 JSON 记录
│   └── zvec/        # Zvec 向量数据库文件
└── ocrdata/         # 示例测试文档与数据
```

## 🛠 技术栈

*   **后端**：FastAPI, LangChain, httpx, Tenacity (重试机制)
*   **OCR/VLM**：DeepSeek-OCR / Qwen-VL (通过 SiliconFlow API)
*   **向量库**：zvec (高性能本地向量存储)
*   **检索**：Rank-BM25, BGE-M3 (Embedding), BGE-Reranker (精排)
*   **前端**：TailwindCSS, Lucide Icons, Vanilla JS (SSE 实现)
*   **环境**：Python 3.12+, `uv` 包管理器

## 🚀 快速开始

### 环境准备
*   安装 [uv](https://github.com/astral-sh/uv)

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
