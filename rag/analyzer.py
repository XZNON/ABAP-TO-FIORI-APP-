"""
Core RAG logic — two LangChain chains, both using Groq 
 
  Chain 1 — ABAP Summarizer
    Input : raw ABAP source code
    Output: plain-language functional description used as the RAG query
 
  Chain 2 — Re-ranker / Recommender
    Input : functional summary + top-k retrieved app descriptions
    Output: structured recommendation (best match, gaps, action)

Available Groq models (fast + free tier):
  - llama-3.3-70b-versatile     (best quality, recommended)
  - llama-3.1-8b-instant        (fastest, lower cost)
  - mixtral-8x7b-32768          (good for long ABAP files, 32k context)
  - gemma2-9b-it                (lightweight alternative)
"""

from typing import List, Dict, Any
import os

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from langchain_core.output_parsers import StrOutputParser
 
from vectordb.store import FioriVectorStore
 
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = "llama-3.3-70b-versatile"  

ABAP_SUMMARY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are an SAP technical analyst. Your job is to read ABAP source code
and produce a concise, plain-language functional description suitable for
semantic similarity search against a catalog of SAP Fiori apps.
 
Output a single paragraph (3-5 sentences) covering:
- What business process does this report serve?
- Which SAP module / sub-module (e.g. FI-AP, MM-PUR)?
- What data does it read (key tables, key fields)?
- What output does it produce (ALV grid, aging buckets, totals, etc.)?
- Who uses it and when (AP team, month-end, etc.)?
 
Do not output code. Do not use bullet points. Plain prose only.""",
        ),
        ("human", "ABAP source code:\n\n{abap_code}"),
    ]
)
 
RERANK_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are an SAP solution architect helping decide whether a custom ABAP
report can be replaced by a standard SAP Fiori app.
 
You will receive:
1. A functional summary of the custom ABAP report
2. A list of candidate standard SAP apps with similarity scores
 
Your task:
- Pick the BEST matching standard app and explain why (be specific: same tables?
  same bucket logic? same user role?)
- Identify any functional gaps between the custom report and the best match
- Give a clear BUILD vs REUSE recommendation with rationale
 
Format your response as:
 
BEST MATCH: <App ID> — <App Title>
WHY: <2-3 sentences>
GAPS: <bullet list of differences, or "None identified">
RECOMMENDATION: <1-2 sentence decision>""",
        ),
        (
            "human",
            """Functional summary of custom report:
{summary}
 
Candidate standard apps (ranked by similarity):
{candidates}""",
        ),
    ]
)

class SAPRAGAnalyzer:
    """
    Orchestrates the two-chain RAG pipeline using LangChain + Groq.
    """

    def __init__(self,vector_store : FioriVectorStore,groq_api_key : str):
        self.vector_store = vector_store
        self._llm = ChatOpenAI(
            model = GROQ_MODEL,
            api_key=groq_api_key,
            base_url=GROQ_BASE_URL,
            temperature=0,
            max_tokens=1024
        )

        self._summarize_chain = ABAP_SUMMARY_PROMPT | self._llm | StrOutputParser()
        self._rank_chain = RERANK_PROMPT | self._llm | StrOutputParser()

    
    def analyze(self,abap_code: str,top_k : int = 5) -> Dict[str,Any]:
        """
        Rag pipeline:
            1. summarize ABAP -> query string
            2. Embed query -> vector similalrity
            3. Re-rank + recomend apps
        """

        #summarize the abap code
        print("Running ABAP summarizer")
        summary = self._summarize_chain.invoke({"abap_code" : abap_code})
        print(f"Summary : {summary[:120]}...\n")

        #retrival step (fetch the top k results)
        print("      Querying vector store...")
        matches = self.vector_store.similarity_search(query=summary, k=top_k)

        print("Running re-ranker")
        candidates_text = "\n\n".join(
            f"[{i+1}] Score {m['score']:.2f} — {m['app_id']} | {m['title']}\n"
            f"    {m['description'][:300]}"
            for i, m in enumerate(matches)
        )

        recommendation = self._rank_chain.invoke(
            {"summary" : summary,"candidates" : candidates_text}
        )

        return {
            "summary" : summary,
            "matches" : matches,
            "recommendation" : recommendation
        }