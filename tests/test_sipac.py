from urllib.parse import parse_qs

import pytest
from dados import cenario_3010
from sipac_simulado import SipacSimulado

from pca_assistente.montagem import Regras
from pca_assistente.navegador import LoginNecessario, caminho
from pca_assistente.servico import montar_sem_planilha, resumo
from pca_assistente.sipac import Parado, corpo_busca, ler_grupo


def _ler(sim, **kw):
    return ler_grupo(sim, "3010", 2026, Regras(), saida=lambda *a: None, pausa=0, **kw)


def test_corpo_da_busca():
    q = parse_qs(corpo_busca("3010", 2026))
    assert q["tipoReq.id"] == ["16"] and q["subTipoReq.id"] == ["1"]
    assert q["codigo_busca"] == ["3010"] and q["grupo.codigo"] == ["3010"]
    assert q["dataInicial"] == ["01/01/2026"] and q["dataFinal"] == ["31/12/2026"]
    assert q["acao"] == ["13"] and q["busca"] == ["true"]


def test_le_so_os_detalhes_das_enviadas_um_por_vez():
    sim = SipacSimulado(cenario_3010())
    lt = _ler(sim)
    assert len(lt.busca.linhas) == 9 and lt.busca.confere
    assert len(lt.lidas) == 7
    assert sim.pedidos[0][0] == "GET" and sim.pedidos[1] == ("POST", "/sipac/buscaListaReq.do")
    assert sum(1 for p in sim.pedidos if p[1] == "/sipac/acompanharReqMaterial.do") == 7


def test_leitura_bate_com_os_dados():
    lidas = cenario_3010()
    lt = _ler(SipacSimulado(lidas))
    orig = {b.id: d for b, d in lidas}
    for b, d in lt.lidas:
        assert d.itens == orig[b.id].itens and d.valor == orig[b.id].valor


def test_login_no_meio_para():
    with pytest.raises(LoginNecessario):
        _ler(SipacSimulado(cenario_3010(), login_no_detalhe=3))


def test_parar():
    chamadas = iter(range(100))
    with pytest.raises(Parado):
        _ler(SipacSimulado(cenario_3010()), parar=lambda: next(chamadas) >= 2)


def test_resumo_sem_dados_pessoais():
    lt = _ler(SipacSimulado(cenario_3010()))
    txt = "\n".join(resumo(lt, montar_sem_planilha(lt, Regras())))
    assert "usuario.ficticio" not in txt and "90000-0000" not in txt
    assert "9 requisições" in txt and "✔ confere" in txt
    assert "EAJ 9551 9305 9066: requisições R$ 351,81" in txt
    assert "CCS-DOD 9416 9396 9115: requisições R$ 5.310.382,56" in txt


def test_caminho_sem_parametros():
    assert caminho("https://sipac.ufrn.br/sipac/x.do?idReq=1&a=2") == "sipac.ufrn.br/sipac/x.do"
