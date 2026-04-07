#!/bin/bash

# --- 配置區 ---
# MODEL_DIR="./qwen3.5-0.6b"
# MODEL_PATH="${MODEL_DIR}/qwen3.5-0.6b.gguf"
MODEL_DIR="models/gemma-4-2b"
MODEL_PATH="${MODEL_DIR}/gemma-4-E2B-it-Q4_K_M.gguf"
# MMPROJ_PATH="${MODEL_DIR}/mmproj-BF16.gguf"
LLAMA_SERVER="models/llama-cpp/llama-server"
PID_FILE="./llama_server.pid"
LOG_FILE="./llama_server.log"
PORT=8080

# --- 功能函數 ---
start_server() {
    # 檢查並清理無效的 PID 文件
    if [ -f "$PID_FILE" ]; then
        if ! ps -p $(cat "$PID_FILE") > /dev/null; then
            rm "$PID_FILE"
        else
            echo "⚠️ 服務已經在運行 (PID: $(cat "$PID_FILE"))。"
            exit 1
        fi
    fi

    if [ ! -f "$LLAMA_SERVER" ] || [ ! -f "$MODEL_PATH" ]; then
        echo "❌ 錯誤：找不到 llama-server 或模型文件。"
        exit 1
    fi

    echo "🚀 正在啟動 Gemma 4 2b API 服務 (M4 優化版)..."
    
    # 徹底移除 --ubatch，統一使用 -b 256
    # 使用單行啟動避免反斜杠空格錯誤
    # 修改這一行，明確給予 'on' 參數：
    # --mmproj "$MMPROJ_PATH" \
    export GGML_METAL_TENSOR_ENABLE=1
    nohup "$LLAMA_SERVER" \
        -m "$MODEL_PATH" \
        --port "$PORT" \
        -ngl 99 \
        -np 1 \
	-t 8 \
        -c 32768 \
        -b 1024 \
        -ub 1024 \
        --reasoning-budget 0 \
	--reasoning off \
        --flash-attn on \
        --cache-type-k q8_0 \
        --cache-type-v q8_0 \
        --mmap \
        > "$LOG_FILE" 2>&1 &




    echo $! > "$PID_FILE"
    sleep 2
    
    if ps -p $(cat "$PID_FILE") > /dev/null; then
        echo "✅ 啟動成功！"
        echo "📍 API 地址: http://localhost:$PORT/v1/models"
    else
        echo "❌ 啟動失敗，請檢查日誌: tail -n 20 $LOG_FILE"
        rm "$PID_FILE"
    fi
}

stop_server() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        echo "🛑 正在關閉 Gemma 服務 (PID: $PID)..."
        kill "$PID" && rm "$PID_FILE"
        echo "✅ 服務已停止。"
    else
        pkill -f llama-server
        echo "✅ 已嘗試清理所有相關進程。"
    fi
}

case "$1" in
    start) start_server ;;
    stop) stop_server ;;
    restart) stop_server; sleep 1; start_server ;;
    status) 
        if [ -f "$PID_FILE" ] && ps -p $(cat "$PID_FILE") > /dev/null; then
            echo "🟢 運行中 (PID: $(cat "$PID_FILE"))"
        else
            echo "🔴 已停止"
        fi
        ;;
    *) echo "用法: $0 {start|stop|restart|status}"; exit 1 ;;
esac
