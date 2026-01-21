import os
import logging
import json
import requests
from typing import Sequence, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
# Handle imports for 2026/custom env structure
try:
    from langchain.retrievers import EnsembleRetriever, ContextualCompressionRetriever
    from langchain.retrievers.document_compressors.base import BaseDocumentCompressor
except ImportError:
    from langchain_classic.retrievers.ensemble import EnsembleRetriever
    from langchain_classic.retrievers.contextual_compression import ContextualCompressionRetriever
    from langchain_classic.retrievers.document_compressors.base import BaseDocumentCompressor
    from langchain_core.documents import Document
    from langchain_core.callbacks import Callbacks
    from pydantic import BaseModel, Field, PrivateAttr

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.documents import Document

# Custom Reranker for SiliconFlow
class SiliconFlowReranker(BaseDocumentCompressor):
    model: str = "BAAI/bge-reranker-v2-m3"
    api_key: str = Field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY"))
    base_url: str = Field(default_factory=lambda: os.getenv("DEEPSEEK_BASE_URL"))
    top_n: int = 3

    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Optional[Callbacks] = None,
    ) -> Sequence[Document]:
        if not documents:
            return []

        url = f"{self.base_url}/rerank"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        doc_texts = [d.page_content for d in documents]
        payload = {
            "model": self.model,
            "query": query,
            "documents": doc_texts,
            "top_n": self.top_n,
            "return_documents": False 
        }

        try:
            logger.info(f"Reranking {len(documents)} docs with {self.model} via API...")
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            results = response.json().get("results", [])
            
            # Sort and filter
            # Results usually contain index and relevance_score
            reranked_docs = []
            for res in results:
                index = res.get("index")
                score = res.get("relevance_score")
                if index is not None and index < len(documents):
                    doc = documents[index]
                    doc.metadata["relevance_score"] = score
                    reranked_docs.append(doc)
            
            return reranked_docs[:self.top_n]

        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            # Fallback: return top N original docs
            return list(documents)[:self.top_n]

def main():
    logger.info("Starting RAG Verification (Hybrid Search + Reranking + SiliconFlow API)...")

    # 1. Setup Sample Data
    logger.info("Creating sample documents...")
    docs = [
        Document(page_content="LangChain is a framework for developing applications powered by language models.", metadata={"source": "doc1"}),
        Document(page_content="Retrieval-Augmented Generation (RAG) combines an LLM with a retrieval system.", metadata={"source": "doc2"}),
        Document(page_content="Hybrid search combines keyword-based search (like BM25) with semantic search (vectors).", metadata={"source": "doc3"}),
        Document(page_content="Reranking involves scoring retrieved documents to improve relevance before passing to the LLM.", metadata={"source": "doc4"}),
        Document(page_content="BAAI/bge-m3 is a state-of-the-art embedding model supporting multi-linguality and various retrieval tasks.", metadata={"source": "doc5"}),
        Document(page_content="SiliconFlow provides high-performance API serving for models like Qwen and DeepSeek.", metadata={"source": "doc6"}),
        Document(page_content="Apples are a type of fruit that grow on trees.", metadata={"source": "distractor1"}),
        Document(page_content="The sky is blue because of Rayleigh scattering.", metadata={"source": "distractor2"}),
    ]

    # 2. Initialize Embeddings (SiliconFlow API)
    embedding_model_name = "BAAI/bge-m3"
    logger.info(f"Initializing Embeddings via API: {embedding_model_name}...")
    
    # Use OpenAIEmbeddings compatible client for SiliconFlow
    embeddings = OpenAIEmbeddings(
        model=embedding_model_name,
        openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
        openai_api_base=os.getenv("DEEPSEEK_BASE_URL"),
        check_embedding_ctx_length=False 
    )

    # 3. Setup Retrievers
    
    # 3a. Vector Search (Semantic)
    logger.info("Indexing documents into FAISS (Remote Embeddings)...")
    try:
        vectorstore = FAISS.from_documents(docs, embeddings)
        vector_retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    except Exception as e:
        logger.error(f"Failed to create vector store (likely API error or model not supported for embeddings): {e}")
        logger.info("Falling back to Fake Embeddings for demonstration if API fails...")
        from langchain_core.embeddings import FakeEmbeddings
        embeddings = FakeEmbeddings(size=1024)
        vectorstore = FAISS.from_documents(docs, embeddings)
        vector_retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

    # 3b. Keyword Search (BM25)
    logger.info("Initializing BM25 Retriever...")
    bm25_retriever = BM25Retriever.from_documents(docs)
    bm25_retriever.k = 5

    # 3c. Ensemble (Hybrid)
    logger.info("Creating Ensemble Retriever (Hybrid)...")
    ensemble_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, vector_retriever],
        weights=[0.5, 0.5]
    )

    # 4. Setup Reranker (SiliconFlow API)
    logger.info("Initializing Reranker (SiliconFlow API)...")
    reranker = SiliconFlowReranker(top_n=3)
    
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=reranker,
        base_retriever=ensemble_retriever
    )

    # 5. Setup LLM (SiliconFlow)
    logger.info("Initializing LLM via SiliconFlow...")
    llm = ChatOpenAI(
        base_url=os.getenv("DEEPSEEK_BASE_URL"),
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        model=os.getenv("MODEL_ID"),
        temperature=0.1,
    )

    # 6. Define RAG Chain
    template = """Answer the question based ONLY on the following context:
{context}

Question: {question}
"""
    prompt = ChatPromptTemplate.from_template(template)

    def format_docs(docs):
        return "\n\n".join([f"[Source: {d.metadata.get('source', 'unknown')}] {d.page_content}" for d in docs])

    rag_chain = (
        {"context": compression_retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    # 7. Execute Query
    query = "How does hybrid search work?"
    logger.info(f"Executing Query: '{query}'")
    
    logger.info("Invoking chain...")
    try:
        # Debug: Retrieve docs first to show reranking effect
        retrieved_docs = compression_retriever.invoke(query)
        logger.info(f"Retrieved & Reranked {len(retrieved_docs)} documents:")
        for i, doc in enumerate(retrieved_docs):
            logger.info(f"  {i+1}. {doc.page_content[:50]}... (Score: {doc.metadata.get('relevance_score', 'N/A')})")

        response = rag_chain.invoke(query)
        print("\n" + "="*50)
        print(f"QUESTION: {query}")
        print("-" * 50)
        print(f"ANSWER:\n{response}")
        print("="*50 + "\n")
        logger.info("Verification Complete!")
    except Exception as e:
        logger.error(f"Error during chain invocation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()