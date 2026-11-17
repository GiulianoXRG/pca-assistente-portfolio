"""Junta as peças: leitura do SIPAC → montagem → plano na planilha → gravação. Usado pelo CLI e pela tela."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from .montagem import Regras, Resultado, brl, montar
from .planilha import Plano, ler_catalogo, planejar, vagas_mat
from .saida import Saida, gravar
from .sipac import Leitura


def aba_mat(ano: int) -> str:
    return f"MAT{ano % 100:02d}"


@dataclass
class Preparo:
    leitura: Leitura
    resultado: Resultado
    plano: Plano | None = None
    sid: str | None = None
    aba: str = ""
    erro_planilha: str | None = None
    gravado_em: datetime | None = None
    copias: list[str] = field(default_factory=list)


def montar_sem_planilha(lt: Leitura, regras: Regras, vagas: int = 10) -> Resultado:
    b = lt.busca
    return montar(lt.grupo, lt.ano, b.linhas, b.total_qtd, b.total_valor, lt.lidas, {}, regras, vagas)


def preparar(lt: Leitura, regras: Regras, saida: Saida | None, sid: str | None) -> Preparo:
    """Lê a planilha (se houver), monta com o catálogo real e planeja a escrita. Não grava nada."""
    aba = aba_mat(lt.ano)
    if not (saida and sid):
        return Preparo(lt, montar_sem_planilha(lt, regras), aba=aba,
                       erro_planilha="Planilha do grupo não configurada: a prévia não usa o CATÁLOGO.")
    titulos = saida.titulos(sid)
    faltam = [a for a in ("REQ", aba, "CATÁLOGO") if a not in titulos]
    if faltam:
        return Preparo(lt, montar_sem_planilha(lt, regras), sid=sid, aba=aba,
                       erro_planilha=f"A planilha não tem a(s) aba(s) {', '.join(faltam)}.")
    g = saida.ler(sid, ["REQ", aba, "CATÁLOGO"])
    try:
        cat = ler_catalogo(g["CATÁLOGO"])
        b = lt.busca
        res = montar(lt.grupo, lt.ano, b.linhas, b.total_qtd, b.total_valor, lt.lidas, cat, regras,
                     vagas_mat(g[aba], aba))
        plano = planejar(res, lt.ano, aba, g["REQ"], g[aba], g["CATÁLOGO"])
    except ValueError as e:
        return Preparo(lt, montar_sem_planilha(lt, regras), sid=sid, aba=aba, erro_planilha=str(e))
    return Preparo(lt, res, plano, sid, aba)


def executar_gravacao(pr: Preparo, saida: Saida) -> list[str]:
    if not pr.plano or not pr.sid:
        raise RuntimeError(pr.erro_planilha or "Nada para gravar.")
    pr.copias = gravar(saida, pr.sid, pr.plano, [pr.aba, "REQ"])
    pr.gravado_em = datetime.now()
    return pr.copias


def resumo(lt: Leitura, res: Resultado) -> list[str]:
    """Resumo sem dados pessoais (sem usuário, e-mail, Observações)."""
    b = lt.busca
    st = Counter(x.status for x in b.linhas)
    linhas = [f"Grupo {lt.grupo}, {lt.ano}: {len(b.linhas)} requisições na busca "
              f"({', '.join(f'{n} {s}' for s, n in st.most_common())}).",
              "Rodapé da busca: " + (f"{b.total_qtd} requisições, {brl(b.total_valor)}" if b.total_qtd is not None
                                    else "não encontrado") + (" ✔ confere" if b.confere else " ✖ não confere") + ".",
              f"Lidas: {len(lt.lidas)} requisições, {sum(len(d.itens) for _, d in lt.lidas)} itens; "
              f"{len(res.matriz.linhas)} códigos distintos."]
    for c in res.matriz.todas:
        cat, req = res.totais.get(c.nome, (Decimal(0), Decimal(0)))
        linhas.append(f"  {c.cabecalho.replace(chr(10), ' ')}: requisições {brl(req)}")
    linhas.append(f"REQ: {len(res.req)} linhas ({sum(1 for r in res.req if r[11] == 'OK')} OK).")
    if res.avisos:
        linhas.append(f"Conferências ({len(res.avisos)}):")
        linhas += [f"  {a}" for a in res.avisos]
    else:
        linhas.append("Conferências: tudo certo.")
    return linhas
