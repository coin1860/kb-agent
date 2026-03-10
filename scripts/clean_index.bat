@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

echo 🔍 Fetching configuration paths...

:: Find Python
set "PYTHON=python"
if exist "lib\python3.11\python.exe" (
    set "PYTHON=lib\python3.11\python.exe"
) else if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
)

:: Extract index path dynamically
set "PYTHONPATH=src"
for /f "delims=" %%i in ('"%PYTHON%" -c "import kb_agent.config as config; print(config.load_settings().index_path)" 2^>nul') do set "INDEX_PATH=%%i"

if "%INDEX_PATH%"=="" (
    echo ❌ Error: Could not determine index_path from kb-agent configuration.
    echo Please ensure your configuration is valid.
    exit /b 1
)
if "%INDEX_PATH%"=="None" (
    echo ❌ Error: Could not determine index_path from kb-agent configuration.
    echo Please ensure your configuration is valid.
    exit /b 1
)

set "CHROMA_DIR=%INDEX_PATH%\.chroma"

echo ===============================================
echo 🗑️  Cleanup Target Overview:
echo    Index Path:  %INDEX_PATH%
echo    Chroma DB:   %CHROMA_DIR%
echo ===============================================
echo.
echo ⚠️  WARNING: This will PERMANENTLY delete all generated indexes and markdown summaries.
echo    Your original source files ^(in source_docs_path and archive_path^) will NOT be affected.
echo.
set /p REPLY="Are you sure you want to proceed? (y/N) " 
echo.

if /i "%REPLY%"=="y" (
    echo 🧹 Starting cleanup...

    if exist "%CHROMA_DIR%" (
        echo    -^> Removing ChromaDB directory...
        rmdir /s /q "%CHROMA_DIR%"
    ) else (
        echo    -^> ChromaDB directory not found, skipping.
    )

    echo    -^> Removing all indexed markdown ^(*.md^) files...
    del /q /f "%INDEX_PATH%\*.md" 2>nul

    echo    -^> Removing knowledge graph data...
    del /q /f "%INDEX_PATH%\knowledge_graph.json" 2>nul

    echo ✅ Cleanup complete! Your kb-agent index is now completely fresh.
    echo    You can now run 'kb-agent index' or use the TUI to re-index your documents.
) else (
    echo ⛔ Cleanup canceled.
)
