' run-tick.vbs — launches run-tick.ps1 with no visible console window.
' wscript.exe is a GUI host; window-style 0 means fully hidden.
'
' Usage (from Task Scheduler):
'   wscript.exe /nologo "<path>\run-tick.vbs" "<path>\run-tick.ps1" "-Repo X -AgencyPath Y"
'
' Arguments(0) = absolute path to run-tick.ps1
' Arguments(1) = the full argument string to pass to PowerShell

Dim WshShell, cmd
Set WshShell = CreateObject("WScript.Shell")
cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ _
    & WScript.Arguments(0) _
    & """ " _
    & WScript.Arguments(1)
WshShell.Run cmd, 0, True
Set WshShell = Nothing
