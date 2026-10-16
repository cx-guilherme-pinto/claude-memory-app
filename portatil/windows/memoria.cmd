@echo off
rem Memoria portable: command line. Examples:
rem   memoria.cmd selftest
rem   memoria.cmd update
"%~dp0python.exe" -m memoria %*
exit /b %ERRORLEVEL%
