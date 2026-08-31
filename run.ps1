param(
    [switch]$SkipInstall,
    [switch]$NoBrowser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$EnvFile = Join-Path $Root ".env"
$EnvExample = Join-Path $Root ".env.example"
$VenvDir = Join-Path $BackendDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$LogDir = Join-Path $Root "tmp\run-logs"

function Write-Step {
    param([string]$Message)
    Write-Host "[PDFMaker] $Message" -ForegroundColor Cyan
}

function Get-RequiredCommand {
    param([string[]]$Names)

    foreach ($name in $Names) {
        $command = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($command) {
            return $command.Source
        }
    }

    throw "Required command not found: $($Names -join ', ')"
}

function Test-Port {
    param([int]$Port)

    $client = [Net.Sockets.TcpClient]::new()
    try {
        $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(200)) {
            return $false
        }
        $client.EndConnect($async)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Invoke-InDirectory {
    param(
        [string]$Directory,
        [string]$FilePath,
        [string[]]$Arguments
    )

    Push-Location $Directory
    try {
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
        }
    } finally {
        Pop-Location
    }
}

function Start-AppProcess {
    param(
        [string]$Name,
        [string]$FilePath,
        [string]$Arguments,
        [string]$WorkingDirectory,
        [string]$OutLog,
        [string]$ErrLog
    )

    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $Arguments `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $OutLog `
        -RedirectStandardError $ErrLog `
        -WindowStyle Hidden `
        -PassThru

    return [pscustomobject]@{
        Name = $Name
        Process = $process
        OutLog = $OutLog
        ErrLog = $ErrLog
    }
}

function Stop-AppProcess {
    param([object]$App)

    if ($null -eq $App) {
        return
    }

    try {
        if (-not $App.Process.HasExited) {
            Write-Step "Stopping $($App.Name)..."
            $App.Process.Kill($true)
            $App.Process.WaitForExit(5000) | Out-Null
        }
    } catch {
        Write-Warning "Could not stop $($App.Name): $($_.Exception.Message)"
    } finally {
        $App.Process.Dispose()
    }
}

function Show-LogTail {
    param(
        [string]$Name,
        [string]$OutLog,
        [string]$ErrLog
    )

    Write-Host ""
    Write-Host "Last output from ${Name}:" -ForegroundColor Yellow
    if (Test-Path $OutLog) {
        Get-Content $OutLog -Tail 40
    }
    if (Test-Path $ErrLog) {
        Get-Content $ErrLog -Tail 40
    }
}

if (-not (Test-Path $BackendDir)) {
    throw "Backend directory not found: $BackendDir"
}

if (-not (Test-Path $FrontendDir)) {
    throw "Frontend directory not found: $FrontendDir"
}

if (-not (Test-Path $EnvFile)) {
    if (-not (Test-Path $EnvExample)) {
        throw ".env is missing and .env.example was not found."
    }

    Copy-Item $EnvExample $EnvFile
    Write-Step "Created .env from .env.example"
}

$python = Get-RequiredCommand @("py.exe", "python.exe", "python")
$npm = Get-RequiredCommand @("npm.cmd", "npm.exe", "npm")

if (-not $SkipInstall) {
    if (-not (Test-Path $VenvPython)) {
        Write-Step "Creating backend virtual environment..."
        if ((Split-Path -Leaf $python) -ieq "py.exe") {
            Invoke-InDirectory $BackendDir $python @("-3.11", "-m", "venv", ".venv")
        } else {
            Invoke-InDirectory $BackendDir $python @("-m", "venv", ".venv")
        }
    }

    $requirements = Join-Path $BackendDir "requirements.txt"
    $backendStamp = Join-Path $VenvDir ".requirements.stamp"
    if (-not (Test-Path $backendStamp) -or (Get-Item $requirements).LastWriteTimeUtc -gt (Get-Item $backendStamp).LastWriteTimeUtc) {
        Write-Step "Installing backend dependencies..."
        Invoke-InDirectory $BackendDir $VenvPython @("-m", "pip", "install", "-r", "requirements.txt")
        Set-Content -Path $backendStamp -Value (Get-Date).ToString("o")
    }

    $nodeModules = Join-Path $FrontendDir "node_modules"
    $packageLock = Join-Path $FrontendDir "package-lock.json"
    if (-not (Test-Path $nodeModules) -or ((Test-Path $packageLock) -and (Get-Item $packageLock).LastWriteTimeUtc -gt (Get-Item $nodeModules).LastWriteTimeUtc)) {
        Write-Step "Installing frontend dependencies..."
        if (Test-Path $packageLock) {
            Invoke-InDirectory $FrontendDir $npm @("ci")
        } else {
            Invoke-InDirectory $FrontendDir $npm @("install")
        }
    }
} else {
    if (-not (Test-Path $VenvPython)) {
        throw "Backend virtual environment is missing. Run without -SkipInstall first."
    }
}

if (Test-Port 8000) {
    Write-Warning "Port 8000 is already in use. The backend may fail to start."
}
if (Test-Port 5173) {
    Write-Warning "Port 5173 is already in use. Vite may choose another port."
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$backendOut = Join-Path $LogDir "backend.out.log"
$backendErr = Join-Path $LogDir "backend.err.log"
$frontendOut = Join-Path $LogDir "frontend.out.log"
$frontendErr = Join-Path $LogDir "frontend.err.log"

$backend = $null
$frontend = $null

try {
    Write-Step "Starting backend at http://127.0.0.1:8000"
    $backend = Start-AppProcess `
        -Name "backend" `
        -FilePath $VenvPython `
        -Arguments "-m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000" `
        -WorkingDirectory $BackendDir `
        -OutLog $backendOut `
        -ErrLog $backendErr

    Write-Step "Starting frontend at http://127.0.0.1:5173"
    $frontend = Start-AppProcess `
        -Name "frontend" `
        -FilePath $npm `
        -Arguments "run dev -- --host 127.0.0.1" `
        -WorkingDirectory $FrontendDir `
        -OutLog $frontendOut `
        -ErrLog $frontendErr

    Start-Sleep -Seconds 3

    foreach ($app in @($backend, $frontend)) {
        if ($app.Process.HasExited) {
            Show-LogTail $app.Name $app.OutLog $app.ErrLog
            throw "$($app.Name) exited early with code $($app.Process.ExitCode)."
        }
    }

    Write-Host ""
    Write-Host "PDFMaker is running." -ForegroundColor Green
    Write-Host "Frontend: http://127.0.0.1:5173"
    Write-Host "Backend:  http://127.0.0.1:8000/api/health"
    Write-Host "Logs:     $LogDir"
    Write-Host ""
    Write-Host "Press Ctrl+C to stop both processes."

    if (-not $NoBrowser) {
        Start-Process "http://127.0.0.1:5173"
    }

    while ($true) {
        Start-Sleep -Seconds 2
        foreach ($app in @($backend, $frontend)) {
            if ($app.Process.HasExited) {
                Show-LogTail $app.Name $app.OutLog $app.ErrLog
                throw "$($app.Name) stopped with code $($app.Process.ExitCode)."
            }
        }
    }
} finally {
    Stop-AppProcess $frontend
    Stop-AppProcess $backend
}
