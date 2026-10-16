#!/usr/bin/env bash
# Publica a release a partir de dist/ (corre scripts/build.sh antes).
#
# TODAS as chamadas a APIs específicas do alojamento estão em create_release().
# Tudo o resto usa só git (tag) e o padrão RELEASE_DOWNLOAD_URL (downloads),
# que é igual no Gitea e no GitHub: {repo}/releases/download/{version}/{file}.
#
# Fornecedor: RELEASE_PROVIDER (release.conf; uma variável de ambiente sobrepõe).
#   gitea   API v1: POST /repos/{owner}/{name}/releases e .../releases/{id}/assets.
#           Token: $GITEA_TOKEN, ou o que o git guarda para o servidor
#           (`git credential fill`, por exemplo no Keychain do macOS).
#           Primeiro faz GET /api/v1/user (só leitura) para confirmar que o token
#           tem acesso à API. Se não tiver, pára e explica.
#   github  `gh release create` (usa $GH_TOKEN, $GITHUB_TOKEN ou o login do gh).
#           Funciona com GitHub Enterprise: o servidor vem do MEMORY_APP_REPO_URL
#           (o gh recebe --repo <servidor>/<dono>/<nome>). Para um servidor que não seja
#           github.com, o gh precisa de login nesse servidor (`gh auth login --hostname <servidor>`)
#           ou de GH_ENTERPRISE_TOKEN. A verificação dos assets usa `gh release download`,
#           que funciona também com repositórios privados ou internos.
#
# O token nunca é impresso nem gravado: vai para o curl pelo stdin (--config -).
#
# Uso:
#   scripts/publish-release.sh             # cria a tag (se faltar), a release e os assets
#   scripts/publish-release.sh --so-token  # só confirma o acesso à API (gitea)
set -euo pipefail
cd "$(dirname "$0")/.."

SO_TOKEN=0
[ "${1:-}" = "--so-token" ] && SO_TOKEN=1

conf() { # valor de release.conf, com sobreposição pelo ambiente
  local v="${!1:-}"
  [ -n "$v" ] && { printf '%s' "$v"; return; }
  grep -m1 "^$1=" release.conf | cut -d= -f2-
}

REPO_URL="$(conf MEMORY_APP_REPO_URL)"
VERSION="$(conf MEMORY_APP_VERSION)"
PATTERN="$(conf RELEASE_DOWNLOAD_URL)"
PROVIDER="$(conf RELEASE_PROVIDER)"

repo="${REPO_URL%/}"
repo="${repo%.git}"
host="$(printf '%s' "$repo" | sed -E 's#^[a-z]+://([^/]+).*#\1#')"
name="${repo##*/}"
owner="${repo%/*}"
owner="${owner##*/}"

wheel="memoria-${VERSION#v}-py3-none-any.whl"
ASSETS=("$wheel" constraints.txt SHA256SUMS install.sh install.ps1)
# Versão portátil (scripts/build_portatil.py), se o build a gerou.
for z in dist/Memoria-"${VERSION#v}"-*.zip; do
  if [ -e "$z" ]; then ASSETS+=("${z#dist/}"); fi
done

TOKEN=""
VERIFICADO_API=0

falha() { echo "Erro: $*" >&2; exit 1; }

url_asset() {
  printf '%s' "$PATTERN" | sed -e "s#{repo}#$repo#g" -e "s#{host}#$host#g" -e "s#{owner}#$owner#g" \
    -e "s#{name}#$name#g" -e "s#{version}#$VERSION#g" -e "s#{file}#$1#g"
}

# curl com o token no cabeçalho, passado pelo stdin (não aparece em `ps` nem em logs).
curl_token() {
  if [ -n "$TOKEN" ]; then
    printf 'header = "Authorization: token %s"\n' "$TOKEN" | curl --config - "$@"
  else
    curl "$@"
  fi
}

