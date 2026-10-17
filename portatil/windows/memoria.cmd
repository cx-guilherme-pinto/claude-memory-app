@echo off
rem Agent Memory portable: old name of agent-memory.cmd (until v0.4). Examples:
rem   memoria.cmd selftest
rem   memoria.cmd update
"%~dp0python.exe" -m memoria %*
exit /b %ERRORLEVEL%
