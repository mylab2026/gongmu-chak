@echo off
cd /d "%~dp0"
title GongmuChak Test
"%~dp0runtime\python.exe" "%~dp0app.py"
if errorlevel 1 pause
