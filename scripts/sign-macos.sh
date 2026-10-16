#!/usr/bin/env bash
# Assina e notariza a Memória portátil do Mac. OPCIONAL: não faz parte da release normal.
#
# Quem instala com o setup do workshop (curl + extrair) não precisa disto: sem
# quarentena, o Gatekeeper não pergunta nada. Serve para:
#   - quem descarrega o zip pelo browser, AirDrop ou Mail (ficheiro em quarentena);
#   - empresas cujo EDR só aceita executáveis assinados.
#
# Corre-o o organizador, no Mac dele, com o seu Developer ID. O script não guarda
# credenciais: usa um perfil do Keychain criado uma vez com
#   xcrun notarytool store-credentials <perfil> --apple-id <email> --team-id <TEAMID>
# (pede uma palavra-passe específica da app; ver docs/portatil.md).
#
# Uso (depois de scripts/build.sh):
#   scripts/sign-macos.sh --identidade "Developer ID Application: Nome (TEAMID)" --perfil <perfil> \
#     dist/Memoria-<versão>-macos-arm64.zip dist/Memoria-<versão>-macos-x86_64.zip
#   scripts/sign-macos.sh --adhoc --saida /tmp/teste dist/Memoria-<versão>-macos-arm64.zip
#     (teste sem conta Apple: assina ad hoc com o hardened runtime e não notariza)
#
# Para cada zip:
#   1. extrai a Memoria.app;
#   2. troca o lançador sh por um executável compilado (portatil/macos/lancador.c, arm64 + x86_64);
#   3. assina de dentro para fora: cada Mach-O, o python3.12 e o lançador (com
#      portatil/macos/entitlements.plist) e por fim a app (hardened runtime, carimbo de tempo);
#   4. notariza (notarytool --wait), agrafa o ticket (stapler) e verifica (spctl);
#   5. volta a fazer o zip com o mesmo nome. Se o zip estava em dist/, atualiza o SHA256SUMS.
set -euo pipefail
cd "$(dirname "$0")/.."

IDENTIDADE=""
PERFIL=""
ADHOC=0
SAIDA=""
ZIPS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --identidade) IDENTIDADE="$2"; shift 2 ;;
    --perfil) PERFIL="$2"; shift 2 ;;
    --adhoc) ADHOC=1; shift ;;
    --saida) SAIDA="$2"; shift 2 ;;
    -h|--help) sed -n '2,27p' "$0"; exit 0 ;;
    -*) echo "Opção desconhecida: $1" >&2; exit 2 ;;
    *) ZIPS+=("$1"); shift ;;
  esac
done

falha() { echo "Erro: $*" >&2; exit 1; }
[ "$(uname -s)" = Darwin ] || falha "só corre no macOS."
[ ${#ZIPS[@]} -gt 0 ] || falha "indica pelo menos um zip do Mac (ver --help)."
if [ "$ADHOC" = 1 ]; then
  ASSINAR=(--sign - --timestamp=none)
else
  [ -n "$IDENTIDADE" ] || falha "falta --identidade \"Developer ID Application: ...\"."
  [ -n "$PERFIL" ] || falha "falta --perfil (perfil do notarytool no Keychain)."
  security find-identity -v -p codesigning | grep -qF "\"$IDENTIDADE\"" ||
    falha "a identidade \"$IDENTIDADE\" não está no Keychain (security find-identity -v -p codesigning)."
  ASSINAR=(--sign "$IDENTIDADE" --timestamp)
fi
command -v clang >/dev/null || falha "falta o clang (Xcode ou Command Line Tools)."
DIREITOS="portatil/macos/entitlements.plist"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

clang -arch arm64 -arch x86_64 -mmacosx-version-min=11.0 -O2 -Wall -Werror \
  -o "$tmp/lancador" portatil/macos/lancador.c

eh_macho() { file -b "$1" | grep -q '^Mach-O'; }
# codesign com o hardened runtime; só mostra o que não for o aviso de substituir a assinatura.
assinar() {
  local saida
  saida="$(codesign --force --options runtime "${ASSINAR[@]}" "$@" 2>&1)" || { echo "$saida" >&2; return 1; }
  printf '%s\n' "$saida" | grep -v 'replacing existing signature' >&2 || true
}

for zip in "${ZIPS[@]}"; do
  [ -f "$zip" ] || falha "não encontrei $zip"
  nome="$(basename "$zip")"
  case "$nome" in Memoria-*-macos-*.zip) ;; *) falha "$nome não é um zip do Mac da Memória." ;; esac
  echo "== $nome"
  pasta="$tmp/${nome%.zip}"
  mkdir -p "$pasta"
  ditto -x -k "$zip" "$pasta"
  app="$pasta/Memoria.app"
  [ -d "$app" ] || falha "$nome não tem Memoria.app."

  install -m 755 "$tmp/lancador" "$app/Contents/MacOS/memoria"

  echo "  a assinar..."
  n=0
  while IFS= read -r -d '' f; do
    if eh_macho "$f"; then
      assinar "$f"
      n=$((n + 1))
    fi
  done < <(find "$app/Contents/Resources" -type f \( -name '*.so' -o -name '*.dylib' -o -perm -u+x \) \
           ! -path '*/bin/python3.12' -print0)
  assinar --entitlements "$DIREITOS" "$app/Contents/Resources/python/bin/python3.12"
  assinar --entitlements "$DIREITOS" "$app/Contents/MacOS/memoria"
  assinar "$app"
  codesign --verify --deep --strict "$app"
  echo "  assinados $((n + 2)) executáveis e a app."

  if [ "$ADHOC" = 0 ]; then
    echo "  a notarizar (demora alguns minutos)..."
    ditto -c -k --norsrc --noextattr --noqtn --keepParent "$app" "$tmp/notarizar.zip"
    xcrun notarytool submit "$tmp/notarizar.zip" --keychain-profile "$PERFIL" --wait \
      --output-format json > "$tmp/notarizacao.json" || true
    estado="$(plutil -extract status raw -o - "$tmp/notarizacao.json" 2>/dev/null || echo "?")"
    if [ "$estado" != "Accepted" ]; then
      id="$(plutil -extract id raw -o - "$tmp/notarizacao.json" 2>/dev/null || echo "<id>")"
      falha "a notarização devolveu \"$estado\". Ver: xcrun notarytool log $id --keychain-profile $PERFIL"
    fi
    xcrun stapler staple -q "$app"
    xcrun stapler validate -q "$app"
    spctl -a -t exec -vv "$app"
  fi

  destino="${SAIDA:-$(dirname "$zip")}/$nome"
  mkdir -p "$(dirname "$destino")"
  # Sem atributos estendidos: o código está todo em Mach-O e o ticket em Contents/CodeResources.
  ditto -c -k --norsrc --noextattr --noqtn --keepParent "$app" "$tmp/$nome"
  mv -f "$tmp/$nome" "$destino"
  echo "  pronto: $destino"
done

# O SHA256SUMS tem de acompanhar os zips assinados.
if [ -z "$SAIDA" ] && ls dist/memoria-*.whl >/dev/null 2>&1; then
  python3 scripts/render_installers.py --somas dist
  echo "SHA256SUMS atualizado."
fi
