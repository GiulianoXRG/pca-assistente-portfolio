import pytest
from dados import cenario_3010
from fastapi.testclient import TestClient
from modelo import planilha
from sipac_simulado import SipacSimulado

from pca_assistente import config
from pca_assistente.navegador import LoginNecessario
from pca_assistente.saida import SaidaMemoria
from pca_assistente.sipac import ler_grupo
from pca_assistente.web.app import criar_app

SID = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"


class Memoria(SaidaMemoria):
    def titulo(self, sid):
        return "PCA 3010 FICTÍCIO"


@pytest.fixture
def cli(tmp_path, monkeypatch):
    for nome, arq in (("PASTA", tmp_path), ("ARQ_CONFIG", tmp_path / "config.json"),
                      ("ARQ_GOOGLE", tmp_path / "google.json"), ("ARQ_TOKEN", tmp_path / "token.json"),
                      ("ARQ_OAUTH_CLIENTE", tmp_path / "oauth-cliente.json")):
        monkeypatch.setattr(config, nome, arq)
    mem = Memoria({SID: planilha()})
    estado = {"login": False}

    def ler(grupo, ano, regras, saida, parar):
        if estado["login"]:
            raise LoginNecessario("Faça login no SIPAC no Chrome do assistente e tente de novo.")
        return ler_grupo(SipacSimulado(cenario_3010()), grupo, ano, regras, saida, parar, pausa=0)

    app = criar_app(ler=ler, abrir_saida=lambda cfg, *a, **k: mem,
                    situacao=lambda: {"chrome": True, "sipac": True, "login": False})
    c = TestClient(app)
    c.mem, c.app_, c.estado = mem, app, estado
    return c


def _esperar(c):
    c.app_.state.executor.esperar(10)
    return c.get("/estado").json()


def test_paginas_abrem(cli):
    assert "Buscar no SIPAC" in cli.get("/").text
    assert "Mapa de unidades" in cli.get("/configuracoes").text
    assert cli.get("/resultado", follow_redirects=False).status_code == 303


def test_fluxo_buscar_previa_gravar(cli):
    r = cli.post("/config/planilha", data={"grupo": "3010", "link": f"https://docs.google.com/spreadsheets/d/{SID}/edit#gid=0"})
    assert r.status_code == 200 and config.carregar()["planilhas"]["3010"] == SID
    assert "Acesso OK" in cli.post("/config/testar", data={"grupo": "3010"}).text
    assert cli.post("/buscar", data={"grupo": "3010", "ano": "2026"}).json()["ok"]
    e = _esperar(cli)
    assert e["erro"] is None and e["tem_resultado"]
    assert any("7/7 lendo requisição" in l["t"] for l in e["linhas"])
    html = cli.get("/resultado").text
    assert "Gravar na planilha" in html and "Entra na MAT" in html and "Fora: status ESTORNADA" in html
    assert "R$ 351,81" in html and "usuario.ficticio" not in html
    assert cli.post("/gravar").json()["ok"]
    e = _esperar(cli)
    assert e["erro"] is None and "Gravado" in e["resultado"]
    g = cli.mem.planilhas[SID]["MAT26"]
    assert g[1][8].startswith("CCS-DOD")
    assert any(t.startswith("MAT26 (antes") for t in cli.mem.planilhas[SID])
    assert "Abrir a planilha" in cli.get("/resultado").text
    assert cli.post("/gravar").status_code == 409  # não grava duas vezes o mesmo resultado
    assert config.carregar()["historico"] == ["3010"]


def test_sem_planilha_so_previa(cli):
    cli.post("/buscar", data={"grupo": "3010", "ano": "2026"})
    _esperar(cli)
    html = cli.get("/resultado").text
    assert "Só prévia" in html and "id=\"bt-gravar\"" not in html
    assert cli.post("/gravar").status_code == 400


def test_login_avisa_e_para(cli):
    cli.estado["login"] = True
    cli.post("/buscar", data={"grupo": "3010", "ano": "2026"})
    e = _esperar(cli)
    assert "faça login" in e["erro"].lower()


def test_grupo_invalido(cli):
    assert cli.post("/buscar", data={"grupo": "abc", "ano": "2026"}).status_code == 400


def test_config_mapa_e_regras(cli):
    cli.post("/config/mapa", data={"mapa": "DOD/CCS = CCS-DOD\nNOVA = NOVA COL\nlixo"})
    assert config.carregar()["mapa"] == {"DOD/CCS": "CCS-DOD", "NOVA": "NOVA COL"}
    cli.post("/config/regras", data={"na_mat": ["ENVIADA"], "fora_req": ["CANCELADA"], "ordem": "leitura"})
    cfg = config.carregar()
    assert cfg["fora_req"] == ["CANCELADA"] and cfg["ordem"] == "leitura"


def test_config_chave_google(cli):
    chave = b'{"type": "service_account", "client_email": "pca@projeto-ficticio.iam.gserviceaccount.com"}'
    cli.post("/config/google", data={"forma": "servico"}, files={"chave": ("google.json", chave, "application/json")})
    assert config.ARQ_GOOGLE.read_bytes() == chave
    assert "pca@projeto-ficticio.iam.gserviceaccount.com" in cli.get("/configuracoes").text
    r = cli.post("/config/google", data={"forma": "servico"}, files={"chave": ("x.json", b"{}", "application/json")})
    assert "não reconhecido" in r.text


def test_link_invalido(cli):
    r = cli.post("/config/planilha", data={"grupo": "3010", "link": "não é link"})
    assert "Não reconheci" in r.text
