$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# 1) checa python
$pyCmd = $null
try { $pyCmd = (Get-Command python -ErrorAction Stop).Source } catch {}
if (-not $pyCmd) {
  Write-Host "Python não encontrado no PATH. Instale Python 3 e tente de novo."
  exit 1
}

# 2) tqdm
try {
  python -c "import tqdm" 2>$null
} catch {
  Write-Host "Instalando tqdm..."
  python -m pip install --upgrade pip | Out-Null
  python -m pip install tqdm
}

# 3) roda
Write-Host "Rodando porteiro VGP (pitstop 30min)..."
python .\scan_vgp_pitstop_30min.py

# 4) abre pasta de saída
$OutDir = Join-Path $PSScriptRoot "scan_out"
Write-Host "Abrindo pasta: $OutDir"
Start-Process explorer.exe $OutDir
