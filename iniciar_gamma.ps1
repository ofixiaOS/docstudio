param(
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$baseDir = $PSScriptRoot
$backendDir = Join-Path $baseDir 'backend'
$frontendDir = Join-Path $baseDir 'frontend'
$dataDir = Join-Path $backendDir 'data'
$logsDir = Join-Path $dataDir 'logs'
$venvPython = Join-Path $backendDir '.venv\Scripts\python.exe'
$requirements = Join-Path $backendDir 'requirements.txt'
$requirementsHashFile = Join-Path $dataDir '.requirements.sha256'
$viteScript = Join-Path $frontendDir 'node_modules\vite\bin\vite.js'

function Get-Sha256Hex([string]$Path) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        return ([System.BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '')
    }
    finally {
        $stream.Dispose()
        $sha.Dispose()
    }
}

New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

Write-Host 'Iplacex Studio' -ForegroundColor Cyan
Write-Host 'Preparando el entorno local...' -ForegroundColor DarkGray

if (-not (Test-Path -LiteralPath $venvPython)) {
    $systemPython = (Get-Command python -ErrorAction Stop).Source
    & $systemPython -m venv (Join-Path $backendDir '.venv')
}

$requirementsHash = Get-Sha256Hex $requirements
$installedHash = if (Test-Path -LiteralPath $requirementsHashFile) {
    (Get-Content -LiteralPath $requirementsHashFile -Raw).Trim()
} else { '' }
if ($requirementsHash -ne $installedHash) {
    Write-Host 'Instalando dependencias del backend...' -ForegroundColor Yellow
    & $venvPython -m pip install --disable-pip-version-check -q -r $requirements
    Set-Content -LiteralPath $requirementsHashFile -Value $requirementsHash -Encoding ascii
}

if (-not (Test-Path -LiteralPath $viteScript)) {
    Write-Host 'Instalando dependencias del frontend...' -ForegroundColor Yellow
    $npm = (Get-Command npm.cmd -ErrorAction Stop).Source
    & $npm ci --prefix $frontendDir
}

$node = (Get-Command node -ErrorAction Stop).Source
$backendOut = Join-Path $logsDir 'backend.out.log'
$backendErr = Join-Path $logsDir 'backend.err.log'
$frontendOut = Join-Path $logsDir 'frontend.out.log'
$frontendErr = Join-Path $logsDir 'frontend.err.log'

$backend = Start-Process -FilePath $venvPython -ArgumentList '-m','uvicorn','main:app','--host','127.0.0.1','--port','8765' `
    -WorkingDirectory $backendDir -WindowStyle Hidden -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr -PassThru
$frontend = Start-Process -FilePath $node -ArgumentList $viteScript,'--host','127.0.0.1','--port','5173' `
    -WorkingDirectory $frontendDir -WindowStyle Hidden -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr -PassThru

try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/health' -TimeoutSec 1
            if ($health.status -eq 'ok') { $ready = $true; break }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $ready) {
        throw "El backend no inició. Revisa $backendErr"
    }

    Write-Host 'Listo: http://127.0.0.1:5173' -ForegroundColor Green
    Write-Host "Datos: $dataDir" -ForegroundColor DarkGray
    Write-Host 'Presiona Enter para cerrar la aplicación.' -ForegroundColor DarkGray
    if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:5173' }
    Read-Host | Out-Null
}
finally {
    foreach ($process in @($frontend, $backend)) {
        if ($process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
