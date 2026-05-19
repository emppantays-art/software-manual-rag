# Line‑by‑Line Code Explanation

This document explains **every line** of `index.py` and `query.py` – what it does and why it's there.

---

## 📄 `index.py` – Indexing the PDF

### 1. Imports and setup
```python
#!/usr/bin/env python3
```
**Tells the system** to run this script with Python 3 (not needed on Windows, but harmless).

```python
import chromadb
```
**Imports the ChromaDB library** – a vector database that stores text chunks and their embeddings (numerical representations). Later we can search these vectors by similarity.

```python
from sentence_transformers import SentenceTransformer
```
**Imports the SentenceTransformer class** – loads pre‑trained models that convert sentences/paragraphs into fixed‑size vectors (embeddings). We use `all-MiniLM-L6-v2`.

```python
import pdfplumber
```
**Imports pdfplumber** – a Python library that extracts text and tables from PDFs. It preserves reading order better than PyPDF2.

```python
import re
```
**Imports regular expressions** – used to split text at sentence boundaries (`.`, `!`, `?`) and detect headings like "Step 1".

```python
import os
```
**Imports OS module** – used to check if a file exists (e.g., `os.path.exists(PDF_PATH)`).

```python
try:
    import camelot
    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False
    print("Camelot not available. Using pdfplumber for tables.")
```
**Tries to import Camelot** – an optional library that extracts tables as DataFrames and converts them to Markdown. If not installed, we set a flag `CAMELOT_AVAILABLE = False` and fall back to pdfplumber's table extraction. This keeps the script working even without Camelot.

### 2. Configuration variables
```python
PDF_PATH = "software_manual.pdf"
```
**Path to the PDF file** – change this if your PDF has a different name.

```python
CHUNK_SIZE = 800
```
**Maximum characters per chunk** – 800 characters is about 150 words, small enough to fit in the LLM's context and fast to embed.

```python
OVERLAP = 200
```
**Number of characters that overlap between consecutive chunks** – prevents answers from being cut off at chunk boundaries. For example, if a sentence spans two chunks, the overlap ensures both chunks contain parts of it.

```python
EMBED_MODEL = "all-MiniLM-L6-v2"
```
**Name of the embedding model** – a small, fast model (384‑dimension vectors) that runs on CPU. Good balance of speed and quality.

### 3. Function: `extract_text_and_tables(pdf_path)`
```python
def extract_text_and_tables(pdf_path):
```
**Defines a function** that takes a PDF file path and returns a single string containing all text and tables (formatted as Markdown).

```python
    full_text = ""
```
**Initializes an empty string** – we'll accumulate extracted content here.

```python
    with pdfplumber.open(pdf_path) as pdf:
```
**Opens the PDF file** using pdfplumber. The `with` statement automatically closes the file when done.

```python
        for page_num, page in enumerate(pdf.pages, start=1):
```
**Loops through each page** – `enumerate` gives us a page number (starting at 1) and the page object.

```python
            text = page.extract_text()
```
**Extracts all text from the current page** – returns a string with the text in reading order.

```python
            if text:
                full_text += f"\n--- Page {page_num} ---\n" + text
```
**If text exists, append it** to `full_text` with a page marker. This helps the LLM know which page the answer came from (though we don't use it directly for answers, it's useful for debugging).

```python
    use_camelot = CAMELOT_AVAILABLE
```
**Copies the global flag into a local variable** – so we can modify it inside the function without affecting the global.

```python
    if use_camelot:
```
**If Camelot is installed**, try to extract tables with it.

```python
        try:
            tables = camelot.read_pdf(pdf_path, pages='all', flavor='lattice')
```
**Reads all tables** assuming they have borders (lattice). Camelot returns a list of `Table` objects.

```python
            if len(tables) == 0:
                tables = camelot.read_pdf(pdf_path, pages='all', flavor='stream')
```
**If no lattice tables found**, try stream mode (for borderless tables like those created with spaces or tab stops).

```python
            for table in tables:
                df = table.df
```
**Converts each table to a pandas DataFrame** – rows and columns preserved.

```python
                markdown = f"\n--- Table on page {table.page} ---\n"
                markdown += df.to_markdown(index=False)
                full_text += markdown
```
**Converts DataFrame to Markdown table format** and appends it to `full_text` with a marker. Markdown tables are easy for the LLM to read.

