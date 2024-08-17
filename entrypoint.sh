#!/usr/bin/env bash
EXPOSED_PORT="${PORT:-2300}"
./migrate.sh
uvicorn app:app --proxy-headers --host 0.0.0.0 --port "$EXPOSED_PORT" --log-config=log_conf.yaml