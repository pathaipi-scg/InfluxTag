@echo off

cd /d D:\influxtag

call .venv\Scripts\activate.bat

python -m uvicorn influxTag_list:app --host 0.0.0.0 --port 1866

