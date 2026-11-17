# Gera dist\PCA-assistente-instalador.zip (programa PyInstaller onedir + instalador + LEIA-ME).
# "Continue": no PowerShell 5.1 o stderr de uv/pyinstaller vira erro; o resultado é conferido por $LASTEXITCODE.
$ErrorActionPreference = "Continue"
$repo = Split-Path $PSScriptRoot -Parent
Set-Location $repo
uv run pytest -q
if ($LASTEXITCODE -ne 0) { throw "Testes falharam: nada empacotado." }
uv run --with pyinstaller pyinstaller pca.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou." }

$pacote = Join-Path $repo "dist\pacote"
if (Test-Path $pacote) { Remove-Item -Recurse -Force $pacote }
New-Item -ItemType Directory -Force -Path $pacote | Out-Null
Copy-Item -Recurse (Join-Path $repo "dist\pca-assistente") $pacote
Copy-Item (Join-Path $repo "scripts\instalar.ps1"), (Join-Path $repo "scripts\instalar.cmd"),
          (Join-Path $repo "scripts\iniciar.ps1"), (Join-Path $repo "LEIA-ME.md") $pacote
$zip = Join-Path $repo "dist\PCA-assistente-instalador.zip"
if (Test-Path $zip) { Remove-Item -Force $zip }
Compress-Archive -Path (Join-Path $pacote "*") -DestinationPath $zip
Write-Host "Pronto: $zip"
