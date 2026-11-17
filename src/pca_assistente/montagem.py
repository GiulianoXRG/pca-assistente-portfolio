"""Dados lidos do SIPAC → conteúdo de REQ, MAT{AA} e CATÁLOGO + conferências (funções puras).

Não sabe nada de Google Sheets: produz listas/objetos que `planilha.py` encaixa na planilha real.
Textos dos avisos nunca trazem usuário, e-mail ou Observações.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal

from .parsers import Detalhe, LinhaBusca

# Ordem = ordem das colunas na MAT (como nas planilhas já feitas à mão).
MAPA_PADRAO: dict[str, str] = {
    "DOD/CCS": "CCS-DOD",
    "DPAT/CCS": "CCS-DPAT",
    "DFST/CCS": "CCS-DFST",
    "DAS/PROGESP": "DAS/PROGESP",
    "ES/UFRN": "ES",
    "EAJ": "EAJ",
    "ALM-FACISA": "FACISA",
    "SMP/FACISA": "FACISA",
    "CEO/CB": "CB",
    "INST. CÉREBRO": "ICE",
}

OK, NAO = "OK", "NÃO"


@dataclass
class Regras:
    na_mat: tuple[str, ...] = ("ENVIADA",)                 # entram na MAT (REQ: OK)
    fora_req: tuple[str, ...] = ("ESTORNADA", "CANCELADA")  # nem aparecem na REQ
    ordem: str = "alfabetica"                              # 'alfabetica' | 'leitura'
    mapa: dict[str, str] = field(default_factory=lambda: dict(MAPA_PADRAO))

    def entra_mat(self, status: str) -> bool:
        return status.upper() in self.na_mat

    def entra_req(self, status: str) -> bool:
        return status.upper() not in self.fora_req


@dataclass(frozen=True)
class ItemCatalogo:
    codigo: str
    denominacao: str = ""
    unid_med: str = ""
    valor: Decimal | None = None


@dataclass
class Aviso:
    tipo: str      # 'soma', 'preco', 'fora_catalogo', 'grupo', 'repetido', 'busca', 'unidade', 'diversos', 'leitura'
    texto: str
    grave: bool = False  # grave = não deveria gravar sem olhar

    def __str__(self) -> str:
        return ("⚠ " if self.grave else "• ") + self.texto


def brl(v: Decimal) -> str:
    s = f"{v:,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


# ---------- REQ ----------

def linhas_req(busca: list[LinhaBusca], ano: int, regras: Regras) -> list[list]:
    """Linhas A..L da REQ para o ano (sem a M, que é manual). Data mais nova primeiro."""
    res = []
    for x in sorted(busca, key=lambda x: (x.data, x.numero), reverse=True):
        if not regras.entra_req(x.status):
            continue
        res.append([x.data, x.requisicao, x.unidade, x.unidade_custo, x.grupo, x.tipo, x.almoxarifado,
                    x.status, x.usuario, x.valor, ano, OK if regras.entra_mat(x.status) else NAO])
    return res


# ---------- MAT ----------

@dataclass
class Coluna:
    nome: str
    numeros: list[int] = field(default_factory=list)   # nº das requisições (sem /ano), mais nova primeiro
    siglas: list[str] = field(default_factory=list)    # siglas SIPAC que caíram aqui
    partes: list["Coluna"] = field(default_factory=list)  # só DIVERSOS: as unidades excedentes

    @property
    def cabecalho(self) -> str:
        if self.partes:
            return "\n".join([self.nome, *(f"{p.nome} {' '.join(map(str, p.numeros))}" for p in self.partes)])
        return "\n".join([self.nome, *map(str, self.numeros)])


@dataclass
class LinhaMat:
    codigo: str
    denominacao: str
    unid_med: str
    valor_req: Decimal                                  # preço unitário da (primeira) requisição
    qtds: dict[str, Decimal] = field(default_factory=dict)  # nome da coluna (ou DIVERSOS) → qtd


@dataclass
class Matriz:
    colunas: list[Coluna]          # até `vagas`, na ordem das colunas I, J, ...
    diversos: Coluna | None        # unidades excedentes (coluna S), se houver
    linhas: list[LinhaMat]
    destino: dict[str, str] = field(default_factory=dict)  # sigla SIPAC → nome da coluna onde caiu

    @property
    def todas(self) -> list[Coluna]:
        return [*self.colunas, *([self.diversos] if self.diversos else [])]

    def total_coluna(self, nome: str, precos: dict[str, Decimal]) -> Decimal:
        return sum((ln.qtds.get(nome, Decimal(0)) * precos.get(ln.codigo, ln.valor_req) for ln in self.linhas),
                   Decimal(0))


DIVERSOS = "DIVERSOS"


def nome_coluna(sigla: str, mapa: dict[str, str]) -> tuple[str, bool]:
    """(nome da coluna, achou no mapa)."""
    if sigla in mapa:
        return mapa[sigla], True
    alvo = sigla.strip().upper()
    for k, v in mapa.items():
        if k.strip().upper() == alvo:
            return v, True
    return sigla, False


def montar_mat(lidas: list[tuple[LinhaBusca, Detalhe]], regras: Regras, vagas: int = 10,
               avisos: list[Aviso] | None = None) -> Matriz:
    """Uma coluna por unidade (requisições da mesma unidade somam). Excedentes → DIVERSOS."""
    avisos = avisos if avisos is not None else []
    lidas = [(b, d) for b, d in lidas if regras.entra_mat(b.status)]
    ordem_mapa = list(dict.fromkeys(regras.mapa.values()))
    cols: dict[str, Coluna] = {}
    sem_mapa: set[str] = set()
    for b, _ in sorted(lidas, key=lambda bd: (bd[0].data, bd[0].numero), reverse=True):
        nome, achou = nome_coluna(b.unidade, regras.mapa)
        if not achou:
            sem_mapa.add(b.unidade)
        c = cols.setdefault(nome, Coluna(nome))
        c.numeros.append(b.numero)
        if b.unidade not in c.siglas:
            c.siglas.append(b.unidade)
    for s in sorted(sem_mapa):
        avisos.append(Aviso("unidade", f"Unidade {s} não está no mapa de unidades: usei a própria sigla como coluna."))

    def chave(c: Coluna):
        return (ordem_mapa.index(c.nome) if c.nome in ordem_mapa else len(ordem_mapa), c.nome)

    todas = sorted(cols.values(), key=chave)
    colunas, sobra = todas[:vagas], todas[vagas:]
    diversos = None
    destino = {c.nome: c.nome for c in colunas}
    if sobra:
        diversos = Coluna(DIVERSOS, partes=sobra)
        for c in sobra:
            destino[c.nome] = DIVERSOS
            diversos.numeros.extend(c.numeros)
            diversos.siglas.extend(c.siglas)
        avisos.append(Aviso("diversos", (
            f"Há {len(todas)} unidades e só {vagas} colunas: {', '.join(c.nome for c in sobra)} foram para DIVERSOS. "
            "Atenção: a coluna QTD (E) soma só as colunas das unidades, não a DIVERSOS (decisão pendente)."), True))

    por_sigla = {b.unidade: destino[nome_coluna(b.unidade, regras.mapa)[0]] for b, _ in lidas}
    linhas: dict[str, LinhaMat] = {}
    for b, d in sorted(lidas, key=lambda bd: (bd[0].data, bd[0].numero)):  # leitura: mais antiga primeiro
        col = por_sigla[b.unidade]
        for it in d.itens:
            ln = linhas.get(it.codigo)
            if ln is None:
                ln = linhas[it.codigo] = LinhaMat(it.codigo, it.denominacao, it.unid_med, it.valor)
            ln.qtds[col] = ln.qtds.get(col, Decimal(0)) + it.qt
    lista = list(linhas.values())
    if regras.ordem == "alfabetica":
        lista.sort(key=lambda ln: (ln.denominacao.upper(), ln.codigo))
    return Matriz(colunas, diversos, lista, por_sigla)


# ---------- CATÁLOGO ----------

INCLUIDO = "INCLUÍDO PELO PCA ASSISTENTE – CONFERIR"


def novos_no_catalogo(m: Matriz, catalogo: dict[str, ItemCatalogo]) -> list[ItemCatalogo]:
    return [ItemCatalogo(ln.codigo, ln.denominacao, ln.unid_med, ln.valor_req)
            for ln in sorted(m.linhas, key=lambda ln: ln.codigo) if ln.codigo not in catalogo]


# ---------- conferências ----------

@dataclass
class Resultado:
    req: list[list]
    matriz: Matriz
    novos_catalogo: list[ItemCatalogo]
    avisos: list[Aviso]
    totais: dict[str, tuple[Decimal, Decimal]]  # coluna → (total pelo preço do catálogo, total das requisições)


def conferir(grupo: str, busca_linhas: list[LinhaBusca], total_qtd: int | None, total_valor: Decimal | None,
             lidas: list[tuple[LinhaBusca, Detalhe]], m: Matriz, catalogo: dict[str, ItemCatalogo],
             regras: Regras) -> tuple[list[Aviso], dict[str, tuple[Decimal, Decimal]]]:
    av: list[Aviso] = []
    # 6. busca × lido
    soma = sum((x.valor for x in busca_linhas), Decimal(0))
    if total_qtd is not None and total_qtd != len(busca_linhas):
        av.append(Aviso("busca", f"A busca diz {total_qtd} requisições, mas li {len(busca_linhas)}.", True))
    if total_valor is not None and total_valor != soma:
        av.append(Aviso("busca", f"A busca diz {brl(total_valor)} no total, mas a soma lida é {brl(soma)}.", True))
    precisam = {x.id for x in busca_linhas if regras.entra_mat(x.status)}
    lidos = {b.id for b, _ in lidas}
    for x in busca_linhas:
        if x.id in precisam - lidos:
            av.append(Aviso("leitura", f"Requisição {x.requisicao} não foi lida (faltou o detalhe).", True))

    for b, d in lidas:
        if not regras.entra_mat(b.status):
            continue
        # 1. soma dos itens × valor
        s = sum((i.qt * i.valor for i in d.itens), Decimal(0))
        if s != d.valor:
            av.append(Aviso("soma", f"Requisição {b.requisicao}: soma dos itens {brl(s)} ≠ valor da requisição "
                                    f"{brl(d.valor)}.", True))
        if b.valor != d.valor:
            av.append(Aviso("soma", f"Requisição {b.requisicao}: valor na busca {brl(b.valor)} ≠ no detalhe "
                                    f"{brl(d.valor)}."))
        # 4. outro grupo / subgrupo
        if (d.grupo and d.grupo != grupo) or (b.grupo and b.grupo != grupo):
            av.append(Aviso("grupo", f"Requisição {b.requisicao} é do grupo {d.grupo or b.grupo}, não {grupo}.", True))
        fora = sorted({i.codigo for i in d.itens if not i.codigo.startswith(grupo)})
        if fora:
            av.append(Aviso("grupo", f"Requisição {b.requisicao}: {len(fora)} item(ns) com código de outro grupo "
                                     f"({', '.join(fora[:5])}).", True))
        # 5. código repetido
        rep = [c for c, n in Counter(i.codigo for i in d.itens).items() if n > 1]
        if rep:
            av.append(Aviso("repetido", f"Requisição {b.requisicao}: código repetido {', '.join(sorted(rep))} "
                                        "(as quantidades foram somadas)."))
        # preço da requisição × catálogo
        for i in d.itens:
            c = catalogo.get(i.codigo)
            if c and c.valor is not None and c.valor != i.valor:
                av.append(Aviso("preco", f"{i.codigo} ({i.denominacao[:40]}): requisição {b.requisicao} "
                                         f"{brl(i.valor)}, catálogo {brl(c.valor)}."))
    # 3. fora do catálogo
    for n in novos_no_catalogo(m, catalogo):
        av.append(Aviso("fora_catalogo", f"{n.codigo} ({n.denominacao[:40]}) não está no CATÁLOGO: será incluído "
                                         "no fim, para conferir."))
    # 2. total da coluna (preço catálogo) × total das requisições
    precos = {k: v.valor for k, v in catalogo.items() if v.valor is not None}
    valor_req: dict[str, Decimal] = {}
    for b, d in lidas:
        if regras.entra_mat(b.status) and b.unidade in m.destino:
            col = m.destino[b.unidade]
            valor_req[col] = valor_req.get(col, Decimal(0)) + d.valor
    totais = {}
    for col in m.todas:
        cat, req = m.total_coluna(col.nome, precos), valor_req.get(col.nome, Decimal(0))
        totais[col.nome] = (cat, req)
        if cat != req:
            av.append(Aviso("preco", f"Coluna {col.nome}: {brl(cat)} pelo preço do catálogo × {brl(req)} nas "
                                     f"requisições (diferença {brl(cat - req)})."))
    return av, totais


def montar(grupo: str, ano: int, busca_linhas: list[LinhaBusca], total_qtd: int | None,
           total_valor: Decimal | None, lidas: list[tuple[LinhaBusca, Detalhe]],
           catalogo: dict[str, ItemCatalogo], regras: Regras | None = None, vagas: int = 10) -> Resultado:
    """Tudo de uma vez: REQ do ano, matriz da MAT, novos do catálogo, avisos e totais por coluna."""
    regras = regras or Regras()
    avisos: list[Aviso] = []
    req = linhas_req(busca_linhas, ano, regras)
    m = montar_mat(lidas, regras, vagas, avisos)
    av, totais = conferir(grupo, busca_linhas, total_qtd, total_valor, lidas, m, catalogo, regras)
    return Resultado(req, m, novos_no_catalogo(m, catalogo), avisos + av, totais)
