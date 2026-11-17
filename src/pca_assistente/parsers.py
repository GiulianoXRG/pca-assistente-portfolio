"""HTML do SIPAC → dados (funções puras, sem rede).

Lê o HTML cru com regex, porque a busca tem `<form>` dentro de `<tr>` e o DOMParser perde os inputs.
As Observações do detalhe NÃO são extraídas (trazem contatos pessoais: nunca vão para log, git ou planilha);
o e-mail do usuário também não.
"""
from __future__ import annotations

import html as _html
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

_S = re.S | re.I


class FormatoInesperado(ValueError):
    """O HTML não tem a estrutura esperada (página trocou, sessão expirou, login...)."""


# ---------- utilidades ----------

def norm(s: str) -> str:
    """Maiúsculas, sem acentos e com espaços simples (para comparar rótulos)."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip().upper()


def texto(fragmento: str) -> str:
    """Texto visível de um trecho de HTML, numa linha."""
    s = re.sub(r"<(script|style)\b.*?</\1>", " ", fragmento, flags=_S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", _html.unescape(s).replace("\xa0", " ")).strip()


def linhas(pagina: str) -> list[str]:
    """Texto da página quebrado em linhas por célula/bloco (vazias descartadas)."""
    s = re.sub(r"<(script|style)\b.*?</\1>", " ", pagina, flags=_S)
    s = re.sub(r"<br\s*/?>|</(td|th|tr|p|div|li|h\d|caption|legend|table)>", "\n", s, flags=re.I)
    s = _html.unescape(re.sub(r"<[^>]+>", " ", s)).replace("\xa0", " ")
    return [t for t in (re.sub(r"[ \t\r\f\v]+", " ", x).strip() for x in s.split("\n")) if t]


def numero(s: str) -> Decimal:
    """'R$ 1.234,56' → Decimal('1234.56'); '1.000' → 1000; '6,5' → 6.5."""
    t = re.sub(r"[^\d,.\-]", "", s or "")
    if not t:
        raise FormatoInesperado(f"número vazio: {s!r}")
    t = t.replace(".", "").replace(",", ".")
    try:
        return Decimal(t)
    except InvalidOperation as e:
        raise FormatoInesperado(f"número inválido: {s!r}") from e


def data_br(s: str) -> date:
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", s or "")
    if not m:
        raise FormatoInesperado(f"data inválida: {s!r}")
    return date(int(m[3]), int(m[2]), int(m[1]))


def _datahora(s: str) -> datetime | None:
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})(?:\s+(\d{2}):(\d{2}))?", s or "")
    if not m:
        return None
    return datetime(int(m[3]), int(m[2]), int(m[1]), int(m[4] or 0), int(m[5] or 0))


def _trs(trecho: str) -> list[str]:
    """Pedaços de cada <tr> (corta no próximo <tr>, então tabelas aninhadas não atrapalham)."""
    return re.split(r"<tr\b", trecho, flags=re.I)[1:]


def _celulas(tr: str) -> list[str]:
    return [texto(c) for c in re.findall(r"<td\b[^>]*>(.*?)</td>", tr, flags=_S)]


# ---------- busca (buscaListaReq.do) ----------

_RX_REQ = re.compile(r"^(\d+)/(\d{4})$")


@dataclass(frozen=True)
class LinhaBusca:
    id: int                 # id interno (acompanharReqMaterial.do?id=…)
    data: date
    numero: int             # 7470
    ano: int                # 2026
    unidade: str            # sigla da unidade requisitante (DAS/PROGESP)
    unidade_custo: str
    grupo: str              # '3010'
    tipo: str
    almoxarifado: str
    status: str
    usuario: str
    valor: Decimal

    @property
    def requisicao(self) -> str:
        return f"{self.numero}/{self.ano}"


@dataclass(frozen=True)
class Busca:
    linhas: list[LinhaBusca]
    total_qtd: int | None        # rodapé "Requisições: N"
    total_valor: Decimal | None  # rodapé "Valor Total: R$ …"

    @property
    def confere(self) -> bool:
        """Rodapé bate com o que foi lido (conferência 6, parte da busca)."""
        return (self.total_qtd == len(self.linhas)
                and self.total_valor == sum((x.valor for x in self.linhas), Decimal(0)))


def _tabela_listagem(pagina: str) -> str | None:
    m = re.search(r"<table\b[^>]*class=\"[^\"]*\blistagem\b[^\"]*\"[^>]*>(.*?)</table>", pagina, flags=_S)
    return m.group(1) if m else None


def _id_interno(tr: str) -> int | None:
    for rx in (r"idReq=(\d+)",
               r"<input\b[^>]*name=\"id\"[^>]*value=\"(\d+)\"",
               r"<input\b[^>]*value=\"(\d+)\"[^>]*name=\"id\""):
        m = re.search(rx, tr, flags=re.I)
        if m:
            return int(m.group(1))
    return None


def ler_busca(pagina: str) -> Busca:
    """Tabela de resultado da busca de requisições. Sem resultado → Busca vazia."""
    tabela = _tabela_listagem(pagina)
    if tabela is None:
        if "NENHUMA REQUISI" in norm(texto(pagina)):
            return Busca([], 0, Decimal(0))
        raise FormatoInesperado("tabela de requisições não encontrada")
    corpo = re.search(r"<tbody\b[^>]*>(.*?)</tbody>", tabela, flags=_S)
    corpo = corpo.group(1) if corpo else tabela
    res: list[LinhaBusca] = []
    for tr in _trs(corpo):
        cel = _celulas(tr)
        i = next((k for k, c in enumerate(cel) if _RX_REQ.match(c)), None)
        if i is None or i < 1 or len(cel) < i + 9:
            continue
        id_ = _id_interno(tr)
        if id_ is None:
            raise FormatoInesperado(f"linha sem id interno (requisição {cel[i]})")
        m = _RX_REQ.match(cel[i])
        res.append(LinhaBusca(
            id=id_, data=data_br(cel[i - 1]), numero=int(m[1]), ano=int(m[2]),
            unidade=cel[i + 1], unidade_custo=cel[i + 2], grupo=cel[i + 3], tipo=cel[i + 4],
            almoxarifado=cel[i + 5], status=cel[i + 6].upper(), usuario=cel[i + 7],
            valor=numero(cel[i + 8]),
        ))
    t = texto(pagina)
    mq = re.search(r"Requisi\S*es:\s*(\d+)", t)
    mv = re.search(r"Valor Total:\s*R\$\s*([\d.,]+)", t)
    return Busca(res, int(mq[1]) if mq else None, numero(mv[1]) if mv else None)


def opcoes_status(pagina: str) -> list[str]:
    """Textos do <select name="status"> do formulário de busca (sem o '-- TODOS --')."""
    m = re.search(r"<select\b[^>]*name=\"status\"[^>]*>(.*?)</select>", pagina, flags=_S)
    if not m:
        return []
    ops = [texto(o) for o in re.findall(r"<option\b[^>]*>(.*?)</option>", m.group(1), flags=_S)]
    return [o for o in ops if o and not o.startswith("--")]


# ---------- detalhe (acompanharReqMaterial.do, acao=200) ----------

_RX_COD = re.compile(r"^\d{12,13}$")  # há códigos antigos com 12 dígitos (ex.: 301000000289)


@dataclass(frozen=True)
class Item:
    nr: int
    codigo: str          # 13 dígitos
    denominacao: str
    unid_med: str
    qt: Decimal
    valor: Decimal       # unitário
    total: Decimal
    status: str


@dataclass(frozen=True)
class Detalhe:
    numero: int
    ano: int
    tipo: str
    grupo_nome: str      # 'MATERIAL ODONTOLOGICO'
    grupo: str           # '3010'
    unidade: str         # sigla: 'DAS/PROGESP'
    unidade_nome: str
    unidade_codigo: str  # '11.65.05'
    status: str
    valor: Decimal
    data_cadastro: datetime | None
    data_envio: datetime | None
    itens: list[Item] = field(default_factory=list)

    @property
    def requisicao(self) -> str:
        return f"{self.numero}/{self.ano}"


def _campo(lin: list[str], rotulo: str) -> str:
    """Valor do rótulo 'Rótulo:' na mesma linha ou na seguinte. '' se não houver."""
    alvo = norm(rotulo).rstrip(":")
    for i, l in enumerate(lin):
        n = norm(l)
        if not n.startswith(alvo):
            continue
        resto = n[len(alvo):]
        if resto and not resto.lstrip().startswith(":"):
            continue  # outro rótulo que só começa igual
        depois = l.split(":", 1)[1].strip() if ":" in l else ""
        return depois or (lin[i + 1] if i + 1 < len(lin) else "")
    return ""


def _sigla_nome_codigo(s: str) -> tuple[str, str, str]:
    """'DAS/PROGESP - DIRETORIA X (11.65.05)' → ('DAS/PROGESP', 'DIRETORIA X', '11.65.05')."""
    cod = ""
    m = re.search(r"\(([\d.]+)\)\s*$", s)
    if m:
        cod, s = m.group(1), s[: m.start()].strip()
    sigla, _, nome = s.partition(" - ")
    return sigla.strip(), nome.strip(), cod


def ler_itens(pagina: str) -> list[Item]:
    itens: list[Item] = []
    for tr in _trs(pagina):
        cel = _celulas(tr)
        k = next((j for j, c in enumerate(cel) if _RX_COD.match(c)), None)
        if k is None or k < 1 or len(cel) < k + 6 or not cel[k - 1].isdigit():
            continue
        itens.append(Item(
            nr=int(cel[k - 1]), codigo=cel[k], denominacao=cel[k + 1], unid_med=cel[k + 2],
            qt=numero(cel[k + 3]), valor=numero(cel[k + 4]), total=numero(cel[k + 5]),
            status=next((c for c in reversed(cel[k + 6:]) if c and not c.isdigit()), ""),  # há célula vazia no fim
        ))
    return itens


def ler_detalhe(pagina: str) -> Detalhe:
    lin = linhas(pagina)
    req = _campo(lin, "Número da Requisição")
    m = re.search(r"(\d+)\s*/\s*(\d{4})", req)
    if not m:
        raise FormatoInesperado("número da requisição não encontrado no detalhe")
    grupo_txt = _campo(lin, "Grupo de Material")
    mg = re.search(r"^(.*?)\s*\((\d+)\)\s*$", grupo_txt)
    sigla, nome, cod = _sigla_nome_codigo(_campo(lin, "Unidade Requisitante"))
    valor = _campo(lin, "Valor da Requisição")
    return Detalhe(
        numero=int(m[1]), ano=int(m[2]),
        tipo=_campo(lin, "Tipo da Requisição") or _campo(lin, "Tipo"),
        grupo_nome=mg[1] if mg else grupo_txt, grupo=mg[2] if mg else "",
        unidade=sigla, unidade_nome=nome, unidade_codigo=cod,
        status=_campo(lin, "Status Atual").upper(),
        valor=numero(valor) if valor else Decimal(0),
        data_cadastro=_datahora(_campo(lin, "Data de Cadastro")),
        data_envio=_datahora(_campo(lin, "Data de Envio")),
        itens=ler_itens(pagina),
    )
