# start_erp_sync.ps1 - run the ERPNext outbox sync as a background service
$logDir = "C:\AI_Assisstant\Omron_PLC_AI\logs"
if (-not (Test-Path -LiteralPath $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

$python = "C:\AI_Assisstant\Omron_PLC_AI\venv\Scripts\python.exe"
$script = "C:\AI_Assisstant\Omron_PLC_AI\erp_sync.py"
$stamp = Get-Date -Format "yyyyMMdd"
$log = Join-Path $logDir "erp_sync_$stamp.log"

# if already running, don't double-start
$existing = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match "erp_sync"
}
if ($existing) {
    Write-Output "erp_sync already running (PID $($existing.ProcessId -join ', ')))"
    exit 0
}

$proc = Start-Process -FilePath $python -ArgumentList $script -WindowStyle Hidden -PassThru -RedirectStandardOutput "$logDir\erp_sync_stdout.log" -RedirectStandardError "$logDir\erp_sync_stderr.log"
Write-Output "erp_sync started, PID $($proc.Id), logs: $logDir"