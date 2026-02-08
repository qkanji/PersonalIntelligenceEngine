"""
Phase 2 Utility Functions
Helper functions for finding notebooks and creating markdown files.
"""

import os


def find_notebook_folders(pdf_dir):
    """Find all notebook folders containing _structure.json files."""
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
    """Create a safe filename encoding the full path."""
    def sanitize(s):
        return "".join(c if c.isalnum() or c in " -_" else "_" for c in s).strip()

    nb = sanitize(notebook)[:50]
    sec = sanitize(section.replace('/', '_').replace('\\', '_'))[:50]
    pg = sanitize(page_name)[:50]
    return f"{nb}__{sec}__{order:03d}_{pg}.md"


def create_md_header(pdf_path, notebook, section, page_name, order):
    """Create a metadata header for the markdown file."""
    return f"""---
source_pdf: {pdf_path}
notebook: {notebook}
section: {section}
page: {page_name}
order: {order}
---

# {page_name}

"""
