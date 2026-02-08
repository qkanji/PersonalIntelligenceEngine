"""
Phase 2: PDF to Markdown Processing
Converts page PDFs from notebooks_pdf/ to individual Markdown files.
Uses marker-pdf with GPU (CUDA) for high-quality conversion.
"""

import os
import sys
import json
import time
from tqdm import tqdm

from phase2_ocr.marker_engine import convert_pdf_to_markdown
from phase2_ocr.utils import find_notebook_folders, safe_filename, create_md_header


# Directories
BASE_DIR = os.path.dirname(__file__)
PDF_DIR = os.path.join(BASE_DIR, "notebooks_pdf")
MD_DIR = os.path.join(BASE_DIR, "notebooks_md")


def format_time(seconds):
    """Format seconds into human-readable time."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        mins = seconds / 60
        return f"{mins:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"



def process_page(pdf_path, notebook, section, page_name, order):
    """Process a single page PDF and return formatted markdown."""
    header = create_md_header(pdf_path, notebook, section, page_name, order)
    content = convert_pdf_to_markdown(pdf_path)
    return header + content


def main():
    print("=" * 50)
    print("Phase 2: PDF to Markdown (marker-pdf)")
    print("=" * 50)

    if not os.path.exists(PDF_DIR):
        print(f"\nError: PDF directory not found: {PDF_DIR}")
        sys.exit(1)

    notebooks = find_notebook_folders(PDF_DIR)
    if not notebooks:
        print(f"\nNo notebooks found in: {PDF_DIR}")
        sys.exit(1)

    print(f"\nFound {len(notebooks)} notebook(s)")
    os.makedirs(MD_DIR, exist_ok=True)

    total_processed = 0
    total_pages = 0
    overall_start = time.time()

    for nb in notebooks:
        print(f"\n{'='*50}")
        print(f"Processing: {nb['name']}")
        print('='*50)

        with open(nb['structure_file'], 'r', encoding='utf-8') as f:
            structure = json.load(f)

        pages = structure.get('pages', [])
        notebook_name = structure.get('notebook', nb['name'])
        total_pages += len(pages)

        print(f"  Found {len(pages)} page(s)")

        nb_start = time.time()
        processed = 0

        # Progress bar with custom format
        pbar = tqdm(pages, desc="  Converting", unit="page",
                    bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]')

        for page_info in pbar:
            page_start = time.time()
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

                # Update progress bar with timing info
                page_time = time.time() - page_start
                avg_time = (time.time() - nb_start) / max(processed, 1)
                remaining_pages = len(pages) - processed
                eta = avg_time * remaining_pages

                pbar.set_postfix({
                    'last': f'{page_time:.1f}s',
                    'avg': f'{avg_time:.1f}s',
                    'eta': format_time(eta)
                })

            except Exception as e:
                pbar.write(f"  ✗ Error: {page_info['name']}: {e}")

        pbar.close()

        # Notebook summary
        nb_time = time.time() - nb_start
        print(f"  ✓ Completed {processed}/{len(pages)} pages in {format_time(nb_time)}")
        if processed > 0:
            print(f"  Average: {nb_time/processed:.1f}s per page")

    # Final summary
    total_time = time.time() - overall_start
    print("\n" + "=" * 50)
    print("Processing Complete")
    print("=" * 50)
    print(f"Processed: {total_processed}/{total_pages} pages")
    print(f"Total time: {format_time(total_time)}")
    if total_processed > 0:
        print(f"Average: {total_time/total_processed:.1f}s per page")
    print(f"Output: {MD_DIR}")
    print("\nNext step: Run 'python 3_generate_embeddings.py'")


if __name__ == "__main__":
    main()
