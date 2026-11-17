from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from pca_assistente.parsers import (
    FormatoInesperado, ler_busca, ler_detalhe, linhas, numero, opcoes_status,
)

FIX = Path(__file__).parent / "fixtures"


def fixture(nome: str) -> str:
    return (FIX / nome).read_text(encoding="utf-8")


# ---------- utilidades ----------

@pytest.mark.parametrize("txt,esperado", [
    ("R$ 1.234,56", "1234.56"), ("R$ 57,36", "57.36"), ("6", "6"), ("1.000", "1000"), ("6,5", "6.5"),
])
def test_numero(txt, esperado):
    assert numero(txt) == Decimal(esperado)


def test_numero_vazio():
    with pytest.raises(FormatoInesperado):
        numero("")


# ---------- busca ----------

def test_busca_le_todas_as_linhas_sem_o_rodape():
    b = ler_busca(fixture("busca.html"))
    assert [x.requisicao for x in b.linhas] == ["9001/2026", "9002/2026", "9003/2026", "9004/2026"]


def test_busca_id_interno_com_form_dentro_do_tr():
    b = ler_busca(fixture("busca.html"))
    assert [x.id for x in b.linhas] == [900101, 900102, 900103, 900104]


def test_busca_campos_da_linha():
    x = ler_busca(fixture("busca.html")).linhas[0]
    assert x.data == date(2026, 3, 5)
    assert (x.numero, x.ano) == (9001, 2026)
    assert x.unidade == "DOD/CCS" and x.unidade_custo == "DOD/CCS"
    assert x.grupo == "3010"
    assert x.tipo.startswith("REQUISIÇÃO PARA PARTICIPAR")
    assert x.almoxarifado == "ALMOXARIFADO CENTRAL"
    assert x.status == "ENVIADA"
    assert x.usuario == "SERVIDOR FICTICIO UM"
    assert x.valor == Decimal("1234.50")


def test_busca_status_com_acento():
    b = ler_busca(fixture("busca.html"))
    assert [x.status for x in b.linhas] == ["ENVIADA", "ENVIADA", "EM AQUISIÇÃO", "ESTORNADA"]


def test_busca_rodape_confere():
    b = ler_busca(fixture("busca.html"))
    assert b.total_qtd == 4
    assert b.total_valor == Decimal("3310.97")
    assert b.confere


def test_busca_rodape_nao_confere_quando_falta_linha():
    html = fixture("busca.html").replace("<td>9004/2026</td>", "<td>sem número</td>")
    b = ler_busca(html)
    assert len(b.linhas) == 3 and not b.confere


def test_busca_sem_resultado():
    b = ler_busca("<html><body><div>Nenhuma requisição encontrada.</div></body></html>")
    assert b.linhas == [] and b.confere


def test_busca_pagina_estranha():
    with pytest.raises(FormatoInesperado):
        ler_busca("<html><body>Sessão expirada</body></html>")


def test_opcoes_status():
    assert opcoes_status(fixture("busca.html")) == [
        "CADASTRADA", "ENVIADA", "EM AQUISIÇÃO", "ESTORNADA", "CANCELADA"]


# ---------- detalhe ----------

def test_detalhe_cabecalho():
    d = ler_detalhe(fixture("detalhe.html"))
    assert d.requisicao == "9001/2026"
    assert d.tipo.startswith("REQUISIÇÃO PARA PARTICIPAR")
    assert (d.grupo_nome, d.grupo) == ("MATERIAL ODONTOLOGICO", "3010")
    assert (d.unidade, d.unidade_codigo) == ("DOD/CCS", "99.01.01")
    assert d.unidade_nome == "DEPARTAMENTO FICTICIO DE ODONTOLOGIA"
    assert d.status == "ENVIADA"
    assert d.valor == Decimal("1234.50")
    assert d.data_cadastro == datetime(2026, 3, 4, 10, 15)
    assert d.data_envio == datetime(2026, 3, 5, 8, 2)


def test_detalhe_itens():
    itens = ler_detalhe(fixture("detalhe.html")).itens
    assert [i.nr for i in itens] == [1, 2, 3]
    i = itens[0]
    assert i.codigo == "3010009000101"
    assert i.denominacao == "PINÇA FICTÍCIA PARA ALGODÃO Nº 17"
    assert i.unid_med == "UNIDADE"
    assert (i.qt, i.valor, i.total) == (Decimal(6), Decimal("9.56"), Decimal("57.36"))
    assert i.status == "ANALISADO"
    assert itens[1].denominacao == "RESINA FICTÍCIA & COMPOSTA A2"
    assert itens[1].qt == Decimal(1000)
    assert itens[2].codigo == "301000000903"  # código antigo de 12 dígitos
    assert all(i.status == "ANALISADO" for i in itens)  # célula vazia no fim da linha


def test_detalhe_soma_dos_itens_bate_com_o_valor():
    d = ler_detalhe(fixture("detalhe.html"))
    assert sum(i.qt * i.valor for i in d.itens) == d.valor


def test_detalhe_nao_guarda_observacoes_nem_email():
    d = ler_detalhe(fixture("detalhe.html"))
    r = repr(d)
    for proibido in ("99999-0000", "fulano", "Fulano", "@exemplo.br", "Contato"):
        assert proibido not in r


def test_detalhe_ignora_historico():
    d = ler_detalhe(fixture("detalhe.html"))
    assert len(d.itens) == 3


def test_detalhe_pagina_estranha():
    with pytest.raises(FormatoInesperado):
        ler_detalhe("<html><body>Faça login</body></html>")


def test_linhas_quebra_por_celula():
    assert linhas("<tr><th>A:</th><td>1</td></tr><tr><td>B<br>C</td></tr>") == ["A:", "1", "B", "C"]
