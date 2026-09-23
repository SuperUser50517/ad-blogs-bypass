# Empacota o companion (host.py + corrente.py + Playwright) numa pasta com
# snet-bypass-companion.exe (PyInstaller --onedir), para quem instala nao
# precisar de Python. Roda na maquina do desenvolvedor; o que se distribui e a
# pasta dist\snet-bypass-companion\ inteira, via installer\build-installer.ps1.
#
# Uso: .\build.ps1
# Requer: Python 3 com playwright instalado (o PyInstaller e instalado aqui se faltar).
#
# O driver do Playwright (node.exe + pacote JS, ~100 MB) entra pelo hook que o
# proprio playwright traz (hook-playwright.sync_api: collect_data_files). Nenhum
# navegador vai junto: o companion so usa p.request (HTTP), nunca abre janela.
#
# Arquivo em ASCII puro de proposito: o Windows PowerShell 5 le .ps1 sem BOM
# como ANSI, e acento em string sairia trocado.

$ErrorActionPreference = "Stop"

$nome = "snet-bypass-companion"
$dist = Join-Path $PSScriptRoot "dist"
$work = Join-Path $PSScriptRoot "build"
$icone = Join-Path (Split-Path -Parent $PSScriptRoot) "installer\icone.ico"

# O PyInstaller escreve o log no stderr; com "Stop", o PowerShell 5 transformaria
# isso em erro. Quem decide se falhou e o codigo de saida. O Out-Host impede que
# a saida do python vire parte do valor devolvido.
function Invoke-Python {
  $ErrorActionPreference = "Continue"
  & python @args | Out-Host
  return $LASTEXITCODE
}

Push-Location $PSScriptRoot
try {
  Write-Host "[1/3] Conferindo o PyInstaller..."
  if ((Invoke-Python -m PyInstaller --version) -ne 0) {
    Write-Host "      ausente - instalando (pip --user)..."
    if ((Invoke-Python -m pip install --user pyinstaller) -ne 0) { throw "pip install pyinstaller falhou" }
  }

  Write-Host "[2/3] Empacotando $nome..."
  $rc = Invoke-Python -m PyInstaller --noconfirm --clean --onedir --console `
    --name $nome --icon $icone --distpath $dist --workpath $work --specpath $work host.py
  if ($rc -ne 0) { throw "PyInstaller falhou (codigo $rc)" }

  Write-Host "[3/3] Conferindo o resultado..."
  $pasta = Join-Path $dist $nome
  $exe = Join-Path $pasta "$nome.exe"
  $node = Join-Path $pasta "_internal\playwright\driver\node.exe"
  if (-not (Test-Path $exe)) { throw "$exe nao foi gerado." }
  if (-not (Test-Path $node)) { throw "O driver do Playwright nao entrou no pacote ($node ausente)." }

  $mb = [math]::Round(((Get-ChildItem $pasta -Recurse -File | Measure-Object Length -Sum).Sum) / 1MB, 1)
  Write-Host ""
  Write-Host "OK: $exe (pasta: $mb MB)"
  Write-Host "Agora gere o instalador: ..\installer\build-installer.ps1 (o registro no navegador e feito por ele)."
}
finally { Pop-Location }
