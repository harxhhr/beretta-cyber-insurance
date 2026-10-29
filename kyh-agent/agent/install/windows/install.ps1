<#
  Install the KYH agent on Windows as a SYSTEM scheduled task that starts at boot and restarts on failure.
  Run from an elevated PowerShell:

    .\install.ps1 -Server https://collector.example.in:8443 -Token kyh_enr_XXXX -CaFile .\ca.pem

  Requires Python 3.9+ for all users (python.org installer, "Install for all users").
  Why a scheduled task and not a Windows service: a native service needs pywin32 or a wrapper, and the
  agent is deliberately standard-library only. A packaged service (PyInstaller + sc.exe) is future work.
#>
param(
  [Parameter(Mandatory = $true)][string]$Server,
  [Parameter(Mandatory = $true)][string]$Token,
  [Parameter(Mandatory = $true)][string]$CaFile,
  [string]$Python = ""
)
$ErrorActionPreference = "Stop"

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "Run this script from an elevated (Administrator) PowerShell."
}

if (-not $Python) {
  $cmd = Get-Command python.exe -ErrorAction SilentlyContinue
  if (-not $cmd) { $cmd = Get-Command py.exe -ErrorAction SilentlyContinue }
  if (-not $cmd) { throw "Python 3.9+ not found. Install it for all users, or pass -Python C:\Path\python.exe" }
  $Python = $cmd.Source
}
& $Python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)"
if ($LASTEXITCODE -ne 0) { throw "Python 3.9 or newer is required ($Python)" }

$InstallDir = Join-Path $env:ProgramFiles "KYH\Agent"
$DataDir = Join-Path $env:ProgramData "KYH\Agent"
$Here = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)   # the agent\ folder

New-Item -ItemType Directory -Force -Path $InstallDir, $DataDir | Out-Null
if (Test-Path (Join-Path $InstallDir "kyh_agent")) { Remove-Item -Recurse -Force (Join-Path $InstallDir "kyh_agent") }
Copy-Item -Recurse (Join-Path $Here "kyh_agent") $InstallDir
Get-ChildItem -Recurse -Directory -Filter "__pycache__" $InstallDir | Remove-Item -Recurse -Force

# Data folder holds the signing secret: SYSTEM and Administrators only, no inherited access.
icacls $DataDir /inheritance:r /grant:r "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" | Out-Null
Copy-Item $CaFile (Join-Path $DataDir "ca.pem") -Force

Push-Location $InstallDir
& $Python -m kyh_agent enroll --server $Server --token $Token --ca-file (Join-Path $DataDir "ca.pem")
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Enrollment failed" }
Pop-Location

# Quoted: the usual Python path (C:\Program Files\Python313) contains a space.
$action = New-ScheduledTaskAction -Execute "`"$Python`"" -Argument "-m kyh_agent run" -WorkingDirectory $InstallDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
  -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -Hidden
$sys = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName "KYH Live Monitoring Agent" -Action $action -Trigger $trigger -Settings $settings `
  -Principal $sys -Description "Read-only security posture sensor for KYH Cyber Insurance" -Force | Out-Null
Start-ScheduledTask -TaskName "KYH Live Monitoring Agent"

Write-Host ""
Write-Host "Installed. Useful commands (elevated PowerShell):"
Write-Host "  Get-ScheduledTask -TaskName 'KYH Live Monitoring Agent' | Get-ScheduledTaskInfo"
Write-Host "  cd '$InstallDir'; & '$Python' -m kyh_agent status"
Write-Host "  cd '$InstallDir'; & '$Python' -m kyh_agent show-policy"
