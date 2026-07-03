# SafeAir - Launcher de apresentacao
# Sobe o dashboard Streamlit local + um link publico via Cloudflare Tunnel,
# e mostra a URL bem grande no terminal para compartilhar com a plateia.

$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  SafeAir - iniciando dashboard para apresentacao"          -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# 0) Garante que as dependencias Python estao instaladas
Write-Host "Verificando dependencias Python..." -ForegroundColor Yellow
python -c "import streamlit, serial, pandas, plotly" | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Instalando dependencias (primeira vez, pode levar um minuto)..." -ForegroundColor Yellow
    python -m pip install -r requirements.txt
}

# 0b) Garante que o cloudflared.exe existe (baixa se for a primeira vez neste PC)
if (-not (Test-Path ".\cloudflared.exe")) {
    Write-Host "Baixando cloudflared (primeira vez neste computador)..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" -OutFile "cloudflared.exe"
}

# 1) Sobe o Streamlit (se ainda nao estiver rodando)
$streamlitVivo = $false
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8501" -UseBasicParsing -TimeoutSec 2
    if ($r.StatusCode -eq 200) { $streamlitVivo = $true }
} catch {}

if (-not $streamlitVivo) {
    Write-Host "Subindo o Streamlit..." -ForegroundColor Yellow
    Start-Process -FilePath "python" -ArgumentList "-m", "streamlit", "run", "app.py", "--server.headless", "true" `
        -RedirectStandardOutput "streamlit_out.log" -RedirectStandardError "streamlit_err.log" -WindowStyle Hidden

    $tentativas = 0
    while ($tentativas -lt 15) {
        Start-Sleep -Seconds 1
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:8501" -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) { break }
        } catch {}
        $tentativas++
    }
}
Write-Host "Streamlit rodando em http://localhost:8501" -ForegroundColor Green

# 2) Sobe o tunel publico (Cloudflare)
Write-Host "Abrindo link publico (pode levar ate 15s)..." -ForegroundColor Yellow

if (Test-Path "tunnel_err.log") { Remove-Item "tunnel_err.log" -Force }
Start-Process -FilePath ".\cloudflared.exe" -ArgumentList "tunnel", "--url", "http://localhost:8501" `
    -RedirectStandardOutput "tunnel_out.log" -RedirectStandardError "tunnel_err.log" -WindowStyle Hidden

$url = $null
$tentativas = 0
while (-not $url -and $tentativas -lt 30) {
    Start-Sleep -Seconds 1
    if (Test-Path "tunnel_err.log") {
        $match = Select-String -Path "tunnel_err.log" -Pattern "https://[a-zA-Z0-9\-]+\.trycloudflare\.com" | Select-Object -First 1
        if ($match) {
            $url = $match.Matches[0].Value
        }
    }
    $tentativas++
}

Write-Host ""
if ($url) {
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host "  LINK PARA A PLATEIA ACESSAR:"                              -ForegroundColor Green
    Write-Host "  $url"                                                     -ForegroundColor White
    Write-Host "==========================================================" -ForegroundColor Green
    Set-Clipboard -Value $url
    Write-Host "(link ja copiado pra area de transferencia)" -ForegroundColor DarkGray
    Start-Process $url
} else {
    Write-Host "Nao consegui capturar o link publico a tempo." -ForegroundColor Red
    Write-Host "Confira o arquivo tunnel_err.log para ver o que aconteceu." -ForegroundColor Red
}

Write-Host ""
Write-Host "Deixe esta janela aberta durante toda a apresentacao." -ForegroundColor Yellow
Read-Host "Pressione ENTER para encerrar o dashboard e o link publico"

Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process streamlit -ErrorAction SilentlyContinue | Stop-Process -Force
