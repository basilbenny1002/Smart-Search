"""
Auto-indexing script for individual files/folders
Handles adding/updating entries in file search, image, and text databases
Usage: python auto_index.py <file_path>
"""
import os
import sys
import json
import string
import sqlite3
import numpy as np
from typing import Optional

# Image processing imports
try:
    import torch
    import clip
    from PIL import Image
    CLIP_AVAILABLE = True
except ImportError:
    CLIP_AVAILABLE = False
    print("Warning: CLIP not available. Image indexing will be skipped.")

# Text processing imports
try:
    from sentence_transformers import SentenceTransformer
    from PyPDF2 import PdfReader
    from docx import Document
    TEXT_MODELS_AVAILABLE = True
except ImportError:
    TEXT_MODELS_AVAILABLE = False
    print("Warning: Text processing libraries not available. Document indexing will be skipped.")

from models.data_models import FileData
from config import (
    FILE_SEARCH_DB, IMAGE_EMBEDDINGS_DB, TEXT_EMBEDDINGS_DB, FILE_DATA_JSON,
    VALID_IMAGE_EXTENSIONS, VALID_DOCUMENT_EXTENSIONS, VALID_SYMBOLS,
    SKIP_FOLDERS, SKIP_FILES, SKIP_PATTERNS, MIN_IMAGE_SIZE_KB, TEXT_SEARCH_MODEL,
    INDEXED_PATHS_JSON
)
from utils.helpers import is_hidden, is_accessible, get_value


# Initialize models globally
if CLIP_AVAILABLE:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    clip_model, preprocess = clip.load("ViT-B/32", device=device)

if TEXT_MODELS_AVAILABLE:
    text_model = SentenceTransformer(TEXT_SEARCH_MODEL)


def has_valid_characters(filename: str) -> bool:
    """Check if filename contains only valid characters"""
    ALLOWED = set(string.ascii_letters + string.digits).union(VALID_SYMBOLS)
    return all(ch in ALLOWED for ch in filename)


def should_skip(path: str) -> bool:
    """Check if file/folder should be skipped based on skip patterns"""
    basename = os.path.basename(path)
    basename_lower = basename.lower()
    
    # Check skip files
    if basename_lower in SKIP_FILES:
        return True
    
    # Check skip folders
    if os.path.isdir(path) and basename_lower in SKIP_FOLDERS:
        return True
    
    # Check skip patterns
    if any(pattern in basename_lower for pattern in SKIP_PATTERNS):
        return True
    
    # Check if hidden or inaccessible
    if is_hidden(path) or not is_accessible(path):
        return True
    
    return False


