"""Grades no formato do MODELO do PCA (como a API devolve com valueRenderOption=FORMULA). Fictício."""
from __future__ import annotations

REQ_CAB = ["DATA", "REQUISIÇÃO", "UNIDADE", "", "", "", "", "STATUS", "USUÁRIO", "VALOR", "ANO", "COLUNA",
           "OBSERVAÇÃO"]

MAT_CAB = ["#", "CÓDIGO", "DENOMINAÇÃO", "UNID.\nMED.", "QTD", "VALOR", "TOTAL", "OBSERVAÇÃO",
           *[f"UND{k}" for k in range(1, 11)], "DIVERSOS", "QTD \nUND", "PREGÃO"]


def linha_mat(n: int) -> list:
    return ["", "", "=XLOOKUP(B:B;'CATÁLOGO'!A:A;'CATÁLOGO'!B:B)", "=XLOOKUP(B:B;'CATÁLOGO'!A:A;'CATÁLOGO'!C:C)",
            f"=SUM(I{n}:R{n})", "=SUMIF('CATÁLOGO'!A:A;B:B;'CATÁLOGO'!D:D)", f"=E{n}*F{n}",
            "", "", "", "", "", "", "", "", "", "", "", "", f"=COUNTA(I{n}:S{n})"]


def mat(linhas: int = 342, aba: str = "MAT26") -> list[list]:
    l1 = ["SIPAC: instrução", "", "", "", "", "", "", ""] + [f"=COUNTA({c}3:{c}344)" for c in "IJKLMNOPQR"]
    return [l1, list(MAT_CAB)] + [linha_mat(n) for n in range(3, 3 + linhas)]


def linha_cat(n: int) -> list:
    return ["", "", "", "", "=SUMIF('MAT25'!B:B;A:A;'MAT25'!E:E)", "=SUMIF('MAT25'!B:B;A:A;'MAT25'!G:G)",
            "=SUMIF('MAT26'!B:B;A:A;'MAT26'!E:E)", "=SUMIF('MAT26'!B:B;A:A;'MAT26'!G:G)"]


def catalogo(itens: list[tuple] = ()) -> list[list]:
    """itens: (codigo int, denominacao, und, valor, obs, pregao, unidades)."""
    g = [["Códigos e nomes: instrução"], ["Unidade de medida e valor: instrução"], [],
         ["CÓDIGO", "DENOMINAÇÃO", "UND.\nMED", "VALOR", "REQ 2025", "TOTAL 2025", "REQ 2026", "TOTAL 2026",
          "OBSERVAÇÃO", "PREGÃO 2023/2024", "UNIDADES"]]
    for k, it in enumerate(itens):
        cod, den, und, val, *resto = it
        r = linha_cat(5 + k)
        r[:4] = [cod, den, und, val]
        r += list(resto)
        g.append(r)
    if not itens:
        g += [linha_cat(5), linha_cat(6)]
    return g


def planilha(cat_itens=(), req_linhas=()) -> dict[str, list[list]]:
    return {
        "REQ": [list(REQ_CAB), *[list(r) for r in req_linhas]],
        "MAT25": mat(aba="MAT25"),
        "MAT26": mat(),
        "CATÁLOGO": catalogo(cat_itens),
        "CCS 26": [["não mexer"]],
    }
