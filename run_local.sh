#!/bin/bash
echo "--------------------------------------------------------"
echo "🚀 Starting local Project Management System..."
echo "🔗 Open your browser at: http://127.0.0.1:8888/login"
echo "--------------------------------------------------------"
python3 -m uvicorn api.index:app --reload --port 8888
