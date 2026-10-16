# Versão portátil

[English](portatil.md) · **Português**

Decisão aprovada a 16 out. 2026. Pedido da organização: uma app que se abre, sem instalador.

## O que é

Um zip por plataforma, com o Python e todas as dependências lá dentro:

| Ficheiro | Conteúdo | Tamanho |
|---|---|---|
| `Memoria-<versão>-macos-arm64.zip` | `Memoria.app` (Apple Silicon) | 37 MB |
| `Memoria-<versão>-macos-x86_64.zip` | `Memoria.app` (Intel) | 37 MB |
| `Memoria-<versão>-windows-x64.zip` | pasta `Memoria` (duplo clique em `Memoria.exe`) | 36 MB |

Não há instalador, nem uv, nem PyPI no dia do workshop. Só um download do servidor das releases.
O caminho de instalação com o uv (`install.sh`, `install.ps1`, wheel) continua igual.

## Decisões

1. **Python embutido, entregue pelo setup.** O setup do workshop descarrega o zip com
   `curl` (Mac) ou `Invoke-WebRequest` (Windows) e extrai-o para uma pasta fixa.
   Assim o ficheiro não fica marcado como "transferido da Internet":
   sem Gatekeeper, sem SmartScreen, sem avisos.
2. **Windows em zip.** Não há `.exe` único: seria um executável sem assinatura.
3. **Python do python-build-standalone 3.12.15 nos três zips.** É o mesmo que o uv instala hoje.
   Tem FTS5 e as correções de segurança. Os `.exe` não são assinados.
   A alternativa (zip "embeddable" do python.org, assinado pela PSF) ficou parada no 3.12.10.
4. **`memoria update` troca a pasta no mesmo sítio.** O caminho não muda,
   por isso a ligação ao Claude Code (MCP) continua válida.
5. **Sem assinatura Apple na release normal** (decisão do organizador: só se for mesmo preciso).
   Pelo setup não é preciso: testado, um zip descarregado com `curl` não fica em quarentena
   e a app abre sem perguntas. Há um script opcional para assinar e notarizar
   (ver "Assinatura opcional").

Opções postas de parte: PyInstaller e Briefcase (lançadores sem assinatura, mais falsos
positivos dos antivírus; o Briefcase precisa de uma máquina Windows para o build).

## Como funciona

macOS:

- `Memoria.app/Contents/MacOS/memoria` é um script `sh` que corre
  `Resources/python/bin/python3 -I -B -m memoria "$@"`.
- Sem argumentos abre a janela. Com argumentos é a linha de comandos.
- O MCP é `…/Memoria.app/Contents/MacOS/memoria mcp`.

Windows:

- `Memoria.exe` é uma cópia do `pythonw.exe`. O `sitecustomize.py` abre a janela
  quando o executável é `Memoria.exe` e não há argumentos. Nos outros casos não faz nada.
- `python312._pth` fixa os caminhos e ignora `PYTHONPATH`/`PYTHONHOME` do utilizador.
- O MCP é `…\Memoria\python.exe -m memoria mcp`. Na consola: `memoria.cmd selftest`.
- Se o zip veio pelo browser, a app tira a marca da Internet aos seus ficheiros no arranque.
  Sem isso, o .NET recusa as DLL do pythonnet e do WebView2 e a janela não abre.

Os `.pyc` vêm compilados (hash sem verificação). A app nunca escreve dentro da sua pasta.
O build é reprodutível: o mesmo wheel dá zips iguais, byte a byte.

## Build

```bash
scripts/build.sh                 # wheel, instaladores e os três zips
PORTATIL=0 scripts/build.sh      # sem os zips
uv run --no-project --python 3.12 python scripts/build_portatil.py --wheel dist/memoria-X-py3-none-any.whl --plataforma macos-arm64
```

Corre no Mac e no Linux (CI). As dependências de cada plataforma vêm em wheels
(`uv pip install --python-platform`). No Mac, o build corre o `selftest` de cada zip do Mac
(o Intel pelo Rosetta). O Python fixado (versão, URL e SHA-256) está em `release.conf`.

## Integração no setup do workshop

Esboço. O setup já tem `url_asset` e a verificação do `SHA256SUMS`.

macOS (`hw.optional.arm64` é fiável mesmo num Terminal em Rosetta):

```sh
arq=x86_64; [ "$(sysctl -n hw.optional.arm64 2>/dev/null)" = 1 ] && arq=arm64
zip="Memoria-${MEMORY_APP_VERSION#v}-macos-$arq.zip"
baixar "$(url_asset "$zip")" "$tmp/$zip"      # e confirmar o SHA-256
mkdir -p "$HOME/Applications"
rm -rf "$HOME/Applications/Memoria.app"
ditto -x -k "$tmp/$zip" "$HOME/Applications"
app="$HOME/Applications/Memoria.app/Contents/MacOS/memoria"
"$app" selftest
claude mcp add --scope user memoria -- "$app" mcp
```

Windows (PowerShell 5.1; o `Expand-Archive` é lento com milhares de ficheiros):

```powershell
$zip = 'Memoria-' + $version.TrimStart('v') + '-windows-x64.zip'
Get-Asset (Get-AssetUrl $zip) (Join-Path $tmp $zip)   # e confirmar o SHA-256
$destino = Join-Path $env:LOCALAPPDATA 'Programs'
Remove-Item -Recurse -Force (Join-Path $destino 'Memoria') -ErrorAction SilentlyContinue
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::ExtractToDirectory((Join-Path $tmp $zip), $destino)
$py = Join-Path $destino 'Memoria\python.exe'
& $py -m memoria selftest
claude mcp add --scope user memoria -- $py -m memoria mcp
# Atalho no menu Iniciar para Memoria\Memoria.exe (como o install.ps1 já faz).
```

