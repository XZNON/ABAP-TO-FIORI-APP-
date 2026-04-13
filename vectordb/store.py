"""
Builds and queries a ChromaDB vector store of SAP Fiori app descriptions.
 
Embeddings are generated via LangChain's HuggingFaceEmbeddings
(sentence-transformers/all-MiniLM-L6-v2) — runs locally, no API key needed
for embeddings, keeping costs zero.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import os

import torch
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

PERSIST_DIR = "data/chroma_db"
COLLECTION_NAME = "fiori_apps"
 
class FioriVectorStore:
    """
    Wraps chromaDB + embeddings for similarity search
    """

    def __init__(self,groq_api_key):
        self.groq_api_key = groq_api_key
        self._db : Optional[Chroma] = None
        self._embeddings = self._make_embeddings()
    
    def _make_embeddings(self):
        """
        Using sentence transformer embeddings, can use openAI embeddigns 
        """
        device = "cuda" if torch.cuda.is_available() else "cpu"
        return HuggingFaceEmbeddings(
            model_name = "sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs = {"device" : device},
            encode_kwargs = {"normalize_embeddings": True},
        )

    def index_exists(self) -> bool:
        persist_path = Path(PERSIST_DIR)
        return persist_path.exists() and any(persist_path.iterdir())
    
    def build(self,apps : List[Dict[str,Any]]) ->None:
        """
        Embedd all the app description into chromaDB
        """

        docs = []
        for app in apps:
            tags_str =  ", ".join(app.get("tags",[]))
            content = (
                f"Title: {app.get('title', '')}\n"
                f"Description: {app.get('description', '')}\n"
                f"Type: {app.get('app_type', '')}\n"
                f"Product: {app.get('product', '')}\n"
                f"Business Role: {app.get('business_role', '')}\n"
                f"Tags: {tags_str}"
            )
            docs.append(
                Document(
                    page_content=content,
                    metadata = {
                        "app_id": app.get("app_id", ""),
                        "title": app.get("title", ""),
                        "description": app.get("description", "")[:500],
                        "app_type": app.get("app_type", ""),
                        "product": app.get("product", ""),
                    }
                )
            )
        
        self._db = Chroma.from_documents(
            documents=docs,
            embedding=self._embeddings,
            collection_name=COLLECTION_NAME,
            persist_directory=PERSIST_DIR
        )
        print(f"Persisted {len(docs)} app embeddings")
    
    def load(self) -> None:
        self._db = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=self._embeddings,
            persist_directory=PERSIST_DIR,
        )
    
    def similarity_search(self,query : str, k: int = 5) -> List[Dict[str,Any]]:
        """
        This will return top k apps that have relevant scores.
        We are using cosine similarity for this
        """
        if self._db is None:
            raise RuntimeError("Vector store not loaded. Call build() or load() first.")
        
        results = self._db.similarity_search_with_relevance_scores(query,k=k)

        matches = []

        for doc,score in results:
            matches.append(
                {
                    "app_id": doc.metadata.get("app_id", ""),
                    "title": doc.metadata.get("title", ""),
                    "description": doc.metadata.get("description", ""),
                    "app_type": doc.metadata.get("app_type", ""),
                    "product": doc.metadata.get("product", ""),
                    "score": round(score, 4),
                }
            )
        
        return matches
