import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import os

from vectordb.store import FioriVectorStore
from rag.analyzer import SAPRAGAnalyzer
from crawler.fiori_crawler import FioriCrawler
from dotenv import load_dotenv

load_dotenv()

groq_api_key = os.environ.get("GROQ_API_KEY")

class RAGApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SAP Fiori RAG Analyzer")
        self.root.geometry("700x500")

        self.file_path = None

        # Title
        tk.Label(root, text="SAP Fiori RAG Analyzer", font=("Arial", 16)).pack(pady=10)

        # File button
        tk.Button(root, text="📂 Select ABAP File", command=self.load_file).pack(pady=5)

        self.file_label = tk.Label(root, text="No file selected")
        self.file_label.pack()

        # Analyze button
        tk.Button(root, text="🚀 Analyze", command=self.run_analysis).pack(pady=10)

        # Reset DB button
        tk.Button(root, text="🔄 Reset DB", command=self.reset_db).pack(pady=5)

        # Output box
        self.output = tk.Text(root, height=20, wrap="word")
        self.output.pack(padx=10, pady=10, fill="both", expand=True)

        # Init backend
        self.vector_store = FioriVectorStore(groq_api_key=groq_api_key)

        if self.vector_store.index_exists():
            self.vector_store.load()

    def load_file(self):
        self.file_path = filedialog.askopenfilename(
            filetypes=[("ABAP Files", "*.abap"), ("All Files", "*.*")]
        )
        self.file_label.config(text=self.file_path)

    def log(self, text):
        self.output.insert(tk.END, text + "\n")
        self.output.see(tk.END)

    def run_analysis(self):
        if not self.file_path:
            messagebox.showerror("Error", "Please select a file first")
            return

        threading.Thread(target=self._analyze).start()

    def _analyze(self):
        self.output.delete(1.0, tk.END)

        with open(self.file_path, "r", encoding="utf-8", errors="ignore") as f:
            abap_code = f.read()

        self.log("Analyzing...")

        analyzer = SAPRAGAnalyzer(vector_store=self.vector_store,groq_api_key=groq_api_key)

        results = analyzer.analyze(abap_code)

        self.log("\n=== SUMMARY ===\n")
        self.log(results["summary"])

        self.log("\n=== TOP MATCHES ===\n")
        for i, m in enumerate(results["matches"], 1):
            score = round(m["score"] * 100, 1)
            self.log(f"{i}. {m['title']} ({score}%)")

        self.log("\n=== RECOMMENDATION ===\n")
        self.log(results["recommendation"])

    def reset_db(self):
        self.log("Rebuilding DB...")

        crawler = FioriCrawler()
        apps = crawler.crawl()

        self.vector_store.build(apps)

        self.log("DB rebuilt successfully!")

if __name__ == "__main__":
    root = tk.Tk()
    app = RAGApp(root)
    root.mainloop()