O WebView2 continua a ser instalado pelo setup, se faltar. Sem ele, a app abre no browser.

## Download pelo browser (plano B)

macOS: o Gatekeeper bloqueia a app (não tem assinatura). No macOS 15 ou mais recente já não
há "Abrir" com o botão direito. Há duas saídas:

- no Terminal: `xattr -dr com.apple.quarantine ~/Applications/Memoria.app`;
- ou Definições do Sistema → Privacidade e Segurança → "Abrir mesmo assim" (pede a palavra-passe;
  descrito pela Apple e por terceiros, não verificado aqui).

Windows: o SmartScreen mostra "O Windows protegeu o computador".
Clica em "Mais informações" e depois em "Executar mesmo assim".

Nota para a página da release (está no CHANGELOG, que é o texto da release):
"Instala com o comando de uma linha. Descarregar pelo browser exige aprovação em
Definições do Sistema → Privacidade e Segurança."

## Assinatura opcional (macOS)

Só para quem descarrega pelo browser, AirDrop ou Mail, ou para empresas cujo EDR
só aceita executáveis assinados. Não faz parte da release normal. Corre-a o organizador,
no Mac dele, com o seu Developer ID. Nenhum script guarda credenciais.

Uma vez, no Mac do organizador:

1. Criar o certificado "Developer ID Application" (Xcode → Settings → Accounts →
   Manage Certificates → +). Só o titular da conta o pode criar.
2. Criar uma palavra-passe específica da app em account.apple.com.
3. Guardar o perfil do notarytool no Keychain (pede a palavra-passe; não fica em ficheiros):

   ```bash
   xcrun notarytool store-credentials memoria-notary --apple-id <email> --team-id <TEAMID>
   ```

Em cada release, depois de `scripts/build.sh` e antes de `scripts/publish-release.sh`:

```bash
scripts/sign-macos.sh --identidade "Developer ID Application: <Nome> (<TEAMID>)" --perfil memoria-notary \
  dist/Memoria-<versão>-macos-arm64.zip dist/Memoria-<versão>-macos-x86_64.zip
```

O script troca o lançador `sh` por um executável compilado (`portatil/macos/lancador.c`,
arm64 e x86_64), assina cada Mach-O e a app com o hardened runtime e
`portatil/macos/entitlements.plist`, notariza, agrafa o ticket, verifica com `spctl`,
refaz os zips e atualiza o `SHA256SUMS`.
Para testar sem conta Apple: `scripts/sign-macos.sh --adhoc --saida /tmp/teste <zip>`.

Testado em modo `--adhoc` (macOS 26.6, Apple Silicon): `codesign --verify --deep --strict`
passa depois de extrair com o `ditto` e com o extrator do `memoria update`; `selftest --gui`
passa com o hardened runtime (o zip Intel também, no Rosetta); correr a app não estraga a assinatura.
Por testar: a notarização e o `spctl` com um Developer ID verdadeiro.

## Verificado

No Mac (Apple Silicon, macOS 26.6):

- Os três zips geram-se em cerca de 25 s.
- Zip descarregado com `curl` e extraído com `unzip`: sem quarentena.
  `memoria selftest --gui` passa (janela pronta em menos de 1 s). Abre pelo Finder (`open`).
- Nada é escrito dentro da app.
- Zip Intel: `selftest` passa no Rosetta (sem janela).
- Cópia com quarentena (`0083;…;Google Chrome;…` e `0081;…;Safari;`): o `ditto` e o `unzip`
  passam a quarentena do zip para a app. A app não arranca. O macOS mostra o aviso do
  Gatekeeper (`spctl`: "rejected, no usable signature"). Depois de `xattr -dr com.apple.quarantine`, abre.
- `memoria update` com um servidor local: descarrega, verifica o SHA-256, corre o `selftest`
  da versão nova, troca a pasta e reindexa. Testado também em `~/Applications` e com a app renomeada.
- MCP por stdio através do lançador (`memoria mcp`): as três ferramentas respondem.
- O script de troca do Windows passa no parser e corre no PowerShell 7 (no Mac).
- O mesmo arranque do Windows (Python com outro nome, sem argumentos, janela aberta
  pelo `sitecustomize`) funciona no Mac.
- Envio dos assets de 37 MB para o Gitea: as releases v0.2.2 a v0.4.0 foram publicadas com eles.

## Por verificar (Windows não corre aqui)

- Duplo clique em `Memoria.exe` abre a janela (pythonnet, WinForms e WebView2 em modo `._pth`).
- O `python312._pth` é respeitado pelo Python do python-build-standalone
  (confirmado só pela leitura do `getpath.py` do CPython 3.12).
- O `pywin32.pth` e o `pywin32_bootstrap` funcionam neste modo.
- A remoção da marca da Internet (`Zone.Identifier`) resolve o erro 0x80131515 do .NET.
- O texto exato do SmartScreen para o `Memoria.exe` sem assinatura.
- O script de troca no PowerShell 5.1 com ficheiros em uso (MCP aberto no Claude Code).
- Políticas das empresas: AppLocker, regras ASR do Defender, antivírus.
- Windows ARM (corre o zip x64 em emulação).

Também por fazer: o menu da app mostra "Memoria" (sem acento), a app não tem ícone,
e o aviso de versão nova na interface diz `memoria update` (na versão portátil é o caminho completo).
