"""Ponto de entrada do executável (PyInstaller): pca.exe [ler|prever|gravar|verificar|web]."""
import sys

from pca_assistente.cli import main

if __name__ == "__main__":
    sys.exit(main())
