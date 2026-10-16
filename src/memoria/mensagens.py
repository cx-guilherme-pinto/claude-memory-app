"""Mensagens da CLI, do selftest e dos erros, em pt, en, hi e he.

Cada chave tem as quatro línguas e os mesmos marcadores ({nome}); um teste confirma.
As traduções para hindi e hebraico devem ser revistas por quem fala a língua.
"""

from __future__ import annotations


def _m(pt: str, en: str, hi: str, he: str) -> dict[str, str]:
    return {"pt": pt, "en": en, "hi": hi, "he": he}


MENSAGENS: dict[str, dict[str, str]] = {
    # ------------------------------------------------------------------ erros
    "erro.memoria_nao_encontrada": _m(
        "Memória não encontrada: {ref}",
        "Memory not found: {ref}",
        "मेमोरी नहीं मिली: {ref}",
        "הזיכרון לא נמצא: {ref}",
    ),
    "erro.ficheiro_mudou": _m(
        "O ficheiro mudou no disco entretanto. Cancela e volta a abrir para editar.",
        "The file changed on disk in the meantime. Cancel and open it again to edit.",
        "इस बीच डिस्क पर फ़ाइल बदल गई। कैंसल करें और एडिट करने के लिए फिर से खोलें।",
        "הקובץ השתנה בדיסק בינתיים. בטלו ופתחו אותו שוב כדי לערוך.",
    ),
    "erro.url": _m(
        "O url tem de começar por http:// ou https://.",
        "The URL must start with http:// or https://.",
        "URL http:// या https:// से शुरू होना चाहिए।",
        "כתובת ה-URL חייבת להתחיל ב-http:// או ב-https://.",
    ),
    "erro.tipo_invalido": _m(
        "Tipo inválido: {tipo}. Usa um destes: {tipos}.",
        "Invalid type: {tipo}. Use one of: {tipos}.",
        "इनवैलिड टाइप: {tipo}। इनमें से कोई एक इस्तेमाल करें: {tipos}।",
        "סוג לא תקין: {tipo}. השתמשו באחד מאלה: {tipos}.",
    ),
    "erro.frontmatter_mapa": _m(
        "o frontmatter não é um mapa YAML",
        "the frontmatter is not a YAML mapping",
        "frontmatter एक YAML मैपिंग नहीं है",
        "ה-frontmatter אינו מיפוי YAML",
    ),
    "erro.falta_titulo": _m("Falta o título.", "The title is missing.", "टाइटल नहीं दिया गया।", "חסרה כותרת."),
    "erro.falta_projeto": _m("Falta o projeto.", "The project is missing.", "प्रोजेक्ट नहीं दिया गया।", "חסר פרויקט."),
    "erro.demasiadas": _m(
        "Demasiadas memórias com o nome {base}.",
        "Too many memories named {base}.",
        "{base} नाम की बहुत अधिक मेमोरी हैं।",
        "יותר מדי זיכרונות בשם {base}.",
    ),
    "erro.nota_grande": _m("A nota é demasiado grande.", "The note is too large.", "नोट बहुत बड़ा है।", "ההערה גדולה מדי."),
    "erro.falta_cabecalho": _m(
        "Falta o cabeçalho no início: linhas '---' com tipo, titulo e projeto.",
        "The header is missing at the top: '---' lines with tipo, titulo and projeto.",
        "शुरुआत में हेडर नहीं है: '---' लाइनें, जिनमें tipo, titulo और projeto हों।",
        "חסרה כותרת עליונה בהתחלה: שורות '---' עם tipo, titulo ו-projeto.",
    ),
    "erro.yaml": _m(
        "O cabeçalho YAML tem um erro.",
        "The YAML header has an error.",
        "YAML हेडर में एक एरर है।",
        "בכותרת ה-YAML יש שגיאה.",
    ),
    "erro.yaml_linha": _m(
        "O cabeçalho YAML tem um erro (linha {linha}).",
        "The YAML header has an error (line {linha}).",
        "YAML हेडर में एक एरर है (लाइन {linha})।",
        "בכותרת ה-YAML יש שגיאה (שורה {linha}).",
    ),
    "erro.cabecalho_mapa": _m(
        "O cabeçalho tem de ser uma lista de 'chave: valor'.",
        "The header must be a list of 'key: value' lines.",
        "हेडर 'key: value' लाइनों की सूची होना चाहिए।",
        "הכותרת העליונה חייבת להיות רשימה של שורות 'key: value'.",
    ),
    "erro.falta_titulo_cabecalho": _m(
        "Falta o titulo no cabeçalho.",
        "The header has no titulo.",
        "हेडर में titulo नहीं है।",
        "בכותרת העליונה חסר titulo.",
    ),
    "erro.dados_invalidos": _m("Dados inválidos.", "Invalid data.", "इनवैलिड डेटा।", "נתונים לא תקינים."),
    "erro.so_http": _m("Só ligações http/https.", "Only http/https links.", "सिर्फ़ http/https लिंक।", "רק קישורי http/https."),
    "erro.lingua": _m(
        "Língua não suportada: {codigo}. Usa uma destas: {linguas}.",
        "Unsupported language: {codigo}. Use one of: {linguas}.",
        "यह भाषा सपोर्टेड नहीं है: {codigo}। इनमें से कोई एक इस्तेमाल करें: {linguas}।",
        "שפה לא נתמכת: {codigo}. השתמשו באחת מאלה: {linguas}.",
    ),
    "erro.marcador": _m(
        "Marcador desconhecido no padrão: {padrao}",
        "Unknown placeholder in the pattern: {padrao}",
        "पैटर्न में अज्ञात प्लेसहोल्डर: {padrao}",
        "מציין מקום לא מוכר בתבנית: {padrao}",
    ),
    "erro.falta_urls": _m(
        "Falta MEMORY_APP_REPO_URL ou RELEASE_DOWNLOAD_URL em {caminho} e no release.conf do pacote.",
        "MEMORY_APP_REPO_URL or RELEASE_DOWNLOAD_URL is missing in {caminho} and in the package's release.conf.",
        "{caminho} में और पैकेज की release.conf में MEMORY_APP_REPO_URL या RELEASE_DOWNLOAD_URL नहीं है।",
        "MEMORY_APP_REPO_URL או RELEASE_DOWNLOAD_URL חסרים ב-{caminho} וב-release.conf של החבילה.",
    ),
    "erro.url_recusado": _m(
        "URL recusado (só https): {url}",
        "URL refused (https only): {url}",
        "URL रिजेक्ट (सिर्फ़ https): {url}",
        "כתובת URL נדחתה (רק https): {url}",
    ),
    "erro.fts5": _m(
        "O SQLite deste Python não tem FTS5 (sqlite {versao}, erro: {erro}). "
        "Reinstala com o Python gerido pelo uv: uv tool install --force --managed-python --python 3.12 <wheel>",
        "This Python's SQLite has no FTS5 (sqlite {versao}, error: {erro}). "
        "Reinstall with the uv-managed Python: uv tool install --force --managed-python --python 3.12 <wheel>",
        "इस Python के SQLite में FTS5 नहीं है (sqlite {versao}, एरर: {erro})। "
        "uv द्वारा प्रबंधित Python के साथ फिर से इंस्टॉल करें: uv tool install --force --managed-python --python 3.12 <wheel>",
        "ל-SQLite של Python הזה אין FTS5 (sqlite {versao}, שגיאה: {erro}). "
        "התקינו מחדש עם Python שמנוהל על ידי uv: uv tool install --force --managed-python --python 3.12 <wheel>",
    ),
    "erro.zip_caminho": _m(
        "Caminho fora da pasta no zip: {ficheiro}",
        "Path outside the folder in the zip: {ficheiro}",
        "zip में फ़ोल्डर के बाहर का पाथ: {ficheiro}",
        "נתיב מחוץ לתיקייה בקובץ ה-zip: {ficheiro}",
    ),
    "erro.zip_ligacao": _m(
        "Ligação para fora da pasta no zip: {ficheiro}",
        "Link pointing outside the folder in the zip: {ficheiro}",
        "zip में फ़ोल्डर के बाहर जाने वाला लिंक: {ficheiro}",
        "קישור שמפנה אל מחוץ לתיקייה בקובץ ה-zip: {ficheiro}",
    ),
    # ----------------------------------------------------------------- avisos
    "aviso.config_invalido": _m(
        "Aviso: {caminho} inválido ({erro}). A ignorar.",
        "Warning: {caminho} is invalid ({erro}). Ignoring it.",
        "वॉर्निंग: {caminho} इनवैलिड है ({erro})। इसे इग्नोर कर रहे हैं।",
        "אזהרה: {caminho} לא תקין ({erro}). מתעלמים ממנו.",
    ),
    "aviso.memoria_ignorada": _m(
        "Aviso: memória ignorada: {erro}",
        "Warning: memory skipped: {erro}",
        "वॉर्निंग: मेमोरी स्किप की गई: {erro}",
        "אזהרה: זיכרון דולג: {erro}",
    ),
    # -------------------------------------------------------------------- CLI
    "cli.descricao": _m(
        "Memória: notas locais do Claude Code, com grafo e servidor MCP. Sem argumentos, abre a janela.",
        "Memória: local notes for Claude Code, with a graph and an MCP server. With no arguments, it opens the window.",
        "Memória: Claude Code के लिए लोकल नोट्स, ग्राफ़ और MCP सर्वर के साथ। बिना आर्ग्युमेंट के यह विंडो खोलता है।",
        "Memória: הערות מקומיות ל-Claude Code, עם גרף ושרת MCP. בלי ארגומנטים היא פותחת את החלון.",
    ),
    "cli.browser": _m(
        "abrir a interface no browser em vez da janela",
        "open the interface in the browser instead of the window",
        "विंडो के बजाय ब्राउज़र में इंटरफ़ेस खोलें",
        "לפתוח את הממשק בדפדפן במקום בחלון",
    ),
    "cli.mcp": _m(
        "servidor MCP em stdio (para o Claude Code)",
        "MCP server over stdio (for Claude Code)",
        "stdio पर MCP सर्वर (Claude Code के लिए)",
        "שרת MCP דרך stdio (עבור Claude Code)",
    ),
    "cli.add": _m("adicionar uma memória", "add a memory", "एक मेमोरी जोड़ें", "להוסיף זיכרון"),
    "cli.add.tipo": _m(
        "licao, fazer, nao_fazer ou historico",
        "licao, fazer, nao_fazer or historico",
        "licao, fazer, nao_fazer या historico",
        "licao, fazer, nao_fazer או historico",
    ),
    "cli.add.titulo": _m(
        "título curto (por omissão, a primeira linha do texto)",
        "short title (by default, the first line of the text)",
        "छोटा टाइटल (डिफ़ॉल्ट रूप से, टेक्स्ट की पहली लाइन)",
        "כותרת קצרה (כברירת מחדל, השורה הראשונה של הטקסט)",
    ),
    "cli.add.projeto": _m("nome do projeto", "project name", "प्रोजेक्ट का नाम", "שם הפרויקט"),
    "cli.add.texto": _m(
        "corpo em Markdown (por omissão, lê do stdin)",
        "body in Markdown (by default, read from stdin)",
        "Markdown में मुख्य भाग (डिफ़ॉल्ट रूप से, stdin से पढ़ा जाता है)",
        "גוף ב-Markdown (כברירת מחדל, נקרא מ-stdin)",
    ),
    "cli.add.tarefa": _m(
        "chave do ticket, ex.: ABC-123 ou dono/repo#12",
        "ticket key, e.g. ABC-123 or owner/repo#12",
        "टिकट की key, जैसे ABC-123 या owner/repo#12",
        "מפתח הטיקט, למשל ABC-123 או owner/repo#12",
    ),
    "cli.add.epico": _m(
        "chave do épico ou do pai, ex.: ABC-100",
        "epic or parent key, e.g. ABC-100",
        "एपिक या पैरेंट की key, जैसे ABC-100",
        "מפתח האפיק או ההורה, למשל ABC-100",
    ),
    "cli.add.url": _m("ligação para o ticket ou PR", "link to the ticket or PR", "टिकट या PR का लिंक", "קישור לטיקט או ל-PR"),
    "cli.add.etiqueta": _m(
        "palavra para pesquisa (pode repetir)",
        "search word (can be repeated)",
        "खोज के लिए शब्द (दोहरा सकते हैं)",
        "מילת חיפוש (אפשר לחזור עליה)",
    ),
    "cli.add.ficheiro": _m(
        "caminho de código (pode repetir)",
        "code path (can be repeated)",
        "कोड पाथ (दोहरा सकते हैं)",
        "נתיב קוד (אפשר לחזור עליו)",
    ),
    "cli.add.ligacao": _m(
        "outra memória (pode repetir)",
        "another memory (can be repeated)",
        "कोई दूसरी मेमोरी (दोहरा सकते हैं)",
        "זיכרון אחר (אפשר לחזור עליו)",
    ),
    "cli.add.custo": _m("custo em dólares", "cost in US dollars", "अमेरिकी डॉलर में लागत", "עלות בדולרים"),
    "cli.procurar": _m("procurar memórias", "search memories", "मेमोरी खोजें", "לחפש זיכרונות"),
    "cli.reindex": _m(
        "reconstruir o índice a partir dos Markdown",
        "rebuild the index from the Markdown files",
        "Markdown फ़ाइलों से इंडेक्स फिर से बनाएँ",
        "לבנות מחדש את האינדקס מקובצי ה-Markdown",
    ),
    "cli.update": _m("instalar a versão mais recente", "install the latest version", "लेटेस्ट वर्ज़न इंस्टॉल करें", "להתקין את הגרסה האחרונה"),
    "cli.update.verificar": _m(
        "só mostrar se há versão nova",
        "only show whether there is a new version",
        "सिर्फ़ दिखाएँ कि नया वर्ज़न है या नहीं",
        "רק להציג אם יש גרסה חדשה",
    ),
    "cli.update.forcar": _m(
        "reinstalar mesmo que seja a mesma versão",
        "reinstall even if it is the same version",
        "वही वर्ज़न होने पर भी फिर से इंस्टॉल करें",
        "להתקין מחדש גם אם זו אותה גרסה",
    ),
    "cli.update.versao": _m(
        "instalar esta tag (ex.: v0.1.0)",
        "install this tag (e.g. v0.1.0)",
        "यह टैग इंस्टॉल करें (जैसे v0.1.0)",
        "להתקין את התג הזה (למשל v0.1.0)",
    ),
    "cli.selftest": _m("verificar a instalação", "check the installation", "इंस्टॉलेशन की जाँच करें", "לבדוק את ההתקנה"),
    "cli.selftest.gui": _m(
        "abrir a janela e fechá-la sozinha",
        "open the window and close it automatically",
        "विंडो खोलें और अपने-आप बंद करें",
        "לפתוח את החלון ולסגור אותו אוטומטית",
    ),
    "cli.lingua": _m(
        "mostrar ou escolher a língua (pt, en, hi, he)",
        "show or choose the language (pt, en, hi, he)",
        "भाषा दिखाएँ या चुनें (pt, en, hi, he)",
        "להציג או לבחור את השפה (pt, en, hi, he)",
    ),
    "cli.lingua_atual": _m(
        "Língua: {nome} ({codigo}). Sistema: {sistema}.",
        "Language: {nome} ({codigo}). System: {sistema}.",
        "भाषा: {nome} ({codigo})। सिस्टम: {sistema}।",
        "שפה: {nome} ({codigo}). מערכת: {sistema}.",
    ),
    "cli.sem_resultados": _m("Sem resultados.", "No results.", "कोई परिणाम नहीं।", "אין תוצאות."),
    "cli.reindex_feito": _m(
        "Índice reconstruído: {total} memórias em {segundos} s.",
        "Index rebuilt: {total} memories in {segundos} s.",
        "इंडेक्स फिर से बना: {segundos} s में {total} मेमोरी।",
        "האינדקס נבנה מחדש: {total} זיכרונות תוך {segundos} שניות.",
    ),
    "cli.ignorados": _m(
        "Aviso: {n} ficheiro(s) ignorado(s) (ver acima).",
        "Warning: {n} file(s) skipped (see above).",
        "वॉर्निंग: {n} फ़ाइल स्किप हुईं (ऊपर देखें)।",
        "אזהרה: {n} קבצים דולגו (ראו למעלה).",
    ),
    "cli.redigidos": _m(
        "Aviso: {n} segredo(s) redigido(s).",
        "Warning: {n} secret(s) redacted.",
        "वॉर्निंग: {n} secrets मास्क किए गए।",
        "אזהרה: {n} סודות הוסתרו.",
    ),
    # --------------------------------------------------------------- selftest
    "st.ok": _m("OK", "OK", "OK", "OK"),
    "st.falhou": _m("FALHOU", "FAILED", "फ़ेल", "נכשל"),
    "st.sqlite": _m(
        "SQLite {versao} com FTS5",
        "SQLite {versao} with FTS5",
        "FTS5 के साथ SQLite {versao}",
        "SQLite {versao} עם FTS5",
    ),
    "st.redacao": _m("Redação de segredos", "Secret redaction", "Secrets मास्क करना", "הסתרת סודות"),
    "st.fts": _m("Pesquisa FTS5", "FTS5 search", "FTS5 सर्च", "חיפוש FTS5"),
    "st.arestas": _m("Arestas e relacionadas", "Edges and related memories", "एजेस और रिलेटेड मेमोरी", "קשתות וזיכרונות קשורים"),
    "st.chave": _m("Pesquisa por tarefa e épico", "Search by task and epic", "टास्क और एपिक से सर्च", "חיפוש לפי משימה ואפיק"),
    "st.reindex": _m("Reindex a partir do Markdown", "Reindex from Markdown", "Markdown से रीइंडेक्स", "בניית אינדקס מחדש מ-Markdown"),
    "st.mcp": _m("Servidor MCP (3 ferramentas)", "MCP server (3 tools)", "MCP सर्वर (3 टूल)", "שרת MCP (3 כלים)"),
    "st.basicas": _m("Operações básicas: {erro}", "Basic operations: {erro}", "बुनियादी काम: {erro}", "פעולות בסיסיות: {erro}"),
    "st.ui": _m("Interface incluída no pacote", "Interface included in the package", "पैकेज में इंटरफ़ेस शामिल है", "הממשק כלול בחבילה"),
    "st.urls_ok": _m("URLs de atualização ({host})", "Update URLs ({host})", "अपडेट URL ({host})", "כתובות עדכון ({host})"),
    "st.urls_erro": _m("URLs de atualização: {erro}", "Update URLs: {erro}", "अपडेट URL: {erro}", "כתובות עדכון: {erro}"),
    "st.pasta": _m("Pasta das memórias: {pasta}", "Memory folder: {pasta}", "मेमोरी फ़ोल्डर: {pasta}", "תיקיית הזיכרונות: {pasta}"),
    "st.sem_escrita": _m(
        "Sem escrita em {pasta}: {erro}",
        "Cannot write to {pasta}: {erro}",
        "{pasta} में लिखा नहीं जा सकता: {erro}",
        "אי אפשר לכתוב ב-{pasta}: {erro}",
    ),
    "st.copia_temporaria": _m(
        "A app corre de uma cópia temporária do macOS. Move-a para Aplicações.",
        "The app is running from a temporary macOS copy. Move it to Applications.",
        "ऐप macOS की एक अस्थायी कॉपी से चल रहा है। इसे Applications में ले जाएँ।",
        "האפליקציה רצה מעותק זמני של macOS. העבירו אותה לתיקיית Applications.",
    ),
    "st.portatil": _m(
        "Versão portátil {plataforma}: {raiz}",
        "Portable version {plataforma}: {raiz}",
        "पोर्टेबल वर्ज़न {plataforma}: {raiz}",
        "גרסה ניידת {plataforma}: {raiz}",
    ),
    "st.lingua": _m(
        "Língua: {nome} ({codigo})",
        "Language: {nome} ({codigo})",
        "भाषा: {nome} ({codigo})",
        "שפה: {nome} ({codigo})",
    ),
    "st.resultado": _m("selftest: {estado}", "selftest: {estado}", "selftest: {estado}", "selftest: {estado}"),
    "st.antes_janela": _m(
        "selftest: {estado} (antes da janela)",
        "selftest: {estado} (before the window)",
        "selftest: {estado} (विंडो से पहले)",
        "selftest: {estado} (לפני החלון)",
    ),
    "st.ligar": _m("Para ligar ao Claude Code:", "To connect it to Claude Code:", "Claude Code से जोड़ने के लिए:", "כדי לחבר ל-Claude Code:"),
    # ----------------------------------------------------------------- janela
    "jan.sem_webview2": _m(
        "O WebView2 Runtime não está instalado.",
        "The WebView2 Runtime is not installed.",
        "WebView2 Runtime इंस्टॉल नहीं है।",
        "WebView2 Runtime אינו מותקן.",
    ),
    "jan.sem_gtk": _m(
        "Sem GTK/Qt para a janela nativa.",
        "No GTK/Qt for the native window.",
        "नेटिव विंडो के लिए GTK/Qt नहीं है।",
        "אין GTK/Qt לחלון המקורי.",
    ),
    "jan.sem_ui": _m(
        "A UI não está no pacote ({pasta}). Corre scripts/build.sh.",
        "The UI is not in the package ({pasta}). Run scripts/build.sh.",
        "UI पैकेज में नहीं है ({pasta})। scripts/build.sh चलाएँ।",
        "הממשק לא נמצא בחבילה ({pasta}). הריצו scripts/build.sh.",
    ),
    "jan.selftest_sem_janela": _m(
        "selftest --gui: FALHOU. Janela nativa indisponível: {motivo}",
        "selftest --gui: FAILED. Native window unavailable: {motivo}",
        "selftest --gui: फ़ेल। नेटिव विंडो उपलब्ध नहीं: {motivo}",
        "selftest --gui: נכשל. החלון המקורי אינו זמין: {motivo}",
    ),
    "jan.sem_janela_browser": _m(
        "Sem janela, a app abre a mesma interface no browser.",
        "Without the window, the app opens the same interface in the browser.",
        "विंडो के बिना ऐप वही इंटरफ़ेस ब्राउज़र में खोलता है।",
        "בלי החלון, האפליקציה פותחת את אותו ממשק בדפדפן.",
    ),
    "jan.indisponivel": _m(
        "Janela nativa indisponível ({motivo}). A abrir no browser.",
        "Native window unavailable ({motivo}). Opening in the browser.",
        "नेटिव विंडो उपलब्ध नहीं ({motivo})। ब्राउज़र में खोल रहे हैं।",
        "החלון המקורי אינו זמין ({motivo}). פותחים בדפדפן.",
    ),
    "jan.sem_resposta": _m(
        "selftest --gui: FALHOU. A interface não respondeu em {s} s.",
        "selftest --gui: FAILED. The interface did not respond within {s} s.",
        "selftest --gui: फ़ेल। इंटरफ़ेस ने {s} s में जवाब नहीं दिया।",
        "selftest --gui: נכשל. הממשק לא הגיב תוך {s} שניות.",
    ),
    "jan.erro_ui": _m(
        "selftest --gui: FALHOU. Erro na interface: {erro}",
        "selftest --gui: FAILED. Interface error: {erro}",
        "selftest --gui: फ़ेल। इंटरफ़ेस में एरर: {erro}",
        "selftest --gui: נכשל. שגיאה בממשק: {erro}",
    ),
    "jan.ok": _m(
        "selftest --gui: OK. {nos} nós; interface pronta em {ms} ms (ponte {via} em {ponte} ms, dados {grafo} ms); "
        "total desde o arranque {total} ms.",
        "selftest --gui: OK. {nos} nodes; interface ready in {ms} ms (bridge {via} in {ponte} ms, data {grafo} ms); "
        "total since start {total} ms.",
        "selftest --gui: OK. {nos} नोड; इंटरफ़ेस {ms} ms में तैयार (ब्रिज {via}, {ponte} ms में; डेटा {grafo} ms); "
        "शुरुआत से कुल {total} ms।",
        "selftest --gui: OK. {nos} צמתים; הממשק מוכן תוך {ms} ms (גשר {via} תוך {ponte} ms, נתונים {grafo} ms); "
        'סה"כ מההפעלה {total} ms.',
    ),
    "jan.pywebview": _m(
        "o pywebview não carregou: {erro}",
        "pywebview did not load: {erro}",
        "pywebview लोड नहीं हुआ: {erro}",
        "pywebview לא נטען: {erro}",
    ),
    "jan.renderer": _m(
        "o pywebview escolheu {renderer}, não o WebView2",
        "pywebview picked {renderer}, not WebView2",
        "pywebview ने WebView2 के बजाय {renderer} चुना",
        "pywebview בחר ב-{renderer} ולא ב-WebView2",
    ),
    "jan.winforms": _m(
        "WinForms/pythonnet falhou: {erro}",
        "WinForms/pythonnet failed: {erro}",
        "WinForms/pythonnet फ़ेल: {erro}",
        "WinForms/pythonnet נכשל: {erro}",
    ),
    "jan.nao_arrancou": _m(
        "a janela não arrancou: {erro}",
        "the window did not start: {erro}",
        "विंडो शुरू नहीं हुई: {erro}",
        "החלון לא נפתח: {erro}",
    ),
    "jan.browser_url": _m(
        "Memória no browser: {url}",
        "Memória in the browser: {url}",
        "ब्राउज़र में Memória: {url}",
        "Memória בדפדפן: {url}",
    ),
    "jan.browser_aberto": _m(
        "A página abriu no browser. Ctrl+C para terminar.",
        "The page opened in the browser. Press Ctrl+C to stop.",
        "पेज ब्राउज़र में खुल गया। बंद करने के लिए Ctrl+C दबाएँ।",
        "הדף נפתח בדפדפן. Ctrl+C לסיום.",
    ),
    "jan.browser_abre": _m(
        "Abre este endereço no browser. Ctrl+C para terminar.",
        "Open this address in the browser. Press Ctrl+C to stop.",
        "यह पता ब्राउज़र में खोलें। बंद करने के लिए Ctrl+C दबाएँ।",
        "פתחו את הכתובת הזו בדפדפן. Ctrl+C לסיום.",
    ),
    "jan.browser_ok": _m(
        "selftest: OK no browser em {ms} ms.",
        "selftest: OK in the browser in {ms} ms.",
        "selftest: OK, ब्राउज़र में {ms} ms में।",
        "selftest: OK בדפדפן תוך {ms} ms.",
    ),
    "jan.browser_falhou": _m(
        "selftest: FALHOU no browser.",
        "selftest: FAILED in the browser.",
        "selftest: ब्राउज़र में फ़ेल।",
        "selftest: נכשל בדפדפן.",
    ),
    # --------------------------------------------------- página sem sessão
    "web.sem_sessao_titulo": _m("Sessão sem chave", "Session without a key", "बिना key का सेशन", "הפעלה ללא מפתח"),
    "web.sem_sessao_1": _m(
        "Abre o endereço completo que a Memória mostrou no terminal. Começa por {base}?t=",
        "Open the full address that Memória printed in the terminal. It starts with {base}?t=",
        "वह पूरा पता खोलें जो Memória ने टर्मिनल में दिखाया था। यह {base}?t= से शुरू होता है।",
        "פתחו את הכתובת המלאה ש-Memória הציגה בטרמינל. היא מתחילה ב-{base}?t=",
    ),
    "web.sem_sessao_2": _m(
        "Ou fecha esta página e corre de novo: memoria --browser",
        "Or close this page and run it again: memoria --browser",
        "या यह पेज बंद करें और फिर से चलाएँ: memoria --browser",
        "או סגרו את הדף והריצו שוב: memoria --browser",
    ),
    # ----------------------------------------------------------------- update
    "up.sem_git": _m(
        "O git não está instalado. É preciso para descobrir as versões.",
        "git is not installed. It is needed to find the versions.",
        "git इंस्टॉल नहीं है। वर्ज़न खोजने के लिए इसकी ज़रूरत है।",
        "git אינו מותקן. הוא נדרש כדי למצוא את הגרסאות.",
    ),
    "up.sem_clt": _m(
        "O git não está instalado (faltam as Command Line Tools do Xcode).",
        "git is not installed (the Xcode Command Line Tools are missing).",
        "git इंस्टॉल नहीं है (Xcode Command Line Tools नहीं हैं)।",
        "git אינו מותקן (חסרים ה-Command Line Tools של Xcode).",
    ),
    "up.git_lento": _m(
        "O git demorou mais de {s} s a responder.",
        "git took more than {s} s to answer.",
        "git ने जवाब देने में {s} s से ज़्यादा समय लिया।",
        "git לקח יותר מ-{s} שניות לענות.",
    ),
    "up.ls_remote": _m(
        "git ls-remote falhou: {erro}",
        "git ls-remote failed: {erro}",
        "git ls-remote फ़ेल: {erro}",
        "git ls-remote נכשל: {erro}",
    ),
    "up.download_falhou": _m(
        "O download falhou ({codigo}): {url}",
        "Download failed ({codigo}): {url}",
        "डाउनलोड फ़ेल ({codigo}): {url}",
        "ההורדה נכשלה ({codigo}): {url}",
    ),
    "up.sem_ligacao": _m(
        "Sem ligação a {host}: {motivo}",
        "No connection to {host}: {motivo}",
        "{host} से कनेक्शन नहीं: {motivo}",
        "אין חיבור ל-{host}: {motivo}",
    ),
    "up.sem_credenciais": _m(
        "Download recusado e não há credenciais: {url}",
        "Download refused and there are no credentials: {url}",
        "डाउनलोड रिजेक्ट हुआ और कोई क्रेडेंशियल नहीं है: {url}",
        "ההורדה נדחתה ואין פרטי גישה: {url}",
    ),
    "up.sem_uv": _m(
        "Não encontrei o uv. Instala-o primeiro (ver README).",
        "uv was not found. Install it first (see the README).",
        "uv नहीं मिला। पहले इसे इंस्टॉल करें (README देखें)।",
        "uv לא נמצא. התקינו אותו קודם (ראו README).",
    ),
    "up.falta_repo": _m(
        "Falta MEMORY_APP_REPO_URL em {caminho} e no release.conf do pacote.",
        "MEMORY_APP_REPO_URL is missing in {caminho} and in the package's release.conf.",
        "{caminho} में और पैकेज की release.conf में MEMORY_APP_REPO_URL नहीं है।",
        "MEMORY_APP_REPO_URL חסר ב-{caminho} וב-release.conf של החבילה.",
    ),
    "up.sem_versoes": _m(
        "Não encontrei nenhuma versão (tags vX.Y.Z) no repositório.",
        "No version (vX.Y.Z tags) was found in the repository.",
        "रिपॉज़िटरी में कोई वर्ज़न (vX.Y.Z टैग) नहीं मिला।",
        "לא נמצאה אף גרסה (תגי vX.Y.Z) במאגר.",
    ),
    "up.versao_invalida": _m("Versão inválida: {tag}", "Invalid version: {tag}", "इनवैलिड वर्ज़न: {tag}", "גרסה לא תקינה: {tag}"),
    "up.versoes": _m(
        "Versão instalada: {atual}. Última: {ultima}.",
        "Installed version: {atual}. Latest: {ultima}.",
        "इंस्टॉल वर्ज़न: {atual}। लेटेस्ट: {ultima}।",
        "הגרסה המותקנת: {atual}. האחרונה: {ultima}.",
    ),
    "up.ja_recente": _m(
        "Já tens a versão mais recente.",
        "You already have the latest version.",
        "आपके पास पहले से लेटेस्ट वर्ज़न है।",
        "הגרסה האחרונה כבר מותקנת.",
    ),
    "up.falta_soma": _m(
        "{nome} não está no SHA256SUMS da versão {tag}.",
        "{nome} is not in the SHA256SUMS of version {tag}.",
        "{nome} वर्ज़न {tag} की SHA256SUMS में नहीं है।",
        "{nome} לא מופיע ב-SHA256SUMS של גרסה {tag}.",
    ),
    "up.a_descarregar": _m("A descarregar {nome}…", "Downloading {nome}…", "{nome} डाउनलोड हो रहा है…", "מוריד את {nome}…"),
    "up.sha_instalado": _m(
        "SHA-256 não confere: {nome}. Nada foi instalado.",
        "SHA-256 mismatch: {nome}. Nothing was installed.",
        "SHA-256 मेल नहीं खाता: {nome}। कुछ भी इंस्टॉल नहीं हुआ।",
        "SHA-256 לא תואם: {nome}. שום דבר לא הותקן.",
    ),
    "up.a_instalar": _m("A instalar com o uv…", "Installing with uv…", "uv से इंस्टॉल हो रहा है…", "מתקין עם uv…"),
    "up.uv_falhou": _m(
        "uv tool install falhou (código {codigo}).",
        "uv tool install failed (code {codigo}).",
        "uv tool install फ़ेल (कोड {codigo})।",
        "uv tool install נכשל (קוד {codigo}).",
    ),
    "up.atualizado": _m(
        "Atualizado para {versao}. As memórias não foram tocadas.",
        "Updated to {versao}. Your memories were not touched.",
        "{versao} पर अपडेट हो गया। आपकी मेमोरी में कोई बदलाव नहीं हुआ।",
        "עודכן לגרסה {versao}. הזיכרונות לא שונו.",
    ),
    "up.reindex_falhou": _m(
        "Aviso: o reindex falhou. Corre `memoria reindex` à mão.",
        "Warning: the reindex failed. Run `memoria reindex` yourself.",
        "वॉर्निंग: reindex फ़ेल। `memoria reindex` खुद चलाएँ।",
        "אזהרה: בניית האינדקס נכשלה. הריצו `memoria reindex` ידנית.",
    ),
    "up.nova_janela": _m(
        "A atualização continua numa nova janela, depois de esta terminar.",
        "The update continues in a new window after this one closes.",
        "यह विंडो बंद होने के बाद अपडेट एक नई विंडो में जारी रहेगा।",
        "העדכון ימשיך בחלון חדש אחרי שהחלון הזה ייסגר.",
    ),
    # Mensagens dos scripts PowerShell que o update lança no Windows.
    "ps.a_instalar": _m(
        "A instalar a nova versão da Memória...",
        "Installing the new version of Memória...",
        "Memória का नया वर्ज़न इंस्टॉल हो रहा है...",
        "מתקין את הגרסה החדשה של Memória...",
    ),
    "ps.uv_falhou": _m("uv tool install falhou.", "uv tool install failed.", "uv tool install फ़ेल।", "uv tool install נכשל."),
    "ps.enter": _m("Enter para fechar", "Press Enter to close", "बंद करने के लिए Enter दबाएँ", "Enter לסגירה"),
    "ps.atualizada": _m(
        "Memória atualizada. As memórias não foram tocadas.",
        "Memória updated. Your memories were not touched.",
        "Memória अपडेट हो गई। आपकी मेमोरी में कोई बदलाव नहीं हुआ।",
        "Memória עודכנה. הזיכרונות לא שונו.",
    ),
    "ps.fecha": _m(
        "Fecha a Memória e o Claude Code para continuar...",
        "Close Memória and Claude Code to continue...",
        "जारी रखने के लिए Memória और Claude Code बंद करें...",
        "סגרו את Memória ואת Claude Code כדי להמשיך...",
    ),
    "ps.nao_substituiu": _m(
        "Não consegui substituir a pasta. Nada foi alterado.",
        "Could not replace the folder. Nothing was changed.",
        "फ़ोल्डर बदला नहीं जा सका। कुछ भी नहीं बदला।",
        "לא הצלחתי להחליף את התיקייה. שום דבר לא שונה.",
    ),
    # --------------------------------------------------------- versão portátil
    "pt.selftest_falhou": _m(
        "A versão {versao} falhou o selftest. Nada foi alterado.",
        "Version {versao} failed the selftest. Nothing was changed.",
        "वर्ज़न {versao} selftest में फ़ेल रहा। कुछ भी नहीं बदला।",
        "גרסה {versao} נכשלה ב-selftest. שום דבר לא שונה.",
    ),
    "pt.copia_temporaria": _m(
        "A Memória está a correr de uma cópia temporária do macOS. Move-a para Aplicações e tenta outra vez.",
        "Memória is running from a temporary macOS copy. Move it to Applications and try again.",
        "Memória macOS की एक अस्थायी कॉपी से चल रहा है। इसे Applications में ले जाएँ और फिर से कोशिश करें।",
        "Memória רצה מעותק זמני של macOS. העבירו אותה לתיקיית Applications ונסו שוב.",
    ),
    "pt.sha": _m(
        "SHA-256 não confere: {nome}. Nada foi alterado.",
        "SHA-256 mismatch: {nome}. Nothing was changed.",
        "SHA-256 मेल नहीं खाता: {nome}। कुछ भी नहीं बदला।",
        "SHA-256 לא תואם: {nome}. שום דבר לא שונה.",
    ),
    "pt.extrair": _m(
        "Não consegui extrair {nome}: {erro}",
        "Could not extract {nome}: {erro}",
        "{nome} को निकाला नहीं जा सका: {erro}",
        "לא הצלחתי לחלץ את {nome}: {erro}",
    ),
    "pt.plataforma": _m(
        "{nome} não tem a versão portátil esperada ({plataforma}). Nada foi alterado.",
        "{nome} does not contain the expected portable version ({plataforma}). Nothing was changed.",
        "{nome} में अपेक्षित पोर्टेबल वर्ज़न ({plataforma}) नहीं है। कुछ भी नहीं बदला।",
        "{nome} אינו מכיל את הגרסה הניידת הצפויה ({plataforma}). שום דבר לא שונה.",
    ),
    "pt.a_verificar": _m("A verificar a nova versão…", "Checking the new version…", "नए वर्ज़न की चेक हो रहा है…", "בודק את הגרסה החדשה…"),
    "pt.atualizado": _m(
        "Atualizado para {versao} em {pasta}. As memórias não foram tocadas.",
        "Updated to {versao} in {pasta}. Your memories were not touched.",
        "{pasta} में {versao} पर अपडेट हो गया। आपकी मेमोरी में कोई बदलाव नहीं हुआ।",
        "עודכן לגרסה {versao} ב-{pasta}. הזיכרונות לא שונו.",
    ),
    "pt.reabrir": _m(
        "Fecha e volta a abrir a Memória e o Claude Code.",
        "Close and reopen Memória and Claude Code.",
        "Memória और Claude Code को बंद करके फिर से खोलें।",
        "סגרו ופתחו מחדש את Memória ואת Claude Code.",
    ),
}
