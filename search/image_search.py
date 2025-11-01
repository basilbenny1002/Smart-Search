"""Image search functionality - Search images by description"""
import os
import sqlite3
import numpy as np
import clip
import torch
import threading
import time

device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=device)

# Global variables for embeddings cache
image_embeddings = None
image_paths = None
embeddings_loaded = False
last_access_time = None
unload_timer = None
UNLOAD_DELAY = 120  # 2 minutes in seconds


def load_embeddings():
    """
    Loads the embeddings from the SQL database and normalizes them.
    This is called lazily when needed.
    """
    global image_embeddings, image_paths, embeddings_loaded, last_access_time
    
    if embeddings_loaded:
        print("Embeddings already loaded, using cached data")
        last_access_time = time.time()
        return image_embeddings, image_paths
    
    print("Loading embeddings from database...")
    conn = sqlite3.connect("embeddings.db")
    c = conn.cursor()

    c.execute("SELECT path, embedding FROM embeddings")
    rows = c.fetchall()

    if not rows:
        print("No embeddings found in database")
        conn.close()
        return None, None

    image_paths = [row[0] for row in rows]

    # Convert bytes back to float32 arrays
    image_embeddings = np.vstack([
        np.frombuffer(row[1], dtype=np.float32) for row in rows
    ])

    # Normalize the embeddings row-wise
    norms = np.linalg.norm(image_embeddings, axis=1, keepdims=True)
    image_embeddings = image_embeddings / norms

    conn.close()
    
    embeddings_loaded = True
    last_access_time = time.time()
    print(f"Loaded {len(image_paths)} image embeddings")
    
    # Start the unload timer
    schedule_unload()
    
    return image_embeddings, image_paths


def unload_embeddings():
    """
    Unloads embeddings from memory to free up RAM.
    """
    global image_embeddings, image_paths, embeddings_loaded, unload_timer
    
    current_time = time.time()
    if last_access_time and (current_time - last_access_time) >= UNLOAD_DELAY:
        print("Unloading embeddings from memory (inactive for 2 minutes)")
        image_embeddings = None
        image_paths = None
        embeddings_loaded = False
        unload_timer = None
    else:
        # Reschedule if there was recent activity
        schedule_unload()


def schedule_unload():
    """
    Schedules automatic unloading of embeddings after inactivity.
    """
    global unload_timer
    
    # Cancel existing timer if any
    if unload_timer:
        unload_timer.cancel()
    
    # Schedule new timer
    unload_timer = threading.Timer(UNLOAD_DELAY, unload_embeddings)
    unload_timer.daemon = True
    unload_timer.start()


def is_embeddings_loaded():
    """
    Check if embeddings are currently loaded in memory.
    """
    return embeddings_loaded


def force_load_embeddings():
    """
    Force load embeddings immediately (called when switching to image search mode).
    """
    return load_embeddings()


def search_images(query: str, limit: int = 50):
    """
    Performs the search on the available embeddings.
    Automatically loads embeddings if not already loaded.
    
    :param query: Search string
    :param limit: Maximum number of results to return
    :return: List of image paths sorted by relevance    
    """
    global last_access_time
    
    # Load embeddings if not loaded
    emb, paths = load_embeddings()
    
    if emb is None or paths is None:
        print("No embeddings available for search")
        return []
    
    # Update last access time
    last_access_time = time.time()
    
    # Perform search
    text = clip.tokenize([query]).to(device)
    
    with torch.no_grad():
        text_embedding = model.encode_text(text)
        text_embedding = text_embedding / text_embedding.norm(dim=-1, keepdim=True)  # Normalize

    text_embedding = text_embedding.cpu().numpy()
    similarities = (text_embedding @ emb.T).squeeze(0)
    indices = similarities.argsort()[::-1][:limit]
    
    return [paths[i] for i in indices]
