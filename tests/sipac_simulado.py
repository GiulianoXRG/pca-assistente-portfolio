"""SIPAC simulado: responde aos pedidos de `sipac.ler_grupo` com HTML fictício gerado a partir de dados.py."""
from __future__ import annotations

from urllib.parse import parse_qs

from pca_assistente.montagem import brl


def _v(x) -> str:
    return brl(x)


def html_busca(lidas) -> str:
    linhas = []
    for b, _ in lidas:
        linhas.append(
            f'<tr><form action="/sipac/acompanharReqMaterial.do"><td><input type="hidden" name="id" value="{b.id}"></td></form>'
            f"<td>{b.data:%d/%m/%Y}</td><td>{b.requisicao}</td><td>{b.unidade}</td><td>{b.unidade_custo}</td>"
            f"<td>{b.grupo}</td><td>{b.tipo}</td><td>{b.almoxarifado}</td><td>{b.status}</td><td>{b.usuario}</td>"
            f"<td>{_v(b.valor)}</td><td><a href=\"/sipac/populaCadReqMaterial.do?idReq={b.id}\">x</a></td></tr>")
    total = sum((b.valor for b, _ in lidas), 0)
    return (f'<html><body><table class="listagem"><tbody>{"".join(linhas)}'
            f'<tr><td colspan="12">Requisições: {len(lidas)} | Valor Total: {_v(total)}</td></tr>'
            "</tbody></table></body></html>")


def html_detalhe(b, d) -> str:
    itens = "".join(
        f"<tr><td>{i.nr}</td><td>{i.codigo}</td><td>{i.denominacao}</td><td>{i.unid_med}</td><td>{str(i.qt).replace('.', ',')}</td>"
        f"<td>{_v(i.valor)}</td><td>{_v(i.total)}</td><td>0</td><td>0</td><td>0</td><td>{i.status}</td></tr>"
        for i in d.itens)
    return ("<html><body><table>"
            f"<tr><th>Número da Requisição:</th><td>{d.requisicao}</td></tr>"
            f"<tr><th>Tipo da Requisição:</th><td>{d.tipo}</td></tr>"
            f"<tr><th>Grupo de Material:</th><td>{d.grupo_nome} ({d.grupo})</td></tr>"
            f"<tr><th>Unidade Requisitante:</th><td>{d.unidade} - {d.unidade_nome} ({d.unidade_codigo})</td></tr>"
            f"<tr><th>Valor da Requisição:</th><td>{_v(d.valor)}</td></tr>"
            "<tr><th>Observações:</th><td>ligar (84) 90000-0000</td></tr>"
            f"<tr><th>Status Atual:</th><td>{d.status}</td></tr></table>"
            f'<table class="listagem"><tbody>{itens}</tbody></table></body></html>')


class SipacSimulado:
    def __init__(self, lidas, login_no_detalhe: int | None = None):
        self.lidas = lidas
        self.pedidos: list[tuple[str, str]] = []
        self.login_no_detalhe = login_no_detalhe
        self.preparado = False

    def pedir(self, metodo, rota, corpo=None):
        self.pedidos.append((metodo, rota.split("?")[0]))
        if rota.startswith("/sipac/preparaBuscaListaReq.do"):
            self.preparado = True
            return "<html><body>form</body></html>"
        if rota == "/sipac/buscaListaReq.do":
            assert self.preparado, "busca sem inicializar a sessão JSF"
            q = parse_qs(corpo)
            assert q["tipoReq.id"] == ["16"] and q["acao"] == ["13"]
            return html_busca([bd for bd in self.lidas if bd[0].grupo == q["grupo.codigo"][0]])
        if rota == "/sipac/acompanharReqMaterial.do":
            q = parse_qs(corpo)
            assert q["acao"] == ["200"]
            n = sum(1 for m, r in self.pedidos if r == rota)
            if self.login_no_detalhe == n:
                return "<html><body>Entrar no Sistema - autenticacao.ufrn.br</body></html>"
            b, d = next(bd for bd in self.lidas if bd[0].id == int(q["id"][0]))
            return html_detalhe(b, d)
        raise AssertionError(f"rota inesperada {rota}")
