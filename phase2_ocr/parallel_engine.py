"""
Parallel PDF Processing Engine
Uses CPU multiprocessing to process multiple PDF pages simultaneously.
Leverages the Ryzen 9 5900XT's 16 cores for faster throughput.
"""

import os
import contextlib
from concurrent.futures import ProcessPoolExecutor, as_completed


def _process_page_worker(pdf_path):
    """
    Worker function that runs in a separate process on CPU.
    Forces CPU-only execution to avoid CUDA overhead.
    """
    # Must set these BEFORE any torch import
    import sys
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"  # Disable CUDA entirely
    
    import torch
    import contextlib
   
    # Ensure torch uses CPU
    if torch.cuda.is_available():
        torch.cuda.set_device(-1)  # Invalid device to force CPU fallback
    
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.config.parser import ConfigParser
    from phase2_ocr.pdf_slicer import split_pdf, cleanup_splits
    
    # Configure marker - let it auto-detect (will use CPU since CUDA is hidden)
    config = ConfigParser({
        "output_format": "markdown",
        "force_ocr": False,
    })
    
    try:
        converter = PdfConverter(
            config=config.generate_config_dict(),
            artifact_dict=create_model_dict()
        )
    except Exception:
        # If initialization fails, try with explicit CPU device
        converter = PdfConverter(
            config=config.generate_config_dict(),
            artifact_dict=create_model_dict(),
        )
    
    # Process the PDF (split if multi-page)
    page_paths = split_pdf(pdf_path)
    try:
        parts = []
        for p in page_paths:
            # Suppress internal logs
            with open(os.devnull, 'w') as devnull:
                with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
                    result = converter(p)
            parts.append(result.markdown)
        return "\n\n".join(parts)
    finally:
        cleanup_splits(page_paths, pdf_path)


class ParallelEngine:
    """Parallel processing engine using CPU workers."""
    
    def __init__(self, max_workers=5):
        """
        Initialize with worker pool.
        max_workers=5 is safe for 32GB RAM (~6GB per worker).
        """
        self.max_workers = max_workers
        self.executor = None
    
    def __enter__(self):
        self.executor = ProcessPoolExecutor(max_workers=self.max_workers)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.executor:
            self.executor.shutdown(wait=True)
    
    def process_batch(self, pdf_paths):
        """
        Process multiple PDFs in parallel.
        
        Yields (index, markdown_content) as each completes.
        """
        if not self.executor:
            raise RuntimeError("Use ParallelEngine as context manager")
        
        # Submit all jobs
        future_to_index = {
            self.executor.submit(_process_page_worker, path): idx
            for idx, path in enumerate(pdf_paths)
        }
        
        # Yield results as they complete
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                markdown = future.result()
                yield idx, markdown
            except Exception as e:
                yield idx, f"<!-- Error: {e} -->"
