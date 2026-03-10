@echo off
setlocal
chcp 65001 >nul

set "TARGET_DIR=%~dp0..\models"
set "SOURCE_DIR=%~dp0..\docs\image\bge-parts"

if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"

echo Assembling and extracting the model parts...

:: Find Python
set "PYTHON=python"
if exist "%~dp0..\.venv\Scripts\python.exe" (
    set "PYTHON=%~dp0..\.venv\Scripts\python.exe"
)

:: Create a temporary Python script to assemble and extract
set "TEMP_PY=%TEMP%\extract_bge_%RANDOM%.py"
(
echo import sys, os, glob, tarfile, io
echo source_dir = r"%SOURCE_DIR%"
echo target_dir = r"%TARGET_DIR%"
echo parts = sorted^(glob.glob^(os.path.join^(source_dir, "bge_part_*.png"^)^)^)
echo if not parts:
echo     print^("Error: No parts found in", source_dir^)
echo     sys.exit^(1^)
echo print^("Found {} parts, reading...".format^(len^(parts^)^)^)
echo data = bytearray^(^)
echo for p in parts:
echo     with open^(p, "rb"^) as f:
echo         data.extend^(f.read^(^)^)
echo print^("Decompressing and extracting... Please wait."^)
echo try:
echo     with tarfile.open^(fileobj=io.BytesIO^(data^), mode="r:xz"^) as t:
echo         t.extractall^(path=target_dir^)
echo except Exception as e:
echo     print^("Error extracting:", e^)
echo     sys.exit^(1^)
) > "%TEMP_PY%"

"%PYTHON%" "%TEMP_PY%"
set "PY_ERROR=%ERRORLEVEL%"
del "%TEMP_PY%"

if %PY_ERROR% equ 0 (
    echo Extraction successful! The model is restored to: %TARGET_DIR%\bge-small-zh-v1.5
    echo You can now safely delete the %SOURCE_DIR% directory.
) else (
    echo Error: Failed to extract the model.
    exit /b 1
)
