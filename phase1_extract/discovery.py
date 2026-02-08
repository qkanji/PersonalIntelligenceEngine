"""
OneNote Discovery Module - discovers notebooks via PowerShell COM.
"""
import subprocess
import sys
import xml.etree.ElementTree as ET

NS = {"one": "http://schemas.microsoft.com/office/onenote/2013/onenote"}


def get_notebook_hierarchy():
    """Get the XML hierarchy of all notebooks via PowerShell."""
    script = '''
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $onenote = New-Object -ComObject OneNote.Application
    $hierarchy = ""
    $onenote.GetHierarchy("", 1, [ref]$hierarchy)
    [Console]::Write($hierarchy)
    '''
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True
    )
    if result.returncode != 0:
        raise Exception(result.stderr.decode('utf-8', errors='ignore'))

    xml_str = result.stdout.decode('utf-8', errors='ignore')
    xml_str = xml_str.replace('\ufeff', '').replace('\x00', '')

    # Find start of XML
    for marker in ['<?xml', '<one:']:
        pos = xml_str.find(marker)
        if pos > 0:
            xml_str = xml_str[pos:]
            break
    return xml_str.strip()


def list_notebooks():
    """List all available notebooks and return their info."""
    try:
        xml_str = get_notebook_hierarchy()
    except Exception as e:
        print(f"Error connecting to OneNote: {e}")
        sys.exit(1)

    if not xml_str:
        return []

    root = ET.fromstring(xml_str)
    notebooks = []
    for nb in root.findall(".//one:Notebook", NS):
        notebooks.append({
            "name": nb.get("name"),
            "id": nb.get("ID"),
            "path": nb.get("path", "")
        })
    return notebooks


def display_notebooks(notebooks):
    """Display available notebooks to user."""
    print("\n" + "=" * 50)
    print("Available OneNote Notebooks:")
    print("=" * 50)
    for i, nb in enumerate(notebooks, 1):
        print(f"  [{i}] {nb['name']}")
    print("  [A] All notebooks")
    print("  [Q] Quit")
    print("=" * 50)


def get_user_selection(notebooks):
    """Get user's notebook selection."""
    while True:
        choice = input("\nEnter choice (number, A for all, Q to quit): ").strip()
        if choice.upper() == "Q":
            return None
        if choice.upper() == "A":
            return notebooks
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(notebooks):
                return [notebooks[idx]]
            print(f"Invalid choice. Enter 1-{len(notebooks)}, A, or Q.")
        except ValueError:
            print("Invalid input. Enter a number, A, or Q.")
