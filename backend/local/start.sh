#!/bin/sh
set -eu
python -m local.seed_local --bootstrap
exec uvicorn local.app:app --host 0.0.0.0 --port 8080
