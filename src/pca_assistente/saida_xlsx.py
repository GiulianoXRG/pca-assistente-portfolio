"""Saída em arquivo .xlsx (openpyxl), com a mesma interface `Saida`: para testar antes do Google Sheets.

O "id" da planilha é o caminho do arquivo. As mudanças (cópias de segurança + escrita) ficam em memória e o
arquivo só é salvo no fim de `aplicar`, de uma vez (arquivo temporário + troca).
"""
from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path

from .planilha import EPOCA, Plano
from .saida import deslocar_formula, parse_a1


def eh_xlsx(sid: str | None) -> bool:
    return bool(sid) and str(sid).lower().endswith((".xlsx", ".xlsm"))


def _valor(v):
    if v is None:
        return ""
    if isinstance(v, datetime):
        d = v - datetime(EPOCA.year, EPOCA.month, EPOCA.day)
        return d.days + d.seconds / 86400 if d.seconds else d.days
    if isinstance(v, date):
        return (v - EPOCA).days
    if hasattr(v, "text"):  # ArrayFormula / DataTableFormula
        return str(v.text)
    return v


class SaidaXlsx:
    def __init__(self):
        self._wbs: dict[str, object] = {}

    def _wb(self, sid: str, recarregar: bool = False):
        from openpyxl import load_workbook
        if recarregar or sid not in self._wbs:
            if not Path(sid).exists():
                raise FileNotFoundError(f"Arquivo não encontrado: {sid}")
            self._wbs[sid] = load_workbook(sid)
        return self._wbs[sid]

    def titulo(self, sid):
        return Path(sid).name

    def titulos(self, sid):
        return list(self._wb(sid, recarregar=True).sheetnames)

    def ler(self, sid, abas):
        wb = self._wb(sid, recarregar=True)
        res = {}
        for a in abas:
            ws = wb[a]
            res[a] = [[_valor(c) for c in linha] for linha in ws.iter_rows(values_only=True)]
        return res

    def duplicar(self, sid, aba, novo):
        wb = self._wb(sid)
        ws = wb.copy_worksheet(wb[aba])
        ws.title = novo[:31]
        ws.sheet_state = "hidden"

    def apagar_aba(self, sid, titulo):
        wb = self._wb(sid)
        wb.remove(wb[titulo])

    def aplicar(self, sid, plano: Plano):
        wb = self._wb(sid)
        for aba, (depois, n) in plano.inserir.items():
            wb[aba].insert_rows(depois + 2, n)  # depois é 0-based; insere logo abaixo
        for aba, origem, de, ate, c0, c1 in plano.copiar_formulas:
            ws = wb[aba]
            for c in range(c0, c1 + 1):
                v = ws.cell(origem + 1, c + 1).value
                for lin in range(de, ate + 1):
                    ws.cell(lin + 1, c + 1).value = (deslocar_formula(v, lin - origem)
                                                     if isinstance(v, str) and v.startswith("=") else v)
        for aba, lista in plano.valores.items():
            for a1, vals in lista:
                nome, l0, c0, _, _ = parse_a1(a1)
                ws = wb[nome]
                for i, linha in enumerate(vals):
                    for j, v in enumerate(linha):
                        ws.cell(l0 + i + 1, c0 + j + 1).value = None if v == "" else v
        for aba, (col, de, ate) in plano.datas.items():
            ws = wb[aba]
            for lin in range(de, ate + 1):
                ws.cell(lin + 1, col + 1).number_format = "DD/MM/YYYY"
        self.salvar(sid)

    def salvar(self, sid):
        tmp = str(sid) + ".tmp"
        self._wbs[sid].save(tmp)
        try:
            os.replace(tmp, sid)
        except PermissionError as e:
            os.remove(tmp)
            raise RuntimeError("Não consegui salvar: feche o arquivo no Excel e tente de novo.") from e


def abrir(cfg: dict, sid: str | None = None, interativo: bool = False):
    """Saída certa para a planilha: arquivo .xlsx ou Google Sheets."""
    if eh_xlsx(sid):
        return SaidaXlsx()
    from .google_sheets import abrir_saida
    return abrir_saida(cfg, interativo)
