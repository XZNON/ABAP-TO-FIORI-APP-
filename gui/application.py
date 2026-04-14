"""
app.py — SAP Fiori RAG Analyzer GUI
=====================================
Run with: python app.py
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import os

from vectordb.store import FioriVectorStore
from rag.analyzer import SAPRAGAnalyzer
from helpers.firoi_dataset import FioriDatasetManager   
from helpers.process_fiori import process_fiori_excel
from dotenv import load_dotenv

load_dotenv()


class RAGApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SAP Fiori RAG Analyzer")
        self.root.geometry("700x540")
        self.file_path = None
        self.vector_store = None  
        

        tk.Label(root, text="SAP Fiori RAG Analyzer", font=("Arial", 16, "bold")).pack(pady=10)

        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="Select ABAP File", width=18, command=self.load_file).grid(row=0, column=0, padx=5)
        tk.Button(btn_frame, text="Analyze", width=18, command=self.run_analysis).grid(row=0, column=1, padx=5)
        tk.Button(btn_frame, text="Reset DB", width=18, command=self.run_reset_db).grid(row=0, column=2, padx=5)

        self.file_label = tk.Label(root, text="No file selected", fg="gray")
        self.file_label.pack()

        self.status_label = tk.Label(root, text="Starting up...", fg="blue")
        self.status_label.pack()

        self.output = tk.Text(root, height=22, wrap="word", state="disabled")
        self.output.pack(padx=10, pady=10, fill="both", expand=True)

        threading.Thread(target=self._init_vector_store, daemon=True).start()

    def _init_vector_store(self):

        groq_api_key = os.environ.get("GROQ_API_KEY")
        if not groq_api_key:
            self._set_status("ERROR: GROQ_API_KEY not set in .env", "red")
            return

        self._set_status("Loading embedding model (first run may take ~30s)...", "blue")
        self.vector_store = FioriVectorStore(groq_api_key=groq_api_key)

        if self.vector_store.index_exists():
            self.vector_store.load()
            self._set_status("Ready — index loaded.", "green")
        else:
            self._set_status("Ready — no index yet. Click Analyze to build it.", "orange")

    def _set_status(self, text: str, color: str = "black"):
        self.root.after(0, lambda: self.status_label.config(text=text, fg=color))

    def log(self, text: str):
        def _append():
            self.output.config(state="normal")
            self.output.insert(tk.END, text + "\n")
            self.output.see(tk.END)
            self.output.config(state="disabled")
        self.root.after(0, _append)

    def _clear_output(self):
        self.root.after(0, lambda: (
            self.output.config(state="normal"),
            self.output.delete(1.0, tk.END),
            self.output.config(state="disabled"),
        ))

    def load_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("ABAP Files", "*.abap"), ("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if path:
            self.file_path = path
            self.file_label.config(text=os.path.basename(path), fg="black")

    def run_analysis(self):
        if not self.file_path:
            messagebox.showerror("Error", "Please select an ABAP file first.")
            return
        if self.vector_store is None:
            messagebox.showinfo("Please wait", "Embedding model is still loading. Try again in a moment.")
            return
        threading.Thread(target=self._analyze, daemon=True).start()

    def _analyze(self):
        self._clear_output()
        groq_api_key = os.environ.get("GROQ_API_KEY")

        try:
            with open(self.file_path, "r", encoding="utf-8", errors="ignore") as f:
                abap_code = f.read()

            self._set_status("Analyzing...", "blue")
            self.log("Reading ABAP file...")

            if not self.vector_store.index_exists():
                self.log("No index found — building automatically...")
                self._build_db()

            self.log("Running RAG analysis with Groq...")
            analyzer = SAPRAGAnalyzer(
                vector_store=self.vector_store,
                groq_api_key=groq_api_key,
            )
            results = analyzer.analyze(abap_code)

            self.log("\n=== SUMMARY ===")
            self.log(results["summary"])

            self.log("\n=== TOP MATCHES ===")
            for i, m in enumerate(results["matches"], 1):
                score = round(m["score"] * 100, 1)
                self.log(f"{i}. [{score}%] {m['title']}  (App ID: {m.get('app_id', 'N/A')})")
                self.log(f"   {m['description'][:120]}...")

            self.log("\n=== RECOMMENDATION ===")
            self.log(results["recommendation"])

            self._set_status("Analysis complete.", "green")

        except Exception as e:
            self.log(f"\nERROR: {e}")
            self._set_status(f"Error: {e}", "red")

    def run_reset_db(self):
        if self.vector_store is None:
            messagebox.showinfo("Please wait", "Still initializing. Try again in a moment.")
            return
        threading.Thread(target=self._build_db, daemon=True).start()

    def _build_db(self):
        try:
            self._set_status("Rebuilding DB...", "blue")
            dataset = FioriDatasetManager()

            self.log("Downloading Fiori dataset (Playwright)...")
            dataset.refresh_dataset()

            self.log("Processing dataset...")
            apps = process_fiori_excel(dataset.download_path)
            self.log(f"Parsed {len(apps)} apps.")

            self.log("Building vector index (this takes a minute)...")
            self.vector_store.build(apps)

            self.log("DB rebuilt successfully!")
            self._set_status("DB ready.", "green")

        except Exception as e:
            self.log(f"\nERROR during DB build: {e}")
            self._set_status(f"DB build failed: {e}", "red")


if __name__ == "__main__":
    root = tk.Tk()
    app = RAGApp(root)
    root.mainloop()