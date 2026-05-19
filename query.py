# query.py
import chromadb
from sentence_transformers import SentenceTransformer, CrossEncoder
import requests
import json
import re

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:3b"
EMBED_MODEL = "all-MiniLM-L6-v2"
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

INITIAL_RESULTS = 15
FINAL_RESULTS = 6
TEMPERATURE = 0.0
MAX_TOKENS = 500

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_collection("my_document")
embedder = SentenceTransformer(EMBED_MODEL)
reranker = CrossEncoder(RERANKER_MODEL)

def ask_llama(prompt):
    response = requests.post(OLLAMA_URL, json={
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS
    })
    return response.json()["response"]

def rerank_chunks(query, chunks):
    pairs = [[query, chunk] for chunk in chunks]
    scores = reranker.predict(pairs)
    scored = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
    return [chunk for chunk, score in scored]

def answer_matches_question_type(question, answer):
    if answer == "Not found in document.":
        return True
    q_lower = question.lower()
    if "keyboard shortcut" in q_lower or "shortcut key" in q_lower:
        if not re.search(r'[A-Za-z]+[\+\-][A-Za-z0-9\+\-]+', answer):
            return False
    if re.search(r'(how much space|distance|measurement|pt|inch|mm|cm)', q_lower):
        if not re.search(r'\d+(\.\d+)?\s*(pt|inch|in|mm|cm|")', answer, re.IGNORECASE):
            return False
    if re.search(r'(version|v\.|release)', q_lower):
        if not re.search(r'\d+(\.\d+)+', answer):
            return False
    return True

question = input("🔍 Ask a question about the document: ")
q_emb = embedder.encode(question).tolist()
initial = collection.query(query_embeddings=[q_emb], n_results=INITIAL_RESULTS)
initial_chunks = initial['documents'][0]
reranked = rerank_chunks(question, initial_chunks)
top_chunks = reranked[:FINAL_RESULTS]
context = "\n---\n".join(top_chunks)

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

raw_answer = ask_llama(prompt).strip()
if answer_matches_question_type(question, raw_answer):
    final_answer = raw_answer
else:
    final_answer = "Not found in document."

print("\n📖 Exact answer from document:")
print(final_answer)