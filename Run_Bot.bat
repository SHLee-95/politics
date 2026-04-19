@echo off
chcp 65001 > nul
echo ====================================
echo  Political Science Journal Crawler
echo ====================================
echo.

cd /d "%~dp0"

python journal_crawler.py

echo.
echo ====================================
echo  Done! Press any key to close.
echo ====================================
pause > nul
