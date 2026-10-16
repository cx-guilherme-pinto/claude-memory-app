Memória {versao} (portable version for Windows 10/11)

Open
  Double-click Memoria.exe. No install and no admin rights needed.

If you see "Windows protected your PC"
  Click "More info", then "Run anyway".
  It only happens when the zip came through a browser.

Check it and connect it to Claude Code
  In PowerShell, in this folder:
    .\memoria.cmd selftest
  The selftest prints the right "claude mcp add" command for this folder.

Update
  Close Claude Code and run:
    .\memoria.cmd update

Notes
  Memories live in %USERPROFILE%\.memoria, outside this folder.
  Once it's connected to Claude Code, don't move this folder.
  If the window doesn't open (WebView2 is missing), Memória opens in the browser.

Em português: LEIA-ME.txt.
