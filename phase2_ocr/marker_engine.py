"""
Marker-PDF Wrapper
Converts PDF files to Markdown using marker-pdf with GPU acceleration.
"""

import torch
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.config.parser import ConfigParser


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

        # Configure for GPU if available
        config_parser = ConfigParser({
            "output_format": "markdown",
            "force_ocr": True,  # Force OCR for handwriting
        })

        # Create model dict - this loads all required models
        self._converter = PdfConverter(
            config=config_parser.generate_config_dict(),
            artifact_dict=create_model_dict(),
        )

        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Marker-pdf ready on: {device.upper()}")

    def convert(self, pdf_path: str) -> str:
        """
        Convert a single PDF to Markdown.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Markdown string
        """
        self._init_converter()

        # Run conversion
        result = self._converter(pdf_path)

        # Extract markdown from result
        return result.markdown


def get_engine() -> MarkerEngine:
    """Get the singleton MarkerEngine instance."""
    return MarkerEngine()


def convert_pdf_to_markdown(pdf_path: str) -> str:
    """
    Convenience function to convert a PDF to Markdown.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Markdown string
    """
    engine = get_engine()
    return engine.convert(pdf_path)
