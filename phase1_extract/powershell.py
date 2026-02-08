"""
PowerShell Execution Utilities
Low-level functions for running PowerShell scripts.
"""

import subprocess


def run_powershell(script):
    """Run a PowerShell script and return success status and output."""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True
    )
    stdout = result.stdout.decode('utf-8', errors='ignore')
    stderr = result.stderr.decode('utf-8', errors='ignore')
    return result.returncode == 0, stdout, stderr
