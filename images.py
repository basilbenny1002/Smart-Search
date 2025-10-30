import torch
import clip
from PIL import Image
import numpy as np
import sqlite3
import time
import os
import json
import ctypes
valid_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"}
number_of_files = 0
completed_files = 0
time_per_it = 0

device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=device)
image_embeddings, image_paths = None, None

def is_hidden(filepath):
    """Check if a file or folder is hidden."""
    try:
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(filepath))
        return bool(attrs & 2)  # FILE_ATTRIBUTE_HIDDEN
    except Exception:
        return False
    
def find_media(directories: list):
    """
    Returns a list of valid image directories
    :param directories:
    :return Valid image directories:
    """
    valid_images = []
    for directories in directories:
        for root, _, files in os.walk(directories):
            if is_hidden(root):
                continue
            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()

                if ext in valid_extensions and os.path.getsize(file_path) > 10 * 1024 and 'windows' not in file_path.lower() and 'xampp' not in file_path.lower() and len(file) > 3 and file_path not in valid_images:  # Ignore small files
                    valid_images.append(file_path)
        json_data = {path:"" for path in valid_images}
        with open('file_data.json', 'w') as data:
            json.dump(json_data, data)

    return valid_images

def process_start(chosen_paths: list, update_progress=None):
    """
    Generates the image embeddings for all files in the path passed as the argument and saves them
    :param chosen_paths: List of folder/file paths
    :param update_progress: Optional progress callback
    :return:
    """
    global completed_files, number_of_files, image_embeddings, image_paths
    image_paths = find_media(chosen_paths)
    number_of_files = len(image_paths)
    image_embeddings = []

    for path in image_paths:
        start_time = time.time()
        image = preprocess(Image.open(path)).unsqueeze(0).to(device)
        with torch.no_grad():
            embedding = model.encode_image(image)
            embedding = embedding / embedding.norm(dim=-1, keepdim=True)  # Normalize
        image_embeddings.append(embedding.cpu().numpy().squeeze())  # Save as shape [512]
        completed_files += 1

        if update_progress:
            update_progress()

        # Optional debug info
        # print(f"{number_of_files - completed_files} images left")
        # print(f"Time per image: {time.time() - start_time:.6f}s")

    save_embeddings()



def save_embeddings():
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
def search_images(query, image_embeddings, image_paths):
    """
    Performs the search on the available embeddings
    :param query: Search string
    :param image_embeddings: np.ndarray of shape (n_images, 512), already normalized
    :param image_paths: List of image paths corresponding to embeddings
    :return: List of image paths sorted by relevance
    """
    text = clip.tokenize([query]).to(device)
    with torch.no_grad():
        text_embedding = model.encode_text(text)
        text_embedding = text_embedding / text_embedding.norm(dim=-1, keepdim=True)  # Normalize

    text_embedding = text_embedding.cpu().numpy()
    similarities = (text_embedding @ image_embeddings.T).squeeze(0)
    indices = similarities.argsort()[::-1]
    return [image_paths[i] for i in indices]


def load_embeddings():
    """
    Loads the embeddings from the SQL database and normalizes them
    :return:
    """
    global image_embeddings, image_paths
    conn = sqlite3.connect("embeddings.db")
    c = conn.cursor()

    c.execute("SELECT path, embedding FROM embeddings")
    rows = c.fetchall()

    image_paths = [row[0] for row in rows]

    # Convert bytes back to float32 arrays
    image_embeddings = np.vstack([
        np.frombuffer(row[1], dtype=np.float32) for row in rows
    ])

    # Normalize the embeddings row-wise
    norms = np.linalg.norm(image_embeddings, axis=1, keepdims=True)
    image_embeddings = image_embeddings / norms

    conn.close()
    print("Loaded Image Paths:", len(image_paths))
    print("Loaded Embeddings Shape:", image_embeddings.shape)

def process_search(query: str):
    """
    Performs the query search
    :param query:
    :return list of similar image paths:
    """
    load_embeddings()
    return search_images(query, image_embeddings, image_paths)