param(
    [Parameter(Mandatory = $true)]
    [string]$WorkbookPath,

    [ValidateRange(15, 600)]
    [int]$TimeoutSeconds = 150
)

$ErrorActionPreference = "Stop"
$excel = $null
$workbooks = $null
$workbook = $null
$circularReference = $null
$failureMessage = $null
$excelProcessId = $null

Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class ExcelWindowProcessLookup
{
    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
"@

try {
    $resolvedPath = (Resolve-Path -LiteralPath $WorkbookPath).Path
    $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    $candidateDirectory = Split-Path -Parent $resolvedPath
    $candidateName = Split-Path -Leaf $resolvedPath

    if (-not $candidateDirectory.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Workbook candidate must be under the system temporary directory."
    }
    if ((Split-Path -Leaf $candidateDirectory) -notlike "nike-excel-model-*") {
        throw "Workbook candidate directory does not match the approved temporary naming convention."
    }
    if ($candidateName -ne "nike_valuation_model.candidate.xlsx") {
        throw "Workbook candidate filename does not match the approved naming convention."
    }
    if ([System.IO.Path]::GetExtension($resolvedPath) -ne ".xlsx") {
        throw "Workbook candidate must be an .xlsx file."
    }

    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.EnableEvents = $false
    $excel.AskToUpdateLinks = $false
    $excel.AutomationSecurity = 3
    [uint32]$createdProcessId = 0
    [void][ExcelWindowProcessLookup]::GetWindowThreadProcessId(
        [IntPtr]$excel.Hwnd,
        [ref]$createdProcessId
    )
    if ($createdProcessId -eq 0) {
        throw "Could not identify the dedicated Excel process."
    }
    $excelProcessId = [int]$createdProcessId

    $workbooks = $excel.Workbooks
    $workbook = $workbooks.Open($resolvedPath, 0, $false, 5, "", "", $true, 2, "", $false, $false, 0, $false, $false, $false)
    if ($workbook.ReadOnly) {
        throw "Excel opened the workbook candidate as read-only."
    }
    $workbook.ForceFullCalculation = $true
    $excel.Calculation = -4105
    $excel.CalculateFullRebuild()

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $calculationState = [int]$excel.CalculationState
    while ($calculationState -eq 1) {
        if ([DateTime]::UtcNow -ge $deadline) {
            throw "Excel calculation timed out with state $calculationState."
        }
        Start-Sleep -Milliseconds 250
        $calculationState = [int]$excel.CalculationState
    }

    $calculationState = [int]$excel.CalculationState
    while ($calculationState -eq 1) {
        if ([DateTime]::UtcNow -ge $deadline) {
            throw "Excel calculation timed out while restoring automatic mode with state $calculationState."
        }
        Start-Sleep -Milliseconds 250
        $calculationState = [int]$excel.CalculationState
    }

    $circularReference = $excel.CircularReference
    if ($null -ne $circularReference) {
        throw "Workbook contains a circular reference."
    }

    $workbook.Save()
    $workbook.Close($true)
    [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($workbook)
    $workbook = $null
    [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($workbooks)
    $workbooks = $null
    $excel.Quit()
    [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($excel)
    $excel = $null
}
catch {
    $safeMessage = $_.Exception.Message
    if ($null -ne $resolvedPath) {
        $safeMessage = $safeMessage.Replace($resolvedPath, "<candidate>")
    }
    $failureMessage = "Excel recalculation failed: " + $safeMessage
}
finally {
    if ($null -ne $workbook) {
        try { $workbook.Close($false) } catch { }
        try { [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($workbook) } catch { }
    }
    if ($null -ne $circularReference) {
        try { [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($circularReference) } catch { }
    }
    if ($null -ne $workbooks) {
        try { [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($workbooks) } catch { }
    }
    if ($null -ne $excel) {
        try { $excel.Quit() } catch { }
        try { [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($excel) } catch { }
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

if ($null -ne $failureMessage) {
    throw $failureMessage
}

Write-Output "Excel recalculation completed. DedicatedProcessId=$excelProcessId"
