"""Construtores de dados FICTÍCIOS para os testes (sem pessoas reais)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pca_assistente.parsers import Detalhe, Item, LinhaBusca

TIPO = "REQUISIÇÃO DE MATERIAL PARA PARTICIPAR DE UM REGISTRO DE PREÇOS"


def D(x) -> Decimal:
    return Decimal(str(x))


def req(numero: int, unidade: str, status: str, valor, dia: date, itens=(), grupo: str = "3010",
        ano: int = 2026, grupo_det: str | None = None) -> tuple[LinhaBusca, Detalhe]:
    """itens: [(codigo, denominacao, qt, valor_unit)]; valor da requisição = argumento `valor`."""
    b = LinhaBusca(id=900100 + numero % 100 + (numero // 100) * 1000, data=dia, numero=numero, ano=ano,
                   unidade=unidade, unidade_custo=unidade, grupo=grupo, tipo=TIPO, almoxarifado="",
                   status=status, usuario="usuario.ficticio", valor=D(valor))
    its = [Item(nr=k + 1, codigo=c, denominacao=n, unid_med="UNIDADE", qt=D(q), valor=D(v),
                total=D(q) * D(v), status="ANALISADO") for k, (c, n, q, v) in enumerate(itens)]
    d = Detalhe(numero=numero, ano=ano, tipo=TIPO, grupo_nome="MATERIAL FICTICIO",
                grupo=grupo_det if grupo_det is not None else grupo, unidade=unidade, unidade_nome="UNIDADE FICTICIA",
                unidade_codigo="99.00.00", status=status, valor=D(valor), data_cadastro=None, data_envio=None,
                itens=its)
    return b, d


C1, C2, C3, C4 = "3010009000101", "3010009000102", "3010009000103", "3010009000104"


def cenario_3010():
    """Mesmos valores do gabarito 3010/2026 (números de requisição fictícios).

    EAJ: 19,11 + 292,60 + 40,10 = 351,81; DOD: 41.039,80 + 7.400,00 + 5.261.942,76 = 5.310.382,56.
    """
    d = date
    return [
        req(9470, "DAS/PROGESP", "ENVIADA", "57.36", d(2026, 3, 20), [(C1, "PINÇA", 6, "9.56")]),
        req(9416, "DOD/CCS", "ENVIADA", "41039.80", d(2026, 3, 20), [(C2, "BROCA", 4103.98, 10)]),
        req(9396, "DOD/CCS", "ENVIADA", "7400.00", d(2026, 3, 20), [(C2, "BROCA", 740, 10)]),
        req(9115, "DOD/CCS", "ENVIADA", "5261942.76", d(2026, 3, 20), [(C3, "ALGODÃO", 1, "5261942.76")]),
        req(9707, "DPGC/COMPRAS", "EM AQUISIÇÃO", "32.37", d(2026, 3, 18)),
        req(9678, "DPAT/CCS", "ESTORNADA", "100.00", d(2026, 3, 17)),
        req(9551, "EAJ", "ENVIADA", "19.11", d(2026, 3, 11), [(C1, "PINÇA", 1, "9.56"), (C4, "AGULHA", 1, "9.55")]),
        req(9305, "EAJ", "ENVIADA", "292.60", d(2026, 3, 10), [(C4, "AGULHA", 20, "14.63")]),
        req(9066, "EAJ", "ENVIADA", "40.10", d(2026, 3, 6), [(C4, "AGULHA", 2, "20.05")]),
    ]
