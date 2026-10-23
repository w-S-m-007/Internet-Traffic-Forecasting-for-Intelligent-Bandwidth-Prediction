param(
    [string]$ReportDirectory = (Join-Path $PSScriptRoot '..\deliverables\report')
)
# Export with installed Microsoft Word when bundled LibreOffice is unavailable.
# Run with PowerShell from the project root. Word is kept hidden and closed.
$reportRoot = (Resolve-Path -LiteralPath $ReportDirectory).Path
$reportDocx = Join-Path $reportRoot 'project_report.docx'
$reportPdf = Join-Path $reportRoot 'project_report.pdf'
$wordApp = $null
$wordDoc = $null
try {
    $wordApp = New-Object -ComObject Word.Application
    $wordApp.Visible = $false
    $wordApp.DisplayAlerts = 0
    $wordDoc = $wordApp.Documents.Open($reportDocx, $false, $true)
    $wordDoc.Fields.Update() | Out-Null
    $wordDoc.ExportAsFixedFormat($reportPdf, 17)
    Write-Output $reportPdf
}
finally {
    if ($null -ne $wordDoc) { $wordDoc.Close(0) }
    if ($null -ne $wordApp) { $wordApp.Quit() }
}
