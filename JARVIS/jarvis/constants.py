import os
import sys

# Quando o JARVIS roda empacotado pelo PyInstaller, recursos read-only ficam
# em sys._MEIPASS (pasta temporária onde o exe extrai os assets). Em dev/source,
# ficam em JARVIS/ (pai de jarvis/). resource_path() abstrai os dois cenários.
IS_FROZEN = getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")

# Pasta dos assets read-only (web/, modelos, ícones).
if IS_FROZEN:
    SCRIPT_DIR = sys._MEIPASS  # type: ignore[attr-defined]
else:
    SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(*parts: str) -> str:
    """Resolve um path relativo aos assets do JARVIS (web/, plugins/...). Frozen-aware."""
    return os.path.join(SCRIPT_DIR, *parts)


# Diretório de dados do user (AppData/Roaming/JARVIS) — config, modos, histórico,
# logs. SEMPRE fora do exe pra persistir entre updates.
USER_DATA_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "JARVIS")
os.makedirs(USER_DATA_DIR, exist_ok=True)
LOG_DIR = os.path.join(USER_DATA_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(USER_DATA_DIR, "jarvis.config.json")
MODES_FILE = os.path.join(USER_DATA_DIR, "jarvis.modes.json")


# Valores de fallback
FALLBACK_MODE_ID = "modo_padrao"

# Constantes de Atalhos (Windows Virtual Keys & Modifiers)
HOTKEY_MODIFIERS = {
    "alt": 0x0001,
    "ctrl": 0x0002,
    "control": 0x0002,
    "shift": 0x0004,
    "win": 0x0008,
    "windows": 0x0008,
}

HOTKEY_SPECIAL_KEYS = {
    "space": 0x20,
    "enter": 0x0D,
    "tab": 0x09,
    "esc": 0x1B,
    "escape": 0x1B,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "insert": 0x2D,
    "delete": 0x2E,
    # F-keys (VK_F1=0x70 ... VK_F12=0x7B)
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
}
