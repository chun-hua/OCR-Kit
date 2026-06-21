param(
    [ValidateSet('cpu', 'cuda')]
    [string]$Variant = 'cpu',
    [switch]$Clean,
    [switch]$SkipFrontendBuild,
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$BuildVenv = Join-Path $Root '.build-venv'
$Python = Join-Path $BuildVenv 'Scripts\python.exe'
$PyInstaller = Join-Path $BuildVenv 'Scripts\pyinstaller.exe'
$DistRoot = Join-Path $Root "dist\$Variant"
$BuildRoot = Join-Path $Root "build\$Variant"

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Native command failed with exit code $LASTEXITCODE"
    }
}

if ($Clean) {
    Remove-Item -LiteralPath $DistRoot -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $BuildRoot -Recurse -Force -ErrorAction SilentlyContinue
}

if (-not $SkipFrontendBuild) {
    Push-Location (Join-Path $Root 'frontend')
    try {
        if (-not (Test-Path 'node_modules\vite\bin\vite.js')) {
            Invoke-Native { npm ci }
        }
        Invoke-Native { node 'node_modules\vite\bin\vite.js' build }
    }
    finally {
        Pop-Location
    }
}
elseif (-not (Test-Path (Join-Path $Root 'frontend\dist\index.html'))) {
    throw 'Frontend dist was not found. Run without -SkipFrontendBuild first.'
}

if (-not (Test-Path $Python)) {
    Invoke-Native { uv venv --python 3.12 $BuildVenv }
}

Invoke-Native {
    uv pip install --python $Python -r (Join-Path $Root 'requirements.txt')
}
Invoke-Native {
    uv pip install --python $Python 'pyinstaller==6.14.2' 'psutil==7.0.0'
}

if ($Variant -eq 'cuda') {
    Invoke-Native { uv pip uninstall --python $Python onnxruntime }
    Invoke-Native { uv pip install --python $Python 'onnxruntime-gpu==1.27.0' }
}
else {
    $GpuRuntime = Get-ChildItem (Join-Path $BuildVenv 'Lib\site-packages') -Filter 'onnxruntime_gpu-*.dist-info' -ErrorAction SilentlyContinue
    if ($GpuRuntime) {
        Invoke-Native { uv pip uninstall --python $Python onnxruntime-gpu }
    }
    Invoke-Native { uv pip install --python $Python 'onnxruntime==1.27.0' }
}

Invoke-Native {
    & $PyInstaller `
        --noconfirm `
        --windowed `
        --name 'OCR-Kit' `
        --distpath $DistRoot `
        --workpath $BuildRoot `
        --specpath $BuildRoot `
        --add-data "$Root\frontend\dist;frontend\dist" `
        --collect-all paddleocr `
        --collect-all paddlex `
        --collect-all onnxruntime `
        --copy-metadata imagesize `
        --copy-metadata opencv-contrib-python `
        --copy-metadata pyclipper `
        --copy-metadata pypdfium2 `
        --copy-metadata python-bidi `
        --copy-metadata shapely `
        --hidden-import uvicorn.logging `
        --hidden-import uvicorn.loops.auto `
        --hidden-import uvicorn.protocols.http.auto `
        --hidden-import uvicorn.protocols.websockets.auto `
        --hidden-import uvicorn.lifespan.on `
        (Join-Path $Root 'launcher.py')
}

if (-not $SkipInstaller) {
    $Iscc = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if (-not $Iscc) {
        $Candidates = @(
            "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
        )
        $Iscc = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    }
    if (-not $Iscc) {
        throw 'Inno Setup 6 was not found. Install it or use -SkipInstaller.'
    }
    $IsccPath = if ($Iscc -is [System.Management.Automation.CommandInfo]) { $Iscc.Source } else { $Iscc }
    Invoke-Native {
        & $IsccPath "/DVariant=$Variant" (Join-Path $PSScriptRoot 'OCR-Kit.iss')
    }
}

Write-Host "Build complete: $DistRoot\OCR-Kit"
