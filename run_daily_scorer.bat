@echo off
chcp 65001
cd /d "%~dp0"
echo ======================================================
echo === 일일 펀더멘털 및 AI 종합 매력도 스코어 계산 시작 ===
echo === 시작 시간: %date% %time% ===
python daily_scorer.py
echo === 종료 시간: %date% %time% ===
echo ======================================================
pause
