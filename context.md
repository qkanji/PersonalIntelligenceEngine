# Personal Intelligence Engine - Project Context

## Overview

This project is a local RAG (Retrieval-Augmented Generation) system designed for a high school student. It uses Microsoft OneNote notebooks as the primary knowledge base. The goal is to allow the student to "chat" with their notes for study purposes.

## Architecture

The system functions in sequential phases, executed via Python scripts.

- **Phase 1: Extraction** (`1_extract_onenote.py`)
  - Uses `pywin32` (COM Automation) to interact with the OneNote Desktop App.
  - Discover notebooks, sections, and pages.
  - Exports each page individually as a PDF to `notebooks_pdf/`.
  - **Status**: Completed & Functional.
  - **Note**: Requires notebooks to be open in OneNote Desktop. Cloud-only/SharePoint notebooks must be exported to `.onepkg` and imported locally first due to COM API limitations.

- **Phase 2: OCR & Conversion** (`2_ocr_process.py`)
  - Converts PDF pages to Markdown.
  - **Tooling**: Switched from `PaddleOCR` to **`marker-pdf`** for better handling of layouts, tables, and potential handwriting.
  - **PDF Slicer** (`phase2_ocr/pdf_slicer.py`): Splits multi-page PDFs into individual single-page temp files before OCR. OneNote exports can produce multi-page PDFs from a single page, which overwhelms VRAM when processed all at once. Uses `pypdfium2`.
  - **Resume**: Skips pages that already have a corresponding `.md` file.
  - **Hardware Usage**: Optimized for RTX 3050 (6GB VRAM) + Ryzen 9 5900XT. CUDA 12.9 enabled.
  - **Output**: Markdown files stored in `notebooks_md/`.
  - **Status**: Functional. Includes progress tracking, ETA, resume, and large-page handling.

- **Phase 3: Embeddings** (Planned)
  - Generate vector embeddings from Markdown content.
  - **Model**: BGE-M3 (if GPU fits) or all-MiniLM-L6-v2.
  - **Library**: `sentence-transformers`.
  - **Status**: Not started.

- **Phase 4: Storage** (Planned)
  - Database: ChromaDB.
  - **Status**: Not started.

- **Phase 5: Chat Interface** (Planned)
  - Web UI or simple chat window to query the RAG system.
  - **Status**: Not started.

## Environment & Configuration

- **OS**: Windows 11
- **Language**: Python 3.10+
- **Virtual Environment**: `.venv`
- **Dependencies**:
  - `pywin32` (OneNote COM)
  - `marker-pdf` (OCR/Conversion)
  - `torch` (CUDA 12.x support)
  - `poppler` (PDF utils)
- **Code Style**:
  - Max ~100 lines per file (strict strictness on this).
  - Modular design: `phase1_extract/` and `phase2_ocr/` packages house logic.

## Recent Progress & History

1. **Extraction Refactor**: Moved from exporting entire notebooks (slow/fails) to page-by-page export. This improved error handling and granularity.
2. **OCR Switch**: Initially planned `PaddleOCR`, but switched to `marker-pdf` to better handle the complex layouts and "gigantic" pages common in OneNote (infinite canvas).
3. **Optimization**: Phase 2 now provides detailed progress bars (`tqdm`) and time estimates to manage the user's expectations for long processing times on consumer hardware.
4. **Multi-Page PDF Fix**: OneNote pages export as multi-page PDFs (up to 15 pages). marker-pdf loads all pages into VRAM at once, causing hangs on 6GB GPUs. Added `pdf_slicer.py` to split PDFs into single pages and process them individually.
5. **Resume Capability**: Phase 2 now skips pages that have already been converted, so re-runs don't repeat work.
6. **Log Suppression**: Suppressed noisy internal logs from `marker`/`surya` so the user's progress bar stays visible.

## Next Steps

1. Verify Phase 2 output quality on complex handwritten notes.
2. Begin Phase 3: Implement embedding generation logic.
3. Ensure GPU memory management is efficient during embedding generation (given 6GB VRAM constraint).
