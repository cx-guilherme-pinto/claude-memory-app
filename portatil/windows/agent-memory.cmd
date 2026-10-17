@echo off
rem Agent Memory portable: command line. Examples:
rem   agent-memory.cmd selftest
rem   agent-memory.cmd update
"%~dp0python.exe" -m memoria %*
exit /b %ERRORLEVEL%
