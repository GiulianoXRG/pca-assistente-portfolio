"""Conexão SÓ LEITURA com o Chrome do assistente (CDP 9223).

Não clica, não preenche, não navega: faz `fetch` dentro da aba já logada do SIPAC (mesmos cookies).
Nunca imprime URL com parâmetros.
"""
from __future__ import annotations

import json
import urllib.request
from contextlib import contextmanager
from urllib.parse import urlsplit

from .config import CDP, SIPAC


class LoginNecessario(RuntimeError):
    pass


class SemChrome(RuntimeError):
    pass


def caminho(url: str) -> str:
    """URL sem parâmetros (para mensagens)."""
    p = urlsplit(url)
    return p.netloc + p.path


def situacao(cdp: str = CDP, timeout: float = 2) -> dict:
    """Situação do Chrome lida pelo HTTP do CDP (sem Playwright): {chrome, sipac, login}."""
    try:
        with urllib.request.urlopen(cdp + "/json", timeout=timeout) as r:
            abas = [a for a in json.load(r) if a.get("type") == "page"]
    except Exception:
        return {"chrome": False, "sipac": False, "login": False}
    urls = [a.get("url", "") for a in abas]
    return {"chrome": True,
            "sipac": any("sipac.ufrn.br" in u for u in urls),
            "login": any("autenticacao.ufrn.br" in u for u in urls)}


@contextmanager
def conectar(cdp: str = CDP):
    from playwright.sync_api import sync_playwright  # só conecta por CDP: não baixa browsers

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(cdp)
        except Exception as e:
            raise SemChrome("Não achei o Chrome do assistente. Abra pelo atalho \"PCA assistente\".") from e
        try:
            yield browser
        finally:
            browser.close()  # em CDP só desconecta; o Chrome continua aberto


def aba_sipac(browser):
    abas = [pg for ctx in browser.contexts for pg in ctx.pages]
    if any("autenticacao.ufrn.br" in pg.url for pg in abas):
        raise LoginNecessario("Faça login no SIPAC no Chrome do assistente e tente de novo.")
    sipac = [pg for pg in abas if "sipac.ufrn.br" in pg.url]
    if not sipac:
        raise LoginNecessario("Não há aba do SIPAC aberta no Chrome do assistente. Abra o SIPAC e faça login.")
    return sipac[0]


_JS_PEDIR = """async ({url, metodo, corpo}) => {
  const op = {method: metodo, credentials: 'include'};
  if (corpo !== null) { op.body = corpo; op.headers = {'Content-Type': 'application/x-www-form-urlencoded'}; }
  const r = await fetch(url, op);
  const b = await r.arrayBuffer();
  return {status: r.status, url: r.url, texto: new TextDecoder('iso-8859-1').decode(b)};
}"""


class PedidorPagina:
    """Faz os pedidos ao SIPAC dentro da aba logada."""

    def __init__(self, page):
        self.page = page

    def pedir(self, metodo: str, rota: str, corpo: str | None = None) -> str:
        r = self.page.evaluate(_JS_PEDIR, {"url": SIPAC + rota, "metodo": metodo, "corpo": corpo})
        if "autenticacao.ufrn.br" in r["url"] or "/sipac/login" in caminho(r["url"]):
            raise LoginNecessario("A sessão do SIPAC caiu: faça login no Chrome do assistente e tente de novo.")
        if r["status"] >= 400:
            raise RuntimeError(f"SIPAC respondeu {r['status']} em {caminho(SIPAC + rota)}.")
        return r["texto"]