```python
            use_camelot = True
```
**Keeps the flag true** (success).

```python
        except Exception as e:
            print(f"Warning: Camelot failed: {e}. Falling back to pdfplumber tables.")
            use_camelot = False
```
**If anything fails** (e.g., Ghostscript missing), print a warning and switch to fallback mode.

```python
    if not use_camelot:
```
**If Camelot not available or failed**, fall back to pdfplumber's table extraction.

```python
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables()
```
**Extracts tables using pdfplumber** – returns a list of tables, each table is a list of rows, each row is a list of strings.

```python
                for table in tables:
                    if table and len(table) > 1:
```
**Checks if table has at least one header row and one data row**.

```python
                        headers = table[0]
                        rows = table[1:]
```
**Splits first row as headers**, the rest as data rows.

```python
                        markdown = f"\n--- Table on page {page_num} ---\n"
                        markdown += "| " + " | ".join(str(h) if h else "" for h in headers) + " |\n"
                        markdown += "|" + "|".join([" --- " for _ in headers]) + "|\n"
```
**Builds the Markdown table header** – first line has column names separated by pipes, second line has dashes to separate header from body.

```python
                        for row in rows:
                            markdown += "| " + " | ".join(str(cell) if cell else "" for cell in row) + " |\n"
                        full_text += markdown
```
**Adds each data row** (cells separated by pipes) and appends the entire Markdown table to `full_text`.

```python
    return full_text
```
**Returns the accumulated text** (regular text + tables as Markdown).

### 4. Function: `chunk_by_heading(text, max_chunk_size, overlap)`
```python
def chunk_by_heading(text, max_chunk_size=CHUNK_SIZE, overlap=OVERLAP):
```
**Defines the chunking function** – takes the full document text and splits it into overlapping chunks that try to keep headings together with their content.

```python
    lines = text.split('\n')
```
**Splits the text by newline** – each line becomes an element in a list.

```python
    chunks = []
    current_chunk = []
    current_len = 0
```
**Initializes variables** – `chunks` will hold the final list of chunk strings; `current_chunk` builds one chunk at a time; `current_len` tracks the length of `current_chunk` in characters.

```python
    heading_pattern = re.compile(r'^(Step \d+|[0-9]+\.|•|\-|[A-Z][a-z]+ \d+|[A-Z][A-Z\s]+:)')
```
**Compiles a regular expression** that matches common heading patterns:
- `Step 1`, `Step 2`, etc.
- `1.`, `2.` (numbered list)
- `•`, `-` (bullets)
- `Chapter 1`, `Appendix A` (word + number)
- `HEADING:` (all‑caps with colon)

```python
    for line in lines:
```
**Loops over each line** of the document.

```python
        line_len = len(line) + 1
```
**Length of the line plus one for the newline character** – used to track chunk size.

```python
        is_heading = bool(heading_pattern.match(line.strip()))
```
**Checks if the line (stripped of leading/trailing spaces) matches the heading pattern**. If yes, `is_heading` is `True`.

```python
        if is_heading and current_chunk and current_len > max_chunk_size * 0.5:
```
**If this line is a heading, we already have some content, and the current chunk is at least half the max size**, then we finalize the current chunk and start a new one. This prevents tiny chunks with just a heading.

```python
            chunks.append('\n'.join(current_chunk))
```
**Joins the collected lines with newlines** and adds the finished chunk to the `chunks` list.

```python
            overlap_text = '\n'.join(current_chunk)
            if len(overlap_text) > overlap:
                overlap_text = overlap_text[-overlap:]
```
**Extracts the last `overlap` characters** from the chunk we just finished – this becomes the overlap for the next chunk.

```python
            current_chunk = [overlap_text, line]
            current_len = len(overlap_text) + line_len
```
**Starts a new chunk** with the overlap text (if any) followed by the heading line.

```python
        else:
```
**If the line is not a heading, or the chunk is not ready to be cut**, we proceed to normal addition.

```python
            if current_len + line_len > max_chunk_size and current_chunk:
```
**If adding this line would exceed the max chunk size**, and we already have some content, we finalize the current chunk.

