# PCA assistente: abre tudo com um clique (atalho "PCA assistente" na Area de Trabalho).
# 1) Chrome do assistente (perfil proprio, porta 9223) no SIPAC; 2) app local (porta 8010, minimizado);
# 3) a tela do app no mesmo Chrome.
$ErrorActionPreference = "Stop"
$aqui = $PSScriptRoot
$porta = 8010
$cdp = 9223

function Aberta($p) {
  try { $c = New-Object Net.Sockets.TcpClient; $c.Connect("127.0.0.1", $p); $c.Close(); return $true } catch { return $false }
}

$chrome = "$env:ProgramFiles\Google\Chrome\Application\chrome.exe"
if (-not (Test-Path $chrome)) { $chrome = "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe" }
if (-not (Test-Path $chrome)) { $chrome = "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe" }
if (-not (Test-Path $chrome)) {
  Add-Type -AssemblyName PresentationFramework
  [System.Windows.MessageBox]::Show("Nao achei o Google Chrome neste computador. Instale o Chrome e tente de novo.", "PCA assistente") | Out-Null
  exit 1
}
$perfil = Join-Path $env:LOCALAPPDATA "pca-assistente\chrome"
New-Item -ItemType Directory -Force -Path $perfil | Out-Null
$args0 = @("--remote-debugging-port=$cdp", "--remote-debugging-address=127.0.0.1", "--user-data-dir=`"$perfil`"",
           "--no-first-run", "--no-default-browser-check")

if (-not (Aberta $cdp)) {
  Start-Process $chrome -ArgumentList ($args0 + "https://sipac.ufrn.br/sipac/")
}

if (-not (Aberta $porta)) {
  $exe = Join-Path $aqui "pca.exe"                       # instalado (PyInstaller)
  if (-not (Test-Path $exe)) { $exe = Join-Path $aqui "pca-assistente\pca.exe" }
  if (Test-Path $exe) {
    Start-Process $exe -ArgumentList "web" -WorkingDirectory (Split-Path $exe) -WindowStyle Minimized
  } else {                                               # desenvolvimento: repositorio com uv
    $repo = Split-Path $aqui -Parent
    Start-Process "uv" -ArgumentList "run", "pca", "web" -WorkingDirectory $repo -WindowStyle Minimized
  }
  for ($i = 0; $i -lt 60 -and -not (Aberta $porta); $i++) { Start-Sleep -Milliseconds 500 }
}

Start-Process $chrome -ArgumentList ($args0 + "http://127.0.0.1:$porta/")
