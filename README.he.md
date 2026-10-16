# Memória

[English](README.md) · [Português](README.pt.md) · [हिन्दी](README.hi.md) · **עברית**

Memória שומרת את מה ש-Claude Code לומד בקובצי Markdown, במחשב שלכם.
היא מציגה את ההערות כגרף ומחזירה אותן ל-Claude Code דרך שרת MCP.

- **לקחים**, כללים (**לעשות**, **לא לעשות**) ו**היסטוריה** של משימות.
- כל הערה יכולה להיות מקושרת לטיקט (Jira, GitHub) ולאפיק שלו.
- חיפוש מהיר (SQLite FTS5) לפי שם, פרויקט, טיקט, אפיק, תגיות וטקסט.
- חלון עם הגרף, מסננים, ציר זמן, טופס להערה חדשה והפעילות של Claude ב-MCP.
- באנגלית, פורטוגזית, הינדי ועברית.
- הכול נשאר במחשב שלכם. שום דבר לא נשלח החוצה.

## התקנה

לא צריך הרשאות מנהל.

<!-- >>> instalar: gerado a partir de release.conf por scripts/render_installers.py -->
**macOS** (Intel ו-Apple Silicon) ו-Linux, ב-Terminal:

```bash
curl -fsSL https://gitea.guilhermepinto.pt/guilherme/claude-memory-app/releases/download/v0.4.0/install.sh | sh
```

**Windows 10/11**, ב-PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -c "irm https://gitea.guilhermepinto.pt/guilherme/claude-memory-app/releases/download/v0.4.0/install.ps1 | iex"
```
<!-- <<< instalar -->

תוכנית ההתקנה:

1. מתקינה את [uv](https://docs.astral.sh/uv/) (גרסה קבועה) אם הוא חסר;
2. מורידה את ה-wheel ואת `constraints.txt` ובודקת את ה-SHA-256;
3. מתקינה את האפליקציה עם Python 3.12 שמנוהל על ידי uv;
4. ב-Windows, מתקינה את WebView2 Runtime (למשתמש הנוכחי) אם הוא חסר;
5. יוצרת קיצור דרך: `~/Applications/Memória.app` ב-Mac, ו-"Memória" בתפריט Start ב-Windows.

הפקודות נמצאות ב-`~/.local/bin` (Mac/Linux) או ב-`%USERPROFILE%\.local\bin` (Windows).

### גרסה ניידת (בלי התקנה)

בכל release יש גם קובץ zip לכל פלטפורמה, עם Python בפנים:

| קובץ | לפתוח |
|---|---|
| `Memoria-<version>-macos-arm64.zip` (Apple Silicon) | `Memoria.app` |
| `Memoria-<version>-macos-x86_64.zip` (Intel) | `Memoria.app` |
| `Memoria-<version>-windows-x64.zip` | `Memoria\Memoria.exe` |

מחלצים ופותחים. לא צריך הרשאות מנהל ולא רשת. ה-setup של הסדנה עושה את זה לבד.

- חיבור ל-Claude Code: `memoria selftest` מציג את פקודת `claude mcp add` הנכונה.
  ב-Mac: `…/Memoria.app/Contents/MacOS/memoria selftest`; ב-Windows: `memoria.cmd selftest`.
- עדיף להתקין עם פקודת השורה האחת. zip שהורד בדפדפן דורש אישור ב-
  System Settings → Privacy & Security: ה-Mac חוסם את האפליקציה כי היא לא חתומה.
  כדי לשחרר ב-Terminal: `xattr -dr com.apple.quarantine ~/Applications/Memoria.app`.
  ב-Windows, במסך "Windows protected your PC", לחצו על "More info" ואז על "Run anyway".
- אחרי החיבור ל-Claude Code, אל תזיזו את האפליקציה.

פרטים והחלטות: [docs/portatil.md](docs/portatil.md) (באנגלית).

## חיבור ל-Claude Code

```bash
claude mcp add --scope user memoria -- "$HOME/.local/bin/memoria" mcp
```

ב-Windows: `claude mcp add --scope user memoria -- "%USERPROFILE%\.local\bin\memoria.exe" mcp`.

כלי ה-MCP:

| כלי | מטרה |
|---|---|
| `memoria_procurar(texto, projeto?, tipo?, tarefa?, epico?, limite=10)` | חיפוש הערות. מפתח טיקט (`ABC-123`) מחזיר את המשימה ואת האפיק שלה. |
| `memoria_adicionar(tipo, titulo, texto, projeto, tarefa?, epico?, url?, ficheiros?, ligacoes?, etiquetas?, custo_usd?)` | שומר הערה ומחזיר את הנתיב שלה. |
| `memoria_relacionadas(id_ou_caminho, limite=10)` | הערות מקושרות, מהקשר החזק ביותר. |

שמות הכלים והפרמטרים בפורטוגזית והם אף פעם לא משתנים.

## שימוש

| פקודה | מה היא עושה |
|---|---|
| `memoria` | פותחת את החלון. |
| `memoria --browser` | פותחת את אותו ממשק בדפדפן. |
| `memoria add --tipo licao --projeto p --titulo "..." --texto "..." [--tarefa ABC-123 --epico ABC-100 --url ...]` | שומרת הערה. |
| `memoria procurar "text" [--tarefa ABC-123] [--epico ABC-100]` | חיפוש משורת הפקודה. |
| `memoria reindex` | בונה מחדש את האינדקס מקובצי ה-Markdown. |
| `memoria update` | מתקינה את הגרסה האחרונה. |
| `memoria selftest [--gui]` | בודקת את ההתקנה. עם `--gui`, פותחת וסוגרת את החלון. |
| `memoria lingua [pt\|en\|hi\|he]` | מציגה או בוחרת את השפה. |
| `memoria mcp` | שרת MCP (ש-Claude Code משתמש בו). |

בחלון, לחצו על צומת כדי לראות את ההערה. `/` לחיפוש ו-`Esc` לסגירה.
החיפוש מציג זיכרונות, פרויקטים ומשימות/אפיקים; בחרו אחד כדי להתמקד בו.
המסננים בוחרים פרויקט, אפיק, משימה ותקופה. רשימת הסוגים מסננת את המפה.
כפתור הניגון של ציר הזמן מראה את הגרף צומח.

ב-Windows, אם WebView2 חסר, הממשק נפתח בדפדפן בכתובת `127.0.0.1`.
הטרמינל מציג את כתובת ההפעלה (`http://127.0.0.1:<port>/?t=<key>`).
המפתח מקומי ותקף רק כל עוד האפליקציה פתוחה.

