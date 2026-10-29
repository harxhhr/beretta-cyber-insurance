# Remove the KYH agent (elevated PowerShell). Retire the host on the collector first,
# otherwise it goes SILENT after 72 h and counts as failing every warranty control.
$ErrorActionPreference = "SilentlyContinue"
Stop-ScheduledTask -TaskName "KYH Live Monitoring Agent"
Unregister-ScheduledTask -TaskName "KYH Live Monitoring Agent" -Confirm:$false
Remove-Item -Recurse -Force (Join-Path $env:ProgramFiles "KYH\Agent")
Remove-Item -Recurse -Force (Join-Path $env:ProgramData "KYH\Agent")
Write-Host "KYH agent removed."
