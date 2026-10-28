param(
  [switch]$Project,
  [string]$ProjectRoot = (Get-Location).Path
)

$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($Project) {
  $TargetRoot = Join-Path (Resolve-Path $ProjectRoot).Path ".claude/skills"
} else {
  $TargetRoot = Join-Path $HOME ".claude/skills"
}

$Target = Join-Path $TargetRoot "project-quality-loop"
New-Item -ItemType Directory -Force $TargetRoot | Out-Null

$ResolvedSource = (Resolve-Path $SourceDir).Path
$ResolvedTarget = [System.IO.Path]::GetFullPath($Target)
if ($ResolvedSource -eq $ResolvedTarget) {
  Write-Host "이미 설치된 위치에서 실행 중입니다: $Target"
  exit 0
}

if (Test-Path $Target) {
  $Timestamp = Get-Date -Format "yyyyMMddHHmmss"
  $Backup = "$Target.backup.$Timestamp"
  Move-Item $Target $Backup
  Write-Host "기존 스킬 백업: $Backup"
}

Copy-Item -Recurse -Force $SourceDir $Target
Get-ChildItem -Path $Target -Directory -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "설치 완료: $Target"
Write-Host "Claude Code에서 /project-quality-loop 를 실행하세요."
