"""Encaixe do resultado da montagem na planilha real (função pura: grade atual → plano de escrita).

A grade é a lida com `valueRenderOption=FORMULA` (fórmulas como '=…', números como número, datas como serial).
O plano só toca: REQ A:L (linhas do ano; M preservada), MAT{AA} B, H (preservada pelo código), colunas das
unidades/DIVERSOS e o cabeçalho delas; CATÁLOGO: linhas novas no fim (A:D + OBSERVAÇÃO; fórmulas copiadas).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from .montagem import INCLUIDO, ItemCatalogo, Matriz, Resultado
from .parsers import FormatoInesperado, norm, numero

EPOCA = date(1899, 12, 30)  # serial de data do Sheets


class PlanilhaInvalida(ValueError):
    """A aba não tem a estrutura esperada: não gravar."""


# ---------- utilidades ----------

def col_letra(i: int) -> str:
    """0 → A, 25 → Z, 26 → AA."""
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def celula(grade: list[list], lin: int, col: int):
    """lin/col 0-based; '' se não existir."""
    if lin < len(grade) and col < len(grade[lin]):
        return grade[lin][col]
    return ""


def e_formula(v) -> bool:
    return isinstance(v, str) and v.startswith("=")


def para_data(v) -> date | None:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return EPOCA + timedelta(days=int(v))
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        try:
            d, m, a = v.strip()[:10].split("/")
            return date(int(a), int(m), int(d))
        except ValueError:
            return None
    return None


def para_decimal(v) -> Decimal | None:
    if v in ("", None) or e_formula(v):
        return None
    if isinstance(v, (int, float)):
        return Decimal(str(v))
    try:
        return numero(str(v))
    except FormatoInesperado:
        return None


def codigo_txt(v) -> str:
    """Código como texto de 13 dígitos (a planilha guarda como número)."""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def valor_celula(v):
    """Python → valor para a API (RAW)."""
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, datetime):
        v = v.date()
    if isinstance(v, date):
        return (v - EPOCA).days
    return v


def blocos_formula(grade: list[list], lin: int) -> list[tuple[int, int]]:
    """Faixas contíguas (col de, col até) de células com fórmula na linha."""
    res: list[tuple[int, int]] = []
    linha = grade[lin] if lin < len(grade) else []
    for c, v in enumerate(linha):
        if e_formula(v):
            if res and res[-1][1] == c - 1:
                res[-1] = (res[-1][0], c)
            else:
                res.append((c, c))
    return res


def _cod_para_celula(c: str):
    return int(c) if c.isdigit() else c


def _achar(cabecalho: list, *nomes: str) -> int | None:
    alvos = [norm(n) for n in nomes]
    for i, v in enumerate(cabecalho):
        if norm(str(v)).replace("\n", " ") in alvos:
            return i
    return None


# ---------- estrutura ----------

@dataclass
class EstruturaReq:
    col_ano: int
    col_coluna: int
    col_obs: int


def estrutura_req(grade: list[list]) -> EstruturaReq:
    cab = grade[0] if grade else []
    if _achar(cab, "DATA") != 0 or _achar(cab, "REQUISIÇÃO") != 1:
        raise PlanilhaInvalida("REQ: a linha 1 deveria começar com DATA | REQUISIÇÃO.")
    ano, coluna, obs = _achar(cab, "ANO"), _achar(cab, "COLUNA"), _achar(cab, "OBSERVAÇÃO")
    if None in (ano, coluna, obs) or min(ano, coluna, obs) < 10:
        raise PlanilhaInvalida("REQ: faltam os cabeçalhos ANO, COLUNA e OBSERVAÇÃO depois da coluna J.")
    return EstruturaReq(ano, coluna, obs)


@dataclass
class EstruturaMat:
    linha_cab: int            # 0-based
    col_codigo: int
    col_obs: int
    unidades: list[int]       # colunas das unidades (I:R no MODELO)
    diversos: int | None
    ultima_formula: int       # 0-based, última linha com fórmula na DENOMINAÇÃO

    @property
    def primeira(self) -> int:
        return self.linha_cab + 1

    @property
    def linhas_com_formula(self) -> int:
        return self.ultima_formula - self.primeira + 1


def estrutura_mat(grade: list[list], titulo: str) -> EstruturaMat:
    for lc in range(min(10, len(grade))):
        cab = grade[lc]
        cod = _achar(cab, "CÓDIGO")
        if cod is not None:
            break
    else:
        raise PlanilhaInvalida(f"{titulo}: não achei o cabeçalho CÓDIGO.")
    den, obs = _achar(cab, "DENOMINAÇÃO"), _achar(cab, "OBSERVAÇÃO")
    if den is None or obs is None:
        raise PlanilhaInvalida(f"{titulo}: faltam os cabeçalhos DENOMINAÇÃO/OBSERVAÇÃO.")
    fim = len(cab)
    for nome in ("DIVERSOS", "QTD UND", "PREGÃO"):
        k = _achar(cab, nome)
        if k is not None and k > obs:
            fim = min(fim, k)
    unidades = list(range(obs + 1, fim))
    if not unidades:
        raise PlanilhaInvalida(f"{titulo}: não há colunas de unidades depois de OBSERVAÇÃO.")
    diversos = None  # o cabeçalho da DIVERSOS pode ter siglas embaixo do nome
    for i in range(obs + 1, len(cab)):
        if str(cab[i]).strip().upper().startswith("DIVERSOS"):
            diversos = i
            unidades = [u for u in unidades if u < i]
            break
    ult = lc
    for i in range(lc + 1, len(grade)):
        if e_formula(celula(grade, i, den)):
            ult = i
    if ult == lc:
        raise PlanilhaInvalida(f"{titulo}: não há linhas com fórmula na DENOMINAÇÃO.")
    for i in range(lc + 1, len(grade)):
        for c in [cod, obs, *unidades, *([diversos] if diversos is not None else [])]:
            if e_formula(celula(grade, i, c)):
                raise PlanilhaInvalida(f"{titulo}: {col_letra(c)}{i + 1} tem fórmula; o app não sobrescreve.")
    return EstruturaMat(lc, cod, obs, unidades, diversos, ult)


@dataclass
class EstruturaCat:
    linha_cab: int
    col_codigo: int
    col_denominacao: int
    col_unid: int
    col_valor: int
    col_obs: int
    ultima_dado: int          # 0-based; = linha_cab se vazio

    @property
    def formulas(self) -> tuple[int, int]:
        """(primeira, última) coluna das fórmulas entre VALOR e OBSERVAÇÃO."""
        return self.col_valor + 1, self.col_obs - 1


def estrutura_catalogo(grade: list[list]) -> EstruturaCat:
    for lc in range(min(10, len(grade))):
        if _achar(grade[lc], "CÓDIGO") == 0:
            break
    else:
        raise PlanilhaInvalida("CATÁLOGO: não achei o cabeçalho CÓDIGO na coluna A.")
    cab = grade[lc]
    den, und, val, obs = (_achar(cab, "DENOMINAÇÃO"), _achar(cab, "UND. MED", "UNID. MED.", "UND. MED."),
                          _achar(cab, "VALOR"), _achar(cab, "OBSERVAÇÃO"))
    if None in (den, und, val, obs) or not den < und < val < obs:
        raise PlanilhaInvalida("CATÁLOGO: cabeçalhos esperados CÓDIGO | DENOMINAÇÃO | UND. MED | VALOR | … | OBSERVAÇÃO.")
    ult = lc
    for i in range(lc + 1, len(grade)):
        if str(celula(grade, i, 0)).strip():
            ult = i
    return EstruturaCat(lc, 0, den, und, val, obs, ult)


def ler_catalogo(grade: list[list]) -> dict[str, ItemCatalogo]:
    e = estrutura_catalogo(grade)
    res = {}
    for i in range(e.linha_cab + 1, e.ultima_dado + 1):
        c = codigo_txt(celula(grade, i, 0))
        if c:
            res[c] = ItemCatalogo(c, str(celula(grade, i, e.col_denominacao)), str(celula(grade, i, e.col_unid)),
                                  para_decimal(celula(grade, i, e.col_valor)))
    return res


def vagas_mat(grade: list[list], titulo: str) -> int:
    return len(estrutura_mat(grade, titulo).unidades)


# ---------- plano ----------

@dataclass
class Plano:
    valores: dict[str, list[tuple[str, list[list]]]] = field(default_factory=dict)  # aba → [(A1, valores)]
    inserir: dict[str, tuple[int, int]] = field(default_factory=dict)  # aba → (depois da linha 0-based, n)
    garantir: dict[str, int] = field(default_factory=dict)  # aba → nº mínimo de linhas na grade
    copiar_formulas: list[tuple[str, int, int, int, int, int]] = field(default_factory=list)
    # (aba, linha origem 0-based, linha destino de, até (inclusive), col de, col até) — só colunas com fórmula
    datas: dict[str, tuple[int, int, int]] = field(default_factory=dict)  # aba → (col, lin de, lin até) formato data
    resumo: list[str] = field(default_factory=list)
    alertas: list[str] = field(default_factory=list)

    def add(self, aba: str, a1: str, valores: list[list]) -> None:
        self.valores.setdefault(aba, []).append((a1, valores))


def _q(aba: str) -> str:
    return "'" + aba.replace("'", "''") + "'"


def planejar(res: Resultado, ano: int, aba_mat: str, req: list[list], mat: list[list],
             cat: list[list]) -> Plano:
    p = Plano()
    _plano_req(p, res, ano, req)
    _plano_mat(p, res.matriz, aba_mat, mat)
    _plano_cat(p, res.novos_catalogo, cat)
    return p


def _plano_req(p: Plano, res: Resultado, ano: int, grade: list[list]) -> None:
    e = estrutura_req(grade)
    largura = e.col_obs + 1
    antigas = [list(r) + [""] * (largura - len(r)) for r in grade[1:]]
    antigas = [r[:largura] for r in antigas if any(str(x).strip() for x in r[:largura])]
    obs = {str(r[1]).strip(): r[e.col_obs] for r in antigas if str(r[e.col_obs]).strip()}

    def ano_de(r) -> int | None:
        try:
            return int(str(r[e.col_ano]).strip())
        except ValueError:
            d = para_data(r[0])
            return d.year if d else None

    outras = [r for r in antigas if ano_de(r) != ano]
    do_ano_antes = {str(r[1]).strip() for r in antigas if ano_de(r) == ano}
    novas = []
    for ln in res.req:
        linha = [""] * largura
        for k, v in enumerate(ln[:10]):
            linha[k] = v
        linha[e.col_ano], linha[e.col_coluna] = ln[10], ln[11]
        linha[e.col_obs] = obs.get(ln[1], "")
        linha[4] = int(linha[4]) if str(linha[4]).isdigit() else linha[4]
        novas.append(linha)
    todas = novas + outras
    todas.sort(key=lambda r: (para_data(r[0]) or date.min, _numero_req(r[1])), reverse=True)
    vals = [[valor_celula(v) for v in r] for r in todas]
    vals += [[""] * largura for _ in range(len(antigas) - len(todas))]  # limpa sobras
    if vals:
        p.add("REQ", f"{_q('REQ')}!A2:{col_letra(largura - 1)}{len(vals) + 1}", vals)
        p.datas["REQ"] = (0, 1, len(todas))
    entram = [ln[1] for ln in res.req if ln[11] == "OK"]
    novas_nums = [ln[1] for ln in res.req if ln[1] not in do_ano_antes]
    saem = sorted(do_ano_antes - {ln[1] for ln in res.req})
    p.resumo.append(f"REQ: {len(res.req)} requisições de {ano} ({len(entram)} entram na MAT); "
                    f"{len(novas_nums)} novas" + (f": {', '.join(novas_nums)}" if novas_nums else "") + ".")
    if saem:
        p.resumo.append(f"REQ: saem {len(saem)} linhas de {ano} que não vieram na busca: {', '.join(saem)}.")


def _numero_req(s) -> int:
    try:
        return int(str(s).split("/")[0])
    except ValueError:
        return 0


def _qtd(v: Decimal | None):
    return "" if v is None else valor_celula(v)


def _plano_mat(p: Plano, m: Matriz, aba: str, grade: list[list]) -> None:
    e = estrutura_mat(grade, aba)
    if len(m.colunas) > len(e.unidades):
        raise PlanilhaInvalida(f"{aba}: {len(m.colunas)} unidades e só {len(e.unidades)} colunas.")
    if m.diversos is not None and e.diversos is None:
        raise PlanilhaInvalida(f"{aba}: unidades a mais e não há coluna DIVERSOS.")
    obs_antes: dict[str, object] = {}
    usadas_antes = 0
    for i in range(e.primeira, len(grade)):
        c = codigo_txt(celula(grade, i, e.col_codigo))
        if c:
            usadas_antes = i - e.primeira + 1
            o = celula(grade, i, e.col_obs)
            if str(o).strip():
                obs_antes[c] = o
    n = len(m.linhas)
    faltam = n - e.linhas_com_formula
    if faltam > 0:
        p.inserir[aba] = (e.ultima_formula, faltam)
        de, ate = e.ultima_formula + 1, e.ultima_formula + faltam
        for c0, c1 in blocos_formula(grade, e.primeira):
            p.copiar_formulas.append((aba, e.primeira, de, ate, c0, c1))
        p.alertas.append(f"{aba}: {faltam} linha(s) inseridas no fim, com as fórmulas copiadas da linha "
                         f"{e.primeira + 1}. Os contadores da linha 1 (CONT.VALORES) podem não pegar as novas.")
    total = max(n, usadas_antes)
    # cabeçalhos das unidades
    cab = []
    for k, col in enumerate(e.unidades):
        cab.append(m.colunas[k].cabecalho if k < len(m.colunas) else f"UND{k + 1}")
    lin_cab = e.linha_cab + 1
    p.add(aba, f"{_q(aba)}!{col_letra(e.unidades[0])}{lin_cab}:{col_letra(e.unidades[-1])}{lin_cab}", [cab])
    if e.diversos is not None:
        p.add(aba, f"{_q(aba)}!{col_letra(e.diversos)}{lin_cab}",
              [[m.diversos.cabecalho if m.diversos else "DIVERSOS"]])
    # código
    cods = [[_cod_para_celula(ln.codigo)] for ln in m.linhas] + [[""]] * (total - n)
    l0 = e.primeira + 1
    if cods:
        p.add(aba, f"{_q(aba)}!{col_letra(e.col_codigo)}{l0}:{col_letra(e.col_codigo)}{l0 + total - 1}", cods)
        obs = [[obs_antes.get(ln.codigo, "")] for ln in m.linhas] + [[""]] * (total - n)
        p.add(aba, f"{_q(aba)}!{col_letra(e.col_obs)}{l0}:{col_letra(e.col_obs)}{l0 + total - 1}", obs)
        nomes = [c.nome for c in m.colunas]
        qt = [[_qtd(ln.qtds.get(nomes[k])) if k < len(nomes) else "" for k in range(len(e.unidades))]
              for ln in m.linhas] + [[""] * len(e.unidades)] * (total - n)
        p.add(aba, f"{_q(aba)}!{col_letra(e.unidades[0])}{l0}:{col_letra(e.unidades[-1])}{l0 + total - 1}", qt)
        if e.diversos is not None:
            dv = [[_qtd(ln.qtds.get("DIVERSOS"))] for ln in m.linhas] + [[""]] * (total - n)
            p.add(aba, f"{_q(aba)}!{col_letra(e.diversos)}{l0}:{col_letra(e.diversos)}{l0 + total - 1}", dv)
    perdidas = sorted(set(obs_antes) - {ln.codigo for ln in m.linhas})
    if perdidas:
        p.alertas.append(f"{aba}: a OBSERVAÇÃO destes códigos some, porque eles saíram da matriz: "
                         f"{', '.join(perdidas)}.")
    p.resumo.append(f"{aba}: {n} itens em {len(m.colunas)} colunas ({', '.join(c.nome for c in m.colunas)})"
                    + (f" + DIVERSOS ({', '.join(x.nome for x in m.diversos.partes)})" if m.diversos else "") + ".")


def _plano_cat(p: Plano, novos: list[ItemCatalogo], grade: list[list]) -> None:
    if not novos:
        p.resumo.append("CATÁLOGO: nenhum código novo.")
        return
    e = estrutura_catalogo(grade)
    de = e.ultima_dado + 1  # 0-based
    ate = de + len(novos) - 1
    largura = e.col_obs + 1
    vals = []
    for it in novos:
        r = [""] * largura
        r[0] = _cod_para_celula(it.codigo)
        r[e.col_denominacao], r[e.col_unid] = it.denominacao, it.unid_med
        r[e.col_valor] = valor_celula(it.valor) if it.valor is not None else ""
        r[e.col_obs] = INCLUIDO
        vals.append(r)
    a1 = lambda c0, c1: f"{_q('CATÁLOGO')}!{col_letra(c0)}{de + 1}:{col_letra(c1)}{ate + 1}"  # noqa: E731
    p.add("CATÁLOGO", a1(0, e.col_valor), [r[: e.col_valor + 1] for r in vals])
    p.add("CATÁLOGO", a1(e.col_obs, e.col_obs), [[r[e.col_obs]] for r in vals])
    f0, f1 = e.formulas
    for c0, c1 in blocos_formula(grade, e.linha_cab + 1):
        if f0 <= c0 and c1 <= f1:
            p.copiar_formulas.append(("CATÁLOGO", e.linha_cab + 1, de, ate, c0, c1))
    p.garantir["CATÁLOGO"] = ate + 1
    p.resumo.append(f"CATÁLOGO: {len(novos)} código(s) novo(s) no fim: {', '.join(n.codigo for n in novos)}.")


# ---------- cópias de segurança ----------

def nome_copia(aba: str, agora: datetime) -> str:
    return f"{aba} (antes {agora:%Y-%m-%d %Hh%M})"


def copias_para_apagar(titulos: list[str], aba: str, manter: int = 3) -> list[str]:
    """Cópias antigas da aba além das `manter` mais novas (incluindo a que vai ser criada agora)."""
    pref = f"{aba} (antes "
    copias = sorted(t for t in titulos if t.startswith(pref))
    excesso = len(copias) + 1 - manter
    return copias[:excesso] if excesso > 0 else []
