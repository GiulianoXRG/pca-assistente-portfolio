from datetime import date, datetime
from decimal import Decimal

import pytest
from dados import C1, C2, C3, C4, cenario_3010, req
from modelo import mat, planilha

from pca_assistente.montagem import INCLUIDO, montar
from pca_assistente.planilha import (
    PlanilhaInvalida, copias_para_apagar, estrutura_mat, ler_catalogo, nome_copia, planejar, vagas_mat,
)
from pca_assistente.saida import SaidaMemoria, deslocar_formula, gravar, parse_a1

SID = "planilha-ficticia"
CAT_ITENS = [(int(C1), "PINÇA", "UNIDADE", 9.56, "obs manual", "pregão x", "CCS"),
             (int(C2), "BROCA", "UNIDADE", 10, "", "", "")]


def _rodar(saida, lidas, ano=2026, aba="MAT26", agora=datetime(2026, 11, 12, 14, 5)):
    g = saida.ler(SID, ["REQ", aba, "CATÁLOGO"])
    cat = ler_catalogo(g["CATÁLOGO"])
    busca = [b for b, _ in lidas]
    res = montar("3010", ano, busca, len(busca), sum((b.valor for b in busca), Decimal(0)), lidas, cat,
                 vagas=vagas_mat(g[aba], aba))
    plano = planejar(res, ano, aba, g["REQ"], g[aba], g["CATÁLOGO"])
    gravar(saida, SID, plano, [aba, "REQ"], agora)
    return plano


def _saida(**kw):
    return SaidaMemoria({SID: planilha(cat_itens=CAT_ITENS, **kw)})


def test_utilidades_a1_e_formula():
    assert parse_a1("'CATÁLOGO'!E5:H7") == ("CATÁLOGO", 4, 4, 6, 7)
    assert parse_a1("'MAT26'!B3") == ("MAT26", 2, 1, 2, 1)
    assert deslocar_formula("=SUM(I3:R3)", 2) == "=SUM(I5:R5)"
    assert deslocar_formula("=SUMIF('MAT26'!B:B;A:A;'MAT26'!E:E)", 3) == "=SUMIF('MAT26'!B:B;A:A;'MAT26'!E:E)"
    assert deslocar_formula("=E3*F3+$A$1", 1) == "=E4*F4+$A$1"


def test_estrutura_do_modelo():
    e = estrutura_mat(mat(), "MAT26")
    assert e.linha_cab == 1 and e.col_codigo == 1 and e.col_obs == 7
    assert e.unidades == list(range(8, 18)) and e.diversos == 18
    assert e.linhas_com_formula == 342


def test_estrutura_rejeita_formula_onde_o_app_escreve():
    g = mat()
    g[5][1] = "=1+1"
    with pytest.raises(PlanilhaInvalida):
        estrutura_mat(g, "MAT26")


def test_estrutura_rejeita_aba_sem_cabecalho():
    with pytest.raises(PlanilhaInvalida):
        estrutura_mat([["x"], ["y"]], "MAT26")


def test_gravar_mat_escreve_so_b_h_e_unidades():
    s = _saida()
    _rodar(s, cenario_3010())
    g = s.planilhas[SID]["MAT26"]
    assert g[1][8] == "CCS-DOD\n9416\n9396\n9115"
    assert g[1][10] == "EAJ\n9551\n9305\n9066"
    assert g[1][11] == "UND4"
    assert [g[i][1] for i in range(2, 6)] == [int(C4), int(C3), int(C2), int(C1)]  # alfabética
    assert g[2][10] == 23 and g[2][8] == ""                                    # AGULHA só EAJ
    assert g[2][2].startswith("=XLOOKUP") and g[2][4] == "=SUM(I3:R3)"         # fórmulas intactas
    assert g[6][1] == ""


def test_req_reconstroi_so_o_ano_e_preserva_observacao():
    antigas = [
        [46000, "9470/2026", "DAS/PROGESP", "", 3010, "", "", "ENVIADA", "x", 57.36, 2026, "OK", "obs da 9470"],
        [46000, "1111/2026", "EAJ", "", 3010, "", "", "ENVIADA", "x", 1, 2026, "OK", ""],
        [45700, "7031/2025", "DAS/PROGESP", "", 3010, "", "", "ENVIADA", "x", 57.36, 2025, "OK", "obs 2025"],
    ]
    s = _saida(req_linhas=antigas)
    plano = _rodar(s, cenario_3010())
    g = s.planilhas[SID]["REQ"]
    nums = [r[1] for r in g[1:] if r and r[1]]
    assert "1111/2026" not in nums and "9678/2026" not in nums
    assert nums[-1] == "7031/2025"                     # outro ano mantido, no fim (mais antigo)
    l9470 = next(r for r in g if r[1] == "9470/2026")
    assert l9470[12] == "obs da 9470" and l9470[11] == "OK" and l9470[10] == 2026
    assert l9470[0] == (date(2026, 3, 20) - date(1899, 12, 30)).days
    assert next(r for r in g if r[1] == "7031/2025")[12] == "obs 2025"
    assert any("saem 1 linhas" in x and "1111/2026" in x for x in plano.resumo)


