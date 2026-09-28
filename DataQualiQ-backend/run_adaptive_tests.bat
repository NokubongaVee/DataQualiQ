@echo off
cd /d "%~dp0"
.\venv\Scripts\python.exe -m unittest test_adaptive_context.py
