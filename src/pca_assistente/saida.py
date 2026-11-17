"""Saída para o Google Sheets: interface `Saida`, implementação em memória (testes) e a orquestração da gravação.

As implementações reais (conta de serviço / OAuth) ficam em `google_sheets.py`.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Protocol

from .planilha import Plano, copias_para_apagar, nome_copia


class Saida(Protocol):
    def titulos(self, sid: str) -> list[str]: ...
    def ler(self, sid: str, abas: list[str]) -> dict[str, list[list]]: ...
    def duplicar(self, sid: str, aba: str, novo: str) -> None: ...
    def apagar_aba(self, sid: str, titulo: str) -> None: ...
    def aplicar(self, sid: str, plano: Plano) -> None: ...


def gravar(saida: Saida, sid: str, plano: Plano, abas_copia: list[str], agora: datetime | None = None,
           manter: int = 3) -> list[str]:
    """Cópia de segurança das abas (mantém `manter`), depois a escrita em lote. Devolve as cópias criadas."""
    agora = agora or datetime.now()
    titulos = saida.titulos(sid)
    criadas = []
    for aba in abas_copia:
        for velha in copias_para_apagar(titulos, aba, manter):
            saida.apagar_aba(sid, velha)
        novo = nome_copia(aba, agora)
        if novo in titulos:  # mesmo minuto: não duplica de novo
            continue
        saida.duplicar(sid, aba, novo)
        criadas.append(novo)
    saida.aplicar(sid, plano)
    return criadas


# ---------- A1 e fórmulas ----------

_RX_A1 = re.compile(r"^(?:'((?:[^']|'')+)'|([^!]+))!([A-Z]+)(\d+)(?::([A-Z]+)(\d+))?$")


def col_indice(letras: str) -> int:
    n = 0
    for ch in letras:
        n = n * 26 + ord(ch) - 64
    return n - 1


def parse_a1(a1: str) -> tuple[str, int, int, int, int]:
    """"'ABA'!B3:C10" → (aba, lin0, col0, lin1, col1), 0-based inclusivo."""
    m = _RX_A1.match(a1)
    if not m:
        raise ValueError(f"A1 não suportado: {a1}")
    aba = (m[1] or m[2]).replace("''", "'")
    c0, l0 = col_indice(m[3]), int(m[4]) - 1
    c1, l1 = (col_indice(m[5]), int(m[6]) - 1) if m[5] else (c0, l0)
    return aba, l0, c0, l1, c1


_RX_REF = re.compile(r"(?<![A-Za-z0-9_$.])(\$?)([A-Z]{1,3})(\$?)(\d+)(?![\d(])")


def deslocar_formula(f: str, delta: int) -> str:
    """Ajusta referências relativas de linha (como colar no Sheets). Ignora textos entre aspas/nomes de aba."""
    partes = re.split(r"('(?:[^']|'')*'|\"[^\"]*\")", f)
    for i in range(0, len(partes), 2):
        partes[i] = _RX_REF.sub(
            lambda m: f"{m[1]}{m[2]}{m[3]}{m[4] if m[3] else int(m[4]) + delta}", partes[i])
    return "".join(partes)


class SaidaMemoria:
    """Planilha falsa em memória: {sid: {aba: grade}}. Aplica o Plano como o Google aplicaria."""

    def __init__(self, planilhas: dict[str, dict[str, list[list]]]):
        self.planilhas = planilhas
        self.chamadas: list[str] = []

    def titulos(self, sid):
        return list(self.planilhas[sid])

    def ler(self, sid, abas):
        return {a: [list(r) for r in self.planilhas[sid][a]] for a in abas}

    def duplicar(self, sid, aba, novo):
        self.chamadas.append(f"duplicar {aba} → {novo}")
        self.planilhas[sid][novo] = [list(r) for r in self.planilhas[sid][aba]]

    def apagar_aba(self, sid, titulo):
        self.chamadas.append(f"apagar {titulo}")
        del self.planilhas[sid][titulo]

    def aplicar(self, sid, plano: Plano):
        self.chamadas.append("aplicar")
        abas = self.planilhas[sid]
        for aba, (depois, n) in plano.inserir.items():
            g = abas[aba]
            for _ in range(n):
                g.insert(depois + 1, [])
        for aba, n in plano.garantir.items():
            g = abas[aba]
            while len(g) < n:
                g.append([])
        for aba, origem, de, ate, c0, c1 in plano.copiar_formulas:
            g = abas[aba]
            for lin in range(de, ate + 1):
                for c in range(c0, c1 + 1):
                    v = g[origem][c] if c < len(g[origem]) else ""
                    _por(g, lin, c, deslocar_formula(v, lin - origem) if isinstance(v, str) and v.startswith("=")
                         else v)
        for aba, lista in plano.valores.items():
            for a1, vals in lista:
                nome, l0, c0, l1, c1 = parse_a1(a1)
                g = abas[nome]
                for i, linha in enumerate(vals):
                    for j, v in enumerate(linha):
                        _por(g, l0 + i, c0 + j, v)


def _por(g: list[list], lin: int, col: int, v) -> None:
    while len(g) <= lin:
        g.append([])
    r = g[lin]
    while len(r) <= col:
        r.append("")
    r[col] = v
