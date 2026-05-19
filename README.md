# 📚 Local RAG System for Software Manuals

A **Retrieval-Augmented Generation (RAG)** system that answers questions **exactly** from a PDF manual using a local 3B LLM (Llama 3.2). Built with privacy, speed, and strict extractive answers in mind.

---

## 🖥️ Hardware Requirements

### Minimum (CPU only)
- **RAM**: 8 GB
- **CPU**: 4 cores, 2.0 GHz
- **Storage**: 10 GB free (for models, index, PDFs)
- **OS**: Linux, macOS, or Windows (WSL2)

### Recommended (for good speed)
- **RAM**: 16 GB
- **CPU**: Apple Silicon (M1/M2/M3) or Intel i7 / AMD Ryzen 7
- **GPU**: 6+ GB VRAM (optional, but speeds up embedding generation)
- **Storage**: 20 GB free (SSD)

> The 3B model (`llama3.2:3b`) runs comfortably on 4–6 GB RAM. The embedding model (`all-MiniLM-L6-v2`) is lightweight (<100 MB). ChromaDB keeps vectors in memory – plan ~1 GB for a 500‑page manual.

---

## 📦 Software Dependencies & Why They Are Used

| Package | Purpose | Why not something else? |
|---------|---------|--------------------------|
| **uv** | Fast Python package manager | Replaces pip + venv; locks dependencies instantly. |
| **Ollama** | Run LLM locally (`llama3.2:3b`) | No API calls, private, simple CLI. |
| **sentence-transformers** | Create embeddings (text → vectors) | All‑MiniLM‑L6‑v2: small, fast, good English quality. |
| **chromadb** | Vector database (store & search chunks) | Persistent on disk, simple API, lightweight. |
| **pdfplumber** | Extract text from PDF | Handles complex layouts better than PyPDF2; fallback for tables. |
| **camelot‑py[cv]** (optional)| Extract tables as DataFrames → Markdown | Preserves column structure; needs Ghostscript. |
| **transformers** + **torch** | Load cross‑encoder reranker | Reranks retrieved chunks for better accuracy. |
| **requests** | Talk to Ollama’s HTTP API | Lightweight, standard. |
| **ghostscript** (system) | PDF processing for Camelot | Required only if using Camelot; on macOS via Homebrew, on Linux via apt/yum. |

> 💡 If you cannot install Ghostscript, the script automatically falls back to pdfplumber table extraction.

---

## 🚀 Setup Instructions

### 1. Install `uv` (one time)
```bash
curl -LsSf [https://astral.sh/uv/install.sh](https://astral.sh/uv/install.sh) | sh

```

Then restart your terminal or run `source ~/.zshrc` (macOS) / `source ~/.bashrc` (Linux).

### 2. Create project folder and add dependencies

```bash
mkdir my_rag_system && cd my_rag_system
uv init
uv add pdfplumber sentence-transformers chromadb requests transformers torch

# Optional (better tables):
uv add 'camelot-py[cv]'

```

### 3. Install Ollama and pull the 3B model

```bash
ollama pull llama3.2:3b

```

Ollama serves the LLM on `http://localhost:11434`.

### 4. Install Ghostscript (if using Camelot)

* **macOS:** `brew install ghostscript`
* **Ubuntu/Debian:** `sudo apt install ghostscript`
* **RHEL/Fedora:** `sudo yum install ghostscript`

### 5. Place your PDF manual

Place your PDF manual in the folder and name it `software_manual.pdf` (or change `PDF_PATH` in `index.py`).

---

## 📄 Usage

**Index the PDF (run once)**

```bash
uv run python index.py

```

**Ask a question**

```bash
uv run python query.py

```

Type your question when prompted. The system will output an exact sentence from the PDF or *"Not found in document."*

---

## 🧠 How It Works 

**Indexing phase:**

* Extract all text and tables (tables become Markdown).
* Split into overlapping chunks, keeping headings with their content.
* Convert each chunk to a vector (embedding) using `all-MiniLM-L6-v2`.
* Store vectors + original text in ChromaDB (persistent on disk).

**Query phase:**

* Convert your question to a vector.
* ChromaDB finds the top 15 most similar chunks (cosine similarity).
* A cross‑encoder reranks those 15 to pick the best 6.
* Those 6 chunks become the **context**.
* A strict prompt + the context is sent to Llama 3.2 (3B).
* Llama 3.2 extracts the exact answer (or says “Not found”).
* Final validation ensures the answer type matches the question (e.g., no menu steps when asked for a keyboard shortcut).

---

## ✅ Example Run

```bash
$ uv run python index.py
📄 Reading PDF: software_manual.pdf
Extracted 51375 characters
Split into 85 heading‑aware chunks
✅ Indexing complete. 85 chunks stored.

$ uv run python query.py
🔍 Ask a question about the document: What is the exact keyboard shortcut to open the Equation Editor?
📖 Exact answer from document:
Not found in document.

```

---

## 🛠️ Troubleshooting

| Problem | Likely cause | Fix |
| --- | --- | --- |
| **UnboundLocalError: CAMELOT_AVAILABLE** | Using an older version of `index.py` | Use the corrected version from this repo. |
| **Camelot fails to detect tables** | PDF without borders or Ghostscript missing | Install Ghostscript or rely on pdfplumber fallback. |
| **Ollama connection refused** | Ollama not running | Run `ollama serve` in another terminal. |
| **Slow query** | Large PDF or many chunks | Reduce `INITIAL_RESULTS` to 10, `FINAL_RESULTS` to 4 in `query.py`. |
| **Wrong table column values** | Camelot not installed | Install `camelot-py[cv]` and Ghostscript. |
| **ModuleNotFoundError: No module named 'camelot'** | Camelot not installed | Remove Camelot lines or install it. The script works without it. |

---

## 📂 Repository Structure

```text
my_rag_system/
├── index.py               # Indexing script
├── query.py               # Query script with reranking
├── requirements.txt       # Python dependencies (pip)
├── README.md              # This file
├── .gitignore             # Git ignores
├── LICENSE                # MIT License
└── software_manual.pdf    # Your PDF (ignored by git)

```

---

## 📚 Further Reading

* **Ollama** – Local LLMs
* **Sentence‑Transformers** – Embedding models
* **ChromaDB** – Vector database
* **Camelot** – PDF table extraction
* **Cross‑Encoders** – Reranking

---

## 📄 License

MIT License – see `LICENSE` file.
