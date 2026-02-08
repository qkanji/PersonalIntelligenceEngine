"""
Manual PDF Helper
Checks for PDFs in notebooks_pdf/ folder and prepares them for Phase 2
"""

import os

def main():
    """Check for manually exported PDFs."""
    pdf_dir = os.path.join(os.path.dirname(__file__), "notebooks_pdf")

    print("=" * 50)
    print("Manual PDF Helper")
    print("=" * 50)
    print()
    print("Checking for PDFs in:", pdf_dir)
    print()

    if not os.path.exists(pdf_dir):
        os.makedirs(pdf_dir)
        print("Created notebooks_pdf/ folder")
        print()
        print("NEXT STEPS:")
        print("1. Manually export your OneNote notebooks as PDF")
        print("2. Place them in:", pdf_dir)
        print("3. Run this script again to verify")
        print()
        print("How to export from OneNote:")
        print("  - Open OneNote desktop app")
        print("  - Right-click notebook > Export > PDF")
        print("  - Save to the folder above")
        return

    # Check for PDFs
    pdfs = [f for f in os.listdir(pdf_dir) if f.endswith('.pdf')]

    if not pdfs:
        print("No PDFs found yet.")
        print()
        print("NEXT STEPS:")
        print("1. Manually export your OneNote notebooks as PDF")
        print("2. Place them in:", pdf_dir)
        print("3. Run this script again to verify")
        print()
        print("How to export from OneNote:")
        print("  - Open OneNote desktop app")
        print("  - Right-click notebook > Export > PDF")
        print("  - Save to the folder above")
    else:
        print(f"Found {len(pdfs)} PDF(s):")
        print()
        total_size = 0
        for pdf in pdfs:
            path = os.path.join(pdf_dir, pdf)
            size_mb = os.path.getsize(path) / (1024 * 1024)
            total_size += size_mb
            print(f"  ✓ {pdf} ({size_mb:.2f} MB)")

        print()
        print("=" * 50)
        print(f"Total: {len(pdfs)} PDF(s), {total_size:.2f} MB")
        print("=" * 50)
        print()
        print("Ready for Phase 2!")
        print("Next step: Run 'python 2_ocr_process.py'")


if __name__ == "__main__":
    main()
