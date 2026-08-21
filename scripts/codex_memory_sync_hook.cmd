@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "HOOK_EVENT=%~1"
if not defined HOOK_EVENT exit /b 64

if defined CODEX_HOME (
    set "CODEX_ROOT=%CODEX_HOME%"
) else (
    set "CODEX_ROOT=%USERPROFILE%\.codex"
)
set "HOOK_STATE=%CODEX_ROOT%\.bridgeforge-codex\memory-sync"
call :receipt wrapper-start

set "PROJECT_ROOT="
for /f "delims=" %%I in ('git rev-parse --show-toplevel 2^>nul') do if not defined PROJECT_ROOT set "PROJECT_ROOT=%%I"
if not defined PROJECT_ROOT (
    call :receipt git-root-missing
    exit /b 65
)

set "HOOK_PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"
if not exist "%HOOK_PYTHON%" (
    call :receipt project-python-missing
    exit /b 66
)

"%HOOK_PYTHON%" -B "%~dp0codex_memory_sync.py" hook-run --event "%HOOK_EVENT%" --project-root "%PROJECT_ROOT%"
set "HOOK_EXIT=%ERRORLEVEL%"
call :receipt python-exit-%HOOK_EXIT%
exit /b %HOOK_EXIT%

:receipt
if exist "%HOOK_STATE%" >>"%HOOK_STATE%\hook-dispatch.log" echo handler_revision=2 event=%HOOK_EVENT% stage=%~1 date=%DATE% time=%TIME%
exit /b 0
