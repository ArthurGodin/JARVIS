"""
Autostart com Windows via registry HKCU\\...\\Run.

Por que HKCU e não HKLM? HKLM exige admin (UAC) e roda pra todos os users.
HKCU é por-usuário, não exige privilégios e basta pro escopo do JARVIS
(assistente pessoal, configurado por usuário).

Comportamento:
- Em frozen (.exe): aponta pro próprio executável (sys.executable).
- Em dev: aponta pro `python -m jarvis.app` da instalação atual — útil pra
  testar o autostart sem rebuild.
"""
import os
import sys
import winreg

REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_VALUE_NAME = "JARVIS"


def _get_command() -> str:
    """Comando que o Windows executa no logon."""
    if getattr(sys, "frozen", False):
        # PyInstaller: sys.executable é o JARVIS.exe gerado
        return f'"{sys.executable}"'
    # Dev: python.exe -m jarvis.app rodando no diretório do projeto
    project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return f'"{sys.executable}" -m jarvis.app'


def is_enabled() -> bool:
    """Retorna True se o autostart está registrado no registry."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ) as key:
            try:
                winreg.QueryValueEx(key, REG_VALUE_NAME)
                return True
            except FileNotFoundError:
                return False
    except OSError:
        return False


def enable() -> tuple:
    """Registra o JARVIS pra iniciar com o Windows. Retorna (ok, msg)."""
    cmd = _get_command()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, REG_VALUE_NAME, 0, winreg.REG_SZ, cmd)
        return True, "Autostart ativado — JARVIS vai iniciar com o Windows"
    except OSError as e:
        return False, f"Falha ao ativar autostart: {e}"


def disable() -> tuple:
    """Remove o registro de autostart."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, REG_VALUE_NAME)
                return True, "Autostart desativado"
            except FileNotFoundError:
                return True, "Autostart já estava desativado"
    except OSError as e:
        return False, f"Falha ao desativar autostart: {e}"


def get_command_preview() -> str:
    """Pra UI mostrar exatamente o que será registrado."""
    return _get_command()
