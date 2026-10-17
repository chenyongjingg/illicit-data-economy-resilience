@echo off
REM CIS sprint watchdog -- advances the pipeline as far as it can actually go.
REM Registered as a Windows scheduled task "CIS_Pipeline_Watchdog".
REM To remove:  schtasks /delete /tn "CIS_Pipeline_Watchdog" /f
REM
REM It is safe to run repeatedly: run_pipeline.py only LAUNCHES a stage whose
REM evidence artefact is absent and which has a runner; it never re-runs a DONE
REM stage. Everything it does is appended to _logs\watchdog.log.
REM
REM 2026-09-24 FIX (a): this task left CIS_HOST/CIS_PORT unset, so rsc.py fell
REM back to its compiled-in DEFAULTS -- the decommissioned pod
REM cpod-1vn6o9mm47jc:25355. Every tick therefore died at the first SSH call and
REM the pipeline never advanced, on AC power as much as on battery. Host/port are
REM not credentials, so they belong here. The PASSWORD is deliberately NOT set
REM here: it must not live in a file, and touching rsc.py's default literal is
REM the author's call.
REM 2026-09-24 FIX (b): the old tail was `echo exit=%ERRORLEVEL%` then `endlocal`,
REM so the child's code never reached cmd.exe and Task Scheduler always recorded
REM 0. A log line is not a status -- the scheduler only reads the code.
REM 2026-09-24 FIX (c): keep this file CRLF and ASCII-only. cmd.exe mis-parses
REM LF-only line endings (fragments get executed as commands), and UTF-8 comments
REM are mojibake under the OEM code page.

setlocal
set PY=C:\Python314\python.exe
set ROOT=D:\CIS
set LOG=%ROOT%\_logs\watchdog.log
REM ==== 2026-09-25 C-416: THE ENDPOINT LITERALS ARE GONE (do not re-add) ====
REM Until 2026-09-25 this file carried the host and the port VERBATIM as the
REM schedule side of the reconciliation below. It is published (it is in the repo
REM whitelist), so that copy was an endpoint shipping with the code. Both values
REM now come from HKCU\Environment -- the same key the C9 block already reads.
REM WHAT CHANGED, stated rather than left to be discovered: the check can no longer
REM detect 'the registry changed since this file was written' (it was a copy compared
REM against its own origin -- a gate that could only ever catch itself). It is
REM replaced by two checks that CAN fail: a value absent from the registry exits 87,
REM and a CALLER-provided value that disagrees with the registry still exits 87.
set CIS_USER=root
REM ==== 2026-09-25 C9: EXPLICIT ENV + RECONCILIATION (do not delete) ====
REM Until 2026-09-25 the PASSWORD came only from the caller's environment and the
REM host/port copies below were never checked against the registry. rsc.py has NO
REM compiled-in endpoint default any more, so a missing variable fails loudly --
REM that is intended. This block (a) reads CIS_PASS from HKCU\Environment
REM EXPLICITLY, and (b) RECONCILES this file's host/port against the same key.
REM On mismatch it writes one line (value never printed) and exits 87; if the
REM password is absent it exits 88.
REM NOTE: CIS_USER is deliberately NOT reconciled -- the registry has no such
REM value and rsc.py keeps an account default; an account is not an endpoint.
for /f "tokens=2,*" %%A in ('reg query "HKCU\Environment" /v CIS_HOST 2^>nul ^| findstr /i "CIS_HOST"') do set "REG_HOST=%%B"
for /f "tokens=2,*" %%A in ('reg query "HKCU\Environment" /v CIS_PORT 2^>nul ^| findstr /i "CIS_PORT"') do set "REG_PORT=%%B"
for /f "tokens=2,*" %%A in ('reg query "HKCU\Environment" /v CIS_PASS 2^>nul ^| findstr /i "CIS_PASS"') do set "CIS_PASS=%%B"
if not defined REG_HOST (echo C9-ENV-MISMATCH field=CIS_HOST reason=registry-missing >> "%LOG%" & endlocal & exit /b 87)
if not defined REG_PORT (echo C9-ENV-MISMATCH field=CIS_PORT reason=registry-missing >> "%LOG%" & endlocal & exit /b 87)
if not defined CIS_HOST set "CIS_HOST=%REG_HOST%"
if not defined CIS_PORT set "CIS_PORT=%REG_PORT%"
if /i not "%REG_HOST%"=="%CIS_HOST%" (echo C9-ENV-MISMATCH field=CIS_HOST reason=schedule-vs-registry >> "%LOG%" & endlocal & exit /b 87)
if /i not "%REG_PORT%"=="%CIS_PORT%" (echo C9-ENV-MISMATCH field=CIS_PORT reason=schedule-vs-registry >> "%LOG%" & endlocal & exit /b 87)
if not defined CIS_PASS (echo C9-NO-PASS reason=registry-missing >> "%LOG%" & endlocal & exit /b 88)
echo c9-env-v1 reconciled host=ok port=ok pass=set >> "%LOG%"
REM ==== end C9 block ====

if not exist "%ROOT%\_logs" mkdir "%ROOT%\_logs"

echo. >> "%LOG%"
echo ===== %DATE% %TIME% ===== >> "%LOG%"
REM 2026-09-25 ADD: record the CALLER's environment PRESENCE -- never any value.
REM Why: the identical command succeeds under the Scheduled Task and fails in a bare
REM shell, because the password lives in HKCU\Environment -- not in this file and not
REM in run_pipeline.py's argv. Without these lines watchdog.log has NO caller field, so
REM 'who ran this block' is unprovable from bytes; with them it is falsifiable: run it
REM from a bare shell and every line below reads 'unset' instead of 'set'.
echo caller-env-v1 since 2026-09-25 ; presence only ; values never printed >> "%LOG%"
if defined CIS_HOST (echo caller-env-v1 CIS_HOST=set >> "%LOG%") else (echo caller-env-v1 CIS_HOST=unset >> "%LOG%")
if defined CIS_PORT (echo caller-env-v1 CIS_PORT=set >> "%LOG%") else (echo caller-env-v1 CIS_PORT=unset >> "%LOG%")
if defined CIS_USER (echo caller-env-v1 CIS_USER=set >> "%LOG%") else (echo caller-env-v1 CIS_USER=unset >> "%LOG%")
if defined CIS_PASS (echo caller-env-v1 CIS_PASS=set >> "%LOG%") else (echo caller-env-v1 CIS_PASS=unset >> "%LOG%")
echo caller-argv-v1 --advance >> "%LOG%"
cd /d "%ROOT%"
"%PY%" "%ROOT%\_tools\run_pipeline.py" --advance >> "%LOG%" 2>&1
set RC=%ERRORLEVEL%
echo exit=%RC% >> "%LOG%"
endlocal & exit /b %RC%
