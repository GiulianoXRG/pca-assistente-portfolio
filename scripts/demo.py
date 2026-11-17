"""Tela com SIPAC simulado e planilha em memória (dados fictícios), para ver a interface sem SIPAC nem Google.

uv run python scripts/demo.py  →  http://127.0.0.1:8011/
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ["PCA_PASTA"] = tempfile.mkdtemp(prefix="pca-demo-")
RAIZ = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(RAIZ / "src"), str(RAIZ / "tests")]

import uvicorn  # noqa: E402
from dados import cenario_3010  # noqa: E402
from modelo import planilha  # noqa: E402
from sipac_simulado import SipacSimulado  # noqa: E402

from pca_assistente import config  # noqa: E402
from pca_assistente.saida import SaidaMemoria  # noqa: E402
from pca_assistente.sipac import ler_grupo  # noqa: E402
from pca_assistente.web.app import criar_app  # noqa: E402

SID = "DEMO_planilha_ficticia_0000000000"


class Memoria(SaidaMemoria):
    def titulo(self, sid):
        return "PCA 3010 – DEMONSTRAÇÃO"


mem = Memoria({SID: planilha()})
cfg = config.carregar()
cfg["planilhas"]["3010"] = SID
config.salvar(cfg)

app = criar_app(
    ler=lambda g, a, r, saida, parar: ler_grupo(SipacSimulado(cenario_3010()), g, a, r, saida, parar, pausa=0.3),
    abrir_saida=lambda cfg, interativo=False: mem,
    situacao=lambda: {"chrome": True, "sipac": True, "login": False},
)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORTA", "8011")), log_level="warning")
