# Gera o instalador do componente local (Inno Setup 6) para navegadores Chromium.
#
# Uso:
#   .\build-installer.ps1              # reconstroi o exe se estiver velho e compila o setup
#   .\build-installer.ps1 -SkipBuild   # usa o exe que ja existe
#
# Saida: installer\output\ad-blogs-bypass-companion-<versao>-setup.exe
#
# Arquivo em ASCII puro de proposito: o Windows PowerShell 5 le .ps1 sem BOM
# como ANSI, e acento em string sairia trocado.
param([switch]$SkipBuild)

$ErrorActionPreference = "Stop"

$root         = Split-Path -Parent $PSScriptRoot
$companionDir = Join-Path $root "companion"
$exe          = Join-Path $companionDir "dist\snet-bypass-companion\snet-bypass-companion.exe"
$iss          = Join-Path $PSScriptRoot "ad-blogs-bypass-companion.iss"
$extManifest  = Join-Path $root "extension\manifest.json"

# O ISCC nao entra no PATH na instalacao padrao do Inno Setup - procurar tambem
# no registro (o Inno se registra como app de 32 bits) e nos caminhos usuais.
function Find-ISCC {
  $cmd = Get-Command iscc.exe -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }

  $regKeys = @(
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
    "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1"
  )
  foreach ($k in $regKeys) {
    $loc = (Get-ItemProperty -Path $k -Name InstallLocation -ErrorAction SilentlyContinue).InstallLocation
    if ($loc) {
      $candidate = Join-Path $loc "ISCC.exe"
      if (Test-Path $candidate) { return $candidate }
    }
  }

  foreach ($p in @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "${env:ProgramFiles}\Inno Setup 6\ISCC.exe")) {
    if ($p -and (Test-Path $p)) { return $p }
  }
  return $null
}

# Versao unica de verdade: extension\manifest.json.
function Get-ExtensionVersion {
  if (-not (Test-Path $extManifest)) { return $null }
  try { return (Get-Content $extManifest -Raw | ConvertFrom-Json).version } catch { return $null }
}

# O ID no allowed_origins do .iss tem que bater com o campo "key" do manifest.
# Errar isso da o erro mais chato de diagnosticar do native messaging: a porta
# abre e fecha na hora, com "Access to the specified native messaging host is
# forbidden" no console do service worker.
function Test-ExtensionId {
  if (-not (Test-Path $extManifest)) { return }
  $key = (Get-Content $extManifest -Raw | ConvertFrom-Json).key
  if (-not $key) {
    Write-Warning "extension\manifest.json nao tem o campo 'key' - o ID da extensao vai variar por maquina e o companion vai recusar a conexao."
    return
  }
  $sha = [System.Security.Cryptography.SHA256]::Create()
  $hash = $sha.ComputeHash([Convert]::FromBase64String($key))
  $id = -join ($hash[0..15] | ForEach-Object { [char](97 + ($_ -shr 4)); [char](97 + ($_ -band 15)) })
  $noIss = (Get-Content $iss -Raw -Encoding UTF8) -notmatch [regex]::Escape($id)
  if ($noIss) { throw "O ID derivado do manifest ($id) nao aparece no .iss. Atualize o #define ExtensionId." }
  Write-Host "      ID da extensao conferido: $id"
}

# --- 1. snet-bypass-companion.exe --------------------------------------------
if (-not $SkipBuild) {
  $maisNovo = Get-ChildItem (Join-Path $companionDir "*.py") | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
  $desatualizado = (-not (Test-Path $exe)) -or ($maisNovo.LastWriteTimeUtc -gt (Get-Item $exe).LastWriteTimeUtc)
  if ($desatualizado) {
    Write-Host "[1/3] exe ausente ou mais antigo que companion\*.py - rodando build.ps1..."
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $companionDir "build.ps1")
    if ($LASTEXITCODE -ne 0) { throw "build.ps1 falhou (codigo $LASTEXITCODE)" }
  }
  else { Write-Host "[1/3] exe ja esta atualizado." }
}
else { Write-Host "[1/3] -SkipBuild: usando o exe existente." }

if (-not (Test-Path $exe)) { throw "$exe nao encontrado - rode companion\build.ps1." }

# --- 2. ISCC ------------------------------------------------------------------
$iscc = Find-ISCC
if (-not $iscc) { throw "ISCC.exe (Inno Setup 6) nao encontrado. Instale o Inno Setup ou coloque o ISCC no PATH." }
Write-Host "[2/3] ISCC: $iscc"
Test-ExtensionId

# --- 3. Compilar --------------------------------------------------------------
$version = Get-ExtensionVersion
$issArgs = @($iss)
if ($version) {
  Write-Host "      versao (do extension\manifest.json): $version"
  $issArgs += "/DAppVersion=$version"
}

Write-Host "[3/3] Compilando o instalador (os ~120 MB do pacote levam alguns minutos)..."
& $iscc @issArgs
if ($LASTEXITCODE -ne 0) { throw "ISCC falhou (codigo $LASTEXITCODE)" }

$setup = Get-ChildItem (Join-Path $PSScriptRoot "output\ad-blogs-bypass-companion-*.exe") -ErrorAction SilentlyContinue |
         Sort-Object LastWriteTime -Descending | Select-Object -First 1
Write-Host ""
if ($setup) {
  Write-Host ("OK: {0} ({1} MB)" -f $setup.FullName, [math]::Round($setup.Length / 1MB, 1))
}
else { Write-Host "OK (nao achei o .exe em installer\output - confira a saida do ISCC acima)." }

# --- 4. Extensao em .zip (para a release) --------------------------------------
# Uma pasta ad-blogs-bypass-<versao>\ dentro do zip: quem extrai carrega essa pasta sem compactacao.
# _metadata\ e gerado pelo navegador ao carregar a extensao e nao vai junto.
if ($version) {
  $extDir  = Join-Path $root "extension"
  $staging = Join-Path ([System.IO.Path]::GetTempPath()) "ad-blogs-bypass-zip"
  $pasta   = Join-Path $staging "ad-blogs-bypass-$version"
  $zip     = Join-Path $PSScriptRoot "output\ad-blogs-bypass-extensao-$version.zip"
  if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
  New-Item -ItemType Directory -Force $pasta | Out-Null
  Get-ChildItem $extDir -Force | Where-Object { $_.Name -ne "_metadata" } |
    Copy-Item -Destination $pasta -Recurse -Force
  if (Test-Path $zip) { Remove-Item $zip -Force }
  # Entrada por entrada, com "/" no nome: o Compress-Archive e o ZipFile do Windows PowerShell 5 gravam
  # "\" (o padrao ZIP e "/"), e extratores fora do Windows criariam arquivos com "\" no nome.
  Add-Type -AssemblyName System.IO.Compression
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $fluxo   = [System.IO.File]::Open($zip, [System.IO.FileMode]::CreateNew)
  $arquivo = New-Object System.IO.Compression.ZipArchive($fluxo, [System.IO.Compression.ZipArchiveMode]::Create)
  try {
    Get-ChildItem $pasta -Recurse -File | ForEach-Object {
      $nome = $_.FullName.Substring($staging.Length + 1).Replace('\', '/')
      [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($arquivo, $_.FullName, $nome) | Out-Null
    }
  }
  finally { $arquivo.Dispose(); $fluxo.Dispose() }
  Remove-Item $staging -Recurse -Force
  Write-Host ("OK: {0} ({1} KB)" -f $zip, [math]::Round((Get-Item $zip).Length / 1KB))
}
