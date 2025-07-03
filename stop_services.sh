#!/bin/bash

# A script to gracefully stop all running micro-scalp engine services.

echo "--- Stopping Micro-Scalp Engine Services ---"

PID_DIR=".pids"

if [ -d "$PID_DIR" ]; then
    for pid_file in "$PID_DIR"/*.pid; do
        if [ -f "$pid_file" ]; then
            pid=$(cat "$pid_file")
            if ps -p $pid > /dev/null; then
                echo "Killing process $(basename "$pid_file" .pid) with PID $pid..."
                kill -9 "$pid"
            else
                echo "Process $(basename "$pid_file" .pid) with PID $pid not found. Already stopped."
            fi
            rm "$pid_file"
        fi
    done
else
    echo "PID directory not found. No processes to stop."
fi

echo "--- All services stopped. ---" 