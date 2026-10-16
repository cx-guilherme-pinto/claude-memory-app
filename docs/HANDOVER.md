# Handover: Memória

Para continuar o trabalho noutra máquina (por exemplo, a da empresa, com GitHub corporativo).
As regras do dia a dia estão no [CLAUDE.md](../CLAUDE.md).

## Estado na v0.4.0

Publicada no Gitea do organizador (`gitea.guilhermepinto.pt/guilherme/claude-memory-app`), a 16 out. 2026.

| Versão | O que trouxe |
|---|---|
| 0.1.0 | Notas Markdown, índice FTS5, grafo, servidor MCP, redação de segredos, `memoria update`, instaladores |
| 0.2.0 | Épico, url e etiquetas; pesquisa por nome, projeto e chave de ticket |
| 0.2.1 | Modo browser corrigido (sessão por cookie); visual do workshop |
| 0.2.2 | Versão portátil (zips Mac arm64/x86_64 e Windows x64) e interface nova |
| 0.2.3 | Editar a memória dentro da app |
| 0.3.0 | 4 línguas (pt, en, hi, he), hebraico RTL, seletor de língua |
| 0.4.0 | Vista "Atividade do Claude" (registo das chamadas MCP) |

Assets de cada release: wheel, `constraints.txt`, `install.sh`, `install.ps1`, `SHA256SUMS`
e os 3 zips portáteis.

Verificado:

- 227 testes no macOS (Apple Silicon), incluindo Playwright e a janela nativa.
- Atualizações reais com `memoria update`: instalação uv 0.2.1 → 0.4.0 e portátil 0.2.3 → 0.3.0 → 0.4.0.
  As notas não mudaram.
- O zip portátil do Mac a correr como `memoria mcp` (como o Claude Code o lança).

## O que falta

1. **Testar no Windows a sério.** Só houve verificação estática: `install.ps1`, o zip portátil,
   o WebView2, o pythonnet, o `memoria-gui.exe` e a troca de pasta no `memoria update`.
2. **Testar no Mac Intel e no Windows ARM.** Os wheels existem (ver `scripts/lock.sh`), mas não houve teste real.
3. **Rever o hindi e o hebraico com quem fala a língua:** `web/src/locales/hi.json`, `he.json` e `src/memoria/mensagens.py`.
4. **Traduzir o que ficou em português:** as mensagens de `install/install.sh` e `install/install.ps1`
   (o `.ps1` tem de ficar ASCII) e os modelos `portatil/windows/LEIA-ME.txt` e `memoria.cmd`
   (o `cmd.exe` lida mal com texto não latino).
5. **Correr o workflow de CI pela primeira vez** (`.github/workflows/release.yml`). No Gitea não havia
   runner: todas as releases foram feitas à mão com os mesmos scripts.
6. **Assinatura Apple real** (Developer ID + notarização): só foi testada a assinatura ad hoc.

## Riscos

- **Repositório privado ou interno.** Os instaladores, o setup do kit e o `memoria update` descarregam
  por `{repo}/releases/download/<tag>/<ficheiro>`. No GitHub esse URL só funciona sem login num
  repositório público. Num repositório privado ou interno, os participantes não conseguem instalar
  nem atualizar. Soluções: publicar as releases num repositório público, ou acrescentar um download
  pela API (com token) ao `update.py` e aos instaladores.
- **Gatekeeper, SmartScreen e EDR.** Os zips não são assinados. Pelo setup (curl ou Invoke-WebRequest)
  não ficam em quarentena. Descarregados pelo browser, o macOS bloqueia-os.
- **Proxies com inspeção de TLS.** O uv precisa de `UV_SYSTEM_CERTS=1`. O `memoria update` usa os
  certificados do sistema (truststore). O `git ls-remote` do update usa a configuração do git.
- **`cryptography` fixado em 46.0.3** (`constraints.in`): é a última versão com wheels para Mac Intel
  e Windows ARM. Vem do `mcp`, mas o servidor stdio não o usa.
- **Atualizar no Windows com o Claude Code aberto.** O `memoria mcp` prende os ficheiros. O script de
  troca espera até 3 minutos e pede para fechar a Memória e o Claude Code.
