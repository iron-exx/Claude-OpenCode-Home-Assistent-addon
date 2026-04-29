# OpenCode als Windows-Aufgabe beim Start registrieren
# Als Administrator ausfuehren!
$Action = New-ScheduledTaskAction -Execute "opencode" -Argument "serve --hostname 0.0.0.0 --port 4096"
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest
Register-ScheduledTask -TaskName "OpenCode HA Server" -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force
Write-Host "✅ OpenCode wird jetzt automatisch beim Windows-Start gestartet!" -ForegroundColor Green
