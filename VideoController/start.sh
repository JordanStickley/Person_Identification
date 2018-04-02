#!/bin/bash
export FLASK_DEBUG=0
export FLASK_APP=main.py
flask run --port=5001 --host=0.0.0.0
