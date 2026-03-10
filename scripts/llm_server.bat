@echo off
setlocal enabledelayedexpansion

set PID_FILE=.llm_server.pid
set LOG_FILE=logs\llm_server.log

if not exist logs mkdir logs

:: Load from .env if it exists
if exist .env (
    for /f "tokens=1,2 delims==" %%A in (.env) do (
        set %%A=%%B
    )
)

:: Configuration with fallbacks
if "%KB_AGENT_LLM_PORT%"=="" set PORT=8081
if not "%KB_AGENT_LLM_PORT%"=="" set PORT=%KB_AGENT_LLM_PORT%

if "%KB_AGENT_LOCAL_LLM_MODEL%"=="" (
    if "%KB_AGENT_LLM_MODEL%"=="" (
        set MODEL_NAME=Qwen3.5-0.8B-Q4_K_M
    ) else (
        set MODEL_NAME=%KB_AGENT_LLM_MODEL%
    )
) else (
    set MODEL_NAME=%KB_AGENT_LOCAL_LLM_MODEL%
)

if "%KB_AGENT_EMBEDDING_MODEL_PATH%"=="" set MODEL_DIR=.\models
if not "%KB_AGENT_EMBEDDING_MODEL_PATH%"=="" set MODEL_DIR=%KB_AGENT_EMBEDDING_MODEL_PATH%

if "%1"=="start" goto start
if "%1"=="stop" goto stop
if "%1"=="restart" goto restart
if "%1"=="status" goto status

echo Usage: %0 {start^|stop^|restart^|status}
goto :eof

:find_gguf
set GGUF_PATH=
:: 1. Direct path
if exist "%MODEL_DIR%\%MODEL_NAME%.gguf" (
    set GGUF_PATH="%MODEL_DIR%\%MODEL_NAME%.gguf"
    exit /b 0
)
:: 2. Subdirectory search in MODEL_DIR
for /r "%MODEL_DIR%" %%F in (%MODEL_NAME%.gguf) do (
    set GGUF_PATH="%%F"
    exit /b 0
)
:: 3. Default models repo
if exist ".\models\%MODEL_NAME%.gguf" (
    set GGUF_PATH=".\models\%MODEL_NAME%.gguf"
    exit /b 0
)
:: 4. Default models repo subdirectory search
for /r ".\models" %%F in (%MODEL_NAME%.gguf) do (
    set GGUF_PATH="%%F"
    exit /b 0
)
exit /b 1

:start
if exist "%PID_FILE%" (
    echo Server might already be running. Try stop first, or delete %PID_FILE% if stale.
    goto :eof
)

echo Looking for model: %MODEL_NAME%
call :find_gguf

if "%GGUF_PATH%"=="" (
    echo Error: Could not find model file for %MODEL_NAME%.
    echo Looked in: %MODEL_DIR% and .\models
    goto :eof
)

echo Found model at: %GGUF_PATH%

set THREADS=%NUMBER_OF_PROCESSORS%
if "%THREADS%"=="" set THREADS=4

echo Starting llama_cpp.server on port %PORT%...
echo Logs will be written to %LOG_FILE%

:: Start the process and get the PID via powershell
powershell -Command "$process = Start-Process python -ArgumentList '-m llama_cpp.server --model %GGUF_PATH% --host 0.0.0.0 --port %PORT% --n_ctx 4096 --n_threads %THREADS% --chat_format chatml' -RedirectStandardOutput '%LOG_FILE%' -RedirectStandardError '%LOG_FILE%' -WindowStyle Hidden -PassThru; $process.Id > '%PID_FILE%'"

echo Server started.
echo Please set KB_AGENT_LLM_BASE_URL=http://localhost:%PORT%/v1 in your settings.
goto :eof

:stop
if exist "%PID_FILE%" (
    set /p SERVER_PID=<%PID_FILE%
    echo Stopping server (PID: !SERVER_PID!)...
    taskkill /F /PID !SERVER_PID! >nul 2>&1
    del "%PID_FILE%"
    echo Server stopped.
) else (
    echo PID file not found. Is the server running?
)
goto :eof

:restart
call :stop
timeout /t 2 /nobreak >nul
call :start
goto :eof

:status
if exist "%PID_FILE%" (
    set /p SERVER_PID=<%PID_FILE%
    tasklist /FI "PID eq !SERVER_PID!" 2>NUL | find /I "!SERVER_PID!">NUL
    if "%ERRORLEVEL%"=="0" (
        echo Server is running (PID: !SERVER_PID!)
    ) else (
        echo Server is NOT running (stale PID file: !SERVER_PID!)
    )
) else (
    echo Server is NOT running.
)
goto :eof
