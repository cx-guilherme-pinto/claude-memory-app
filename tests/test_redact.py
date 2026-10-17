import pytest

from memoria.redact import redigir, redigir_valor

SEGREDOS = [
    ("anthropic", "a chave sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789-_xyz fica"),
    ("anthropic", "admin sk-ant-admin01-ZZZZZZZZZZZZZZZZZZZZ"),
    ("openai", "OPENAI sk-proj-abcdefghijklmnopqrstuvwxyz012345"),
    ("github", "token ghp_0123456789abcdefghijABCDEFGHIJ012345 no texto"),
    ("github", "gho_0123456789abcdefghijABCDEFGHIJ012345"),
    ("github", "github_pat_11ABCDEFG0123456789_abcdefghijklmnopqrstuvwxyz"),
    ("gitlab", "glpat-abcdefghij0123456789"),
    ("aws", "chave AKIAIOSFODNN7EXAMPLE aqui"),
    ("aws", "ASIAABCDEFGHIJKLMNOP"),
    ("slack", "xoxb-1234567890-0987654321-abcdefghijABCDEFGHIJ"),
    ("slack", "xoxp-1234567890-abcdefghij"),
    ("google", "AIzaSyA1234567890abcdefghijklmnopqrstuv"),
    ("stripe", "sk_live_abcdefghijklmnop1234"),
    ("npm", "npm_abcdefghijklmnopqrstuvwxyz0123456789"),
    ("huggingface", "hf_abcdefghijklmnopqrstuvwxyzABCDEF"),
    (
        "jwt",
        "Authorization eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
    ),
]


@pytest.mark.parametrize("tipo,texto", SEGREDOS)
def test_segredos_conhecidos(tipo, texto):
    redigido, n = redigir(texto)
    assert n >= 1
    assert "[REDACTED:" in redigido
    # Nenhum pedaço do segredo sobrevive.
    segredo = max(texto.split(), key=len)
    assert segredo not in redigido


def test_chave_privada():
    texto = (
        "antes\n-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXktdjEAAAAABG5vbmU\nAAAA\n"
        "-----END OPENSSH PRIVATE KEY-----\ndepois"
    )
    redigido, n = redigir(texto)
    assert n == 1
    assert "b3BlbnNzaC1rZXktdjEAAAAABG5vbmU" not in redigido
    assert redigido.startswith("antes\n[REDACTED:private-key]") and redigido.endswith("depois")


def test_chave_privada_sem_fim():
    redigido, _ = redigir("-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA\nresto")
    assert "MIIEpAIBAAKCAQEA" not in redigido


@pytest.mark.parametrize(
    "texto,segredo",
    [
        ("password=hunter2hunter2", "hunter2hunter2"),
        ("DB_PASSWORD = 's3cr3t-valor'", "s3cr3t-valor"),
        ('{"api_key": "abcd1234efgh"}', "abcd1234efgh"),
        ("export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY", "wJalrXUtnFEMI"),
        ("senha: minhaSenha123", "minhaSenha123"),
        ("client_secret: xyz-123-abc", "xyz-123-abc"),
        ("curl -H 'Authorization: Bearer abc123def456ghi789jkl'", "abc123def456ghi789jkl"),
        ("git clone https://user:Sup3rS3cret@github.com/x/y.git", "Sup3rS3cret"),
        ("token 9f8e7d6c5b4a39281706f5e4d3c2b1a0", "9f8e7d6c5b4a39281706f5e4d3c2b1a0"),
    ],
)
def test_atribuicoes(texto, segredo):
    redigido, n = redigir(texto)
    assert n >= 1 and segredo not in redigido, redigido


@pytest.mark.parametrize(
    "texto",
    [
        "max_tokens: 1000 e input_tokens = 2000",
        "O token de internacionalização não é segredo.",
        "A password policy é rígida.",
        "Usar task-runner para tarefas.",
        "custo_usd: 1.25",
        "Ver https://exemplo.pt/caminho?x=1",
    ],
)
def test_sem_falsos_positivos(texto):
    assert redigir(texto) == (texto, 0)


def test_redigir_valor_recursivo():
    dados = {"a": ["sk-ant-api03-ABCDEFGHIJKLMNOP"], "b": 3}
    assert redigir_valor(dados) == {"a": ["[REDACTED:anthropic]"], "b": 3}


def test_memoria_adicionar_redige_antes_de_escrever(mem):
    r = mem.adicionar(
        tipo="licao",
        titulo="Chave ghp_0123456789abcdefghijABCDEFGHIJ012345",
        texto="password=naoGuardar123",
        projeto="p",
        ficheiros=["config/.env AKIAIOSFODNN7EXAMPLE"],
    )
    conteudo = open(r["caminho"], encoding="utf-8").read()
    for segredo in ("ghp_0123456789", "naoGuardar123", "AKIAIOSFODNN7EXAMPLE"):
        assert segredo not in conteudo
    assert r["redigidos"] >= 2