```python
                chunks.append('\n'.join(current_chunk))
                overlap_text = '\n'.join(current_chunk)
                if len(overlap_text) > overlap:
                    overlap_text = overlap_text[-overlap:]
                current_chunk = [overlap_text]
                current_len = len(overlap_text)
```
**Same overlap logic** as before, but without automatically adding a heading.

```python
            current_chunk.append(line)
            current_len += line_len
```
**Add the line to the current chunk** and update the length.

```python
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
```
**After the loop, if there is any remaining text**, add it as the final chunk.

```python
    return chunks
```
**Return the list of chunks**.

### 5. Main indexing routine
```python
print(f"📄 Reading PDF: {PDF_PATH}")
```
**Prints a status message**.

```python
if not os.path.exists(PDF_PATH):
    print(f"ERROR: {PDF_PATH} not found. Place your PDF file in the same folder.")
    exit(1)
```
**Checks if the PDF file exists** – if not, prints an error and exits.

```python
document_text = extract_text_and_tables(PDF_PATH)
print(f"Extracted {len(document_text)} characters")
```
**Extracts text and tables** and prints the total character count.

```python
chunks = chunk_by_heading(document_text)
print(f"Split into {len(chunks)} heading‑aware chunks")
```
**Splits into chunks** and prints the number of chunks.

```python
embedder = SentenceTransformer(EMBED_MODEL)
```
**Loads the embedding model** – downloads it on first run (cached afterwards).

```python
client = chromadb.PersistentClient(path="./chroma_db")
```
**Creates a persistent ChromaDB client** – data will be stored in the `./chroma_db` folder. Persistence means the vectors survive after the script ends.

```python
try:
    client.delete_collection("my_document")
    print("Removed old collection")
except:
    pass
```
**Deletes the existing collection if it exists** – this ensures we always query the most up‑to‑date index. If the collection doesn't exist, we ignore the error.

```python
collection = client.create_collection("my_document")
```
**Creates a new collection** named `my_document` – collections are like tables in a database, grouping related vectors.

```python
for i, chunk in enumerate(chunks):
    embedding = embedder.encode(chunk).tolist()
    collection.add(documents=[chunk], embeddings=[embedding], ids=[f"chunk_{i}"])
```
**Loops over each chunk**:
- `embedder.encode(chunk)` generates a vector (list of floats).
- `.tolist()` ensures it's a regular Python list.
- `collection.add()` stores the chunk text, its embedding, and a unique ID (`chunk_0`, `chunk_1`, ...).

```python
print(f"✅ Indexing complete. {len(chunks)} chunks stored.")
```
**Final success message**.

---

## ❓ `query.py` – Asking Questions

### 1. Imports
```python
#!/usr/bin/env python3
```
**Shebang** – as before.

```python
import chromadb
from sentence_transformers import SentenceTransformer, CrossEncoder
import requests
import json
import re
```
**Imports**:
- `chromadb` – to access the persisted vectors.
- `SentenceTransformer` – to embed the user's question.
- `CrossEncoder` – a different type of model that scores (question, chunk) pairs directly (more accurate than cosine similarity).
- `requests` – to call Ollama's HTTP API.
- `json` – to parse the API response (though `response.json()` does it for us).
- `re` – for pattern matching in answer validation.

### 2. Configuration
```python
OLLAMA_URL = "http://localhost:11434/api/generate"
```
**Ollama's local endpoint** – where we send prompts.

```python
OLLAMA_MODEL = "llama3.2:3b"
```
**The 3B model we pulled** – change to any other model you have.

```python
EMBED_MODEL = "all-MiniLM-L6-v2"
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
```
**Embedding model** (same as indexing) and **cross‑encoder model** (slightly larger, but still small).

```python
INITIAL_RESULTS = 15
FINAL_RESULTS = 6
TEMPERATURE = 0.0
MAX_TOKENS = 500
```
- `INITIAL_RESULTS` – number of chunks retrieved by ChromaDB.
- `FINAL_RESULTS` – number of chunks kept after reranking.
- `TEMPERATURE=0.0` – deterministic (no randomness).
- `MAX_TOKENS=500` – answer length limit.

### 3. Load models and connect to DB
```python
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_collection("my_document")
```
**Reopens the same persistent database** and gets the existing collection.

