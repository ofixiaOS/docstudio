param(
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$baseDir = $PSScriptRoot
$backendDir = Join-Path $baseDir 'backend'
$frontendDir = Join-Path $baseDir 'frontend'
$dataDir = if ($env:GAMMA_DATA_DIR) {
    [System.IO.Path]::GetFullPath($env:GAMMA_DATA_DIR)
} else {
    Join-Path $backendDir 'data'
}
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

function Assert-LocalPortAvailable([int]$Port, [string]$ServiceName) {
    $probe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
    try {
        $probe.Start()
    }
    catch [System.Net.Sockets.SocketException] {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($conn) {
            foreach ($c in $conn) {
                $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
                if ($proc -and ($proc.ProcessName -match 'python|node')) {
                    Write-Host "Liberando puerto $Port ocupado por proceso previo ($($proc.ProcessName), PID $($proc.Id))..." -ForegroundColor Yellow
                    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
                    Start-Sleep -Milliseconds 800
                }
            }
        }
        try {
            $probe2 = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
            $probe2.Start()
            $probe2.Stop()
            return
        }
        catch {
            throw "No se puede iniciar $ServiceName porque el puerto local $Port ya está ocupado. Cierra la instancia anterior y vuelve a ejecutar este script."
        }
    }
    finally {
        $probe.Stop()
    }
}

New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

Write-Host 'DocStudio - Editor de Documentos Asistido por IA' -ForegroundColor Cyan
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

Assert-LocalPortAvailable -Port 8765 -ServiceName 'el backend'
Assert-LocalPortAvailable -Port 5173 -ServiceName 'el frontend'

$backend = $null
$frontend = $null
try {
    $backend = Start-Process -FilePath $venvPython -ArgumentList '-m','uvicorn','main:app','--host','127.0.0.1','--port','8765' `
        -WorkingDirectory $backendDir -WindowStyle Hidden -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr -PassThru

    $backendReady = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        $backend.Refresh()
        if ($backend.HasExited) {
            throw "El backend terminó durante el arranque. Revisa $backendErr"
        }
        try {
            $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/health' -TimeoutSec 1
            if ($health.status -eq 'ok') { $backendReady = $true; break }
        }
        catch {}
        Start-Sleep -Milliseconds 500
    }
    if (-not $backendReady) {
        throw "El backend no respondió durante el arranque. Revisa $backendErr"
    }

    $quotedViteScript = '"' + $viteScript + '"'
    $frontend = Start-Process -FilePath $node -ArgumentList $quotedViteScript,'--host','127.0.0.1','--port','5173' `
        -WorkingDirectory $frontendDir -WindowStyle Hidden -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr -PassThru

    $proxyReady = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        $frontend.Refresh()
        if ($frontend.HasExited) {
            throw "El frontend terminó durante el arranque. Revisa $frontendErr"
        }
        try {
            $health = Invoke-RestMethod -Uri 'http://127.0.0.1:5173/api/health' -TimeoutSec 1
            if ($health.status -eq 'ok') { $proxyReady = $true; break }
        }
        catch {}
        Start-Sleep -Milliseconds 500
    }
    if (-not $proxyReady) {
        throw "La aplicación no respondió a través del proxy de Vite. Revisa $frontendErr"
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
