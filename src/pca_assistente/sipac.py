"""Leitura das requisições de um grupo/ano no SIPAC (só leitura, um pedido por vez)."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Callable, Protocol
from urllib.parse import urlencode

from .montagem import Regras
from .navegador import LoginNecessario
from .parsers import Busca, Detalhe, LinhaBusca, ler_busca, ler_detalhe, norm, texto

PREPARA = "/sipac/preparaBuscaListaReq.do?popula=true&inicio=true"
BUSCA = "/sipac/buscaListaReq.do"
DETALHE = "/sipac/acompanharReqMaterial.do"


class Pedidor(Protocol):
    def pedir(self, metodo: str, rota: str, corpo: str | None = None) -> str: ...


class Parado(RuntimeError):
    pass


@dataclass
class Leitura:
    grupo: str
    ano: int
    busca: Busca
    lidas: list[tuple[LinhaBusca, Detalhe]]


def corpo_busca(grupo: str, ano: int) -> str:
    return urlencode([
        ("tipoReq.id", "16"), ("subTipoReq.id", "1"),
        ("buscaGrupo", "on"), ("codigo_busca", grupo), ("grupo.codigo", grupo),
        ("buscaData", "true"), ("dataInicial", f"01/01/{ano}"), ("dataFinal", f"31/12/{ano}"), ("ano", str(ano)),
        ("status", "0"), ("grupoStatus", "0"), ("proponente.siape", "0"), ("unidade.id", "0"),
        ("unidadeCusto.id", "0"), ("tipo", "0"), ("acao", "13"), ("busca", "true"),
    ], encoding="iso-8859-1")


def corpo_detalhe(id_: int) -> str:
    return urlencode({"id": id_, "requisicao": id_, "acao": 200})


def _checar_pagina(html: str) -> None:
    t = norm(texto(html[:20000]))
    if "AUTENTICACAO.UFRN.BR" in t or re.search(r"\bENTRAR NO SISTEMA\b|SUA SESSAO (FOI )?EXPIR", t):
        raise LoginNecessario("A sessão do SIPAC caiu: faça login no Chrome do assistente e tente de novo.")


def ler_grupo(p: Pedidor, grupo: str, ano: int, regras: Regras, saida: Callable[..., None] = print,
              parar: Callable[[], bool] = lambda: False, pausa: float = 0.7) -> Leitura:
    saida(f"Buscando requisições do grupo {grupo} em {ano}…")
    _checar_pagina(p.pedir("GET", PREPARA))
    time.sleep(pausa)
    html = p.pedir("POST", BUSCA, corpo_busca(grupo, ano))
    _checar_pagina(html)
    busca = ler_busca(html)
    alvo = [x for x in busca.linhas if regras.entra_mat(x.status)]
    saida(f"Achei {len(busca.linhas)} requisições ({len(alvo)} para ler os itens).")
    lidas = []
    for k, x in enumerate(alvo, 1):
        if parar():
            raise Parado(f"Parado depois de ler {k - 1} de {len(alvo)} requisições.")
        time.sleep(pausa)
        saida(f"{k}/{len(alvo)} lendo requisição {x.requisicao}…")
        h = p.pedir("POST", DETALHE, corpo_detalhe(x.id))
        _checar_pagina(h)
        lidas.append((x, ler_detalhe(h)))
    return Leitura(grupo, ano, busca, lidas)
