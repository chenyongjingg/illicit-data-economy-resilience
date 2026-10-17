@echo off
REM Register the CIS sprint watchdog as a per-user scheduled task.
REM Remove with:  schtasks /delete /tn "CIS_Pipeline_Watchdog" /f
schtasks /create /tn "CIS_Pipeline_Watchdog" /tr "D:\CIS\_tools\watchdog.cmd" /sc minute /mo 20 /f
echo CREATE_EXIT=%ERRORLEVEL%
schtasks /query /tn "CIS_Pipeline_Watchdog" /fo LIST
echo QUERY_EXIT=%ERRORLEVEL%
