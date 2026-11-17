from datetime import date
from decimal import Decimal

from dados import C1, C2, C3, C4, D, cenario_3010, req

from pca_assistente.montagem import (
    INCLUIDO, ItemCatalogo, Regras, linhas_req, montar, montar_mat, nome_coluna,
)


def _montar(lidas, catalogo=None, regras=None, vagas=10):
    busca = [b for b, _ in lidas]
    tot = sum((b.valor for b in busca), Decimal(0))
    return montar("3010", 2026, busca, len(busca), tot, lidas, catalogo or {}, regras, vagas)


CAT = {
    C1: ItemCatalogo(C1, "PINÇA", "UNIDADE", D("9.56")),
    C2: ItemCatalogo(C2, "BROCA", "UNIDADE", D(10)),
    C3: ItemCatalogo(C3, "ALGODÃO", "UNIDADE", D("5261942.76")),
    C4: ItemCatalogo(C4, "AGULHA", "UNIDADE", D("9.55")),
}


# ---------- REQ ----------

def test_req_estornada_fora_e_em_aquisicao_nao():
    linhas = linhas_req([b for b, _ in cenario_3010()], 2026, Regras())
    nums = [ln[1] for ln in linhas]
    assert "9678/2026" not in nums  # ESTORNADA (como a 6678/2026 do gabarito)
    em_aq = next(ln for ln in linhas if ln[1] == "9707/2026")
    assert em_aq[7] == "EM AQUISIÇÃO" and em_aq[11] == "NÃO" and em_aq[10] == 2026
    assert all(ln[11] == "OK" for ln in linhas if ln[7] == "ENVIADA")


def test_req_data_mais_nova_primeiro():
    linhas = linhas_req([b for b, _ in cenario_3010()], 2026, Regras())
    datas = [ln[0] for ln in linhas]
    assert datas == sorted(datas, reverse=True)
    assert linhas[0][1] == "9470/2026"


def test_req_estornada_configuravel():
    r = Regras(fora_req=("CANCELADA",))
    linhas = linhas_req([b for b, _ in cenario_3010()], 2026, r)
    est = next(ln for ln in linhas if ln[1] == "9678/2026")
    assert est[11] == "NÃO"


# ---------- MAT ----------

def test_mat_uma_coluna_por_unidade_na_ordem_do_mapa():
    m = montar_mat(cenario_3010(), Regras())
    assert [c.nome for c in m.colunas] == ["CCS-DOD", "DAS/PROGESP", "EAJ"]


def test_mat_cabecalho_com_numeros_sem_ano():
    m = montar_mat(cenario_3010(), Regras())
    cab = {c.nome: c.cabecalho for c in m.colunas}
    assert cab["EAJ"] == "EAJ\n9551\n9305\n9066"
    assert cab["CCS-DOD"] == "CCS-DOD\n9416\n9396\n9115"


def test_mat_mesma_unidade_soma_na_mesma_coluna():
    m = montar_mat(cenario_3010(), Regras())
    agulha = next(ln for ln in m.linhas if ln.codigo == C4)
    assert agulha.qtds == {"EAJ": D(23)}
    broca = next(ln for ln in m.linhas if ln.codigo == C2)
    assert broca.qtds == {"CCS-DOD": D("4843.98")}


def test_mat_so_enviadas():
    m = montar_mat(cenario_3010(), Regras())
    todos = {n for c in m.colunas for n in c.numeros}
    assert 9707 not in todos and 9678 not in todos


def test_mat_codigo_sem_repetir_e_ordem_alfabetica():
    m = montar_mat(cenario_3010(), Regras())
    assert [ln.denominacao for ln in m.linhas] == ["AGULHA", "ALGODÃO", "BROCA", "PINÇA"]
    assert len({ln.codigo for ln in m.linhas}) == len(m.linhas)


def test_mat_ordem_de_leitura():
    m = montar_mat(cenario_3010(), Regras(ordem="leitura"))
    # leitura = requisição mais antiga primeiro, itens na ordem da requisição
    assert [ln.codigo for ln in m.linhas] == [C4, C1, C3, C2]


def test_mat_sigla_sem_mapa_usa_a_propria_e_avisa():
    lidas = [req(9001, "NOVA/UNID", "ENVIADA", 10, date(2026, 1, 2), [(C1, "PINÇA", 1, 10)])]
    avisos = []
    m = montar_mat(lidas, Regras(), avisos=avisos)
    assert m.colunas[0].nome == "NOVA/UNID"
    assert any(a.tipo == "unidade" and "NOVA/UNID" in a.texto for a in avisos)


