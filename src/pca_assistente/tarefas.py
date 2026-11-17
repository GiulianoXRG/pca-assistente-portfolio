"""Executor das tarefas da tela: uma por vez (sessão JSF única), registro ao vivo e Parar."""
from __future__ import annotations

import re
import threading
from datetime import datetime


class Executor:
    def __init__(self, max_linhas: int = 1000):
        self._lock = threading.Lock()
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None
        self.max_linhas = max_linhas
        self.nome = ""
        self.linhas: list[tuple[int, str]] = []
        self._seq = 0
        self.resultado: str | None = None
        self.erro: str | None = None
        self.prog: tuple[int, int] | None = None
        self.fim: datetime | None = None

    @property
    def rodando(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def saida(self, *partes) -> None:
        txt = " ".join(str(p) for p in partes)
        m = re.match(r"\s*(\d+)/(\d+)\b", txt)
        if m and 0 < int(m[1]) <= int(m[2]):
            self.prog = (int(m[1]), int(m[2]))
        with self._lock:
            self._seq += 1
            self.linhas.append((self._seq, datetime.now().strftime("%H:%M:%S ") + txt))
            del self.linhas[:-self.max_linhas]

    def parar_pedido(self) -> bool:
        return self._parar.is_set()

    def iniciar(self, nome: str, fn, *args, **kw) -> bool:
        """fn(*args, saida=..., parar=..., **kw) → texto do resultado. False se já há tarefa rodando."""
        with self._lock:
            if self.rodando:
                return False
            self.nome, self.resultado, self.erro, self.prog, self.fim = nome, None, None, None, None
            self._parar.clear()

            def corpo():
                self.saida(f"▶ {nome}")
                try:
                    self.resultado = fn(*args, saida=self.saida, parar=self.parar_pedido, **kw)
                    self.saida("✔ " + (self.resultado or "Concluído."))
                except Exception as e:  # nossas mensagens já são para a pessoa
                    self.erro = str(e) or type(e).__name__
                    self.saida("⚠ " + self.erro)
                finally:
                    self.fim = datetime.now()

            self._thread = threading.Thread(target=corpo, name="pca-tarefa", daemon=True)
            self._thread.start()
            return True

    def esperar(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    def pedir_parar(self) -> None:
        if self.rodando:
            self._parar.set()
            self.saida("Parando depois da requisição atual…")

    def estado(self, desde: int = 0) -> dict:
        with self._lock:
            return {"rodando": self.rodando, "nome": self.nome, "erro": self.erro, "resultado": self.resultado,
                    "prog": list(self.prog) if self.prog else None, "parando": self._parar.is_set() and self.rodando,
                    "linhas": [{"n": n, "t": t} for n, t in self.linhas if n > desde],
                    "fim": self.fim.strftime("%H:%M:%S") if self.fim else None}