## הפעילות של Claude

הכפתור **הפעילות של Claude** בראש העמודה מראה מה Claude ביקש מ-Memória דרך MCP:

- ארבעה מספרים: קריאות היום, סה״כ קריאות, קריאות לדקה (ממוצע ב-10 הדקות האחרונות)
  וזיכרונות ששלף (בלי כפילויות);
- 100 הזיכרונות האחרונים ששלף, עם שעה, כלי, כותרת, פרויקט ומשימה.
  גם חיפוש בלי תוצאות מופיע, עם מה שחיפש. לחצו על כותרת כדי לפתוח את הזיכרון.

התצוגה מתעדכנת לבד. היא לא מפוצלת לפי הפעלות.

הרישום נשמר ב-`~/.memoria/.indice/registo.sqlite`, במחשב שלכם, בנפרד מהאינדקס
(`memoria reindex` לא מוחק אותו). הטקסט שחיפשו עובר את אותה הסתרת סודות ונחתך.
תוכן ההערות לעולם לא נרשם. שורות ישנות נמחקות לבד; סך הקריאות נשמר.

## שפות

האפליקציה מדברת אנגלית, פורטוגזית, הינדי ועברית. כברירת מחדל היא עוקבת אחרי שפת המערכת:

- **macOS:** השפה הנתמכת הראשונה ב-System Settings › General › Language & Region;
- **Windows:** שפת התצוגה של Windows;
- **אחרות:** `LANGUAGE`, `LC_ALL`, `LC_MESSAGES` או `LANG`.

אם אף אחת לא נתמכת, נבחרת אנגלית.
הבורר בראש העמודה מחליף שפה מיד ושומר את הבחירה ב-`~/.memoria/preferencias.json`.
משורת הפקודה: `memoria lingua he`. המשתנה `MEMORIA_LANG` גובר על הכול.

- עברית נפתחת מימין לשמאל. הטקסט של כל הערה שומר על הכיוון שלו.
- הינדי ועברית משתמשות ב-Noto Sans Devanagari וב-Noto Sans Hebrew, שכלולות באפליקציה.
- מונחים טכניים נשארים באנגלית בכל השפות (MCP, token, טיקט, שמות הכלים).

## איפה הזיכרונות נשמרים

ב-`~/.memoria` (או בתיקייה שמוגדרת ב-`MEMORIA_HOME`):

```text
~/.memoria/
  <project>/<YYYY-MM-DD>-<slug>.md   קובץ אחד לכל הערה
  config.json                        כתובות עדכון (לא חובה)
  .indice/memoria-v2.sqlite          אינדקס; אפשר למחוק
  .indice/registo.sqlite             רישום קריאות ה-MCP ("הפעילות של Claude")
  preferencias.json                  השפה שנבחרה בבורר
```

לכל הערה יש כותרת YAML. שמות השדות בפורטוגזית והם חלק מהחוזה:

