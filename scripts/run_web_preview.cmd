@echo off
setlocal
cd /d "%~dp0.."
py -B -m frontends.web.server --host 127.0.0.1 --port 8765 --port-scan 20 --open %*
