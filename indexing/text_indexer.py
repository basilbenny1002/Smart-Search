"""Text/document indexing functionality - Index document contents for full-text search"""
import os
import sqlite3
import numpy as np
from typing import List, Callable, Optional, Dict, Any
from sentence_transformers import SentenceTransformer
from PyPDF2 import PdfReader
from docx import Document
from config import TEXT_EMBEDDINGS_DB, TEXT_SEARCH_MODEL, VALID_DOCUMENT_EXTENSIONS

# Initialize model (fully local)
model = SentenceTransformer(TEXT_SEARCH_MODEL)

# ---------- Utility: create DB if not exists ----------
def init_db():
    conn = sqlite3.connect(TEXT_EMBEDDINGS_DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS embeddings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT,
            chunk_index INTEGER,
            embedding BLOB,
            content TEXT
        )
    """)
    conn.commit()
    conn.close()


def find_document_files(paths: List[str]) -> List[str]:
    """Find all document files in the given paths"""
    from config import SKIP_PATTERNS
    
    document_files = []

    for path in paths:
        if not os.path.exists(path):
            continue
            
        if os.path.isfile(path):
            ext = os.path.splitext(path)[1].lower()
            if ext in VALID_DOCUMENT_EXTENSIONS:
                document_files.append(path)
        elif os.path.isdir(path):
            for root, _, files in os.walk(path):
                # Skip hidden and system folders
                if any(skip in root.lower() for skip in ['$recycle', 'system volume', 'windows', 'appdata']):
                    continue
                
                # Skip paths containing skip patterns
                root_lower = root.lower()
                if any(pattern in root_lower for pattern in SKIP_PATTERNS):
                    continue
                    
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in VALID_DOCUMENT_EXTENSIONS:
                        document_files.append(os.path.join(root, file))

    return document_files

# ---------- Step 1: Extract text ----------
def extract_text(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    text = ""

    if ext == ".pdf":
        reader = PdfReader(file_path)
        text = "\n".join([page.extract_text() or "" for page in reader.pages])

    elif ext == ".docx":
        doc = Document(file_path)
        text = "\n".join([p.text for p in doc.paragraphs])

    elif ext in [".txt", ".md"]:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

    else:
        raise ValueError(f"Unsupported file type: {ext}")

    return text.strip()


def chunk_text(text, size=1000, overlap=100):
    words = text.split()
    chunks = []
    for i in range(0, len(words), size - overlap):
        chunk = " ".join(words[i:i + size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def embed_text(text):
    # SentenceTransformer works locally
    emb = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
    return emb.astype(np.float32)


def chunk_and_save(file_path):
    init_db()
    try:
        text = extract_text(file_path)
    except Exception as e:
        print(f"Error extracting text from {file_path}: {e}")
        return
        
    if not text:
        print(f"No readable text found in {file_path}")
        return

    # Chunk if necessary
    chunks = chunk_text(text) if len(text.split()) > 1000 else [text]

    conn = sqlite3.connect(TEXT_EMBEDDINGS_DB)
    cur = conn.cursor()

    for i, chunk in enumerate(chunks):
        try:
            emb = embed_text(chunk)
            cur.execute(
                "INSERT INTO embeddings (file_path, chunk_index, embedding, content) VALUES (?, ?, ?, ?)",
                (file_path, i, emb.tobytes(), chunk),
            )
        except Exception as e:
            print(f"Error embedding chunk {i} from {file_path}: {e}")

    conn.commit()
    conn.close()
    print(f"  Saved {len(chunks)} chunks from {os.path.basename(file_path)}")


# ---------- Step 3: Search Documents ----------
def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))






def index_documents(path_list: List[str] = None, progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Index document contents for text search.
    
    Supported formats: .pdf, .docx, .doc, .txt, .md, .rtf, .odt
    
    Args:
        path_list: List of directory paths to scan for documents
        progress_callback: Callback function for progress updates (stage, current, total, message)
    
    Returns:
        dict with status, message, and count
    """
    try:
        if not path_list:
            return {
                "status": "error",
                "message": "No paths provided",
                "count": 0
            }
        
        # Initialize database
        init_db()
        
        # Stage 1: Scanning
        if progress_callback:
            progress_callback('scanning', 0, 1, 'Scanning for documents...')
        
        print("Scanning for documents...")
        documents = find_document_files(path_list)
        print(f"Found {len(documents)} document files to index")
        
        if len(documents) == 0:
            return {
                "status": "warning",
                "message": "No documents found in specified paths",
                "count": 0
            }
        
        # Stage 2: Indexing
        if progress_callback:
            progress_callback('indexing', 0, len(documents), f'Indexing {len(documents)} documents...')
        
        print("Indexing document contents...")
        for idx, document in enumerate(documents):
            chunk_and_save(document)
            
            if progress_callback:
                progress_callback('indexing', idx + 1, len(documents), f'Indexing: {os.path.basename(document)}')
        
        # Stage 3: Complete
        if progress_callback:
            progress_callback('complete', len(documents), len(documents), f'Indexed {len(documents)} documents')
        
        print("Document indexing complete")
        
        return {
            "status": "success",
            "message": f"Successfully indexed {len(documents)} documents",
            "count": len(documents)
        }
    except Exception as e:
        print(f"Error indexing documents: {e}")
        if progress_callback:
            progress_callback('error', 0, 0, f'Error: {str(e)}')
        
        return {
            "status": "error",
            "message": f"Failed to index documents: {e}",
            "count": 0
        }
