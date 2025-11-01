"""Image indexing functionality - Generate and store image descriptions"""
import os
import time
from utils.helpers import find_media
import torch
import clip
from PIL import Image
import numpy as np
import sqlite3
import time
import os
import json
import ctypes
device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=device)
# image_embeddings, image_paths = None, None


def save_embeddings(image_paths, image_embeddings):
    """
    Saves the embeddings to an SQL file
    :return:
    """
    conn = sqlite3.connect("embeddings.db")
    c = conn.cursor()

    # Create table if it doesn't exist
    c.execute("""
        CREATE TABLE IF NOT EXISTS embeddings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE,
            embedding BLOB
        )
    """)

    for path, embedding in zip(image_paths, image_embeddings):
        embedding = embedding.squeeze().astype(np.float32)  # ensure shape [512], correct type
        c.execute("INSERT OR REPLACE INTO embeddings (path, embedding) VALUES (?, ?)",
                  (path, embedding.tobytes()))

    conn.commit()
    conn.close()
    print("Embeddings stored successfully!")


def index_images(path_list: list = None, progress_callback=None) -> dict:
    """
    Index images by generating descriptions for semantic search.
    
    Args:
        path_list: List of directory paths to scan for images
        progress_callback: Callback function(current, total) for progress updates
    
    Returns:
        dict with status, message, and count
    """
    try:
        print(f"Starting image indexing from {len(path_list)} path(s)...")
        images = find_media(path_list)
        print(f"Found {len(images)} images to index")
        
        image_embeddings = []
        for idx, path in enumerate(images):
            image = preprocess(Image.open(path)).unsqueeze(0).to(device)
            with torch.no_grad():
                embedding = model.encode_image(image)
                embedding = embedding / embedding.norm(dim=-1, keepdim=True)  # Normalize
            image_embeddings.append(embedding.cpu().numpy().squeeze())  # Save as shape [512]
            
            if progress_callback and idx % 10 == 0:
                progress_callback(idx, len(images))
        
        save_embeddings(images, image_embeddings)
        print("Image indexing complete!")
        
        return {
            "status": "success",
            "message": f"Successfully indexed {len(images)} images from {len(path_list)} path(s)",
            "count": len(images)
        }
    except Exception as e:
        print(f"Error indexing images: {e}")
        return {
            "status": "error",
            "message": f"Failed to index images: {e}",
            "count": 0
        }
