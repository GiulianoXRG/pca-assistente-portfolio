"""SaidaGoogle com um `service` falso (sem rede) + estrutura no formato do gabarito."""

from dados import cenario_3010
from modelo import planilha

from pca_assistente.google_sheets import SaidaGoogle, requisicoes_estrutura
from pca_assistente.montagem import Regras
from pca_assistente.planilha import Plano, estrutura_catalogo, estrutura_mat
from pca_assistente.saida import SaidaMemoria
from pca_assistente.servico import executar_gravacao, preparar
from pca_assistente.sipac import Leitura
from pca_assistente.parsers import Busca


class _Exec:
    def __init__(self, fn):
        self.fn = fn

    def execute(self):
        return self.fn()


class _Falso:
    """Imita service.spreadsheets() guardando os pedidos; os dados vêm de uma SaidaMemoria."""

    def __init__(self, mem: SaidaMemoria, sid: str):
        self.mem, self.sid = mem, sid
        self.lotes: list[list[dict]] = []
        self.valores: list[dict] = []

    def spreadsheets(self):
        return self

    def values(self):
        return self

    def _props(self):
        return [{"properties": {"title": t, "sheetId": k, "gridProperties": {"rowCount": max(len(g), 1)}}}
                for k, (t, g) in enumerate(self.mem.planilhas[self.sid].items())]

    def get(self, spreadsheetId, fields):
        return _Exec(lambda: {"properties": {"title": "PCA 3010 FICTÍCIO"}, "sheets": self._props()})

    def batchGet(self, spreadsheetId, ranges, **kw):
        assert kw["valueRenderOption"] == "FORMULA"
        abas = [r.strip("'").replace("''", "'") for r in ranges]
        return _Exec(lambda: {"valueRanges": [{"values": self.mem.planilhas[self.sid][a]} for a in abas]})

    def batchUpdate(self, spreadsheetId, body):
        if "requests" in body:
            self.lotes.append(body["requests"])
            for r in body["requests"]:
                if "duplicateSheet" in r:
                    d = r["duplicateSheet"]
                    orig = list(self.mem.planilhas[self.sid])[d["sourceSheetId"]]
                    self.mem.duplicar(self.sid, orig, d["newSheetName"])
        else:
            assert body["valueInputOption"] == "RAW"
            self.valores.append(body)
        return _Exec(lambda: {})


def test_saida_google_faz_copia_oculta_e_escreve_em_lote():
    sid = "x"
    mem = SaidaMemoria({sid: planilha()})
    falso = _Falso(mem, sid)
    g = SaidaGoogle(falso)
    lidas = cenario_3010()
    lt = Leitura("3010", 2026, Busca([b for b, _ in lidas], None, None), lidas)
    pr = preparar(lt, Regras(), g, sid)
    assert pr.erro_planilha is None and pr.plano is not None
    executar_gravacao(pr, g)
    tipos = [list(r)[0] for lote in falso.lotes for r in lote]
    assert tipos.count("duplicateSheet") == 2 and tipos.count("updateSheetProperties") == 2
    assert all(r["updateSheetProperties"]["properties"]["hidden"] for lote in falso.lotes for r in lote
               if "updateSheetProperties" in r)
    assert len(falso.valores) == 1  # uma escrita de valores só
    faixas = [d["range"] for d in falso.valores[0]["data"]]
    assert any(f.startswith("'MAT26'!B3:") for f in faixas)
    assert not any("!C" in f or "!E" in f for f in faixas if f.startswith("'MAT26'"))  # nunca nas fórmulas


def test_requisicoes_estrutura():
    p = Plano()
    p.inserir["MAT26"] = (343, 5)
    p.garantir["CATÁLOGO"] = 600
    p.copiar_formulas.append(("MAT26", 2, 344, 348, 2, 6))
    p.datas["REQ"] = (0, 1, 10)
    meta = {"MAT26": {"sheetId": 7, "gridProperties": {"rowCount": 344}},
            "CATÁLOGO": {"sheetId": 8, "gridProperties": {"rowCount": 487}},
            "REQ": {"sheetId": 0, "gridProperties": {"rowCount": 1000}}}
    r = requisicoes_estrutura(p, meta)
    assert r[0]["insertDimension"]["range"] == {"sheetId": 7, "dimension": "ROWS", "startIndex": 344, "endIndex": 349}
    assert r[1]["appendDimension"]["length"] == 113
    cp = r[2]["copyPaste"]
    assert cp["pasteType"] == "PASTE_FORMULA" and cp["destination"]["endRowIndex"] == 349
    assert cp["source"]["startColumnIndex"] == 2 and cp["source"]["endColumnIndex"] == 7
    assert r[3]["repeatCell"]["cell"]["userEnteredFormat"]["numberFormat"]["pattern"] == "dd/mm/yyyy"


def test_estrutura_no_formato_do_gabarito():
    """Planilha já feita à mão: 7 unidades (I:O), sem DIVERSOS; CATÁLOGO com cabeçalho na linha 1."""
    cab = ["#", "CÓDIGO", "DENOMINAÇÃO", "UNID.\nMED.", "QTD", "VALOR", "TOTAL", "OBSERVAÇÃO",
           "CCS-DOD\n1", "CCS-DPAT\n2", "DAS/\nPROGESP\n3", "ES\n4", "EAJ\n5", "FACISA\n6", "CB\n7", "QTD \nUND", "PREGÃO"]
    linha = ["", 3010009000101, "=XLOOKUP(B:B;'CATÁLOGO'!A:A;'CATÁLOGO'!B:B)", "=X", "=SUM(I3:O3)", "=S", "=E3*F3",
             "", 2, "", "", "", "", "", "", "=COUNTA(I3:O3)"]
    e = estrutura_mat([[""] * 8, cab, linha], "MAT26")
    assert e.unidades == list(range(8, 15)) and e.diversos is None
    cat = [["CÓDIGO", "DENOMINAÇÃO", "UND.\nMED", "VALOR", "REQ 2025", "TOTAL 2025", "REQ 2026", "TOTAL 2026",
            "OBSERVAÇÃO", "REQ 2023/2024", "", "UNIDADES"],
           [3010009000101, "X", "UNIDADE", 10.61, "=S", "=S", "=S", "=S", "DESATIVADO", "ANALISADO"]]
    ec = estrutura_catalogo(cat)
    assert ec.linha_cab == 0 and ec.col_obs == 8 and ec.ultima_dado == 1 and ec.formulas == (4, 7)


def test_sem_planilha_configurada_so_previa():
    lidas = cenario_3010()
    lt = Leitura("3010", 2026, Busca([b for b, _ in lidas], None, None), lidas)
    pr = preparar(lt, Regras(), None, None)
    assert pr.plano is None and "não configurada" in pr.erro_planilha
    assert pr.resultado.totais["EAJ"][1] > 0


def test_planilha_sem_aba_do_ano():
    sid = "x"
    mem = SaidaMemoria({sid: planilha()})
    lidas = cenario_3010()
    lt = Leitura("3010", 2027, Busca([b for b, _ in lidas], None, None), lidas)
    pr = preparar(lt, Regras(), mem, sid)
    assert pr.plano is None and "MAT27" in pr.erro_planilha


