"""
Batch Export Functions
Handles batched PDF export for better performance.
"""

import os
import json
import tempfile
from .powershell import run_powershell


def export_pages_batch(pages_batch):
    """
    Export multiple pages in a single PowerShell session.
    pages_batch: list of dict with 'id' and 'output_path' keys.
    Returns: dict mapping page_id -> (success: bool, error: str)
    """
    batch_file = tempfile.mktemp(suffix='.json')
    with open(batch_file, 'w', encoding='utf-8') as f:
        json.dump(pages_batch, f)

    try:
        batch_file_ps = batch_file.replace('\\', '\\\\')
        script = f'''
        $ErrorActionPreference = "Continue"
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        
        $batchContent = Get-Content "{batch_file_ps}" -Raw -Encoding UTF8
        $batch = $batchContent | ConvertFrom-Json
        $results = @()
        
        foreach ($page in $batch) {{
            $result = @{{
                id = $page.id
                success = $false
                error = ""
            }}
            
            try {{
                $onenote = New-Object -ComObject OneNote.Application
                $onenote.Publish($page.id, $page.output_path, 3, "")
                [System.Runtime.InteropServices.Marshal]::ReleaseComObject($onenote) | Out-Null
                $result.success = $true
            }} catch {{
                $result.error = $_.Exception.Message
            }}
            
            $results += $result
        }}
        
        if ($results.Count -eq 1) {{
            $results[0] | ConvertTo-Json -Compress
        }} else {{
            $results | ConvertTo-Json -Compress
        }}
        '''

        success, stdout, stderr = run_powershell(script)

        if not success or not stdout.strip():
            return {p['id']: (False, stderr) for p in pages_batch}

        # Parse JSON results
        try:
            # Find JSON/List start (first [ or {)
            idx_obj = stdout.find('{')
            idx_arr = stdout.find('[')
            
            if idx_obj == -1 and idx_arr == -1:
                return {p['id']: (False, "No JSON output found") for p in pages_batch}
                
            if idx_obj == -1:
                json_start = idx_arr
            elif idx_arr == -1:
                json_start = idx_obj
            else:
                json_start = min(idx_obj, idx_arr)
            
            if json_start >= 0:
                stdout = stdout[json_start:]
                
            # Attempt to find the end of the JSON to avoid "Extra data" errors from trailing output
            # If it starts with [, it should end with ]
            # If it starts with {, it should end with }
            if stdout.lstrip().startswith('['):
                json_end = stdout.rfind(']')
                if json_end != -1:
                    stdout = stdout[:json_end+1]
            elif stdout.lstrip().startswith('{'):
                json_end = stdout.rfind('}')
                if json_end != -1:
                    stdout = stdout[:json_end+1]

            results = json.loads(stdout)
            if not isinstance(results, list):
                results = [results]

            return {r['id']: (r['success'], r.get('error', '')) for r in results}
        except Exception as e:
            return {p['id']: (False, f"Parse error: {e}") for p in pages_batch}

    finally:
        try:
            os.remove(batch_file)
        except:
            pass
