"""Gera memórias de exemplo (testes e `memoria selftest --exemplo N`).

Escreve sempre na pasta que lhe passam; nunca usa $MEMORIA_HOME por omissão.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

from memoria import store

PROJETOS = ["arena-de-seguranca", "loja-online", "api-pagamentos", "portal-rh", "app-movel"]
PREFIXOS = {"arena-de-seguranca": "ARENA", "loja-online": "LOJA", "api-pagamentos": "PAG", "portal-rh": "RH", "app-movel": "APP"}
TEMAS = [
    ("cache", "Usar cache no build reduz o tempo de CI."),
    ("retries", "Repetir pedidos só com backoff exponencial."),
    ("testes", "Correr os testes de contrato antes do deploy."),
    ("migracoes", "Migrações de base de dados sempre reversíveis."),
    ("tokens", "Contar tokens antes de enviar prompts grandes."),
    ("subagentes", "Dar a cada subagente um objetivo e um limite de custo."),
    ("revisao", "Pedir revisão a um segundo agente antes do merge."),
    ("logs", "Logs estruturados com id de pedido."),
    ("prompts", "Prompts curtos com exemplos concretos."),
    ("seguranca", "Validar entradas no servidor, nunca só no cliente."),
]
FICHEIROS = ["src/app.py", "src/api/rotas.py", "src/db/modelos.py", "tests/test_api.py", "web/src/App.jsx", "Dockerfile"]


def gerar(home: Path, n: int, semente: int = 7) -> list[Path]:
    rnd = random.Random(semente)
    home = Path(home)
    inicio = datetime(2026, 6, 1, 9, 0).astimezone()
    caminhos: list[Path] = []
    titulos: list[str] = []
    for i in range(n):
        tema, frase = TEMAS[i % len(TEMAS)]
        projeto = PROJETOS[rnd.randrange(len(PROJETOS))]
        tipo = store.TIPOS[rnd.randrange(len(store.TIPOS))]
        titulo = f"{tema.capitalize()} {i:03d}"
        ligacoes = rnd.sample(titulos[-40:], k=min(len(titulos[-40:]), rnd.choice([0, 0, 1, 2])))
        corpo = f"{frase}\n\nDetalhe {i}: aplicado na tarefa com sucesso."
        if titulos and rnd.random() < 0.3:
            corpo += f" Ver [[{titulos[rnd.randrange(len(titulos))]}]]."
        prefixo = PREFIXOS[projeto]
        numero = rnd.randrange(10, 60)
        com_tarefa = rnd.random() < 0.7
        caminhos.append(
            store.escrever_nota(
                home,
                tipo=tipo,
                titulo=titulo,
                texto=corpo,
                projeto=projeto,
                tarefa=f"{prefixo}-{numero}" if com_tarefa else None,
                epico=f"{prefixo}-{1 + numero % 4}" if com_tarefa and rnd.random() < 0.6 else None,
                url=f"https://exemplo.atlassian.net/browse/{prefixo}-{numero}" if com_tarefa and rnd.random() < 0.3 else None,
                etiquetas=[tema] if rnd.random() < 0.5 else None,
                ficheiros=rnd.sample(FICHEIROS, k=rnd.choice([0, 1, 2])),
                ligacoes=ligacoes,
                custo_usd=round(rnd.uniform(0.05, 4.0), 2) if rnd.random() < 0.4 else None,
                agora=inicio + timedelta(hours=6 * i),
            )
        )
        titulos.append(titulo)
    return caminhos
