# Native Windows installer (run from repo root).
param(
  [string]$Agents = "claude,codex,grok,cursor",
  [switch]$NoDeps,
  [switch]$NoOcr,
  [switch]$Force,
  [switch]$DesktopOnly,
  [switch]$NoDesktop
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillSrc = Join-Path $Root "skills\everything-to-markdown"
$Venv = Join-Path $Root ".venv"
$Utf8Bom = New-Object System.Text.UTF8Encoding $true

function Test-Tesseract {
  if (Get-Command tesseract -ErrorAction SilentlyContinue) { return $true }
  return Test-Path "C:\Program Files\Tesseract-OCR\tesseract.exe"
}

function Write-DesktopBat([string]$TemplateName, [string]$DestName) {
  $tpl = Join-Path $Root "desktop\$TemplateName"
  if (-not (Test-Path $tpl)) { throw "missing template $tpl" }
  $desktop = [Environment]::GetFolderPath("Desktop")
  $dest = Join-Path $desktop $DestName
  $content = [System.IO.File]::ReadAllText($tpl)
  $content = $content.Replace("__ROOT__", $Root)
  [System.IO.File]::WriteAllText($dest, $content, $Utf8Bom)
  Write-Host "desktop: $dest"
}

function Install-DesktopBats {
  Write-DesktopBat "普通转换.bat" "普通转换.bat"
  if (Test-Tesseract) {
    Write-DesktopBat "扫描转换.bat" "扫描转换.bat"
  } else {
    Write-Host "未检测到 Tesseract，只生成桌面「普通转换.bat」。扫描件需要时再装 Tesseract，然后运行: .\install.ps1 -DesktopOnly -Agents `"`""
  }
}

if ($DesktopOnly) {
  $vpy = Join-Path $Venv "Scripts\python.exe"
  if (-not (Test-Path $vpy)) {
    throw "还没安装依赖。请先在项目文件夹运行: .\install.ps1 -Agents `"`""
  }
  Install-DesktopBats
  exit 0
}

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
if (-not $py) { throw "Python not found. Install Python 3.10+ and re-run." }

if (-not $NoDeps) {
  & $py.Source -m venv $Venv
  $vpy = Join-Path $Venv "Scripts\python.exe"
  & $vpy -m pip install -U pip
  & $vpy -m pip install -r (Join-Path $Root "requirements.txt")
  if (-not $NoOcr) {
    & $vpy -m pip install -r (Join-Path $Root "requirements-ocr.txt")
  }
} else {
  $vpy = $py.Source
}

Set-Content -Path (Join-Path $SkillSrc ".doc2md-python") -Value $vpy -Encoding utf8
& $vpy (Join-Path $SkillSrc "scripts\office_bridge.py") --detect | Set-Content (Join-Path $Root "office-detect.json")

function Install-Skill([string]$Dest) {
  $parent = Split-Path $Dest
  New-Item -ItemType Directory -Force -Path $parent | Out-Null
  if (Test-Path $Dest) {
    if (-not $Force) {
      Write-Host "skip existing $Dest (use -Force)"
      return
    }
    Remove-Item -Recurse -Force $Dest
  }
  New-Item -ItemType Junction -Path $Dest -Target $SkillSrc | Out-Null
  Write-Host "installed $Dest"
}

if ($Agents -eq "all") { $Agents = "claude,codex,grok,cursor" }
foreach ($a in $Agents.Split(",")) {
  $name = $a.Trim()
  if ($name -eq "") { continue }
  switch ($name) {
    "claude" { Install-Skill "$env:USERPROFILE\.claude\skills\everything-to-markdown" }
    "codex" { Install-Skill "$env:USERPROFILE\.codex\skills\everything-to-markdown" }
    "grok" { Install-Skill "$env:USERPROFILE\.grok\skills\everything-to-markdown" }
    "cursor" { Install-Skill "$env:USERPROFILE\.cursor\skills\everything-to-markdown" }
    default { Write-Host "unknown agent $name" }
  }
}

if (-not $NoDesktop) {
  Install-DesktopBats
}

Write-Host "Python: $vpy"
if (Test-Path (Join-Path $Root "office-detect.json")) {
  Get-Content (Join-Path $Root "office-detect.json")
}
