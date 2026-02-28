# NeuralDocs Lab - 高精度文档智能分析与 RAG 系统

NeuralDocs Lab 是一个基于 FastAPI 开发的先进文档分析系统。它利用多模态大模型（VLM）将原始 PDF 或图像转换为结构化的 **Grounded Markdown**（带坐标标签的 Markdown），并实现了基于 **Zvec 原生 Dense+Sparse** 双向量引擎的高精度多轮 RAG 系统。

## 🌟 核心特性

*   **多模态 Grounded OCR**：
    *   利用 VLM（如 DeepSeek-OCR）进行全要素识别。
    *   **1:1 结构还原**：完美保留表格（Markdown 格式）、标题层级、图片描述。
    *   **高精度视觉溯源**：解析过程保留原子块坐标（Bounding Boxes），检索结果可在原始页面上高亮显示。
*   **先进 RAG 架构**：
    *   **原生混合检索（Hybrid Search）**：基于 `zvec` 原生 Dense + Sparse 双向量字段，单次查询完成语义与关键词召回。
    *   **加权融合（Weighted Rerank）**：使用 Zvec 内建重排器按维度权重（默认 0.6:0.4）合并双路结果。
    *   **多轮查询改写**：基于对话历史自动重写提问，解决指代不明问题，支持高质量长对话。
    *   **深度精排（Reranking）**：集成 `BAAI/bge-reranker-v2-m3` 对候选文档进行二次精排，显著提升 Top-1 准确率。
*   **性能深度优化**：
    *   **智能图像处理**：自适应压缩、降采样与 JPEG 优化策略，兼顾识别精度与 API 传输速度。
    *   **异步并发流水线**：多线程并行解析页面，内置串行补偿重试机制应对网络波动。
    *   **实时进度反馈**：通过 SSE（Server-Sent Events）实现解析状态的毫秒级推送。
*   **现代化 SaaS 交互界面**：
    *   **双视图模式**：支持“可视化坐标框”与“Markdown 源码”快速切换。
    *   **交互式溯源**：点击回答来源，系统自动定位并高亮原始页面对应位置。
    *   **全生命周期历史管理**：支持历史会话的持久化存储、一键回放及索引重建。

## 🏗 系统架构

系统运行分为四个核心阶段：
1.  **摄入（Ingestion）**：使用 `pypdfium2` 进行高清图像渲染（默认 3x 缩放）。
2.  **认知解析（Cognitive Processing）**：VLM 提取带坐标对 `<|ref|>...<|det|>[[x1,y1,x2,y2]]` 的 Markdown 片段。
3.  **混合索引（Indexing）**：基于 `zvec` 构建 Dense (Dense Vector) + Sparse (Sparse Vector) 结构的本地向量数据库。
4.  **合成回复（Synthesis）**：执行查询改写 -> Zvec 混合召回 -> BGE 精排 -> 上下文注入生成。

## 📂 目录结构

```text
ocr/
├── engine/          # 核心 OCR 逻辑，集成 VLM API 与正则表达式解析
├── utils/           # PDF 渲染（pypdfium2）与图像预处理工具
├── retrieval.py     # Zvec Dense+Sparse 混合检索调度与二次重排逻辑
├── server.py        # FastAPI 路由、SSE 事件流及任务状态管理
├── web/             # 基于 TailwindCSS 的现代化响应式前端 UI
├── data/            # 运行时持久化数据
│   ├── uploads/     # 原始上传文件
│   ├── images/      # 渲染的逐页 PNG 图片
│   ├── history/     # 会话 JSON 记录
│   └── zvec/        # Zvec 本地数据库文件
└── ocrdata/         # 示例测试文档
```

## 🛠 技术栈

*   **核心框架**：FastAPI, LangChain, httpx, Tenacity
*   **向量引擎**：zvec (高性能本地向量数据库)
*   **OCR/VLM**：DeepSeek-OCR / Qwen-VL (SiliconFlow API)
*   **嵌入与重排**：BGE-M3 (Dense+Sparse), BGE-Reranker-V2-M3
*   **前端**：TailwindCSS, Lucide Icons, Vanilla JS (SSE 实现)

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


test worktree
