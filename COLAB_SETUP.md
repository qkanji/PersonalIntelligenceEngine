# Google Colab Setup Guide

## Colab Notebook Cells (Copy these into a new Colab notebook)

### Cell 1: Check GPU and Mount Drive
```python
# Check GPU
!nvidia-smi

# Mount Google Drive
from google.colab import drive
drive.mount('/content/drive')
```

### Cell 2: Install Dependencies
```python
!pip install -q marker-pdf pypdfium2 tqdm
```

### Cell 3: Setup Directories
```python
import os

# Set paths (adjust these to match your Drive folder structure)
BASE_DIR = "/content/drive/MyDrive/PersonalIntelligenceEngine"
PDF_DIR = f"{BASE_DIR}/notebooks_pdf"
MD_DIR = f"{BASE_DIR}/notebooks_md"

# Create markdown output directory
os.makedirs(MD_DIR, exist_ok=True)

print(f"PDF Directory: {PDF_DIR}")
print(f"Output Directory: {MD_DIR}")

# Verify PDF folder exists
if os.path.exists(PDF_DIR):
    print(f"✓ Found PDF directory")
    # List notebooks
    notebooks = [d for d in os.listdir(PDF_DIR) if os.path.isdir(os.path.join(PDF_DIR, d))]
    print(f"  Notebooks: {notebooks}")
else:
    print("✗ PDF directory not found. Upload your notebooks_pdf folder to Drive first!")
```

### Cell 4: Copy Phase 2 Code Modules
```python
# Create phase2_ocr package
os.makedirs("phase2_ocr", exist_ok=True)

# Write pdf_slicer.py
with open("phase2_ocr/pdf_slicer.py", "w") as f:
    f.write('''
import os
import math
import tempfile
import pypdfium2 as pdfium

def get_page_count(pdf_path):
    doc = pdfium.PdfDocument(pdf_path)
    count = len(doc)
    doc.close()
    return count

def split_pdf(pdf_path):
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
        with open(tmp_path, "wb") as ff:
            single.save(ff)
        single.close()
        page_paths.append(tmp_path)

    doc.close()
    return page_paths

def cleanup_splits(page_paths, original_path):
    for p in page_paths:
        if p != original_path and os.path.exists(p):
            os.remove(p)
    if page_paths and page_paths[0] != original_path:
        tmp_dir = os.path.dirname(page_paths[0])
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass
''')

# Write marker_engine.py  
with open("phase2_ocr/marker_engine.py", "w") as f:
    f.write('''
import os
import contextlib
import torch
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.config.parser import ConfigParser
from phase2_ocr.pdf_slicer import split_pdf, cleanup_splits

class MarkerEngine:
    _instance = None
    _converter = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _init_converter(self):
        if self._converter is not None:
            return
        print("Loading marker-pdf models...")
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
        self._init_converter()
        page_paths = split_pdf(pdf_path)
        try:
            parts = []
            for p in page_paths:
                with open(os.devnull, 'w') as devnull:
                    with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
                        result = self._converter(p)
                parts.append(result.markdown)
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            return "\\n\\n".join(parts)
        finally:
            cleanup_splits(page_paths, pdf_path)
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

def convert_pdf_to_markdown(pdf_path: str) -> str:
    engine = MarkerEngine()
    return engine.convert(pdf_path)
''')

# Write utils.py
with open("phase2_ocr/utils.py", "w") as f:
    f.write('''
import os
import json

def find_notebook_folders(pdf_dir):
    notebooks = []
    if not os.path.exists(pdf_dir):
        return notebooks
    for item in os.listdir(pdf_dir):
        item_path = os.path.join(pdf_dir, item)
        if os.path.isdir(item_path):
            structure_file = os.path.join(item_path, "_structure.json")
            if os.path.exists(structure_file):
                notebooks.append({
                    'folder': item_path,
                    'name': item,
                    'structure_file': structure_file
                })
    return notebooks

def safe_filename(notebook, section, page_name, order):
    def sanitize(s):
        return "".join(c if c.isalnum() or c in " -_" else "_" for c in s).strip()
    nb = sanitize(notebook)[:50]
    sec = sanitize(section.replace('/', '_').replace('\\\\', '_'))[:50]
    pg = sanitize(page_name)[:50]
    return f"{nb}__{sec}__{order:03d}_{pg}.md"

def create_md_header(pdf_path, notebook, section, page_name, order):
    return f"""---
source_pdf: {pdf_path}
notebook: {notebook}
section: {section}
page: {page_name}
order: {order}
---

# {page_name}

"""
''')

# Create __init__.py
with open("phase2_ocr/__init__.py", "w") as f:
    f.write("")

print("✓ Phase 2 modules created")
```