def get_indexed_paths() -> dict:
    """Load indexed paths from JSON file"""
    try:
        if os.path.exists(INDEXED_PATHS_JSON):
            with open(INDEXED_PATHS_JSON, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {'image_paths': [], 'document_paths': []}
    except Exception as e:
        print(f"Warning: Error loading indexed paths: {e}")
        return {'image_paths': [], 'document_paths': []}


def is_path_in_indexed_paths(file_path: str, indexed_paths: list) -> bool:
    """Check if file_path is within any of the indexed paths"""
    file_path = os.path.abspath(file_path)
    
    for indexed_path in indexed_paths:
        indexed_path = os.path.abspath(indexed_path)
        
        # Check if file is within this indexed path
        try:
            # Use os.path.commonpath to check if they share a common root
            common = os.path.commonpath([file_path, indexed_path])
            # If the common path equals the indexed path, file is within it
            if os.path.normcase(common) == os.path.normcase(indexed_path):
                return True
        except ValueError:
            # Different drives on Windows
            continue
    
    return False


def get_file_category(file_type: str) -> str:
    """Determine file category based on file type/extension"""
    if not file_type:
        return 'file'
    
    t = file_type.lower()
    
    if t == 'folder':
        return 'folder'
    if t in ["png", "jpg", "jpeg", "gif", "bmp", "webp", "tiff"]:
        return 'image'
    if t in ["mp4", "mkv", "mov", "avi", "wmv", "flv", "webm"]:
        return 'video'
    if t in ["mp3", "wav", "flac", "m4a", "aac", "ogg"]:
        return 'audio'
    if t in ["zip", "7z", "rar", "tar", "gz"]:
        return 'archive'
    if t in ["pdf", "ppt", "pptx", "xls", "xlsx", "csv", "md", "txt", "rtf", "doc", "docx"]:
        return 'document'
    
    return 'file'


def index_to_file_search_db(file_data: FileData) -> bool:
    """
    Add or update file entry in the file search database.
    Returns True if successful.
    """
    try:
        # Validate filename
        if not has_valid_characters(file_data.file_name):
            print(f"Skipping '{file_data.file_name}' - contains invalid characters")
            return False
        
        # Normalize filename to create prefix key
        normalized_name = file_data.file_name.lower()
        prefix_chars = []
        for char in normalized_name:
            prefix_chars.append(get_value(char))
        normalized_key = ''.join(prefix_chars)
        
        # Get file extension and category
        file_extension = file_data.file_type.lower() if file_data.file_type else 'unknown'
        file_category = get_file_category(file_data.file_type)
        
        # Convert FileData to JSON
        file_json = json.dumps(file_data.to_dict())
        
        # Connect to database
        conn = sqlite3.connect(FILE_SEARCH_DB)
        cursor = conn.cursor()
        
        # Try to insert, or append if exists
        cursor.execute("""
            INSERT INTO file_index (prefix, file_extension, file_category, files_json)
            VALUES (?, ?, ?, json_array(?))
            ON CONFLICT(prefix) DO UPDATE SET
                files_json = json_insert(files_json, '$[#]', json(?))
        """, (normalized_key, file_extension, file_category, file_json, file_json))
        
        conn.commit()
        conn.close()
        
        print(f"✓ Indexed to file search DB: {file_data.file_name} [{file_category}]")
        return True
        
    except Exception as e:
        print(f"✗ Error indexing to file search DB: {e}")
        return False


def index_to_file_data_json(file_path: str) -> bool:
    """
    Add or update image file entry in file_data.json.
    Returns True if successful.
    """
    try:
        # Load existing data
        if os.path.exists(FILE_DATA_JSON):
            with open(FILE_DATA_JSON, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = {}
        else:
            data = {}
        
        # Add or update entry
        data[file_path] = {
            'path': file_path,
            'indexed': True
        }
        
        # Save back to file
        os.makedirs(os.path.dirname(FILE_DATA_JSON), exist_ok=True)
        with open(FILE_DATA_JSON, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        print(f"✓ Updated file_data.json")
        return True
        
    except Exception as e:
        print(f"✗ Error updating file_data.json: {e}")
        return False


def index_image(file_path: str) -> bool:
    """
    Index an image file: add to file_data.json and generate embeddings.
    Returns True if successful.
    """
    if not CLIP_AVAILABLE:
        print("✗ CLIP not available, skipping image indexing")
        return False
    
    try:
        # Check file size
        file_size_kb = os.path.getsize(file_path) / 1024
        if file_size_kb < MIN_IMAGE_SIZE_KB:
            print(f"✗ Image too small ({file_size_kb:.1f} KB < {MIN_IMAGE_SIZE_KB} KB), skipping")
            return False
        
        # Update file_data.json
        index_to_file_data_json(file_path)
        
        # Generate embedding
        image = preprocess(Image.open(file_path)).unsqueeze(0).to(device)
        with torch.no_grad():
            embedding = clip_model.encode_image(image)
            embedding = embedding / embedding.norm(dim=-1, keepdim=True)  # Normalize
        
        embedding_array = embedding.cpu().numpy().squeeze().astype(np.float32)
        
        # Store in database
        conn = sqlite3.connect(IMAGE_EMBEDDINGS_DB)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO embeddings (path, embedding)
            VALUES (?, ?)
        """, (file_path, embedding_array.tobytes()))
        
        conn.commit()
        conn.close()
        
        print(f"✓ Indexed image embeddings")
        return True
        
    except Exception as e:
        print(f"✗ Error indexing image: {e}")
        return False


def extract_text_from_file(file_path: str) -> Optional[str]:
    """Extract text content from various document types"""
    ext = os.path.splitext(file_path)[1].lower()
    
    try:
        if ext == ".pdf":
            reader = PdfReader(file_path)
            text = "\n".join([page.extract_text() or "" for page in reader.pages])
            return text
        
        elif ext == ".docx":
            doc = Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs])
            return text
        
        elif ext in [".txt", ".md"]:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            return text
        
        else:
            print(f"✗ Unsupported document type: {ext}")
            return None
            
    except Exception as e:
        print(f"✗ Error extracting text: {e}")
        return None


def chunk_text(text: str, chunk_size: int = 500) -> list:
    """Split text into chunks of approximately chunk_size characters"""
    words = text.split()
    chunks = []
    current_chunk = []
    current_length = 0
    
    for word in words:
        word_length = len(word) + 1  # +1 for space
        if current_length + word_length > chunk_size and current_chunk:
            chunks.append(' '.join(current_chunk))
            current_chunk = [word]
            current_length = word_length
        else:
            current_chunk.append(word)
            current_length += word_length
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks


def index_document(file_path: str) -> bool:
    """
    Index a document file: extract text and generate embeddings.
    Returns True if successful.
    """
    if not TEXT_MODELS_AVAILABLE:
        print("✗ Text processing libraries not available, skipping document indexing")
        return False
    
    try:
        # Extract text
        text = extract_text_from_file(file_path)
        if not text or not text.strip():
            print(f"✗ No text extracted from document")
            return False
        
        # Split into chunks
        chunks = chunk_text(text, chunk_size=500)
        
        if not chunks:
            print(f"✗ No text chunks created")
            return False
        
        # Generate embeddings for each chunk
        conn = sqlite3.connect(TEXT_EMBEDDINGS_DB)
        cursor = conn.cursor()
        
        # Delete existing entries for this file
        cursor.execute("DELETE FROM embeddings WHERE file_path = ?", (file_path,))
        
        for idx, chunk in enumerate(chunks):
            embedding = text_model.encode(chunk)
            embedding_bytes = np.array(embedding, dtype=np.float32).tobytes()
            
            cursor.execute("""
                INSERT INTO embeddings (file_path, chunk_index, embedding, content)
                VALUES (?, ?, ?, ?)
            """, (file_path, idx, embedding_bytes, chunk))
        
        conn.commit()
        conn.close()
        
        print(f"✓ Indexed document with {len(chunks)} chunks")
        return True
        
    except Exception as e:
        print(f"✗ Error indexing document: {e}")
        return False


def auto_index(file_path: str) -> bool:
    """
    Automatically index a file or folder based on its type.
    
    Args:
        file_path: Absolute path to file or folder to index
    
    Returns:
        True if indexing was successful
    """
    # Normalize path
    file_path = os.path.abspath(file_path)
    
    # Check if path exists
    if not os.path.exists(file_path):
        print(f"✗ Path does not exist: {file_path}")
        return False
    
    # Check if should be skipped
    if should_skip(file_path):
        print(f"✗ Path is in skip list: {file_path}")
        return False
    
    # Get file info
    basename = os.path.basename(file_path)
    
    # Determine file type
    if os.path.isdir(file_path):
        file_type = 'folder'
        ext = None
    else:
        ext = os.path.splitext(basename)[1].lower()
        file_type = ext.strip('.') if ext else 'unknown'
    
    print(f"\n{'='*60}")
    print(f"Auto-indexing: {basename}")
    print(f"Path: {file_path}")
    print(f"Type: {file_type}")
    print(f"{'='*60}\n")
    
    # Create FileData object
    file_data = FileData(basename, file_path, file_type)
    
    # Always index to file search database
    success = index_to_file_search_db(file_data)
    
    # Load indexed paths for images and documents
    indexed_paths = get_indexed_paths()
    
    # If it's an image, check if it's in indexed image paths before indexing embeddings
    if ext in VALID_IMAGE_EXTENSIONS:
        if is_path_in_indexed_paths(file_path, indexed_paths.get('image_paths', [])):
            print(f"\nDetected image file in indexed path, indexing embeddings...")
            image_success = index_image(file_path)
            success = success and image_success
        else:
            print(f"\nImage file not in indexed paths, skipping embedding generation")
            print(f"(Image paths: {indexed_paths.get('image_paths', [])})")
    
    # If it's a document, check if it's in indexed document paths before indexing text
    elif ext in VALID_DOCUMENT_EXTENSIONS:
        if is_path_in_indexed_paths(file_path, indexed_paths.get('document_paths', [])):
            print(f"\nDetected document file in indexed path, indexing text content...")
            doc_success = index_document(file_path)
            success = success and doc_success
        else:
            print(f"\nDocument file not in indexed paths, skipping text indexing")
            print(f"(Document paths: {indexed_paths.get('document_paths', [])})")
    
    print(f"\n{'='*60}")
    print(f"{'✓ INDEXING COMPLETE' if success else '✗ INDEXING FAILED'}")
    print(f"{'='*60}\n")
    
    return success


def main():
    """Main entry point for command-line usage"""
    if len(sys.argv) < 2:
        print("Usage: python auto_index.py <file_path>")
        print("\nExample:")
        print("  python auto_index.py C:\\Users\\Documents\\test.pdf")
        print("  python auto_index.py \"C:\\Users\\Pictures\\photo.jpg\"")
        sys.exit(1)
    
    file_path = sys.argv[1]
    success = auto_index(file_path)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
