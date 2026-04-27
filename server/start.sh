#!/bin/bash

cd /usr/andy/world-cup-prediction/server || exit 1
source .venv/bin/activate
nohup uvicorn app.main:app --reload --port 8000 > /tmp/worldcup-server.log 2>&1 &
echo "服务已启动, PID: $!"
