# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec do JARVIS.

Estratégia: --onedir (modo padrão) — gera pasta `dist/JARVIS/` com o .exe + DLLs.
Vantagens vs onefile:
- Boot ~3x mais rápido (não extrai pra temp toda vez).
- Mais fácil de debugar (você vê os arquivos).
- Anti-vírus geralmente não falsa positivo.

Pra distribuir, zipa a pasta dist/JARVIS/ inteira.
"""
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Caminhos de dados a embedar
import openwakeword
OWW_DIR = os.path.dirname(openwakeword.__file__)
OWW_MODELS = os.path.join(OWW_DIR, "resources", "models")

block_cipher = None

# ── Arquivos de dados ─────────────────────────────────────────────
# (src, dest_relative_to_bundle)
datas = [
    # web/ inteiro (HTML, CSS, JS, ícone, chime WAV)
    ("jarvis/web", "jarvis/web"),

    # Modelos OpenWakeWord (~14MB) - precisam estar onde a lib procura
    (OWW_MODELS, "openwakeword/resources/models"),

    # Briefing NÃO entra aqui — datas iria pra _internal/. Copiado via post-build no fim.
]

# NÃO usar collect_data_files("openwakeword") — puxa training data desnecessário.
# Os modelos .onnx que precisamos já foram explicitamente embutidos acima.

# ── Hidden imports ────────────────────────────────────────────────
hiddenimports = [
    # pycaw + comtypes (audio control)
    "comtypes",
    "comtypes.client",
    "pycaw",
    "pycaw.pycaw",

    # webview backend (EdgeChromium é o default no Win10+)
    "webview",
    "webview.platforms.edgechromium",

    # sounddevice precisa do _portaudio (binário)
    "sounddevice",
    "_sounddevice",

    # openwakeword runtime — apenas o necessário pra inferência
    "openwakeword",
    "openwakeword.model",
    "openwakeword.utils",
    "onnxruntime",

    # groq SDK
    "groq",

    # edge-tts (TTS neural) — usa aiohttp/certifi por baixo
    "edge_tts",
    "aiohttp",
    "certifi",

    # pygetwindow / pyrect (transitivo)
    "pygetwindow",
    "pyrect",

    # psutil
    "psutil",
]

hiddenimports += collect_submodules("comtypes")
hiddenimports += collect_submodules("edge_tts")

# ── Análise ───────────────────────────────────────────────────────
a = Analysis(
    ["jarvis/app.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Coisas que openwakeword importa pra TREINAR modelos, mas que
        # NÃO são usadas em runtime (só inferência ONNX). Cortar isso
        # baixa o build de 770MB pra ~210MB.
        # NOTA: sklearn É usado em runtime pelo openwakeword — não excluir.
        "torch",
        "torchaudio",
        "torchvision",
        "transformers",
        "datasets",
        "cv2",
        "pandas",
        "matplotlib",
        "tensorflow",
        "tflite_runtime",        # usamos só onnxruntime
        "tflite",

        # Standard libs grandes que não usamos.
        # NOTA: unittest e test NÃO podem ser excluídos — numpy.testing puxa.
        "tkinter",
        "PIL.ImageTk",
        "pytest",

        # SDKs concorrentes do groq que vêm como peer-dep mas não usamos
        "anthropic",
        "openai",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="JARVIS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # UPX comprime mais mas anti-vírus odeia. Off por padrão.
    console=False,       # SEM CONSOLE — abre direto a UI. Logs vão pra arquivo.
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="jarvis/web/jarvis.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="JARVIS",
)

# Post-build: copia o briefing pra raiz da pasta dist/JARVIS/ (junto do .exe).
# datas={"...": "."} colocaria em _internal/, e queremos visível pro user.
import shutil
_dist_root = os.path.join("dist", "JARVIS")
if os.path.isdir(_dist_root):
    shutil.copy2("JARVIS_MASTER_BRIEFING.md", _dist_root)
    print(f"[spec] Briefing copiado pra {_dist_root}/")
