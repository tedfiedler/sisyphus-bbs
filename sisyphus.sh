#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$SCRIPT_DIR/log/sisyphus.log"
WEB_PORT=8000
SSH_PORT=2222

get_pid() {
    lsof -ti :$WEB_PORT 2>/dev/null | head -1
}

start() {
    PID=$(get_pid)
    if [ -n "$PID" ]; then
        echo "Sisyphus BBS is already running (PID $PID)"
        return 1
    fi

    echo "Starting Sisyphus BBS..."
    mkdir -p "$SCRIPT_DIR/log" "$SCRIPT_DIR/db"
    cd "$SCRIPT_DIR"
    python3.14 src/app.py >> "$LOG_FILE" 2>&1 &

    for i in $(seq 1 10); do
        if nc -z localhost $WEB_PORT 2>/dev/null; then
            PID=$(get_pid)
            echo "Sisyphus BBS started (PID $PID)"
            echo "  Web:  http://localhost:$WEB_PORT"
            echo "  SSH:  ssh -p $SSH_PORT localhost"
            echo "  Logs: $LOG_FILE"
            return 0
        fi
        sleep 1
    done

    echo "Failed to start. Check $LOG_FILE"
    return 1
}

stop() {
    PID=$(get_pid)
    if [ -z "$PID" ]; then
        echo "Sisyphus BBS is not running"
        return 1
    fi

    echo "Stopping Sisyphus BBS (PID $PID)..."
    kill "$PID" 2>/dev/null
    sleep 2

    PID=$(get_pid)
    if [ -n "$PID" ]; then
        kill -9 "$PID" 2>/dev/null
    fi
    echo "Stopped."
}

status() {
    PID=$(get_pid)
    if [ -n "$PID" ]; then
        echo "Sisyphus BBS is running (PID $PID)"
        nc -z localhost $SSH_PORT 2>/dev/null && echo "  Web: up  SSH: up" || echo "  Web: up  SSH: down"
    else
        echo "Sisyphus BBS is not running"
    fi
}

case "${1:-}" in
    start)   start ;;
    stop)    stop ;;
    restart) stop; sleep 1; start ;;
    status)  status ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
