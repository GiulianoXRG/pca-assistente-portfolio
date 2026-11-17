"""Saída .xlsx: o mesmo fluxo dos testes da planilha, num arquivo de verdade (fictício)."""
from datetime import date, datetime
from decimal import Decimal

import pytest
from dados import C1, C2, cenario_3010, req
from modelo import mat, planilha
from openpyxl import Workbook, load_workbook

from pca_assistente import config
from pca_assistente.montagem import Regras
from pca_assistente.parsers import Busca
from pca_assistente.saida import gravar
from pca_assistente.saida_xlsx import SaidaXlsx, abrir, eh_xlsx
from pca_assistente.servico import executar_gravacao, preparar
from pca_assistente.sipac import Leitura

CAT_ITENS = [(int(C1), "PINÇA", "UNIDADE", 9.56, "obs manual", "pregão x", "CCS"),
             (int(C2), "BROCA", "UNIDADE", 10, "", "", "")]


def _criar(arq, grades):
    wb = Workbook()
    wb.remove(wb.active)
    for aba, g in grades.items():
        ws = wb.create_sheet(aba)
        for linha in g:
            ws.append([None if v == "" else v for v in linha])
    wb.save(arq)
    return str(arq)


def _leitura(lidas, ano=2026):
    busca = [b for b, _ in lidas]
    return Leitura("3010", ano, Busca(busca, len(busca), sum((b.valor for b in busca), Decimal(0))), lidas)


@pytest.fixture
def arq(tmp_path):
    return _criar(tmp_path / "PCA 3010 teste.xlsx", planilha(cat_itens=CAT_ITENS))


def _rodar(arq, lidas, agora=datetime(2026, 11, 12, 14, 5)):
    s = SaidaXlsx()
    pr = preparar(_leitura(lidas), Regras(), s, arq)
    assert pr.erro_planilha is None, pr.erro_planilha
    gravar(s, arq, pr.plano, [pr.aba, "REQ"], agora)
    return pr


def test_reconhece_xlsx(tmp_path, arq):
    assert eh_xlsx(arq) and not eh_xlsx("1AbCdEfGhIjKlMnOpQrStUv")
    assert isinstance(abrir({}, arq), SaidaXlsx)
    assert config.id_planilha(f'"{arq}"') == str(type(tmp_path)(arq).resolve())
    assert config.id_planilha(str(tmp_path / "nao-existe.xlsx")) is None


def test_grava_no_arquivo(arq):
    pr = _rodar(arq, cenario_3010())
    wb = load_workbook(arq)
    ws = wb["MAT26"]
    assert ws["I2"].value == "CCS-DOD\n9416\n9396\n9115"
    assert ws["K2"].value == "EAJ\n9551\n9305\n9066"
    assert ws["B3"].value == 3010009000104 and ws["K3"].value == 23
    assert ws["E3"].value == "=SUM(I3:R3)" and ws["C3"].value.startswith("=XLOOKUP")
    cat = wb["CATÁLOGO"]
    assert cat["I5"].value == "obs manual" and cat["A7"].value == 3010009000103
    assert cat["G7"].value == "=SUMIF('MAT26'!B:B;A:A;'MAT26'!E:E)"
    req = wb["REQ"]
    assert req["B2"].value == "9470/2026" and req["L2"].value == "OK" and req["A2"].number_format == "DD/MM/YYYY"
    copia = wb["MAT26 (antes 2026-11-12 14h05)"]
    assert copia.sheet_state == "hidden" and copia["I2"].value == "UND1"
    assert wb["CCS 26"]["A1"].value == "não mexer"
    assert pr.plano is not None


def test_idempotente_e_preserva_observacao(arq):
    _rodar(arq, cenario_3010())
    wb = load_workbook(arq)
    wb["MAT26"]["H6"] = "conferir marca"   # PINÇA (última na ordem alfabética)
    wb["REQ"]["M2"] = "obs da 9470"
    wb.save(arq)
    lidas = cenario_3010() + [req(9999, "EAJ", "ENVIADA", 1, date(2026, 1, 1), [("3010009000105", "LIMA", 1, 1)])]
    _rodar(arq, lidas, agora=datetime(2026, 11, 12, 15, 0))
    wb = load_workbook(arq)
    ws = wb["MAT26"]
    linha = next(r for r in range(3, 10) if ws.cell(r, 2).value == int(C1))
    assert ws.cell(linha, 8).value == "conferir marca"
    assert next(r for r in wb["REQ"].iter_rows(values_only=True) if r[1] == "9470/2026")[12] == "obs da 9470"


def test_insere_linhas(tmp_path):
    g = planilha(cat_itens=CAT_ITENS)
    g["MAT26"] = mat(linhas=2)
    a = _criar(tmp_path / "curta.xlsx", g)
    _rodar(a, cenario_3010())
    ws = load_workbook(a)["MAT26"]
    assert ws["B6"].value == int(C1) and ws["E6"].value == "=SUM(I6:R6)" and ws["T6"].value == "=COUNTA(I6:S6)"


def test_arquivo_aberto_no_excel(arq, monkeypatch):
    import os

    def trava(*a):
        raise PermissionError("em uso")
    monkeypatch.setattr(os, "replace", trava)
    s = SaidaXlsx()
    pr = preparar(_leitura(cenario_3010()), Regras(), s, arq)
    with pytest.raises(RuntimeError, match="feche o arquivo"):
        executar_gravacao(pr, s)
