"""Indexing package - File, image, and document indexing"""
from .file_indexer import index_files
from .image_indexer import index_images
from .text_indexer import index_documents

__all__ = ['index_files', 'index_images', 'index_documents']