- **Testes de canvas no Chromium headless.** Os animation frames nem sempre correm. Os testes usam
  o valor visto no momento do desenho (`tests/test_browser.py`, `_esperar_desenho`).

## Publicar uma versão

### Mudar de alojamento e versão (um comando)

```bash
scripts/mudar-alojamento.sh --repo-url https://<servidor>/<org>/claude-memory-app.git \
  --provider github --versao vX.Y.Z [--data AAAA-MM-DD]
```

Muda só: `release.conf` (URL, versão e `RELEASE_PROVIDER`), os blocos gerados de `install/install.sh`,
`install/install.ps1` e `README.md`, `pyproject.toml`, `web/package.json`, `web/package-lock.json`
(só o próprio pacote), `uv.lock`, e acrescenta `## [X.Y.Z] - data` no topo do `CHANGELOG.md`.
Não faz commit. No fim diz o que mudou e onde ainda aparece o servidor antigo.
Correr outra vez com os mesmos argumentos não muda nada. O `RELEASE_DOWNLOAD_URL` fica igual.

Para mudar só a versão no mesmo alojamento, passa o URL e o fornecedor atuais.
À mão, sem o script: editar o `release.conf`, `pyproject.toml` e `CHANGELOG.md`, depois
`python3 scripts/render_installers.py --escrever` e `uv lock`.

### Publicar

1. `scripts/mudar-alojamento.sh …` (acima).
2. UI e testes:
   ```bash
   uv sync
   (cd web && npm ci && npm run build) && rm -rf src/memoria/web_dist && cp -R web/dist src/memoria/web_dist
   uv run playwright install chromium && uv run pytest
   ```
3. Commit e push do `main` para o servidor novo. O remoto tem de se chamar `origin`:
   o `publish-release.sh` faz push da tag para `origin`.
   **Não cries a tag à mão.** O `publish-release.sh` cria-a (anotada, no `HEAD`, com a versão do
   `release.conf`) e envia-a. Se já existir, usa-a; tem de apontar para o commit do build.
4. `scripts/build.sh`. Gera em `dist/` o wheel, `constraints.txt`, `install.sh` e `install.ps1` com o
   SHA-256 do wheel, os 3 zips portáteis e o `SHA256SUMS`. `PORTATIL=0 scripts/build.sh` salta os zips.
5. Login: `gh auth login --hostname <servidor>` (ou `GH_ENTERPRISE_TOKEN`). O servidor vem do
   `MEMORY_APP_REPO_URL`: o `GH_HOST` não é preciso (e não atrapalha).
   `scripts/publish-release.sh --so-token` confirma o login.
6. `scripts/publish-release.sh`: cria e envia a tag, cria a release, envia os assets com o `gh`
   (só aqui se fala com a API), verifica-os pela API e depois pelo URL público.
   Num repositório privado ou interno, o URL público dá um aviso (ver "Riscos").
7. Avisar o kit para mudar o `MEMORY_APP_VERSION` no `repos.conf`.

**Atenção ao CI.** Uma tag `v*` enviada para o servidor dispara o `.github/workflows/release.yml`,
que também publica. Escolhe um dos caminhos:
- publicação local (passos 4 a 6): desliga as Actions do repositório, ou o workflow, antes do passo 6;
- publicação pelo CI: depois do passo 3, cria e envia a tag (`git tag -a vX.Y.Z -m "Memória vX.Y.Z"`
  e `git push origin vX.Y.Z`) e não corras os passos 4 a 6. O runner precisa de acesso ao PyPI, ao npm
  e aos downloads do python-build-standalone.

O workflow corre build, testes e publicação. A tag tem de ser igual ao `MEMORY_APP_VERSION`.

## Assinatura opcional do Mac

`scripts/sign-macos.sh` assina e notariza os zips do Mac com um Developer ID. Corre-o só o organizador,
no Mac dele, depois do `build.sh` e antes do `publish-release.sh`. Não faz parte da release normal.
Instruções e decisões em [docs/portatil.md](portatil.md#assinatura-opcional-macos).