```python
embedder = SentenceTransformer(EMBED_MODEL)
reranker = CrossEncoder(RERANKER_MODEL)
```
**Loads both models** – the reranker downloads on first use.

### 4. Function: `ask_llama(prompt)`
```python
def ask_llama(prompt):
    response = requests.post(OLLAMA_URL, json={
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS
    })
    return response.json()["response"]
```
**Sends a POST request to Ollama** with the prompt and generation parameters. `stream=False` means we wait for the full answer. The response is JSON; we extract the `"response"` field.

### 5. Function: `rerank_chunks(query, chunks)`
```python
def rerank_chunks(query, chunks):
    pairs = [[query, chunk] for chunk in chunks]
    scores = reranker.predict(pairs)
    scored = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
    return [chunk for chunk, score in scored]
```
- Creates a list of `[question, chunk]` pairs.
- The cross‑encoder predicts a relevance score for each pair (higher = more relevant).
- Sorts chunks by score descending.
- Returns only the chunks (dropping the scores).

### 6. Function: `answer_matches_question_type(question, answer)`
```python
def answer_matches_question_type(question, answer):
    if answer == "Not found in document.":
        return True
```
**If the answer is already “Not found”**, we accept it.

```python
    q_lower = question.lower()
```
**Lowercase the question** for easier matching.

```python
    if "keyboard shortcut" in q_lower or "shortcut key" in q_lower:
        if not re.search(r'[A-Za-z]+[\+\-][A-Za-z0-9\+\-]+', answer):
            return False
```
**If asking for a keyboard shortcut** – the answer must contain a pattern like `Ctrl+S` or `Alt+F4`. If not, reject.

```python
    if re.search(r'(how much space|distance|measurement|pt|inch|mm|cm)', q_lower):
        if not re.search(r'\d+(\.\d+)?\s*(pt|inch|in|mm|cm|")', answer, re.IGNORECASE):
            return False
```
**If asking for a measurement** – the answer must contain a number and a unit (e.g., `0.5"`, `12 pt`). If not, reject.

```python
    if re.search(r'(version|v\.|release)', q_lower):
        if not re.search(r'\d+(\.\d+)+', answer):
            return False
```
**If asking for a version number** – answer must have at least one dot (e.g., `3.2`). If not, reject.

```python
    return True
```
**If all checks pass**, accept the answer.

### 7. Main query flow
```python
question = input("🔍 Ask a question about the document: ")
```
**Prompt the user** for a question.

```python
q_emb = embedder.encode(question).tolist()
initial = collection.query(query_embeddings=[q_emb], n_results=INITIAL_RESULTS)
initial_chunks = initial['documents'][0]
```
**Embed the question** and query ChromaDB for the top `INITIAL_RESULTS` chunks. The result contains a list of documents (chunks).

```python
reranked = rerank_chunks(question, initial_chunks)
top_chunks = reranked[:FINAL_RESULTS]
context = "\n---\n".join(top_chunks)
```
**Rerank the chunks** and keep the top `FINAL_RESULTS`. Join them with `---` separators to form the context.

### 8. Build and send the prompt
```python
prompt = f"""You are an extractive QA robot. Answer the question using ONLY the exact words from the context below.

STRICT RULES:
- If the user asks for a specific type (e.g., "keyboard shortcut", "exact measurement", "specific version number") and the context does NOT contain that exact type, answer exactly: "Not found in document."
- Do NOT substitute a different type of answer.
- If the answer is a list or numbered procedure, output ALL steps exactly as they appear.
- If the answer is not in the context, output "Not found in document."
- For placeholder/template text, output: "The document contains only placeholder/template text. No real information is provided."

Context:
{context}

Question: {question}

Exact answer:"""
```
**The strict prompt** – tells the LLM to extract only, never invent, and avoid type substitution.

```python
raw_answer = ask_llama(prompt).strip()
```
**Get the answer** from Ollama.

```python
if answer_matches_question_type(question, raw_answer):
    final_answer = raw_answer
else:
    final_answer = "Not found in document."
```
**Validate answer type** – if it doesn't match, override with “Not found”.

```python
print("\n📖 Exact answer from document:")
print(final_answer)
```
**Print the result**.
