import os
import logging
import requests
from typing import Sequence, List, Optional
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
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

logger = logging.getLogger(__name__)

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
            return list(documents)[:self.top_n]

class RAGService:
    def __init__(self):
        load_dotenv()
        self.embeddings = OpenAIEmbeddings(
            model="BAAI/bge-m3",
            openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
            openai_api_base=os.getenv("DEEPSEEK_BASE_URL"),
            check_embedding_ctx_length=False
        )
        self.llm = ChatOpenAI(
            base_url=os.getenv("DEEPSEEK_BASE_URL"),
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            model=os.getenv("MODEL_ID"),
            temperature=0.1,
        )
        self.reranker = SiliconFlowReranker(top_n=3)
        self.vectorstore = None
        self.bm25_retriever = None
        self.ensemble_retriever = None
        self.compression_retriever = None
        self.rag_chain = None
        self.documents = []

    def ingest_documents(self, documents: List[Document]):
        """Ingests documents, builds/updates indexes, and refreshes the RAG chain."""
        logger.info(f"Ingesting {len(documents)} documents...")
        self.documents.extend(documents)
        
        # Rebuild indexes
        self.vectorstore = FAISS.from_documents(self.documents, self.embeddings)
        vector_retriever = self.vectorstore.as_retriever(search_kwargs={"k": 5})
        
        self.bm25_retriever = BM25Retriever.from_documents(self.documents)
        self.bm25_retriever.k = 5
        
        self.ensemble_retriever = EnsembleRetriever(
            retrievers=[self.bm25_retriever, vector_retriever],
            weights=[0.5, 0.5]
        )
        
        self.compression_retriever = ContextualCompressionRetriever(
            base_compressor=self.reranker,
            base_retriever=self.ensemble_retriever
        )
        
        self._build_chain()
        logger.info("Ingestion complete.")

    def _build_chain(self):
        template = """Answer the question based ONLY on the following context:
{context}

Question: {question}
"""
        prompt = ChatPromptTemplate.from_template(template)

        def format_docs(docs):
            return "\n\n".join([f"[Source: {d.metadata.get('source', 'unknown')}] {d.page_content}" for d in docs])

        self.rag_chain = (
            {"context": self.compression_retriever | format_docs, "question": RunnablePassthrough()}
            | prompt
            | self.llm
            | StrOutputParser()
        )

    def query(self, question: str) -> str:
        if not self.rag_chain:
            return "No documents indexed. Please upload documents first."
        return self.rag_chain.invoke(question)

# Global instance
rag_engine = RAGService()
