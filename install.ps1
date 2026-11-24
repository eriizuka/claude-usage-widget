# Claude Usage Widget installer (Windows). Run from the repo folder:
#   powershell -ExecutionPolicy Bypass -File install.ps1 [-NoStartup]
param([switch]$NoStartup)
$ErrorActionPreference = 'Stop'
$Repo = $PSScriptRoot
$Widget = Join-Path $Repo 'widget\widget.pyw'

Write-Host '1/4 Python and Pillow'
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { throw 'Python 3.10+ not found. Install it from https://www.python.org (tick "Add to PATH") and run again.' }
& python -m pip install --user --quiet -r (Join-Path $Repo 'requirements.txt')
$pythonw = Join-Path (Split-Path $py.Source) 'pythonw.exe'
if (-not (Test-Path $pythonw)) { $pythonw = $py.Source }

Write-Host '2/4 Claude Code plugin (saves your plan limits)'
if (Get-Command claude -ErrorAction SilentlyContinue) {
    & claude plugin marketplace add $Repo
    & claude plugin install usage-widget@claude-usage-widget
    Write-Host '    Plugin installed: limits appear after your next new Claude Code conversation.'
} else {
    Write-Warning 'The claude CLI was not found, so the plugin was not installed. The widget still shows tokens, cost and context.'
    Write-Warning 'For the 5-hour and weekly limits: npm install -g @anthropic-ai/claude-code, then run this installer again.'
}

Write-Host '3/4 Shortcuts'
$shell = New-Object -ComObject WScript.Shell
function New-Shortcut($path) {
    $s = $shell.CreateShortcut($path); $s.TargetPath = $pythonw; $s.Arguments = "`"$Widget`""
    $s.WorkingDirectory = $Repo; $s.IconLocation = (Join-Path $Repo 'widget\icon.ico'); $s.Description = 'Claude Usage Widget'; $s.Save()
}
New-Shortcut (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Claude Usage.lnk')
if (-not $NoStartup) { New-Shortcut (Join-Path ([Environment]::GetFolderPath('Startup')) 'Claude Usage.lnk') }

Write-Host '4/4 Starting the widget'
Start-Process $pythonw "`"$Widget`""
Write-Host 'Done. Drag to move, double-click to switch size, right-click (or the X) to close.'
