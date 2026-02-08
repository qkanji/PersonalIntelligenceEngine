"""
Phase 1: OneNote Notebook Extraction
Discovers OneNote notebooks and exports them as PDFs using COM automation.
"""

import os
from phase1_extract.discovery import (
    list_notebooks,
    display_notebooks,
    get_user_selection
)
from phase1_extract.export import (
    export_notebooks,
    print_export_summary
)


# Output directory for PDFs
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "notebooks_pdf")


def main():
    """Main function to extract OneNote notebooks."""
    print("=" * 50)
    print("OneNote RAG System - Phase 1: Notebook Extraction")
    print("=" * 50)

    # Get available notebooks (uses PowerShell COM internally)
    print("\nDiscovering notebooks...")
    notebooks = list_notebooks()

    if not notebooks:
        print("No notebooks found. Make sure OneNote has synced notebooks.")
        return

    print(f"Found {len(notebooks)} notebook(s)")

    # Display and get selection
    display_notebooks(notebooks)
    selected = get_user_selection(notebooks)

    if selected is None:
        print("\nExiting...")
        return

    # Export selected notebooks
    exported = export_notebooks(selected, OUTPUT_DIR)

    # Print summary
    print_export_summary(exported, len(selected), OUTPUT_DIR)



if __name__ == "__main__":
    main()
