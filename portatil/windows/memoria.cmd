@echo off
rem Memoria portatil: linha de comandos. Exemplos:
rem   memoria.cmd selftest
rem   memoria.cmd update
"%~dp0python.exe" -m memoria %*
exit /b %ERRORLEVEL%
