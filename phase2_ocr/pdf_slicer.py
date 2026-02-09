"""
PDF Slicer
Splits multi-page PDFs into individual single-page temp files.
OneNote exports can produce multi-page PDFs from a single page,
which overwhelms marker-pdf's VRAM when processed all at once.
Uses pypdfium2 (already installed via marker-pdf).
"""

import os
import tempfile
import pypdfium2 as pdfium


def get_page_count(pdf_path):
    """Return the number of pages in a PDF."""
    doc = pdfium.PdfDocument(pdf_path)
    count = len(doc)
    doc.close()
    return count


def split_pdf(pdf_path):
    """
    Split a multi-page PDF into individual single-page temp files.

    Returns list of temp file paths (caller must clean up).
    For single-page PDFs, returns [original_path] with no temp files.
    """
    doc = pdfium.PdfDocument(pdf_path)
    num_pages = len(doc)

    if num_pages <= 1:
        doc.close()
        return [pdf_path]

    tmp_dir = tempfile.mkdtemp(dir=os.path.dirname(pdf_path))
    page_paths = []

    for i in range(num_pages):
        single = pdfium.PdfDocument.new()
        single.import_pages(doc, [i])

        tmp_path = os.path.join(tmp_dir, f"page_{i:03d}.pdf")
        with open(tmp_path, "wb") as f:
            single.save(f)
        single.close()

        page_paths.append(tmp_path)

    doc.close()
    return page_paths


def cleanup_splits(page_paths, original_path):
    """Remove temp files and directory created by split_pdf."""
    for p in page_paths:
        if p != original_path and os.path.exists(p):
            os.remove(p)

    # Remove temp directory if it's empty
    if page_paths and page_paths[0] != original_path:
        tmp_dir = os.path.dirname(page_paths[0])
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass
