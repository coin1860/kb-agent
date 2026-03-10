#!/bin/bash
# Script to manage the local llama-cpp-python server

PID_FILE=".llm_server.pid"
LOG_FILE="logs/llm_server.log"

# Load environment variables if they exist
if [ -f .env ]; then
  source .env
fi

# Configuration with fallbacks
PORT=${KB_AGENT_LLM_PORT:-8081}
MODEL_NAME=${KB_AGENT_LOCAL_LLM_MODEL:-${KB_AGENT_LLM_MODEL:-"Qwen3.5-0.8B-Q4_K_M"}}
MODEL_DIR=${KB_AGENT_EMBEDDING_MODEL_PATH:-"./models"}

mkdir -p logs

find_gguf() {
    # 1. Direct path
    if [ -f "${MODEL_DIR}/${MODEL_NAME}.gguf" ]; then
        echo "${MODEL_DIR}/${MODEL_NAME}.gguf"
        return 0
    fi
    # 2. Subdirectory search in MODEL_DIR
    local found=$(find "${MODEL_DIR}" -name "${MODEL_NAME}.gguf" 2>/dev/null | head -n 1)
    if [ -n "$found" ]; then
        echo "$found"
        return 0
    fi
    # 3. Default models repo
    if [ -f "./models/${MODEL_NAME}.gguf" ]; then
        echo "./models/${MODEL_NAME}.gguf"
        return 0
    fi
    # 4. Default models repo subdirectory search
    found=$(find ./models -name "${MODEL_NAME}.gguf" 2>/dev/null | head -n 1)
    if [ -n "$found" ]; then
        echo "$found"
        return 0
    fi
    return 1
}

start_server() {
    if [ -f "$PID_FILE" ]; then
        if kill -0 $(cat "$PID_FILE") 2>/dev/null; then
            echo "Server is already running (PID: $(cat $PID_FILE))."
            return 1
        else
            echo "Found stale PID file. Cleaning up."
            rm "$PID_FILE"
        fi
    fi

    echo "Looking for model: $MODEL_NAME"
    GGUF_PATH=$(find_gguf)
    
    if [ -z "$GGUF_PATH" ]; then
        echo "Error: Could not find model file for ${MODEL_NAME}."
        echo "Looked in: ${MODEL_DIR} and ./models"
        return 1
    fi

    echo "Found model at: $GGUF_PATH"
    
    # Check if python is available
    if ! command -v python >/dev/null 2>&1; then
        # fallback to python3
        PYTHON_CMD="python3"
    else
        PYTHON_CMD="python"
    fi

    THREADS=$(sysctl -n hw.ncpu 2>/dev/null || nproc 2>/dev/null || echo 4)
    
    echo "Starting llama_cpp.server on port $PORT..."
    nohup $PYTHON_CMD -m llama_cpp.server \
        --model "$GGUF_PATH" \
        --host 0.0.0.0 \
        --port $PORT \
        --n_ctx 16384 \
        --n_threads $THREADS \
        --chat_format qwen > "$LOG_FILE" 2>&1 &
        
    PID=$!
    echo $PID > "$PID_FILE"
    echo "Server started with PID $PID. Logs: $LOG_FILE"
    echo "Please set KB_AGENT_LLM_BASE_URL=http://localhost:$PORT/v1 in your settings."
}

stop_server() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 $PID 2>/dev/null; then
            echo "Stopping server (PID: $PID)..."
            kill $PID
            rm "$PID_FILE"
            echo "Server stopped."
        else
            echo "Server is not running (stale PID file). Cleaning up."
            rm "$PID_FILE"
        fi
    else
        echo "PID file not found. Is the server running?"
    fi
}

status_server() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 $PID 2>/dev/null; then
            echo "Server is running (PID: $PID)"
        else
            echo "Server is NOT running (stale PID file: $PID)"
        fi
    else
        echo "Server is NOT running."
    fi
}

case "$1" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        stop_server
        sleep 2
        start_server
        ;;
    status)
        status_server
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
esac
