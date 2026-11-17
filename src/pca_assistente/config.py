"""Configuração local (fora do git): %LOCALAPPDATA%\\pca-assistente\\config.json."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .montagem import MAPA_PADRAO, Regras

PASTA = Path(os.getenv("PCA_PASTA") or Path(os.getenv("LOCALAPPDATA", Path.home())) / "pca-assistente")
CDP_PORTA = int(os.getenv("PCA_CDP_PORTA", "9223"))  # sipac-assistente usa 9222
CDP = f"http://127.0.0.1:{CDP_PORTA}"
PORTA = int(os.getenv("PCA_PORTA", "8010"))
SIPAC = "https://sipac.ufrn.br"
PAUSA = 0.7  # segundos entre pedidos ao SIPAC

ARQ_CONFIG = PASTA / "config.json"
ARQ_GOOGLE = PASTA / "google.json"            # chave da conta de serviço
ARQ_OAUTH_CLIENTE = PASTA / "oauth-cliente.json"  # alternativa: cliente OAuth de app desktop
ARQ_TOKEN = PASTA / "token.json"              # token OAuth da conta da usuária


def padrao() -> dict:
    r = Regras()
    return {
        "planilhas": {},          # grupo → spreadsheetId
        "historico": [],          # grupos usados, mais recente primeiro
        "mapa": dict(MAPA_PADRAO),
        "na_mat": list(r.na_mat),
        "fora_req": list(r.fora_req),
        "ordem": r.ordem,
        "forma_google": "servico",  # 'servico' | 'oauth'
    }


def carregar(arq: Path | None = None) -> dict:
    arq = arq or ARQ_CONFIG
    cfg = padrao()
    try:
        cfg.update(json.loads(arq.read_text(encoding="utf-8")))
    except (FileNotFoundError, ValueError):
        pass
    return cfg


def salvar(cfg: dict, arq: Path | None = None) -> None:
    arq = arq or ARQ_CONFIG
    arq.parent.mkdir(parents=True, exist_ok=True)
    tmp = arq.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(arq)


def regras(cfg: dict) -> Regras:
    return Regras(na_mat=tuple(s.upper() for s in cfg["na_mat"]), fora_req=tuple(s.upper() for s in cfg["fora_req"]),
                  ordem=cfg["ordem"], mapa=dict(cfg["mapa"]))


def id_planilha(texto: str) -> str | None:
    """Link ou id colado → spreadsheetId."""
    texto = (texto or "").strip().strip('"')
    if texto.lower().endswith((".xlsx", ".xlsm")):  # teste em arquivo local
        p = Path(texto).expanduser()
        return str(p.resolve()) if p.exists() else None
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]{20,})", texto)
    if m:
        return m.group(1)
    return texto if re.fullmatch(r"[A-Za-z0-9_-]{20,}", texto) else None


def lembrar_grupo(cfg: dict, grupo: str) -> None:
    h = [g for g in cfg["historico"] if g != grupo]
    cfg["historico"] = [grupo, *h][:20]
