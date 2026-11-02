# Exports a .docx to a PDF next to it with Microsoft Word.
#   powershell -ExecutionPolicy Bypass -File docs\submission\to_pdf.ps1 deliverables\Group19_Capstone_exe_summary.docx
param([Parameter(Mandatory = $true)][string]$Docx)
$full = (Resolve-Path $Docx).Path
$pdf = [IO.Path]::ChangeExtension($full, '.pdf')
$w = New-Object -ComObject Word.Application
$w.Visible = $false
$w.DisplayAlerts = 0
try {
  $d = $w.Documents.Open($full, $false, $true)
  $d.ExportAsFixedFormat($pdf, 17, $false, 0)
  "pages: $($d.ComputeStatistics(2))"
  $d.Close(0)
} finally { $w.Quit() }
"wrote $pdf"