token_git() {
  printf 'protocol=https\nhost=%s\n\n' "$host" |
    GIT_TERMINAL_PROMPT=0 git credential fill 2>/dev/null | sed -n 's/^password=//p'
}

notas_da_versao() {
  python3 - "${VERSION#v}" <<'PY'
import re, sys
texto = open("CHANGELOG.md", encoding="utf-8").read()
m = re.search(rf"^## \[{re.escape(sys.argv[1])}\][^\n]*\n(.*?)(?=^## \[|\Z)", texto, re.S | re.M)
print((m.group(1) if m else "").strip())
PY
}

# ---------------------------------------------------------------------------
# ÚNICO sítio com chamadas específicas do alojamento.
# ---------------------------------------------------------------------------
create_release() {
  case "$PROVIDER" in
    gitea)
      local api="https://$host/api/v1"
      TOKEN="${GITEA_TOKEN:-$(token_git)}"
      [ -n "$TOKEN" ] || falha "sem token: exporta GITEA_TOKEN ou guarda credenciais no git para $host."

      # 1) Só leitura: o token tem acesso à API?
      local codigo
      codigo="$(curl_token -sS -o /dev/null -w '%{http_code}' "$api/user")"
      if [ "$codigo" != "200" ]; then
        falha "o token não tem acesso à API do Gitea (GET /api/v1/user devolveu $codigo).
Cria um token em https://$host/user/settings/applications com o scope write:repository
e exporta-o como GITEA_TOKEN. Nada foi publicado."
      fi
      echo "Token com acesso à API: ok."
      [ "$SO_TOKEN" = 1 ] && return 0

      local tmp
      tmp="$(mktemp -d)"
      # 2) A release já existe?
      codigo="$(curl_token -sS -o "$tmp/rel.json" -w '%{http_code}' "$api/repos/$owner/$name/releases/tags/$VERSION")"
      local id
      if [ "$codigo" = "200" ]; then
        id="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$tmp/rel.json")"
        echo "A release $VERSION já existe (id $id): só junto os assets que faltam."
      else
        notas_da_versao > "$tmp/notas.md"
        python3 - "$VERSION" "$tmp/notas.md" > "$tmp/pedido.json" <<'PY'
import json, sys
versao, notas = sys.argv[1], open(sys.argv[2], encoding="utf-8").read()
print(json.dumps({"tag_name": versao, "name": versao, "body": notas, "draft": False, "prerelease": "-" in versao}))
PY
        codigo="$(curl_token -sS -o "$tmp/rel.json" -w '%{http_code}' -X POST \
          -H 'Content-Type: application/json' --data-binary "@$tmp/pedido.json" \
          "$api/repos/$owner/$name/releases")"
        [ "$codigo" = "201" ] || { cat "$tmp/rel.json" >&2; falha "criar a release devolveu $codigo."; }
        id="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$tmp/rel.json")"
        echo "Release $VERSION criada (id $id)."
      fi
      # 3) Assets (os que já existem ficam).
      local existentes
      existentes="$(python3 -c 'import json,sys; print("\n".join(a["name"] for a in json.load(open(sys.argv[1])).get("assets") or []))' "$tmp/rel.json")"
      for f in "${ASSETS[@]}"; do
        if printf '%s\n' "$existentes" | grep -qxF "$f"; then
          echo "  já existe: $f"
          continue
        fi
        codigo="$(curl_token -sS -o "$tmp/asset.json" -w '%{http_code}' -X POST \
          -F "attachment=@dist/$f" "$api/repos/$owner/$name/releases/$id/assets?name=$f")"
        [ "$codigo" = "201" ] || { cat "$tmp/asset.json" >&2; falha "enviar $f devolveu $codigo."; }
        echo "  enviado: $f"
      done
      rm -rf "$tmp"
      ;;
    github)
      command -v gh >/dev/null || falha "falta o gh (GitHub CLI)."
      [ "$SO_TOKEN" = 1 ] && { gh auth status --hostname "$host"; return 0; }
      local alvo="$host/$owner/$name"
      local notas
      notas="$(mktemp)"
      notas_da_versao > "$notas"
      local extra=()
      [[ "$VERSION" == *-* ]] && extra+=(--prerelease)
      if gh release view "$VERSION" --repo "$alvo" >/dev/null 2>&1; then
        gh release upload "$VERSION" --repo "$alvo" "${ASSETS[@]/#/dist/}"
      else
        gh release create "$VERSION" --repo "$alvo" --title "$VERSION" \
          --notes-file "$notas" --verify-tag "${extra[@]}" "${ASSETS[@]/#/dist/}"
      fi
      rm -f "$notas"
      # Verificação pela API (funciona em repositórios privados e internos).
      local tmp
      tmp="$(mktemp -d)"
      gh release download "$VERSION" --repo "$alvo" --dir "$tmp" >/dev/null || falha "gh release download falhou."
      for f in "${ASSETS[@]}"; do
        cmp -s "$tmp/$f" "dist/$f" || falha "o asset $f na release difere de dist/$f"
      done
      rm -rf "$tmp"
      VERIFICADO_API=1
      echo "Assets verificados pela API do GitHub."
      ;;
    *)
      falha "RELEASE_PROVIDER desconhecido: $PROVIDER (usa gitea ou github)."
      ;;
  esac
}

