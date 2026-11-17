"""Saída real no Google Sheets (google-api-python-client): conta de serviço (padrão) ou OAuth de app desktop.

Credenciais só em %LOCALAPPDATA%\\pca-assistente (google.json / oauth-cliente.json / token.json).
"""
from __future__ import annotations

import json

from . import config
from .planilha import Plano

ESCOPOS = ["https://www.googleapis.com/auth/spreadsheets"]


class ErroGoogle(RuntimeError):
    pass


# ---------- credenciais ----------

def email_servico() -> str | None:
    try:
        return json.loads(config.ARQ_GOOGLE.read_text(encoding="utf-8")).get("client_email")
    except (FileNotFoundError, ValueError):
        return None


def descrever_conta(cfg: dict) -> str:
    if cfg.get("forma_google") == "oauth":
        if config.ARQ_TOKEN.exists():
            return "conta Google pessoal (OAuth) conectada"
        if config.ARQ_OAUTH_CLIENTE.exists():
            return "OAuth: falta entrar com a conta Google (Configurações → Conectar)"
        return f"OAuth: falta o arquivo {config.ARQ_OAUTH_CLIENTE.name} na pasta de configuração"
    e = email_servico()
    if e:
        return f"conta de serviço {e} (compartilhe cada planilha com ela como Editor)"
    return f"falta a chave da conta de serviço ({config.ARQ_GOOGLE})"


def credenciais(cfg: dict, interativo: bool = False):
    if cfg.get("forma_google") == "oauth":
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        cred = None
        if config.ARQ_TOKEN.exists():
            cred = Credentials.from_authorized_user_file(str(config.ARQ_TOKEN), ESCOPOS)
        if cred and cred.expired and cred.refresh_token:
            cred.refresh(Request())
        if not cred or not cred.valid:
            if not interativo:
                raise ErroGoogle("Conecte a conta Google em Configurações.")
            if not config.ARQ_OAUTH_CLIENTE.exists():
                raise ErroGoogle(f"Falta {config.ARQ_OAUTH_CLIENTE.name} na pasta de configuração.")
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(str(config.ARQ_OAUTH_CLIENTE), ESCOPOS)
            cred = flow.run_local_server(port=0, open_browser=True)
        config.ARQ_TOKEN.parent.mkdir(parents=True, exist_ok=True)
        config.ARQ_TOKEN.write_text(cred.to_json(), encoding="utf-8")
        return cred
    from google.oauth2 import service_account
    if not config.ARQ_GOOGLE.exists():
        raise ErroGoogle(f"Falta a chave da conta de serviço em {config.ARQ_GOOGLE}.")
    return service_account.Credentials.from_service_account_file(str(config.ARQ_GOOGLE), scopes=ESCOPOS)


def abrir_saida(cfg: dict, interativo: bool = False) -> "SaidaGoogle":
    from googleapiclient.discovery import build
    return SaidaGoogle(build("sheets", "v4", credentials=credenciais(cfg, interativo), cache_discovery=False))


def _explicar(e: Exception) -> ErroGoogle:
    from googleapiclient.errors import HttpError
    if isinstance(e, HttpError):
        st = e.resp.status
        if st == 403:
            quem = email_servico()
            return ErroGoogle("Sem permissão na planilha." + (f" Compartilhe com {quem} como Editor." if quem else ""))
        if st == 404:
            return ErroGoogle("Planilha não encontrada: confira o link colado.")
        return ErroGoogle(f"Google Sheets respondeu {st}.")
    return ErroGoogle(str(e))


# ---------- saída ----------

