# Assembles deliverables/Group19_Capstone_data.zip for the capstone upload.
#   powershell -ExecutionPolicy Bypass -File docs\submission\build_submission_zip.ps1 [-VideoLink <url>]
# The video itself is not packed (it is too large); its Google Drive link goes into the video description.
# Put the log book in deliverables as Group19_Capstone_logbook.<pdf|docx|xlsx>; anything missing is reported.
param([string]$VideoLink)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$del = Join-Path $root 'deliverables'
$name = 'Group19_Capstone_data'
$stage = Join-Path ([IO.Path]::GetTempPath()) $name
$zip = Join-Path $del "$name.zip"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
$missing = @()

function Put($folder, $patterns, $label) {
  $dir = Join-Path $stage $folder
  New-Item -ItemType Directory -Force $dir | Out-Null
  $found = @()
  foreach ($p in $patterns) { $found += Get-ChildItem -LiteralPath $del -File | Where-Object { $_.Name -like $p } }
  if ($found.Count -eq 0) { $script:missing += $label; return }
  foreach ($f in $found) { Copy-Item -LiteralPath $f.FullName -Destination $dir }
}

Put '1_Executive_Summary' @('Group19_Capstone_exe_summary.pdf', 'Group19_Capstone_exe_summary.docx') 'executive summary'
$desc = Join-Path $del 'Group19_Capstone_video_description.txt'
if ($VideoLink) {
  $lines = Get-Content -LiteralPath $desc -Encoding UTF8 | ForEach-Object { if ($_ -like 'Video link:*') { "Video link: $VideoLink" } else { $_ } }
  Set-Content -LiteralPath $desc -Value $lines -Encoding UTF8
}
if (-not (Select-String -LiteralPath $desc -Pattern '^Video link: https?://' -Quiet)) { $missing += 'video link (run with -VideoLink <url>)' }
Put '2_Video' @('Group19_Capstone_video_description.txt') 'video description'
Put '3_Research_Paper' @('Beretta_Research_Paper_IEEE.pdf') 'research paper'
Put '4_Poster' @('Group19_Capstone_Poster.pdf', 'Group19_Capstone_Poster.pptx') 'poster'
Put '5_Log_Book' @('Group19_Capstone_logbook.*') 'log book'

# source code: the committed repository, without the deliverables folder
$src = Join-Path $stage '6_Source_Code'
New-Item -ItemType Directory -Force $src | Out-Null
$srcZip = Join-Path $src 'beretta-cyber-insurance.zip'
Push-Location $root
try { git archive --format=zip --prefix=beretta-cyber-insurance/ -o $srcZip HEAD -- . ':(exclude)deliverables' } finally { Pop-Location }
Set-Content -LiteralPath (Join-Path $src 'README.txt') -Value "Source code of Beretta (Group 19).`r`nRepository: https://github.com/harxhhr/beretta-cyber-insurance`r`nCommit: $((git -C $root rev-parse --short HEAD))`r`nSee README.md inside the archive for how to run the system and its tests." -Encoding UTF8

if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path $stage -DestinationPath $zip
Get-ChildItem -Recurse $stage -File | ForEach-Object { '{0,10:N0}  {1}' -f $_.Length, $_.FullName.Substring($stage.Length + 1) }
Remove-Item $stage -Recurse -Force
"wrote $zip ($([math]::Round((Get-Item $zip).Length / 1MB, 1)) MB)"
if ($missing.Count) { "MISSING: $($missing -join ', ')" }