# ---------------------------------------------------------------------------
if [ "$SO_TOKEN" = 1 ]; then
  create_release
  exit 0
fi

# No CI, a tag que disparou o workflow tem de ser a versão do release.conf.
if [ -n "${GITHUB_REF_NAME:-}" ] && [ "${GITHUB_REF_TYPE:-tag}" = "tag" ] && [ "$GITHUB_REF_NAME" != "$VERSION" ]; then
  falha "a tag $GITHUB_REF_NAME não é a versão do release.conf ($VERSION)."
fi
for f in "${ASSETS[@]}"; do
  [ -f "dist/$f" ] || falha "falta dist/$f. Corre scripts/build.sh."
done
(cd dist && if command -v sha256sum >/dev/null; then sha256sum -c --quiet SHA256SUMS; else shasum -a 256 -c --quiet SHA256SUMS; fi) ||
  falha "dist/SHA256SUMS não confere."

# Tag (git puro, igual em qualquer alojamento).
if ! git rev-parse -q --verify "refs/tags/$VERSION" >/dev/null; then
  [ -z "$(git status --porcelain --untracked-files=no)" ] || falha "há alterações por gravar no git."
  git tag -a "$VERSION" -m "Memória $VERSION"
  echo "Tag $VERSION criada em $(git rev-parse --short HEAD)."
fi
if ! git ls-remote --exit-code --tags origin "refs/tags/$VERSION" >/dev/null 2>&1; then
  git push origin "refs/tags/$VERSION"
fi

create_release

# Verificação: cada asset descarregado pelo padrão público confere com dist/.
echo "A verificar os downloads..."
tmp="$(mktemp -d)"
for f in "${ASSETS[@]}"; do
  url="$(url_asset "$f")"
  if ! curl_token -fsSL --retry 3 -o "$tmp/$f" "$url"; then
    if [ "$VERIFICADO_API" = 1 ]; then
      # A release está certa (vista pela API), mas o URL público não responde:
      # o repositório é privado ou interno. Os instaladores e o `memoria update`
      # descarregam por este URL, por isso precisam de um repositório público.
      echo "Aviso: $url não se descarrega sem login (repositório privado ou interno)." >&2
      echo "       Os instaladores e o memoria update precisam de um repositório público." >&2
      continue
    fi
    falha "não consegui descarregar $url"
  fi
  cmp -s "$tmp/$f" "dist/$f" || falha "o download de $f difere de dist/$f"
  echo "  ok: $url"
done
rm -rf "$tmp"
echo "Release $VERSION publicada."
