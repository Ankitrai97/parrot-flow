param(
  [string]$Python = ".\.venv\Scripts\python.exe",
  [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
if (-not $SkipInstall) {
  & $Python -m pip install -e ".[build]"
  if ($LASTEXITCODE -ne 0) { throw "Build dependency installation failed" }
}
& $Python -m PyInstaller --noconfirm --clean --windowed --name ParrotFlow `
  --add-data "assets;assets" `
  --collect-all faster_whisper --collect-all ctranslate2 --collect-all av --collect-all onnxruntime --collect-all nvidia --collect-all webview --collect-all pythonnet --collect-all clr_loader `
  packaging\run_localdictate.py
if ($LASTEXITCODE -ne 0) { throw "Parrot Flow packaging failed" }

Write-Host "Built application: dist\ParrotFlow\ParrotFlow.exe"
