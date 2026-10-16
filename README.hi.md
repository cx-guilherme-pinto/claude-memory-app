# Memória

[English](README.md) · [Português](README.pt.md) · **हिन्दी** · [עברית](README.he.md)

Memória वो सब Markdown फ़ाइलों में सेव करता है जो Claude Code सीखता है, आपके अपने कंप्यूटर पर।
यह इन notes को एक graph में दिखाता है और MCP server के ज़रिए Claude Code को वापस देता है।

- **सबक** (lessons), नियम (**करें**, **न करें**) और टास्क की **हिस्ट्री**।
- हर note किसी ticket (Jira, GitHub) और उसके epic से लिंक हो सकता है।
- नाम, प्रोजेक्ट, ticket, epic, tags और टेक्स्ट से तेज़ सर्च (SQLite FTS5)।
- Graph, filters, timeline, नए note का फ़ॉर्म और Claude की MCP एक्टिविटी वाली विंडो।
- English, पुर्तगाली, हिंदी और हिब्रू में।
- सब कुछ आपके कंप्यूटर पर रहता है। कुछ भी बाहर नहीं जाता।

## इंस्टॉल

Admin rights की ज़रूरत नहीं।

<!-- >>> instalar: gerado a partir de release.conf por scripts/render_installers.py -->
**macOS** (Intel और Apple Silicon) और Linux, Terminal में:

```bash
curl -fsSL https://github.com/cx-guilherme-pinto/claude-memory-app/releases/download/v0.4.1/install.sh | sh
```

**Windows 10/11**, PowerShell में:

```powershell
powershell -ExecutionPolicy Bypass -c "irm https://github.com/cx-guilherme-pinto/claude-memory-app/releases/download/v0.4.1/install.ps1 | iex"
```
<!-- <<< instalar -->

Installer ये करता है:

1. अगर [uv](https://docs.astral.sh/uv/) नहीं है तो उसे इंस्टॉल करता है (फ़िक्स्ड वर्ज़न);
2. wheel और `constraints.txt` डाउनलोड करके SHA-256 चेक करता है;
3. uv वाले Python 3.12 के साथ ऐप इंस्टॉल करता है;
4. Windows पर, WebView2 Runtime न हो तो उसे इंस्टॉल करता है (सिर्फ़ इस user के लिए);
5. शॉर्टकट बनाता है: Mac पर `~/Applications/Memória.app`, Windows पर Start menu में "Memória"।

Commands `~/.local/bin` (Mac/Linux) या `%USERPROFILE%\.local\bin` (Windows) में रहते हैं।

### पोर्टेबल वर्ज़न (बिना इंस्टॉल)

हर release में हर प्लेटफ़ॉर्म के लिए एक zip भी है, अंदर Python के साथ:

| फ़ाइल | खोलें |
|---|---|
| `Memoria-<version>-macos-arm64.zip` (Apple Silicon) | `Memoria.app` |
| `Memoria-<version>-macos-x86_64.zip` (Intel) | `Memoria.app` |
| `Memoria-<version>-windows-x64.zip` | `Memoria\Memoria.exe` |

Unzip करें और खोलें। न admin चाहिए, न नेटवर्क। Workshop का setup यह खुद कर देता है।

- Claude Code से जोड़ने के लिए: `memoria selftest` सही `claude mcp add` command दिखाता है।
  Mac पर `…/Memoria.app/Contents/MacOS/memoria selftest`; Windows पर `memoria.cmd selftest`।
- एक लाइन वाले install command का इस्तेमाल करें। ब्राउज़र से डाउनलोड किए zip के लिए
  System Settings → Privacy & Security में approval चाहिए: macOS ऐप को ब्लॉक करता है (signed नहीं है)।
  Terminal से अनब्लॉक करें: `xattr -dr com.apple.quarantine ~/Applications/Memoria.app`।
  Windows पर "Windows protected your PC" आए तो "More info" और फिर "Run anyway" पर क्लिक करें।
- Claude Code से जोड़ने के बाद ऐप को मूव न करें।

डिटेल्स और फ़ैसले: [docs/portatil.md](docs/portatil.md) (English)।

## Claude Code से जोड़ें

```bash
claude mcp add --scope user memoria -- "$HOME/.local/bin/memoria" mcp
```

Windows पर: `claude mcp add --scope user memoria -- "%USERPROFILE%\.local\bin\memoria.exe" mcp`।

MCP tools:

| Tool | काम |
|---|---|
| `memoria_procurar(texto, projeto?, tipo?, tarefa?, epico?, limite=10)` | Notes सर्च करता है। Ticket key (`ABC-123`) से टास्क और उसका epic मिलता है। |
| `memoria_adicionar(tipo, titulo, texto, projeto, tarefa?, epico?, url?, ficheiros?, ligacoes?, etiquetas?, custo_usd?)` | Note सेव करके उसका path लौटाता है। |
| `memoria_relacionadas(id_ou_caminho, limite=10)` | लिंक हुए notes, सबसे मज़बूत रिलेशन पहले। |

Tools और parameters के नाम पुर्तगाली में हैं और कभी नहीं बदलते।

## इस्तेमाल

| Command | क्या करता है |
|---|---|
| `memoria` | विंडो खोलता है। |
| `memoria --browser` | वही इंटरफ़ेस ब्राउज़र में खोलता है। |
| `memoria add --tipo licao --projeto p --titulo "..." --texto "..." [--tarefa ABC-123 --epico ABC-100 --url ...]` | Note सेव करता है। |
| `memoria procurar "text" [--tarefa ABC-123] [--epico ABC-100]` | Command line से सर्च। |
| `memoria reindex` | Markdown फ़ाइलों से index फिर से बनाता है। |
| `memoria update` | लेटेस्ट वर्ज़न इंस्टॉल करता है। |
| `memoria selftest [--gui]` | इंस्टॉलेशन चेक करता है। `--gui` के साथ विंडो खोलकर बंद करता है। |
| `memoria lingua [pt\|en\|hi\|he]` | भाषा दिखाता या चुनता है। |
| `memoria mcp` | MCP server (Claude Code इसे इस्तेमाल करता है)। |

विंडो में किसी node पर क्लिक करके note देखें। सर्च के लिए `/` और बंद करने के लिए `Esc` दबाएँ।
सर्च में memories, projects और tasks/epics दिखते हैं; किसी एक को चुनकर उस पर फ़ोकस करें।
Filters से project, epic, task और अवधि चुनें। Types की लिस्ट से map फ़िल्टर होता है।
Timeline का play बटन graph को बढ़ते हुए दिखाता है।

Windows पर WebView2 न हो तो इंटरफ़ेस ब्राउज़र में `127.0.0.1` पर खुलता है।
Terminal सेशन का पता दिखाता है (`http://127.0.0.1:<port>/?t=<key>`)।
यह key लोकल है और सिर्फ़ ऐप खुला रहने तक काम करती है।

## Claude की एक्टिविटी

कॉलम के ऊपर **Claude की एक्टिविटी** बटन दिखाता है कि Claude ने MCP पर Memória से क्या माँगा:

- चार नंबर: आज की कॉल्स, कुल कॉल्स, कॉल्स प्रति मिनट (पिछले 10 मिनट का एवरेज) और रिकॉल हुई मेमोरी (यूनिक);
- पिछली 100 रिकॉल हुई मेमोरी: समय, tool, टाइटल, प्रोजेक्ट और टास्क।
  जिस सर्च का कोई रिज़ल्ट नहीं आया, वो भी सर्च किए टेक्स्ट के साथ दिखती है। मेमोरी खोलने के लिए टाइटल पर क्लिक करें।

व्यू अपने-आप रिफ़्रेश होता है। यह सेशन के हिसाब से अलग नहीं होता।

Log `~/.memoria/.indice/registo.sqlite` में आपके कंप्यूटर पर रहता है, index से अलग
(`memoria reindex` इसे नहीं मिटाता)। सर्च किया टेक्स्ट secrets मास्क करके और छोटा करके सेव होता है।
Notes का कंटेंट कभी log नहीं होता। पुरानी लाइनें अपने-आप हटती हैं; कुल कॉल्स की गिनती बनी रहती है।

## भाषाएँ

ऐप English, पुर्तगाली, हिंदी और हिब्रू बोलता है। डिफ़ॉल्ट रूप से यह सिस्टम की भाषा लेता है:

- **macOS:** System Settings › General › Language & Region में पहली सपोर्टेड भाषा;
- **Windows:** Windows की display language;
- **बाक़ी:** `LANGUAGE`, `LC_ALL`, `LC_MESSAGES` या `LANG`।

कोई भी सपोर्टेड न हो तो English।
कॉलम के ऊपर वाला picker भाषा तुरंत बदलता है और `~/.memoria/preferencias.json` में सेव करता है।
Command line से: `memoria lingua hi`। `MEMORIA_LANG` variable सब पर भारी है।

- हिब्रू दाएँ से बाएँ खुलती है। हर note का टेक्स्ट अपनी दिशा में रहता है।
- हिंदी और हिब्रू के लिए Noto Sans Devanagari और Noto Sans Hebrew ऐप में शामिल हैं।
- Technical terms हर भाषा में English में रहते हैं (MCP, token, ticket, tools के नाम)।

## मेमोरी कहाँ रहती हैं

`~/.memoria` में (या `MEMORIA_HOME` वाले फ़ोल्डर में):

```text
~/.memoria/
  <project>/<YYYY-MM-DD>-<slug>.md   हर note की एक फ़ाइल
  config.json                        update URLs (ऑप्शनल)
  .indice/memoria-v2.sqlite          index; डिलीट कर सकते हैं
  .indice/registo.sqlite             MCP कॉल्स का log ("Claude की एक्टिविटी")
  preferencias.json                  picker में चुनी भाषा
```

हर note में एक YAML हेडर होता है। Fields के नाम पुर्तगाली में हैं और contract का हिस्सा हैं:

```markdown
---
tipo: licao            # licao (सबक) | fazer (करें) | nao_fazer (न करें) | historico (हिस्ट्री)
titulo: Build cache इस्तेमाल करें
projeto: arena-de-seguranca
tarefa: ARENA-12       # ऑप्शनल: ticket key (या owner/repo#12)
epico: ARENA-1         # ऑप्शनल: epic या parent
url: https://company.atlassian.net/browse/ARENA-12   # ऑप्शनल
etiquetas: [ci, cache] # ऑप्शनल: tags
ficheiros: [orquestrador/plan.mjs]
data: '2026-10-16T13:25:33+01:00'
custo_usd: 1.25        # ऑप्शनल
ligacoes: [Retries से बचें]
---

Cache से build 3 गुना तेज़ होता है। देखें [[Retries से बचें]]।
```

आप फ़ाइलें हाथ से एडिट कर सकते हैं; ऐप बदलाव पकड़ लेता है।
`memoria reindex` कभी भी index फिर से बनाता है।
`epico`, `url` और `etiquetas` v0.2 में आए और ऑप्शनल हैं: v0.1 के notes चलते रहते हैं।

Tickets:

- Jira keys कैपिटल में रहती हैं (`abc-123` → `ABC-123`); GitHub की `owner/repo#12` जैसी।
- `tarefa` न हो तो ऐप उसे `url` से निकालता है, अगर वो Jira ticket या issue/PR हो।
- बिना `epico` वाला note अपने टास्क का epic ले लेता है, अगर कोई और note उसे बताता हो।
- `ABC-123` सर्च करने पर उस टास्क के notes, उसके epic के notes और उसे mention करने वाले notes मिलते हैं।

Links की ताक़त, सबसे मज़बूत पहले:
explicit link (`[[...]]` या `ligacoes`), वही टास्क, वही epic, वही प्रोजेक्ट, शेयर्ड फ़ाइलें।

## अपडेट

```bash
memoria update
```

1. `git ls-remote --tags` से लेटेस्ट वर्ज़न ढूँढता है (बिना API)।
2. wheel और `constraints.txt` डाउनलोड करके `SHA256SUMS` चेक करता है।
3. `uv tool install --force` से फिर से इंस्टॉल करता है।
4. Index फिर से बनाता है। **आपके notes को कभी नहीं छूता।**

Windows पर इंस्टॉल एक नई विंडो में पूरा होता है। पहले Claude Code बंद करें।

पोर्टेबल वर्ज़न में update नया zip डाउनलोड करके चेक करता है और ऐप का फ़ोल्डर उसी जगह बदल देता है।
Claude Code से कनेक्शन चलता रहता है।

URLs `~/.memoria/config.json` से आते हैं और वहाँ न हों तो पैकेज की `release.conf` से।
पढ़ी जाने वाली keys (उसी नाम का environment variable इन्हें ओवरराइड करता है):

| Key | उदाहरण |
|---|---|
| `MEMORY_APP_REPO_URL` | `https://<server>/<owner>/claude-memory-app.git` |
| `RELEASE_DOWNLOAD_URL` | `{repo}/releases/download/{version}/{file}` |
| `PYTHON_VERSION` | `3.12` (ऑप्शनल) |
| `UV` | `uv` executable का path (ऑप्शनल) |

## प्राइवेसी

- Notes, index और इंटरफ़ेस आपके कंप्यूटर पर रहते हैं।
- सेव करने से पहले ऐप tokens, API keys (`sk-ant-…`, `ghp_…`, `AKIA…`, `xox…`),
  JWTs, private keys और `password=…` जैसे पैटर्न मास्क करता है।
- इंटरफ़ेस सिर्फ़ `127.0.0.1` पर, एक random session key के साथ सुनता है।
- नेटवर्क का इस्तेमाल सिर्फ़ वर्ज़न चेक (`git ls-remote`) और `memoria update` के लिए होता है।
  बंद करने के लिए: `MEMORIA_SEM_UPDATE=1`।
- न embeddings, न models। सर्च सादा टेक्स्ट है (SQLite FTS5)।

## आम समस्याएँ

- **"इस Python के SQLite में FTS5 नहीं है"**: uv वाले Python से फिर से इंस्टॉल करें
  (`uv tool install --force --managed-python --python 3.12 <wheel>`)।
- **कंपनी का proxy**: uv और `memoria update` `HTTPS_PROXY` और सिस्टम certificates इस्तेमाल करते हैं।
  uv के लिए `UV_SYSTEM_CERTS=1` भी सेट करें।
- **विंडो नहीं खुलती**: `memoria --browser` वही इंटरफ़ेस ब्राउज़र में खोलता है।

## डेवलपमेंट

डेवलपमेंट की जानकारी English में है: [README.md](README.md#development), [CLAUDE.md](CLAUDE.md)
और [docs/HANDOVER.md](docs/HANDOVER.md)।

## License

MIT। देखें [LICENSE](LICENSE)।
Bricolage Grotesque, Noto Sans Devanagari और Noto Sans Hebrew फ़ॉन्ट SIL Open Font License 1.1
(`web/public/fonts/`) के साथ इंटरफ़ेस में शामिल हैं।
