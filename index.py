# index.py – Index a PDF with table preservation and heading‑aware chunking
import chromadb
from sentence_transformers import SentenceTransformer
import pdfplumber
import re
import os

# Try to import Camelot (optional)
try:
    import camelot
    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False
    print("Camelot not available. Using pdfplumber for tables.")

# ---------- CONFIGURATION ----------
PDF_PATH = "software_manual.pdf"
CHUNK_SIZE = 800
OVERLAP = 200
EMBED_MODEL = "all-MiniLM-L6-v2"

def extract_text_and_tables(pdf_path):
    full_text = ""

    # 1. Regular text from pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text:
                full_text += f"\n--- Page {page_num} ---\n" + text

    # 2. Tables – try Camelot only if available
    use_camelot = CAMELOT_AVAILABLE   # local copy of global flag
    if use_camelot:
        try:
            tables = camelot.read_pdf(pdf_path, pages='all', flavor='lattice')
            if len(tables) == 0:
                tables = camelot.read_pdf(pdf_path, pages='all', flavor='stream')
            for table in tables:
                df = table.df
                markdown = f"\n--- Table on page {table.page} ---\n"
                markdown += df.to_markdown(index=False)
                full_text += markdown
            use_camelot = True   # success
        except Exception as e:
            print(f"Warning: Camelot failed: {e}. Falling back to pdfplumber tables.")
            use_camelot = False

    if not use_camelot:
        # Fallback: pdfplumber's table extraction
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables()
                for table in tables:
                    if table and len(table) > 1:
                        headers = table[0]
                        rows = table[1:]
                        markdown = f"\n--- Table on page {page_num} ---\n"
                        markdown += "| " + " | ".join(str(h) if h else "" for h in headers) + " |\n"
                        markdown += "|" + "|".join([" --- " for _ in headers]) + "|\n"
                        for row in rows:
                            markdown += "| " + " | ".join(str(cell) if cell else "" for cell in row) + " |\n"
                        full_text += markdown

    return full_text

def chunk_by_heading(text, max_chunk_size=CHUNK_SIZE, overlap=OVERLAP):
    lines = text.split('\n')
    chunks = []
    current_chunk = []
    current_len = 0
    heading_pattern = re.compile(r'^(Step \d+|[0-9]+\.|•|\-|[A-Z][a-z]+ \d+|[A-Z][A-Z\s]+:)')

    for line in lines:
        line_len = len(line) + 1
        is_heading = bool(heading_pattern.match(line.strip()))

        if is_heading and current_chunk and current_len > max_chunk_size * 0.5:
            chunks.append('\n'.join(current_chunk))
            overlap_text = '\n'.join(current_chunk)
            if len(overlap_text) > overlap:
                overlap_text = overlap_text[-overlap:]
            current_chunk = [overlap_text, line]
            current_len = len(overlap_text) + line_len
        else:
            if current_len + line_len > max_chunk_size and current_chunk:
                chunks.append('\n'.join(current_chunk))
                overlap_text = '\n'.join(current_chunk)
                if len(overlap_text) > overlap:
                    overlap_text = overlap_text[-overlap:]
                current_chunk = [overlap_text]
                current_len = len(overlap_text)
            current_chunk.append(line)
            current_len += line_len

    if current_chunk:
        chunks.append('\n'.join(current_chunk))
    return chunks

# ---------- MAIN ----------
print(f"📄 Reading PDF: {PDF_PATH}")
if not os.path.exists(PDF_PATH):
    print(f"ERROR: {PDF_PATH} not found.")
    exit(1)

document_text = extract_text_and_tables(PDF_PATH)
print(f"Extracted {len(document_text)} characters")

chunks = chunk_by_heading(document_text)
print(f"Split into {len(chunks)} heading‑aware chunks")

embedder = SentenceTransformer(EMBED_MODEL)
client = chromadb.PersistentClient(path="./chroma_db")

try:
    client.delete_collection("my_document")
    print("Removed old collection")
except:
    pass

collection = client.create_collection("my_document")

for i, chunk in enumerate(chunks):
    embedding = embedder.encode(chunk).tolist()
    collection.add(documents=[chunk], embeddings=[embedding], ids=[f"chunk_{i}"])

print(f"✅ Indexing complete. {len(chunks)} chunks stored.")