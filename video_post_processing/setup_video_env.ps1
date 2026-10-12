$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $ScriptDir "video_env"
$Requirements = Join-Path $ScriptDir "requirements-video.txt"

Write-Host "Project directory: $ScriptDir"
Write-Host "Virtual environment: $VenvDir"

$PythonLauncher = $null
$PythonArgs = @()

if (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonLauncher = "py"
    $PythonArgs = @("-3")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonLauncher = "python"
} else {
    throw "Python 3 was not found. Install Python 3 and make sure 'py' or 'python' is available in PowerShell."
}

Write-Host ""
Write-Host "Python:"
& $PythonLauncher @PythonArgs --version

if (-not (Test-Path $VenvDir)) {
    Write-Host ""
    Write-Host "Creating virtual environment..."
    & $PythonLauncher @PythonArgs -m venv $VenvDir
} else {
    Write-Host ""
    Write-Host "Existing video_env found; reusing it."
}

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    throw "Virtual environment was not created correctly: $VenvPython not found."
}

Write-Host ""
Write-Host "Upgrading pip..."
& $VenvPython -m pip install --upgrade pip setuptools wheel

Write-Host ""
Write-Host "Installing video-analysis dependencies..."
& $VenvPython -m pip install -r $Requirements

Write-Host ""
Write-Host "Verifying imports..."
& $VenvPython -c "import sys, numpy, cv2, pandas, matplotlib; print('Python:     ', sys.version.split()[0]); print('NumPy:      ', numpy.__version__); print('OpenCV:     ', cv2.__version__); print('pandas:     ', pandas.__version__); print('matplotlib: ', matplotlib.__version__); print(); print('Environment OK.')"

Write-Host ""
Write-Host "Setup complete."
Write-Host ""
Write-Host "Run the regression tests with:"
Write-Host "  .\video_env\Scripts\python.exe .\test_motion_detector.py"
Write-Host ""
Write-Host "Run the dataset without rendering tracking videos with:"
Write-Host '  .\video_env\Scripts\python.exe .\Video_post_process_video_timing_v5.py "..\Final Results" --no-video'
