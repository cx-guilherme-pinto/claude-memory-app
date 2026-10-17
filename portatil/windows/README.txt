Agent Memory {versao} (portable version for Windows 10/11)

Open
  Double-click Memoria.exe. No install and no admin rights needed.

If you see "Windows protected your PC"
  Click "More info", then "Run anyway".
  It only happens when the zip came through a browser.

Check it and connect it to Claude Code
  In PowerShell, in this folder:
    .\agent-memory.cmd selftest
  The selftest prints the right "claude mcp add" command for this folder.

Update
  Close Claude Code and run:
    .\agent-memory.cmd update

Notes
  Memories live in %USERPROFILE%\.agent-memory, outside this folder
  (or in %USERPROFILE%\.memoria, if you already had it from v0.4 or earlier).
  Once it's connected to Claude Code, don't move this folder.
  If the window doesn't open (WebView2 is missing), Agent Memory opens in the browser.

Em português: README.pt.txt.