class SaidaGoogle:
    def __init__(self, service):
        self.s = service.spreadsheets()

    def _meta(self, sid: str) -> dict[str, dict]:
        try:
            r = self.s.get(spreadsheetId=sid, fields="properties.title,sheets.properties").execute()
        except Exception as e:
            raise _explicar(e) from e
        self.ultimo_titulo = r.get("properties", {}).get("title", "")
        return {sh["properties"]["title"]: sh["properties"] for sh in r.get("sheets", [])}

    def titulo(self, sid: str) -> str:
        self._meta(sid)
        return self.ultimo_titulo

    def titulos(self, sid):
        return list(self._meta(sid))

    def ler(self, sid, abas):
        try:
            r = self.s.values().batchGet(spreadsheetId=sid, ranges=["'" + a.replace("'", "''") + "'" for a in abas],
                                         valueRenderOption="FORMULA", dateTimeRenderOption="SERIAL_NUMBER",
                                         majorDimension="ROWS").execute()
        except Exception as e:
            raise _explicar(e) from e
        return {a: vr.get("values", []) for a, vr in zip(abas, r.get("valueRanges", []))}

    def _lote(self, sid, reqs):
        if not reqs:
            return
        try:
            self.s.batchUpdate(spreadsheetId=sid, body={"requests": reqs}).execute()
        except Exception as e:
            raise _explicar(e) from e

    def duplicar(self, sid, aba, novo):
        meta = self._meta(sid)
        p = meta[aba]
        self._lote(sid, [{"duplicateSheet": {"sourceSheetId": p["sheetId"], "insertSheetIndex": len(meta),
                                             "newSheetName": novo}}])
        nova = self._meta(sid)[novo]
        self._lote(sid, [{"updateSheetProperties": {"properties": {"sheetId": nova["sheetId"], "hidden": True},
                                                    "fields": "hidden"}}])

    def apagar_aba(self, sid, titulo):
        self._lote(sid, [{"deleteSheet": {"sheetId": self._meta(sid)[titulo]["sheetId"]}}])

    def aplicar(self, sid, plano: Plano):
        meta = self._meta(sid)
        reqs = requisicoes_estrutura(plano, meta)
        self._lote(sid, reqs)
        dados = [{"range": a1, "values": vals} for lista in plano.valores.values() for a1, vals in lista]
        if dados:
            try:
                self.s.values().batchUpdate(spreadsheetId=sid, body={"valueInputOption": "RAW", "data": dados}).execute()
            except Exception as e:
                raise _explicar(e) from e


def requisicoes_estrutura(plano: Plano, meta: dict[str, dict]) -> list[dict]:
    """Inserir linhas, garantir tamanho, copiar fórmulas e formato de data (função pura, testável)."""
    reqs = []
    linhas = {t: p["gridProperties"]["rowCount"] for t, p in meta.items()}
    for aba, (depois, n) in plano.inserir.items():
        reqs.append({"insertDimension": {"range": {"sheetId": meta[aba]["sheetId"], "dimension": "ROWS",
                                                   "startIndex": depois + 1, "endIndex": depois + 1 + n},
                                         "inheritFromBefore": True}})
        linhas[aba] += n
    for aba, n in plano.garantir.items():
        if linhas[aba] < n:
            reqs.append({"appendDimension": {"sheetId": meta[aba]["sheetId"], "dimension": "ROWS",
                                             "length": n - linhas[aba]}})
    for aba, origem, de, ate, c0, c1 in plano.copiar_formulas:
        sh = meta[aba]["sheetId"]
        reqs.append({"copyPaste": {
            "source": {"sheetId": sh, "startRowIndex": origem, "endRowIndex": origem + 1,
                       "startColumnIndex": c0, "endColumnIndex": c1 + 1},
            "destination": {"sheetId": sh, "startRowIndex": de, "endRowIndex": ate + 1,
                            "startColumnIndex": c0, "endColumnIndex": c1 + 1},
            "pasteType": "PASTE_FORMULA"}})
    for aba, (col, de, ate) in plano.datas.items():
        reqs.append({"repeatCell": {
            "range": {"sheetId": meta[aba]["sheetId"], "startRowIndex": de, "endRowIndex": ate + 1,
                      "startColumnIndex": col, "endColumnIndex": col + 1},
            "cell": {"userEnteredFormat": {"numberFormat": {"type": "DATE", "pattern": "dd/mm/yyyy"}}},
            "fields": "userEnteredFormat.numberFormat"}})
    return reqs

