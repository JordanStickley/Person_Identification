#!/bin/bash
export FLASK_DEBUG=0
export FLASK_APP=main.py

export PORT=5001
[ $# -eq 1 ] && PORT=5002

flask run --port=$PORT --host=0.0.0.0
