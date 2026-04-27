#!/bin/bash

pkill -f "uvicorn app.main:app"
sleep 1
cd /usr/andy/world-cup-prediction/server || exit 1
source .venv/bin/activate
nohup uvicorn app.main:app --reload --port 8000 > /tmp/worldcup-server.log 2>&1 &
echo "服务已重启, PID: $!"
