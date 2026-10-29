# Fill in every page reference (contents, lists of figures and tables) and save a PDF, using Microsoft Word.
#   powershell -ExecutionPolicy Bypass -File docs\report\finish_with_word.ps1
$docx = Join-Path $PSScriptRoot "Beretta_Capstone_Final_Report.docx"
$pdf = [System.IO.Path]::ChangeExtension($docx, ".pdf")
$w = New-Object -ComObject Word.Application
$w.Visible = $false
try {
  $d = $w.Documents.Open($docx)
  $d.Repaginate()
  for ($i = 0; $i -lt 2; $i++) { [void]$d.Fields.Update(); $d.Repaginate() }   # twice: page numbers settle
  $d.Save()
  $d.SaveAs2($pdf, 17)
  "pages: " + $d.ComputeStatistics(2)
  $d.Close($false)
  "wrote $pdf"
} finally { $w.Quit() }
