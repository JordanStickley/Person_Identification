#!/bin/bash
export FLASK_DEBUG=0
export FLASK_APP=main.py

export PORT=5001
[ $# -gt 0 ] && PORT=5002 && export config_file_name=config2

flask run --port=$PORT --host=0.0.0.0
