"""Text/document search functionality - Search within document contents"""
import os
import sqlite3
import numpy as np
from sentence_transformers import SentenceTransformer
from config import TEXT_EMBEDDINGS_DB, TEXT_SEARCH_MODEL

# Initialize model )
model = SentenceTransformer(TEXT_SEARCH_MODEL)

def embed_text(text):
    """Generate embedding for the given text using the sentence transformer model
    param text: str - input text to embed
    return: np.ndarray - embedding vector"""

    emb = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
    return emb.astype(np.float32)



def search_text_content(query: str, limit: int = 50):
    """
    Search for documents containing the query text.
    
    Args:
        query: Search query text
        limit: Maximum number of results to return
    
    Returns:
        List of dicts with file info and matching snippets
    """
    try:
        query_emb = embed_text(query)
        conn = sqlite3.connect(TEXT_EMBEDDINGS_DB)
        cur = conn.cursor()

        cur.execute("SELECT file_path, embedding, content FROM embeddings")
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return []

        scores = []
        for file_path, emb_blob, content in rows:
            emb = np.frombuffer(emb_blob, dtype=np.float32)
            score = cosine_similarity(query_emb, emb)
            scores.append((file_path, score, content))

        # Sort by similarity, filter unique files with best score
        file_best_scores = {}
        for file_path, score, content in scores:
            if file_path not in file_best_scores or score > file_best_scores[file_path][0]:
                file_best_scores[file_path] = (score, content)

        # Convert to list format expected by frontend
        results = []
        for file_path, (score, content) in sorted(file_best_scores.items(), key=lambda x: x[1][0], reverse=True)[:limit]:
            # Extract the text snippet related to the query
            snippet = content[:100] + "..." if len(content) > 100 else content
            
            results.append({
                "name": os.path.basename(file_path),
                "path": file_path,
                "type": os.path.splitext(file_path)[1][1:].upper() if os.path.splitext(file_path)[1] else "FILE",
                "snippet": snippet,
                "score": float(score)
            })

        return results
    except Exception as e:
        print(f"Error searching documents: {e}")
        return []
    
def cosine_similarity(a, b):
    """Calculate cosine similarity between two vectors.
    param a: np.ndarray - first vector"""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


