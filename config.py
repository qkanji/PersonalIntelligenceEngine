"""
Configuration settings for OneNote RAG System.
"""

import os

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Data directories
NOTEBOOKS_PDF_DIR = os.path.join(BASE_DIR, "notebooks_pdf")
NOTEBOOKS_IMAGES_DIR = os.path.join(BASE_DIR, "notebooks_images")
NOTEBOOKS_MARKDOWN_DIR = os.path.join(BASE_DIR, "notebooks_markdown")
CHROMA_DB_DIR = os.path.join(BASE_DIR, "chroma_db")

# Poppler path (for pdf2image)
POPPLER_PATH = os.path.join(
    BASE_DIR, "poppler-24.08.0", "Library", "bin"
)

# PDF to Image settings
PDF_DPI = 300  # High resolution for OCR quality on large pages

# OCR settings
OCR_LANG = "en"  # English

# Chunking settings for embeddings
CHUNK_SIZE = 500  # characters per chunk
CHUNK_OVERLAP = 50  # overlap between chunks


def check_cuda_available():
    """Check if CUDA is available."""
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


# Embedding model selection based on CUDA availability
CUDA_AVAILABLE = check_cuda_available()
EMBEDDING_MODEL = "BAAI/bge-m3" if CUDA_AVAILABLE else "all-MiniLM-L6-v2"


def ensure_directories():
    """Create all necessary directories."""
    dirs = [
        NOTEBOOKS_PDF_DIR,
        NOTEBOOKS_IMAGES_DIR,
        NOTEBOOKS_MARKDOWN_DIR,
        CHROMA_DB_DIR,
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
