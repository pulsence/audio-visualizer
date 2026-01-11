@echo off
setlocal
set "PYTHONPATH=%~dp0src"
start "" /b pythonw -m audio_visualizer
exit /b
endlocal
