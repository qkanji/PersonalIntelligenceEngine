"""
Marker-PDF Wrapper
Converts PDF files to Markdown using marker-pdf with GPU acceleration.
Splits multi-page PDFs to process one page at a time (saves VRAM).
"""

import os
import contextlib
import torch
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.config.parser import ConfigParser

from phase2_ocr.pdf_slicer import split_pdf, cleanup_splits


class MarkerEngine:
    """Singleton wrapper for marker-pdf to keep models loaded."""

    _instance = None
    _converter = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _init_converter(self):
        """Initialize the converter with models (downloads on first run)."""
        if self._converter is not None:
            return

        print("Loading marker-pdf models (first run downloads ~2GB)...")

        config_parser = ConfigParser({
            "output_format": "markdown",
            "force_ocr": False,
            "batch_size": 1,
        })

        self._converter = PdfConverter(
            config=config_parser.generate_config_dict(),
            artifact_dict=create_model_dict(),
        )

        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Marker-pdf ready on: {device.upper()}")

    def convert(self, pdf_path: str) -> str:
        """Convert a PDF to Markdown, processing one page at a time."""
        self._init_converter()

        page_paths = split_pdf(pdf_path)
        try:
            parts = []
            for p in page_paths:
                # Suppress marker's internal progress bars
                with open(os.devnull, 'w') as devnull:
                    with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
                        result = self._converter(p)
                parts.append(result.markdown)
                
                # Clear GPU cache after each page to prevent VRAM buildup
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    
            return "\n\n".join(parts)
        finally:
            cleanup_splits(page_paths, pdf_path)
            # Final cleanup
            if torch.cuda.is_available():
                torch.cuda.empty_cache()


def convert_pdf_to_markdown(pdf_path: str) -> str:
    """Convenience function to convert a PDF to Markdown."""
    engine = MarkerEngine()
    return engine.convert(pdf_path)
