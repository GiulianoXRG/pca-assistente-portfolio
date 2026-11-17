# PyInstaller (onedir): uv run --with pyinstaller pyinstaller pca.spec --noconfirm
# Playwright entra só com o driver (conecta por CDP no Chrome instalado; não baixa browsers).
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = [
    ("src/pca_assistente/web/templates", "pca_assistente/web/templates"),
    ("src/pca_assistente/web/static", "pca_assistente/web/static"),
]
datas += collect_data_files("googleapiclient")  # documentos de discovery do Sheets

a = Analysis(
    ["scripts/pca_entrada.py"],
    pathex=["src"],
    datas=datas,
    hiddenimports=collect_submodules("uvicorn") + collect_submodules("pca_assistente"),
    excludes=["tkinter", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="pca", console=True, icon=None)
coll = COLLECT(exe, a.binaries, a.datas, name="pca-assistente")
