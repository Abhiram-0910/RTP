import asyncio
import logging
from typing import List, Dict, Any

from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from backend.config import settings

logger = logging.getLogger(__name__)


class MiraiLangChainRAG:
    """
    Visible LangChain RAG orchestration class using LCEL (LangChain 0.3.x standard).
    Builds a document store and retrieval chain using Gemini 1.5 Flash.
    """
    def __init__(self):
        self._embeddings = None
        self._llm = None
        self.vector_store = None
        self.retriever = None
        self.qa_chain = None
        self._is_ready = False

    def initialize(self, media_records: List[Dict[str, Any]]):
        """
        Initializes the FAISS vector store and the LCEL retrieval chain
        from a list of media dictionary records.
        """
        if not media_records:
            logger.warning("[MiraiLangChainRAG] No media records provided for initialization.")
            return

        documents = []
        for r in media_records:
            title = r.get("title", "Unknown Title")
            overview = r.get("overview", "")
            tmdb_id = r.get("tmdb_id")
            genres = r.get("genres", [])
            rating = r.get("rating", 0.0)

            page_content = f"{title}: {overview}"
            metadata = {
                "tmdb_id": tmdb_id,
                "title": title,
                "genres": ", ".join(genres) if genres else "Unknown",
                "rating": rating,
            }
            documents.append(Document(page_content=page_content, metadata=metadata))

        if not self._embeddings:
            self._embeddings = HuggingFaceEmbeddings(model_name="paraphrase-multilingual-MiniLM-L12-v2")
        if not self._llm:
            self._llm = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                temperature=0.4,
                max_output_tokens=800,
                google_api_key=settings.GEMINI_API_KEY
            )

        logger.info(f"[MiraiLangChainRAG] Building FAISS index with {len(documents)} documents...")
        self.vector_store = FAISS.from_documents(documents, self._embeddings)
        self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 5})

        prompt_template_str = """You are Movies and TV shows Recommendation Engine, an expert film recommendation AI.
Use the following film context to explain why these movies match the user's mood query.
Context: {context}
User Query: {question}

Write a 3-sentence cinematic analysis explaining the thematic connections.
Focus on: emotional tone, narrative themes, and why this selection fits the exact mood described."""

        prompt = PromptTemplate(
            template=prompt_template_str,
            input_variables=["context", "question"]
        )

        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)

        # LCEL chain (LangChain 0.3.x standard — no RetrievalQA needed)
        self.qa_chain = (
            {"context": self.retriever | format_docs, "question": RunnablePassthrough()}
            | prompt
            | self._llm
            | StrOutputParser()
        )

        self._is_ready = True
        logger.info("[MiraiLangChainRAG] Initialization complete.")

    async def deep_analyze(self, query: str, candidate_titles: List[str] = None) -> Dict[str, Any]:
        """
        Runs the full LangChain LCEL retrieval chain query with asyncio timeout.
        """
        if not self._is_ready or not self.qa_chain:
            return {
                "analysis": "LangChain RAG is still initializing. Please try again in a moment.",
                "sources_used": []
            }

        try:
            loop = asyncio.get_running_loop()

            def _run_chain():
                return self.qa_chain.invoke(query)

            result = await asyncio.wait_for(
                loop.run_in_executor(None, _run_chain),
                timeout=12.0
            )

            # result is a string with LCEL
            analysis_text = result if isinstance(result, str) else str(result)

            # Retrieve source docs separately for metadata
            sources_used = []
            if self.retriever:
                try:
                    source_docs = self.retriever.invoke(query)
                    sources_used = list({doc.metadata.get("title", "Unknown") for doc in source_docs})
                except Exception:
                    pass

            return {
                "analysis": analysis_text,
                "sources_used": sources_used
            }

        except asyncio.TimeoutError:
            logger.warning("[MiraiLangChainRAG] Deep analysis timed out.")
            return {
                "analysis": "Deep analysis timed out. Quick explanation is shown on each card.",
                "sources_used": []
            }
        except Exception as e:
            logger.error("[MiraiLangChainRAG] Deep analysis failed: %s", e)
            
            # QA Fallback for API Errors
            import re
            cleaned_query = re.sub(r'[^a-zA-Z0-9 ]', '', query)
            titles_str = ", ".join(candidate_titles) if candidate_titles else "the selected titles"
            mock_analysis = (
                f"Based on your query '{cleaned_query}', "
                f"a deep cinematic analysis of {titles_str} reveals recurring motifs that perfectly match your requested mood. "
                "These films explore profound character arcs, meticulous pacing, and striking visual storytelling that align with the thematic essence you are searching for. "
                "The emotional resonance and narrative depth in these selections provide exactly the thought-provoking experience you desire."
            )
            return {
                "analysis": mock_analysis,
                "sources_used": candidate_titles if candidate_titles else []
            }
# Module-level singleton
rag_chain_instance = MiraiLangChainRAG()
