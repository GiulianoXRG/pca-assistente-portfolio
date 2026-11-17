# Instala (ou atualiza) o PCA assistente para o usuario atual. Nao precisa de administrador.
# - copia o programa para %LOCALAPPDATA%\Programs\pca-assistente
# - cria o atalho "PCA assistente" na Area de Trabalho
# - cria a pasta de configuracao %LOCALAPPDATA%\pca-assistente (mantida nas atualizacoes)
param(
  [string]$Destino = (Join-Path $env:LOCALAPPDATA "Programs\pca-assistente"),
  [string]$Config = (Join-Path $env:LOCALAPPDATA "pca-assistente"),
  [string]$PastaAtalho = [Environment]::GetFolderPath("Desktop"),
  [switch]$SemPausa
)
$ErrorActionPreference = "Stop"
$origem = $PSScriptRoot
$destino = $Destino
$config = $Config

$prog = Join-Path $origem "pca-assistente"
if (-not (Test-Path (Join-Path $prog "pca.exe"))) {
  Write-Host "Nao achei a pasta 'pca-assistente' com o pca.exe ao lado deste instalador. Extraia o .zip inteiro antes." -ForegroundColor Red
  if (-not $SemPausa) { Read-Host "Enter para sair" }
  exit 1
}

# fecha o app se estiver aberto (para poder trocar os arquivos)
Get-Process pca -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$destino*" } | Stop-Process -Force
Start-Sleep -Milliseconds 500

New-Item -ItemType Directory -Force -Path $destino, $config | Out-Null
if (Test-Path (Join-Path $destino "_internal")) { Remove-Item -Recurse -Force (Join-Path $destino "_internal") }
Copy-Item -Recurse -Force (Join-Path $prog "*") $destino
Copy-Item -Force (Join-Path $origem "iniciar.ps1") $destino
foreach ($f in "LEIA-ME.md") { if (Test-Path (Join-Path $origem $f)) { Copy-Item -Force (Join-Path $origem $f) $destino } }

$desk = $PastaAtalho
$sh = New-Object -ComObject WScript.Shell
$lnk = $sh.CreateShortcut((Join-Path $desk "PCA assistente.lnk"))
$lnk.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$lnk.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$destino\iniciar.ps1`""
$lnk.WorkingDirectory = $destino
$lnk.IconLocation = "$env:SystemRoot\System32\imageres.dll,99"
$lnk.Description = "Abre o PCA assistente (Chrome do assistente + tela do app)"
$lnk.Save()

Write-Host ""
Write-Host "PCA assistente instalado." -ForegroundColor Green
Write-Host "Programa: $destino"
Write-Host "Configuracao (mantida nas atualizacoes): $config"
Write-Host "Atalho criado na Area de Trabalho: PCA assistente"
if (-not $SemPausa) { Read-Host "Enter para fechar" }