def test_mapa_juntando_duas_siglas():
    assert nome_coluna("ALM-FACISA", Regras().mapa) == ("FACISA", True)
    assert nome_coluna("SMP/FACISA", Regras().mapa) == ("FACISA", True)
    assert nome_coluna("INST. CÉREBRO", Regras().mapa) == ("ICE", True)


def test_mat_mais_de_dez_unidades_vai_para_diversos():
    lidas = [req(9000 + k, f"U{k:02d}", "ENVIADA", 1, date(2026, 1, 1 + k), [(C1, "PINÇA", 1, 1)])
             for k in range(12)]
    avisos = []
    m = montar_mat(lidas, Regras(), vagas=10, avisos=avisos)
    assert len(m.colunas) == 10
    assert m.diversos is not None
    assert m.diversos.cabecalho == "DIVERSOS\nU10 9010\nU11 9011"
    assert m.linhas[0].qtds["DIVERSOS"] == D(2)
    assert any(a.tipo == "diversos" and a.grave and "não a DIVERSOS" in a.texto for a in avisos)


# ---------- conferências ----------

def test_gabarito_totais_por_unidade():
    r = _montar(cenario_3010(), CAT)
    assert r.totais["EAJ"][1] == D("351.81")
    assert r.totais["CCS-DOD"][1] == D("5310382.56")


def test_conferencia_preco_catalogo_diferente_da_requisicao():
    r = _montar(cenario_3010(), CAT)
    # EAJ pelo catálogo: AGULHA 23 × 9,55 + PINÇA 1 × 9,56 = 229,21 ≠ 351,81
    assert r.totais["EAJ"][0] == D("229.21")
    assert any(a.tipo == "preco" and "Coluna EAJ" in a.texto for a in r.avisos)
    assert any(a.tipo == "preco" and C4 in a.texto and "14,63" in a.texto for a in r.avisos)
    assert not any("Coluna CCS-DOD" in a.texto for a in r.avisos)


def test_conferencia_soma_dos_itens():
    lidas = [req(9001, "EAJ", "ENVIADA", "100.00", date(2026, 1, 2), [(C1, "PINÇA", 3, "30")])]
    r = _montar(lidas, CAT)
    assert any(a.tipo == "soma" and a.grave and "9001/2026" in a.texto for a in r.avisos)


def test_conferencia_fora_do_catalogo_e_novos():
    r = _montar(cenario_3010(), {C1: CAT[C1]})
    assert [n.codigo for n in r.novos_catalogo] == [C2, C3, C4]
    assert r.novos_catalogo[0].denominacao == "BROCA" and r.novos_catalogo[0].valor == D(10)
    assert sum(a.tipo == "fora_catalogo" for a in r.avisos) == 3
    assert INCLUIDO.startswith("INCLUÍDO PELO PCA ASSISTENTE")


def test_conferencia_outro_grupo_e_subgrupo():
    lidas = [req(9001, "EAJ", "ENVIADA", 1, date(2026, 1, 2), [("3035009000001", "X", 1, 1)], grupo_det="3035")]
    r = _montar(lidas, CAT)
    textos = [a.texto for a in r.avisos if a.tipo == "grupo"]
    assert any("grupo 3035" in t for t in textos)
    assert any("outro grupo" in t for t in textos)


def test_conferencia_codigo_repetido():
    lidas = [req(9001, "EAJ", "ENVIADA", 2, date(2026, 1, 2), [(C1, "PINÇA", 1, 1), (C1, "PINÇA", 1, 1)])]
    r = _montar(lidas, CAT)
    assert any(a.tipo == "repetido" and C1 in a.texto for a in r.avisos)
    assert r.matriz.linhas[0].qtds["EAJ"] == D(2)


def test_conferencia_busca_x_lido():
    lidas = cenario_3010()
    busca = [b for b, _ in lidas]
    r = montar("3010", 2026, busca, len(busca) + 1, D(1), lidas[1:], CAT)
    t = [a.texto for a in r.avisos if a.tipo in ("busca", "leitura")]
    assert any("diz 10 requisições" in x for x in t)
    assert any("diz R$ 1,00" in x for x in t)
    assert any("9470/2026 não foi lida" in x for x in t)


def test_cenario_sem_avisos_graves():
    r = _montar(cenario_3010(), CAT)
    assert not [a for a in r.avisos if a.grave]


def test_avisos_sem_usuario():
    r = _montar(cenario_3010(), {})
    assert not any("usuario.ficticio" in a.texto for a in r.avisos)
