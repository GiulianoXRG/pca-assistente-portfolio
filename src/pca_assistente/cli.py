"""Linha de comando: `pca ler GRUPO ANO`, `pca verificar`, `pca prever/gravar GRUPO ANO`, `pca web`."""
from __future__ import annotations

import argparse
import sys


def _ler(grupo: str, ano: int, cfg: dict):
    from . import config
    from .navegador import PedidorPagina, aba_sipac, conectar
    from .sipac import ler_grupo

    with conectar() as browser:
        return ler_grupo(PedidorPagina(aba_sipac(browser)), grupo, ano, config.regras(cfg), pausa=config.PAUSA)


def main(argv: list[str] | None = None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="pca", description="PCA assistente")
    sub = ap.add_subparsers(dest="cmd")
    for nome, ajuda in (("ler", "lê o SIPAC e mostra o resumo"), ("prever", "lê o SIPAC e mostra o que mudaria na planilha"),
                        ("gravar", "lê o SIPAC e grava na planilha do grupo (pede confirmação)")):
        p = sub.add_parser(nome, help=ajuda)
        p.add_argument("grupo")
        p.add_argument("ano", type=int)
        if nome == "gravar":
            p.add_argument("--sim", action="store_true", help="não perguntar")
    pl = sub.add_parser("planilha", help="liga o grupo a uma planilha (link do Google ou caminho .xlsx)")
    pl.add_argument("grupo")
    pl.add_argument("destino")
    sub.add_parser("verificar", help="situação do Chrome, do login e da conta Google")
    w = sub.add_parser("web", help="abre a tela (porta 8010)")
    w.add_argument("--porta", type=int)
    a = ap.parse_args(argv)

    from . import config
    cfg = config.carregar()
    try:
        if a.cmd == "ler":
            from .servico import montar_sem_planilha, resumo
            lt = _ler(a.grupo, a.ano, cfg)
            print("\n".join(resumo(lt, montar_sem_planilha(lt, config.regras(cfg)))))
        elif a.cmd in ("prever", "gravar"):
            from .saida_xlsx import abrir
            from .servico import executar_gravacao, preparar, resumo
            sid = cfg["planilhas"].get(a.grupo)
            saida = abrir(cfg, sid) if sid else None
            lt = _ler(a.grupo, a.ano, cfg)
            pr = preparar(lt, config.regras(cfg), saida, sid)
            print("\n".join(resumo(lt, pr.resultado)))
            if pr.erro_planilha:
                print("✖ " + pr.erro_planilha)
                return 1
            print("\nO que vai mudar:")
            print("\n".join("  " + x for x in pr.plano.resumo + pr.plano.alertas))
            if a.cmd == "gravar":
                if not a.sim and input("Gravar na planilha? (s/N) ").strip().lower() != "s":
                    print("Nada gravado.")
                    return 0
                copias = executar_gravacao(pr, saida)
                print(f"✔ Gravado. Cópia de segurança: {', '.join(copias) or '(já existia deste minuto)'}")
        elif a.cmd == "planilha":
            sid = config.id_planilha(a.destino)
            if not sid:
                print("✖ Não reconheci: use o link do Google Sheets ou o caminho de um .xlsx que exista.")
                return 1
            cfg["planilhas"][a.grupo] = sid
            config.salvar(cfg)
            print(f"Grupo {a.grupo} → {sid}")
        elif a.cmd == "verificar":
            from .navegador import situacao
            s = situacao()
            print(f"Chrome do assistente (porta {config.CDP_PORTA}): {'aberto' if s['chrome'] else 'fechado'}")
            print(f"Aba do SIPAC: {'sim' if s['sipac'] else 'não'}; tela de login aberta: {'sim' if s['login'] else 'não'}")
            from .google_sheets import descrever_conta
            print("Conta Google: " + descrever_conta(cfg))
            for g, sid in cfg["planilhas"].items():
                print(f"  grupo {g}: planilha configurada")
        elif a.cmd == "web":
            from .web.app import rodar
            rodar(a.porta or config.PORTA)
        else:
            ap.print_help()
    except Exception as e:  # mensagem para a pessoa, sem traceback longo
        print(f"✖ {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
