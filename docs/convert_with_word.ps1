# Update the table of contents in a .docx and save a PDF next to it, using Microsoft Word.
#   powershell -ExecutionPolicy Bypass -File docs\convert_with_word.ps1 docs\Beretta_Demo_Presenter_Guide.docx
param([Parameter(Mandatory = $true)][string]$Docx)
$full = (Resolve-Path $Docx).Path
$pdf = [System.IO.Path]::ChangeExtension($full, ".pdf")
$w = New-Object -ComObject Word.Application
$w.Visible = $false
try {
  $d = $w.Documents.Open($full)
  foreach ($toc in $d.TablesOfContents) { $toc.Update() }
  $d.Save()
  $d.SaveAs2($pdf, 17)   # 17 = PDF
  $d.Close($false)
  "wrote $pdf"
} finally { $w.Quit() }
