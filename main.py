"""
SAP Fiori RAG Analyzer
======================
Analyzes an ABAP report and finds matching standard SAP Fiori apps
 
Usage:
    python main.py --file path/to/your_report.abap
    python main.py --file path/to/your_report.abap --rebuild-index
"""

import argparse
import os
from crawler.fiori_crawler import FioriCrawler
from vectordb.store import FioriVectorStore
from rag.analyzer import SAPRAGAnalyzer
from dotenv import load_dotenv

load_dotenv()

groq_api_key = os.environ.get("GROQ_API_KEY")

def main():
    parser = argparse.ArgumentParser(description="FIORI RAG ANALYZER")

    parser.add_argument("--file", required=True, help="Path to the ABAP source file")
    parser.add_argument("--build-index",action="store_true",help="Re-crawl the SAP Fiori library and rebuild the vector DB")

    parser.add_argument("--top-k",type=int, default=5, help="Number of top matches to return (default: 5)")

    args = parser.parse_args()

    if not groq_api_key:
        raise ValueError(
            "Groq API key is required. Set GROQ_API_KEY env var or pass --groq-api-key"
        )

    with open(args.file,"r",encoding="utf-8",errors="ignore") as f:
        abap_code = f.read()
    
    print(f"\n{'='*60}")
    print("  SAP Fiori RAG Analyzer")
    print(f"{'='*60}\n")

    vector_store = FioriVectorStore(groq_api_key = groq_api_key)

    if args.build_index or not vector_store.index_exists():
        print("[1/3] Crawling SAP Fiori Apps Library...")
        crawler = FioriCrawler()
        apps = crawler.crawl()
        print(f"Fetched {len(apps)} apps. Building vector index...")
        vector_store.build(apps)
        print("Index built and persisted.\n")
    else:
        print("[1/3] Loading existing vector index...\n")
        vector_store.load()
    
        print("[2/3] Parsing ABAP code with Groq...")
        analyzer = SAPRAGAnalyzer(vector_store=vector_store,groq_api_key=groq_api_key)
        results = analyzer.analyze(abap_code=abap_code, top_k=args.top_k)

        print("[3/3] Results\n")
        print(f"  Functional summary:\n  {results['summary']}\n")
        print(f"  Top {args.top_k} matching SAP standard apps:")
        print(f"  {'-'*56}")

        for i,match in enumerate(results["matches"],1):
            score_pct = round(match["score"]*100,1)
            print(f"  {i}. [{score_pct}%] {match['title']}")
            print(f"       App ID : {match.get('app_id', 'N/A')}")
            print(f"       Desc   : {match['description'][:120]}...")
            print()

        print(" Recommendation:")
        print(f"  {results['recommendation']}\n")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    main()