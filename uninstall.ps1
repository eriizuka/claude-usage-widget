# Removes the shortcuts and the Claude Code plugin. Add -RemoveData to also delete ~/.claude-usage-widget.
param([switch]$RemoveData)
foreach ($dir in 'Desktop', 'Startup') {
    Remove-Item (Join-Path ([Environment]::GetFolderPath($dir)) 'Claude Usage.lnk') -ErrorAction SilentlyContinue
}
Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -like '*widget.pyw*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
if (Get-Command claude -ErrorAction SilentlyContinue) {
    & claude plugin uninstall usage-widget@claude-usage-widget
    & claude plugin marketplace remove claude-usage-widget
}
if ($RemoveData) { Remove-Item (Join-Path $HOME '.claude-usage-widget') -Recurse -ErrorAction SilentlyContinue }
Write-Host 'Uninstalled. You can delete this folder now.'
