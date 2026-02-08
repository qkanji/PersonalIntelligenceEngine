"""
OneNote Export Module
Handles exporting notebooks to PDF format via PowerShell.
Exports each page as a separate PDF, preserving notebook structure.
"""

import os
import time
import json

from .powershell import run_powershell
from .structure import get_notebook_structure
from .batch_export import export_pages_batch


def safe_filename(name):
    """Create a safe filename from a string."""
    return "".join(c if c.isalnum() or c in " -_" else "_" for c in name).strip()


def export_notebook_to_pdf(notebook_id, notebook_name, output_dir):
    """
    Export a notebook page-by-page, saving each as a separate PDF.
    Creates a subfolder for the notebook with structure preserved.
    Uses batched export for performance.
    Returns: (notebook_folder_path, list of exported page info)
    """
    # Create notebook folder
    safe_nb_name = safe_filename(notebook_name)
    notebook_folder = os.path.join(output_dir, safe_nb_name)
    os.makedirs(notebook_folder, exist_ok=True)

    print(f"  Exporting '{notebook_name}'...")
    print(f"  Output folder: {notebook_folder}")

    # Get notebook structure with pages
    print(f"  Discovering pages...")
    _, pages = get_notebook_structure(notebook_id)

    if not pages:
        print(f"  Error: No pages found in notebook")
        return None, []

    print(f"  Found {len(pages)} page(s)")

    # Prepare all paths and create directories
    page_jobs = []
    for page in pages:
        section_path = safe_filename(page["path"]) if page["path"] else "Root"
        section_folder = os.path.join(notebook_folder, section_path)
        os.makedirs(section_folder, exist_ok=True)

        page_filename = f"{page['order']:03d}_{safe_filename(page['name'])}.pdf"
        page_pdf_path = os.path.join(section_folder, page_filename)

        page_jobs.append({
            'page': page,
            'output_path': page_pdf_path
        })

    exported_pages = []
    failed_count = 0

    # Process in batches for performance
    BATCH_SIZE = 50
    total_pages = len(page_jobs)

    for batch_start in range(0, total_pages, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total_pages)
        batch_jobs = page_jobs[batch_start:batch_end]

        # Prepare batch for PowerShell
        batch_data = [
            {'id': job['page']['id'], 'output_path': job['output_path']}
            for job in batch_jobs
        ]

        print(f"  Processing batch {batch_start+1}-{batch_end} of {total_pages}...", end="", flush=True)

        # Export batch
        results = export_pages_batch(batch_data)

        # Wait for files to appear and check results
        time.sleep(1)  # Give files time to be written

        batch_success = 0
        batch_failed = 0
        failed_errors = {}

        for job in batch_jobs:
            page = job['page']
            page_pdf_path = job['output_path']
            page_id = page['id']

            success, error = results.get(page_id, (False, "No result"))

            if success and os.path.exists(page_pdf_path) and os.path.getsize(page_pdf_path) > 0:
                exported_pages.append({
                    "path": page_pdf_path,
                    "name": page["name"],
                    "section": page["path"],
                    "order": page["order"]
                })
                batch_success += 1
            else:
                batch_failed += 1
                failed_count += 1
                # Track unique errors
                if error and error not in failed_errors:
                    failed_errors[error] = 0
                if error:
                    failed_errors[error] += 1

        print(f" ✓ {batch_success} | ✗ {batch_failed}")

        # Show sample errors
        if failed_errors and batch_failed > 0:
            for err, count in list(failed_errors.items())[:2]:
                print(f"    Sample error ({count}x): {err}")


    print(f"\n  Exported: {len(exported_pages)}/{len(pages)} pages")
    if failed_count > 0:
        print(f"  Failed: {failed_count} pages")

    if exported_pages:
        # Save structure metadata
        meta_path = os.path.join(notebook_folder, "_structure.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "notebook": notebook_name,
                "pages": exported_pages
            }, f, indent=2)
        return notebook_folder, exported_pages

    return None, []



def export_notebooks(notebooks, output_dir):
    """Export multiple notebooks and return list of exported notebook folders."""
    print(f"\nExporting {len(notebooks)} notebook(s)...")
    os.makedirs(output_dir, exist_ok=True)

    exported = []
    for nb in notebooks:
        folder_path, pages = export_notebook_to_pdf(
            nb["id"],
            nb["name"],
            output_dir
        )
        if folder_path and pages:
            exported.append({
                "folder": folder_path,
                "name": nb["name"],
                "page_count": len(pages)
            })

    return exported


def print_export_summary(exported, total, output_dir):
    """Print summary of export operation."""
    print("\n" + "=" * 50)
    print("Export Summary")
    print("=" * 50)
    print(f"Successfully exported: {len(exported)}/{total} notebooks")

    if exported:
        print(f"\nPDFs saved to: {output_dir}")
        print("\nExported notebooks:")
        for nb in exported:
            print(f"  - {nb['name']} ({nb['page_count']} pages)")
        print("\nNext step: Run 'python 2_ocr_process.py' to process PDFs")
    else:
        print("\nNo notebooks were exported successfully.")