def test_catalogo_inclui_codigos_novos_sem_tocar_nos_manuais():
    s = _saida()
    plano = _rodar(s, cenario_3010())
    g = s.planilhas[SID]["CATÁLOGO"]
    assert g[4][8:11] == ["obs manual", "pregão x", "CCS"]           # I, J, K intactos
    assert [r[0] for r in g[6:]] == [int(C3), int(C4)]
    r = g[6]
    assert r[1] == "ALGODÃO" and r[2] == "UNIDADE" and r[3] == 5261942.76 and r[8] == INCLUIDO
    assert r[6] == "=SUMIF('MAT26'!B:B;A:A;'MAT26'!E:E)"              # fórmulas copiadas
    assert any("2 código(s) novo(s)" in x for x in plano.resumo)


def test_observacao_da_mat_segue_o_codigo():
    s = _saida()
    _rodar(s, cenario_3010())
    g = s.planilhas[SID]["MAT26"]
    linha_pinca = next(i for i in range(2, 8) if g[i][1] == int(C1))
    g[linha_pinca][7] = "conferir marca"
    # nova requisição com item que fica antes da PINÇA na ordem alfabética
    lidas = cenario_3010() + [req(9999, "EAJ", "ENVIADA", 1, date(2026, 4, 1), [("3010009000105", "LIMA", 1, 1)])]
    _rodar(s, lidas, agora=datetime(2026, 11, 12, 15, 0))
    g = s.planilhas[SID]["MAT26"]
    nova = next(i for i in range(2, 9) if g[i][1] == int(C1))
    assert nova != linha_pinca and g[nova][7] == "conferir marca"


def test_idempotente():
    s = _saida()
    _rodar(s, cenario_3010())
    antes = {k: [list(r) for r in v] for k, v in s.planilhas[SID].items() if "(antes" not in k}
    _rodar(s, cenario_3010(), agora=datetime(2026, 11, 12, 15, 0))
    depois = {k: v for k, v in s.planilhas[SID].items() if "(antes" not in k}
    assert depois == antes


def test_insere_linhas_quando_faltam():
    s = SaidaMemoria({SID: planilha(cat_itens=CAT_ITENS)})
    s.planilhas[SID]["MAT26"] = mat(linhas=2)
    plano = _rodar(s, cenario_3010())
    g = s.planilhas[SID]["MAT26"]
    assert g[5][1] == int(C1) and g[5][4] == "=SUM(I6:R6)" and g[5][19] == "=COUNTA(I6:S6)"
    assert any("linha(s) inseridas" in a for a in plano.alertas)


def test_copias_de_seguranca_mantem_tres():
    s = _saida()
    for h in range(5):
        _rodar(s, cenario_3010(), agora=datetime(2026, 11, 12, 10 + h, 0))
    copias = sorted(t for t in s.planilhas[SID] if t.startswith("MAT26 (antes"))
    assert copias == ["MAT26 (antes 2026-11-12 12h00)", "MAT26 (antes 2026-11-12 13h00)",
                      "MAT26 (antes 2026-11-12 14h00)"]
    assert s.planilhas[SID]["CCS 26"] == [["não mexer"]]
    assert sum(t.startswith("REQ (antes") for t in s.planilhas[SID]) == 3


def test_nome_e_limpeza_das_copias():
    assert nome_copia("MAT26", datetime(2026, 11, 12, 9, 7)) == "MAT26 (antes 2026-11-12 09h07)"
    t = ["MAT26", "MAT26 (antes 2026-01-01 10h00)", "MAT26 (antes 2026-01-02 10h00)", "MAT26 (antes 2026-01-03 10h00)"]
    assert copias_para_apagar(t, "MAT26") == ["MAT26 (antes 2026-01-01 10h00)"]  # 2 velhas + a nova = 3


def test_mais_unidades_que_colunas_sem_diversos():
    g = mat()
    for r in g:
        if len(r) > 18:
            r[18] = "" if r is not g[1] else "X"
    lidas = [req(9000 + k, f"U{k:02d}", "ENVIADA", 1, date(2026, 1, 1 + k), [(C1, "PINÇA", 1, 1)]) for k in range(12)]
    s = SaidaMemoria({SID: planilha(cat_itens=CAT_ITENS)})
    s.planilhas[SID]["MAT26"] = g
    with pytest.raises(PlanilhaInvalida):
        _rodar(s, lidas)
