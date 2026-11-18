param([switch]$Remove)

$ErrorActionPreference = 'Stop'
$name = 'SimpleVizioLauncher'
$key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
if ($Remove) {
    Remove-ItemProperty -LiteralPath $key -Name $name -ErrorAction SilentlyContinue
    Write-Output 'Automatic startup removed. Stop any running launcher separately.'
    exit
}

$script = Join-Path $PSScriptRoot 'launcher.py'
$config = Join-Path $PSScriptRoot 'config.json'
if (!(Test-Path -LiteralPath $script) -or !(Test-Path -LiteralPath $config)) {
    throw 'Keep this script beside launcher.py and pair the TV first, so config.json exists.'
}
$python = (Get-Command python.exe -ErrorAction Stop).Source
$pythonw = Join-Path (Split-Path -Parent $python) 'pythonw.exe'
if (!(Test-Path -LiteralPath $pythonw)) {
    throw 'pythonw.exe was not found beside python.exe. Install Python for Windows or create a startup shortcut manually.'
}
$value = '"{0}" "{1}" run' -f $pythonw, $script
New-ItemProperty -LiteralPath $key -Name $name -Value $value -PropertyType String -Force | Out-Null
Write-Output 'Automatic startup configured for your Windows account. Sign in after restart to start the launcher.'
