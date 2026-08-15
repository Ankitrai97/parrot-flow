param(
  [string]$Python = ".\.venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
& $Python -m pip install -e ".[build]"
& $Python -m PyInstaller --noconfirm --clean --windowed --name ParrotFlow `
  --add-data "assets;assets" `
  --collect-all faster_whisper --collect-all ctranslate2 --collect-all av --collect-all onnxruntime --collect-all nvidia `
  packaging\run_localdictate.py

Write-Host "Built application: dist\ParrotFlow\ParrotFlow.exe"
