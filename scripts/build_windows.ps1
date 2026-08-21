$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

$version = & python -c "from core.version import __version__; print(__version__)"
if (-not $version) {
    throw "Unable to read application version."
}

& python -m PyInstaller --noconfirm --clean "packaging\student_code_diagnosis.spec"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

$innoCandidates = @(
    (Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$innoCompiler = $innoCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $innoCompiler) {
    throw "Inno Setup 6 was not found."
}

& $innoCompiler "/DMyAppVersion=$version" "packaging\student_code_diagnosis.iss"
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup build failed."
}

$installerPath = Join-Path $projectRoot "dist\installer\StudentCodeDiagnosis-Setup-$version.exe"
if (-not (Test-Path -LiteralPath $installerPath -PathType Leaf)) {
    throw "Installer was not generated."
}
$installer = Get-Item -LiteralPath $installerPath
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $installer.FullName).Hash.ToLowerInvariant()
"$hash  $($installer.Name)" | Set-Content -LiteralPath "$($installer.FullName).sha256" -Encoding ascii
Write-Output $installer.FullName
