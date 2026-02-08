# OneNote Export Diagnostic Tool
# This script helps diagnose why OneNote export is failing

Write-Host "OneNote Export Diagnostic Tool" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Check 1: OneNote Installation
Write-Host "Checking OneNote installation..." -ForegroundColor Yellow
try {
    $onenote = New-Object -ComObject OneNote.Application
    Write-Host "[OK] OneNote COM object created successfully" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Could not create OneNote COM object: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Check 2: Word Installation (needed for fallback method)
Write-Host "Checking Word installation..." -ForegroundColor Yellow
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $wordVersion = $word.Version
    $word.Quit()
    Write-Host "[OK] Microsoft Word $wordVersion is installed" -ForegroundColor Green
} catch {
    Write-Host "[WARN] Microsoft Word not found - fallback method unavailable" -ForegroundColor Yellow
}

# Check 3: Get Notebooks
Write-Host "Checking available notebooks..." -ForegroundColor Yellow
$hierarchy = ""
try {
    $onenote.GetHierarchy("", 1, [ref]$hierarchy)
    [xml]$xml = $hierarchy
    $ns = New-Object System.Xml.XmlNamespaceManager($xml.NameTable)
    $ns.AddNamespace("one", "http://schemas.microsoft.com/office/onenote/2013/onenote")
    $notebooks = $xml.SelectNodes("//one:Notebook", $ns)
    Write-Host "[OK] Found $($notebooks.Count) notebook(s)" -ForegroundColor Green

    Write-Host ""
    Write-Host "Notebooks:" -ForegroundColor Cyan
    foreach ($nb in $notebooks) {
        Write-Host "  - $($nb.name)" -ForegroundColor White
        Write-Host "    ID: $($nb.ID)" -ForegroundColor Gray
        Write-Host "    Path: $($nb.path)" -ForegroundColor Gray
        Write-Host ""
    }
} catch {
    Write-Host "[FAIL] Could not get notebooks: $($_.Exception.Message)" -ForegroundColor Red
}

# Check 4: Test export on first notebook
if ($notebooks.Count -gt 0) {
    $testNb = $notebooks[0]
    Write-Host "Testing export on first notebook: $($testNb.name)" -ForegroundColor Yellow

    $testPath = Join-Path $env:TEMP "onenote_test.pdf"

    # Try direct PDF export
    Write-Host "  Testing direct PDF export..." -ForegroundColor Gray
    try {
        $onenote.Publish($testNb.ID, $testPath, 1, "")
        Start-Sleep -Seconds 3
        if (Test-Path $testPath) {
            $size = (Get-Item $testPath).Length / 1MB
            Write-Host "  [OK] Direct PDF export works! Size: $([math]::Round($size, 2)) MB" -ForegroundColor Green
            Remove-Item $testPath -ErrorAction SilentlyContinue
        } else {
            Write-Host "  [WARN] Export command succeeded but file not created" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  [FAIL] Direct PDF export failed: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "  Error Code: 0x$($_.Exception.HResult.ToString('X'))" -ForegroundColor Red

        # If Word is available, try Word export
        try {
            Write-Host "  Testing Word export..." -ForegroundColor Gray
            $wordPath = Join-Path $env:TEMP "onenote_test.docx"
            $onenote.Publish($testNb.ID, $wordPath, 0, "")
            Start-Sleep -Seconds 3
            if (Test-Path $wordPath) {
                Write-Host "  [OK] Word export works!" -ForegroundColor Green
                Remove-Item $wordPath -ErrorAction SilentlyContinue
            } else {
                Write-Host "  [FAIL] Word export also failed" -ForegroundColor Red
            }
        } catch {
            Write-Host "  [FAIL] Word export failed: $($_.Exception.Message)" -ForegroundColor Red
        }
    }
}

Write-Host ""
Write-Host "Possible Solutions:" -ForegroundColor Cyan
Write-Host "1. Ensure notebooks are fully synced in OneNote" -ForegroundColor White
Write-Host "2. Try opening the notebook in OneNote desktop app" -ForegroundColor White
Write-Host "3. Check if notebooks are password protected" -ForegroundColor White
Write-Host "4. Try exporting manually: File > Export > PDF in OneNote" -ForegroundColor White
Write-Host "5. Check Windows permissions on the output folder" -ForegroundColor White