```markdown
---
tipo: licao            # licao (לקח) | fazer (לעשות) | nao_fazer (לא לעשות) | historico (היסטוריה)
titulo: Use the build cache
projeto: arena-de-seguranca
tarefa: ARENA-12       # לא חובה: מפתח הטיקט (או owner/repo#12)
epico: ARENA-1         # לא חובה: אפיק או הורה
url: https://company.atlassian.net/browse/ARENA-12   # לא חובה
etiquetas: [ci, cache] # לא חובה: תגיות
ficheiros: [orquestrador/plan.mjs]
data: '2026-10-16T13:25:33+01:00'
custo_usd: 1.25        # לא חובה
ligacoes: [Avoid retries]
---

The build is 3x faster with the cache. See [[Avoid retries]].
```

אפשר לערוך את הקבצים ידנית; האפליקציה מזהה את השינויים.
`memoria reindex` בונה את האינדקס מחדש בכל רגע.
`epico`, `url` ו-`etiquetas` נוספו ב-v0.2 והם לא חובה: הערות של v0.1 עדיין תקינות.

טיקטים:

- מפתחות Jira נשמרים באותיות גדולות (`abc-123` → `ABC-123`); של GitHub נראים כמו `owner/repo#12`.
- בלי `tarefa`, האפליקציה לוקחת אותה מה-`url` כשזה טיקט של Jira או issue/PR.
- הערה בלי `epico` יורשת את האפיק של המשימה שלה, אם הערה אחרת מציינת אותו.
- חיפוש `ABC-123` מוצא את הערות המשימה, את הערות האפיק שלה ואת ההערות שמזכירות אותה.

חוזק הקישורים, מהחזק לחלש:
קישור מפורש (`[[...]]` או `ligacoes`), אותה משימה, אותו אפיק, אותו פרויקט, קבצים משותפים.

## עדכון

```bash
memoria update
```

1. מוצאת את הגרסה האחרונה עם `git ls-remote --tags` (בלי API).
2. מורידה את ה-wheel ואת `constraints.txt` ובודקת את `SHA256SUMS`.
3. מתקינה מחדש עם `uv tool install --force`.
4. בונה מחדש את האינדקס. **היא אף פעם לא נוגעת בהערות.**

ב-Windows, ההתקנה מסתיימת בחלון חדש. סגרו קודם את Claude Code.

בגרסה הניידת, העדכון מוריד את ה-zip החדש, בודק אותו ומחליף את תיקיית האפליקציה באותו מקום.
החיבור ל-Claude Code ממשיך לעבוד.

הכתובות מגיעות מ-`~/.memoria/config.json`, ואם הן חסרות, מ-`release.conf` של החבילה.
המפתחות שנקראים (משתנה סביבה עם אותו שם גובר עליהם):

| מפתח | דוגמה |
|---|---|
| `MEMORY_APP_REPO_URL` | `https://<server>/<owner>/claude-memory-app.git` |
| `RELEASE_DOWNLOAD_URL` | `{repo}/releases/download/{version}/{file}` |
| `PYTHON_VERSION` | `3.12` (לא חובה) |
| `UV` | הנתיב לקובץ ההפעלה `uv` (לא חובה) |

## פרטיות

- ההערות, האינדקס והממשק נשארים במחשב שלכם.
- לפני השמירה, האפליקציה מסתירה tokens, מפתחות API (`sk-ant-…`, `ghp_…`, `AKIA…`, `xox…`),
  JWTs, מפתחות פרטיים ותבניות כמו `password=…`.
- הממשק מאזין רק ב-`127.0.0.1`, עם מפתח הפעלה אקראי.
- השימוש היחיד ברשת הוא בדיקת הגרסה (`git ls-remote`) ו-`memoria update`.
  כדי לכבות: `MEMORIA_SEM_UPDATE=1`.
- אין embeddings ואין מודלים. החיפוש הוא טקסט פשוט (SQLite FTS5).

## בעיות נפוצות

- **"ל-SQLite של Python הזה אין FTS5"**: התקינו מחדש עם ה-Python של uv
  (`uv tool install --force --managed-python --python 3.12 <wheel>`).
- **Proxy של החברה**: uv ו-`memoria update` משתמשים ב-`HTTPS_PROXY` ובתעודות של המערכת.
  עבור uv, הגדירו גם `UV_SYSTEM_CERTS=1`.
- **החלון לא נפתח**: `memoria --browser` פותחת את אותו ממשק בדפדפן.

## פיתוח

מידע על פיתוח נמצא באנגלית: [README.md](README.md#development), [CLAUDE.md](CLAUDE.md)
ו-[docs/HANDOVER.md](docs/HANDOVER.md).

## רישיון

MIT. ראו [LICENSE](LICENSE).
הגופנים Bricolage Grotesque, Noto Sans Devanagari ו-Noto Sans Hebrew כלולים בממשק
תחת רישיון SIL Open Font License 1.1 (`web/public/fonts/`).
