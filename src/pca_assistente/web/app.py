"""Tela local (FastAPI + Jinja2, porta 8010): Início → Resultado → Gravar; Configurações."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import config
from ..montagem import NAO, OK, brl
from ..servico import Preparo, executar_gravacao, preparar
from ..tarefas import Executor

AQUI = Path(__file__).parent
STATUS_CONHECIDOS = ["ENVIADA", "EM AQUISIÇÃO", "ESTORNADA", "CANCELADA", "CADASTRADA"]


def _ler_real(grupo, ano, regras, saida, parar):
    from ..navegador import PedidorPagina, aba_sipac, conectar
    from ..sipac import ler_grupo
    with conectar() as browser:
        return ler_grupo(PedidorPagina(aba_sipac(browser)), grupo, ano, regras, saida, parar, config.PAUSA)


def _abrir_saida_real(cfg, sid=None, interativo=False):
    from ..saida_xlsx import abrir
    return abrir(cfg, sid, interativo)


def _qtd(v) -> str:
    if v is None:
        return ""
    s = f"{v:,.2f}".rstrip("0").rstrip(".") if v != v.to_integral_value() else f"{int(v):,}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def criar_app(ler=_ler_real, abrir_saida=_abrir_saida_real, situacao=None) -> FastAPI:
    app = FastAPI(title="PCA assistente", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=AQUI / "static"), name="static")
    tpl = Jinja2Templates(directory=AQUI / "templates")
    tpl.env.filters["brl"] = brl
    tpl.env.filters["qtd"] = _qtd
    from ..saida_xlsx import eh_xlsx
    tpl.env.tests["xlsx"] = eh_xlsx
    ex = Executor()
    estado: dict = {"preparo": None}
    if situacao is None:
        from ..navegador import situacao as _sit
        situacao = _sit
    app.state.executor, app.state.estado = ex, estado

    def render(request: Request, nome: str, **ctx):
        return tpl.TemplateResponse(request, nome, {"cfg": config.carregar(), **ctx})

    # ---------- páginas ----------

    @app.get("/", response_class=HTMLResponse)
    def inicio(request: Request):
        return render(request, "inicio.html", ano=date.today().year, pr=estado["preparo"])

    @app.get("/resultado", response_class=HTMLResponse)
    def resultado(request: Request):
        pr: Preparo | None = estado["preparo"]
        if pr is None:
            return RedirectResponse("/", 303)
        cfg = config.carregar()
        regras = config.regras(cfg)
        reqs = []
        for x in sorted(pr.leitura.busca.linhas, key=lambda x: (x.data, x.numero), reverse=True):
            if regras.entra_mat(x.status):
                sit, tom = "Entra na MAT (OK)", "ok"
            elif regras.entra_req(x.status):
                sit, tom = f"Só na REQ ({NAO}): status {x.status}", "aten"
            else:
                sit, tom = f"Fora: status {x.status}", "neutro"
            reqs.append({"r": x, "sit": sit, "tom": tom})
        graves = [a for a in pr.resultado.avisos if a.grave]
        return render(request, "resultado.html", pr=pr, reqs=reqs, graves=graves, OK=OK)

    @app.get("/configuracoes", response_class=HTMLResponse)
    def configuracoes(request: Request, msg: str = "", tom: str = "ok"):
        from ..google_sheets import descrever_conta, email_servico
        cfg = config.carregar()
        return render(request, "configuracoes.html", sit=situacao(), conta=descrever_conta(cfg),
                      email=email_servico(), pasta=str(config.PASTA), status=STATUS_CONHECIDOS,
                      mapa_txt="\n".join(f"{k} = {v}" for k, v in cfg["mapa"].items()), msg=msg, tom=tom,
                      tem_oauth=config.ARQ_OAUTH_CLIENTE.exists(), porta_cdp=config.CDP_PORTA)

    # ---------- tarefas ----------

    @app.get("/estado")
    def estado_json(desde: int = 0):
        e = ex.estado(desde)
        e["chrome"] = situacao()
        e["tem_resultado"] = estado["preparo"] is not None
        return e

    @app.post("/buscar")
    def buscar(grupo: str = Form(...), ano: int = Form(...)):
        grupo = grupo.strip()
        if not grupo.isdigit():
            return JSONResponse({"ok": False, "erro": "Grupo deve ser o número (ex.: 3010)."}, 400)
        cfg = config.carregar()
        config.lembrar_grupo(cfg, grupo)
        config.salvar(cfg)

        def tarefa(saida, parar):
            regras = config.regras(cfg)
            lt = ler(grupo, ano, regras, saida, parar)
            sid = cfg["planilhas"].get(grupo)
            ss = None
            if sid:
                saida("Lendo a planilha do grupo…")
                try:
                    ss = abrir_saida(cfg, sid)
                except Exception as e:
                    saida(f"⚠ Não consegui abrir a planilha: {e}")
            pr = preparar(lt, regras, ss, sid)
            estado["preparo"] = pr
            estado["saida"] = ss
            n = len(pr.resultado.avisos)
            return f"Leitura pronta: {len(lt.lidas)} requisições lidas, {n} conferência(s) para olhar. Abra o Resultado."

        if not ex.iniciar(f"Buscar grupo {grupo} / {ano} no SIPAC", tarefa):
            return JSONResponse({"ok": False, "erro": "Já há uma tarefa rodando."}, 409)
        return {"ok": True}

    @app.post("/gravar")
    def gravar():
        pr: Preparo | None = estado["preparo"]
        if pr is None or pr.plano is None:
            return JSONResponse({"ok": False, "erro": "Nada pronto para gravar."}, 400)
        if pr.gravado_em:
            return JSONResponse({"ok": False, "erro": "Este resultado já foi gravado. Busque de novo."}, 409)

        def tarefa(saida, parar):
            ss = estado.get("saida") or abrir_saida(config.carregar(), pr.sid)
            saida("Fazendo a cópia de segurança e gravando…")
            copias = executar_gravacao(pr, ss)
            return "Gravado na planilha." + (f" Cópia de segurança: {', '.join(copias)}." if copias else "")

        if not ex.iniciar("Gravar na planilha", tarefa):
            return JSONResponse({"ok": False, "erro": "Já há uma tarefa rodando."}, 409)
        return {"ok": True}

    @app.post("/parar")
    def parar():
        ex.pedir_parar()
        return {"ok": True}

    # ---------- configurações ----------

    def volta(msg: str, tom: str = "ok"):
        from urllib.parse import urlencode
        return RedirectResponse("/configuracoes?" + urlencode({"msg": msg, "tom": tom}), 303)

    @app.post("/config/planilha")
    def config_planilha(grupo: str = Form(...), link: str = Form("")):
        cfg = config.carregar()
        grupo = grupo.strip()
        if not grupo.isdigit():
            return volta("Grupo deve ser o número (ex.: 3010).", "perigo")
        if not link.strip():
            cfg["planilhas"].pop(grupo, None)
            config.salvar(cfg)
            return volta(f"Planilha do grupo {grupo} removida.")
        sid = config.id_planilha(link)
        if not sid:
            return volta("Não reconheci o link. Copie o endereço inteiro do Google Sheets "
                         "(ou o caminho de um arquivo .xlsx que exista).", "perigo")
        cfg["planilhas"][grupo] = sid
        config.salvar(cfg)
        return volta(f"Planilha do grupo {grupo} guardada. Use “Testar acesso” para conferir.")

    @app.post("/config/testar")
    def config_testar(grupo: str = Form(...)):
        cfg = config.carregar()
        sid = cfg["planilhas"].get(grupo)
        if not sid:
            return volta("Esse grupo não tem planilha.", "perigo")
        try:
            ss = abrir_saida(cfg, sid)
            nome = ss.titulo(sid) if hasattr(ss, "titulo") else sid
            abas = ss.titulos(sid)
        except Exception as e:
            return volta(f"Grupo {grupo}: {e}", "perigo")
        faltam = [a for a in ("REQ", "CATÁLOGO") if a not in abas]
        mats = [a for a in abas if a.startswith("MAT") and "(" not in a]
        if faltam:
            return volta(f"“{nome}” abriu, mas faltam as abas {', '.join(faltam)}.", "aten")
        return volta(f"Acesso OK a “{nome}” (abas {', '.join(mats)}).")

    @app.post("/config/mapa")
    def config_mapa(mapa: str = Form("")):
        cfg = config.carregar()
        novo = {}
        for ln in mapa.splitlines():
            if "=" in ln:
                k, v = (x.strip() for x in ln.split("=", 1))
                if k and v:
                    novo[k] = v
        cfg["mapa"] = novo
        config.salvar(cfg)
        return volta(f"Mapa de unidades guardado ({len(novo)} siglas).")

    @app.post("/config/regras")
    async def config_regras(request: Request):
        f = await request.form()
        cfg = config.carregar()
        cfg["na_mat"] = f.getlist("na_mat") or ["ENVIADA"]
        cfg["fora_req"] = f.getlist("fora_req")
        cfg["ordem"] = "leitura" if f.get("ordem") == "leitura" else "alfabetica"
        config.salvar(cfg)
        return volta("Regras guardadas.")

    @app.post("/config/google")
    async def config_google(forma: str = Form("servico"), chave: UploadFile | None = File(None)):
        cfg = config.carregar()
        cfg["forma_google"] = "oauth" if forma == "oauth" else "servico"
        if chave is not None and chave.filename:
            dados = await chave.read()
            try:
                j = json.loads(dados.decode("utf-8"))
            except ValueError:
                return volta("O arquivo não é um JSON válido.", "perigo")
            config.PASTA.mkdir(parents=True, exist_ok=True)
            if j.get("type") == "service_account":
                config.ARQ_GOOGLE.write_bytes(dados)
                cfg["forma_google"] = "servico"
            elif "installed" in j:
                config.ARQ_OAUTH_CLIENTE.write_bytes(dados)
                cfg["forma_google"] = "oauth"
            else:
                return volta("JSON não reconhecido: use a chave da conta de serviço ou o cliente OAuth (app desktop).",
                             "perigo")
        config.salvar(cfg)
        return volta("Conta Google atualizada.")

    @app.post("/config/conectar")
    def config_conectar():
        def tarefa(saida, parar):
            saida("Abrindo a janela de login do Google no navegador…")
            abrir_saida(config.carregar(), None, True)
            return "Conta Google conectada."
        if not ex.iniciar("Conectar conta Google", tarefa):
            return volta("Já há uma tarefa rodando.", "perigo")
        return volta("Siga a janela do Google que abriu e depois volte aqui.", "aten")

    return app


def rodar(porta: int = config.PORTA) -> None:
    import uvicorn
    uvicorn.run(criar_app(), host="127.0.0.1", port=porta, log_level="warning")
