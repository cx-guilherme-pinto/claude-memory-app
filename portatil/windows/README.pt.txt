Agent Memory {versao} (versão portátil para Windows 10/11)

Abrir
  Duplo clique em Memoria.exe. Não precisa de instalar nem de admin.

Se aparecer "O Windows protegeu o computador"
  Clica em "Mais informações" e depois em "Executar mesmo assim".
  Só acontece se o zip veio pelo browser.

Verificar e ligar ao Claude Code
  No PowerShell, nesta pasta:
    .\agent-memory.cmd selftest
  O selftest mostra o comando "claude mcp add" certo para esta pasta.

Atualizar
  Fecha o Claude Code e corre:
    .\agent-memory.cmd update

Notas
  As memórias ficam em %USERPROFILE%\.agent-memory, fora desta pasta
  (ou em %USERPROFILE%\.memoria, se já a tinhas da v0.4 ou anterior).
  Depois de ligar ao Claude Code, não movas esta pasta.
  Se a janela não abrir (falta o WebView2), a Agent Memory abre no browser.

In English: README.txt.
