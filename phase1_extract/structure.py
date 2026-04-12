"""
Notebook Structure Parsing
Functions for getting and parsing OneNote XML hierarchy.
"""

import xml.etree.ElementTree as ET
from .powershell import run_powershell

NS = {"one": "http://schemas.microsoft.com/office/onenote/2013/onenote"}


def get_notebook_structure(notebook_id):
    """Get full notebook structure with sections and pages."""
    script = f'''
    $onenote = New-Object -ComObject OneNote.Application
    $hierarchy = ""
    $onenote.GetHierarchy("{notebook_id}", 4, [ref]$hierarchy)
    Write-Output $hierarchy
    '''
    success, stdout, stderr = run_powershell(script)
    if not success:
        return None, []

    try:
        xml_str = stdout.replace('\ufeff', '').replace('\x00', '')
        root = ET.fromstring(xml_str)
        return root, parse_structure(root)
    except Exception as e:
        print(f"  Error parsing structure: {e}")
        return None, []


def parse_structure(root, parent_path=""):
    """Parse XML to extract pages with their section paths."""
    pages = []

    for section_group in root.findall("one:SectionGroup", NS):
        sg_name = section_group.get("name", "Group")
        if sg_name == "_Content Library" or "content library" in sg_name.lower():
            continue
        sg_path = f"{parent_path}/{sg_name}" if parent_path else sg_name
        pages.extend(parse_structure(section_group, sg_path))

    for section in root.findall("one:Section", NS):
        sec_name = section.get("name", "Section")
        sec_path = f"{parent_path}/{sec_name}" if parent_path else sec_name

        for idx, page in enumerate(section.findall("one:Page", NS)):
            pages.append({
                "id": page.get("ID"),
                "name": page.get("name", "Untitled"),
                "section": sec_name,
                "path": sec_path,
                "order": idx
            })

    return pages
