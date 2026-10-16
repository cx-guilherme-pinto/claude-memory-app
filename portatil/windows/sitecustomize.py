"""Memória portátil (Windows): abre a janela com um duplo clique em Memoria.exe.

Memoria.exe é uma cópia do pythonw.exe. Sem argumentos, o Python não teria nada
para correr. O Python importa este módulo sempre que arranca, mas ele só age
quando o executável é Memoria.exe e não há argumentos. Nos outros casos
(por exemplo `python.exe -m memoria mcp`) não faz nada.
"""

import os
import sys

# Os .pyc já vêm compilados no zip.
sys.dont_write_bytecode = True

if os.path.basename(sys.executable).lower() == "memoria.exe" and len(sys.orig_argv) <= 1:
    from memoria import portatil

    # os._exit: estamos dentro do arranque do Python, que não deve continuar.
    os._exit(portatil.arrancar_janela())