### Cell 5: Run Processing
```python
import sys
import json
import time
import logging
from tqdm.notebook import tqdm  # Use notebook-friendly tqdm

from phase2_ocr.marker_engine import convert_pdf_to_markdown
from phase2_ocr.utils import find_notebook_folders, safe_filename, create_md_header

def format_time(seconds):
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"

def process_page(pdf_path, notebook, section, page_name, order):
    header = create_md_header(pdf_path, notebook, section, page_name, order)
    content = convert_pdf_to_markdown(pdf_path)
    return header + content

# Suppress logs
for name in ["marker", "surya", "texify", "PIL"]:
    logging.getLogger(name).setLevel(logging.WARNING)

print("=" * 60)
print("Phase 2: PDF to Markdown (Google Colab - GPU)")
print("=" * 60)

notebooks = find_notebook_folders(PDF_DIR)
print(f"\\nFound {len(notebooks)} notebook(s)")

total_processed = 0
total_skipped = 0
overall_start = time.time()

for nb in notebooks:
    print(f"\\n{'='*60}")
    print(f"Processing: {nb['name']}")
    print('='*60)

    with open(nb['structure_file'], 'r', encoding='utf-8') as f:
        structure = json.load(f)

    pages = structure.get('pages', [])
    notebook_name = structure.get('notebook', nb['name'])
    print(f"  Found {len(pages)} page(s)")

    nb_start = time.time()
    processed = 0
    skipped = 0

    pbar = tqdm(pages, desc="  Converting", unit="page")

    for page_info in pbar:
        pdf_path = page_info['path']

        if not os.path.exists(pdf_path):
            continue

        md_filename = safe_filename(
            notebook_name,
            page_info['section'],
            page_info['name'],
            page_info['order']
        )
        md_path = os.path.join(MD_DIR, md_filename)

        # Skip if already processed
        if os.path.exists(md_path):
            skipped += 1
            total_skipped += 1
            continue

        try:
            md_content = process_page(
                pdf_path, notebook_name,
                page_info['section'],
                page_info['name'],
                page_info['order']
            )
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(md_content)

            processed += 1
            total_processed += 1

            # Update progress
            avg_time = (time.time() - nb_start) / max(processed, 1)
            remaining = len(pages) - pbar.n - skipped
            eta = avg_time * remaining

            pbar.set_postfix({'avg': f'{avg_time:.1f}s', 'eta': format_time(eta)})

        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                print(f"  ⚠ GPU OOM on {page_info['name']}, skipping...")
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            else:
                print(f"  ✗ Error: {page_info['name']}: {e}")
        except Exception as e:
            print(f"  ✗ Error: {page_info['name']}: {e}")

    pbar.close()

    # Notebook summary
    nb_time = time.time() - nb_start
    print(f"  ✓ Completed {processed}/{len(pages)} pages in {format_time(nb_time)}")
    if skipped > 0:
        print(f"  ⤭ Skipped {skipped} already-processed pages")
    if processed > 0:
        print(f"  Average: {nb_time/processed:.1f}s per page")

# Final summary
total_time = time.time() - overall_start
print("\\n" + "=" * 60)
print("Processing Complete")
print("=" * 60)
print(f"Processed: {total_processed} pages")
if total_skipped > 0:
    print(f"Skipped: {total_skipped} already-processed pages")
print(f"Total time: {format_time(total_time)}")
if total_processed > 0:
    print(f"Average: {total_time/total_processed:.1f}s per page")
print(f"Output: {MD_DIR}")
```

---

## Usage Instructions

1. **Upload PDFs**: Put your `notebooks_pdf/` folder in Google Drive at `/MyDrive/PersonalIntelligenceEngine/`
2. **Create Notebook**: New Colab notebook → Copy all cells above
3. **Run Cell 1**: Authorize Drive access
4. **Run Cell 2-4**: Install deps and setup (one-time)
5. **Run Cell 5**: Start processing (this will take ~10-30 min for 35 pages)

## Tips

- **GPU Runtime**: Runtime → Change runtime type → T4 GPU (free tier)
- **Resume**: Re-run Cell 5 - it skips already-processed files
- **Download Results**: Right-click `notebooks_md` folder in Drive → Download
- **Monitor**: Watch GPU usage in cell output and Runtime → Manage sessions

Your markdown files will be saved directly to Google Drive!
