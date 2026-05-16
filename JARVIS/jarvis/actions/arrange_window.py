"""
Posiciona uma janela em uma região da tela.

Uso típico: depois de `open_app: code.exe`, uma `arrange_window: title="Visual Studio Code", region="left"`
joga o VSCode na metade esquerda. Você combina pra montar layouts (Modo Trabalho =
VSCode esquerda + Browser direita).

A action faz poll de até 5s pra encontrar a janela (apps demoram pra abrir).
Match no título é por SUBSTRING case-insensitive — então "code", "Visual Studio Code",
"projeto.py - vs code" todos casam.

Regiões aceitas: left, right, top, bottom, top-left, top-right, bottom-left,
bottom-right, center, fullscreen, maximize.
"""
import time
import ctypes

import pygetwindow as gw

from jarvis.actions.base import BaseAction

POLL_S = 0.25
MAX_WAIT_S = 5.0

# Tira tamanho da tela primária via Win32 (não tem isso direto no pygetwindow)
_user32 = ctypes.windll.user32
_user32.SetProcessDPIAware()  # evita escala errada em monitores high-DPI


def _screen_size():
    return _user32.GetSystemMetrics(0), _user32.GetSystemMetrics(1)


def _region_to_rect(region: str):
    """Converte nome de região em (x, y, w, h) ou None se for 'maximize'/inválido."""
    sw, sh = _screen_size()
    half_w = sw // 2
    half_h = sh // 2

    region = region.strip().lower()
    rects = {
        "left":         (0, 0, half_w, sh),
        "right":        (half_w, 0, half_w, sh),
        "top":          (0, 0, sw, half_h),
        "bottom":       (0, half_h, sw, half_h),
        "top-left":     (0, 0, half_w, half_h),
        "top-right":    (half_w, 0, half_w, half_h),
        "bottom-left":  (0, half_h, half_w, half_h),
        "bottom-right": (half_w, half_h, half_w, half_h),
        "center":       (sw // 4, sh // 4, half_w, half_h),
        "fullscreen":   (0, 0, sw, sh),
    }
    return rects.get(region)


def _find_window(title_substr: str):
    """Acha a primeira janela cujo título contém title_substr (case-insensitive)."""
    target = title_substr.strip().lower()
    if not target:
        return None
    for w in gw.getAllWindows():
        try:
            if not w.title:
                continue
            if target in w.title.lower():
                return w
        except Exception:
            continue
    return None


class ArrangeWindowAction(BaseAction):
    def execute(self, action_config: dict, global_config: dict):
        title = (action_config.get("title") or "").strip()
        region = (action_config.get("region") or "").strip().lower()

        if not title:
            return False, "Título da janela não preenchido"
        if not region:
            return False, "Região não preenchida (ex: left, right, top-left, maximize)"

        # Poll até achar a janela
        deadline = time.time() + MAX_WAIT_S
        win = None
        while time.time() < deadline:
            win = _find_window(title)
            if win:
                break
            time.sleep(POLL_S)

        if not win:
            return False, f"Janela com título contendo '{title}' não encontrada após {MAX_WAIT_S}s"

        try:
            # Restaura se estiver minimizada/maximizada antes de mover
            if win.isMinimized:
                win.restore()
            if region == "maximize":
                win.maximize()
                return True, f"'{win.title[:40]}' maximizada"

            rect = _region_to_rect(region)
            if rect is None:
                return False, f"Região '{region}' inválida"

            x, y, w, h = rect
            if win.isMaximized:
                win.restore()
            win.moveTo(x, y)
            win.resizeTo(w, h)
            try:
                win.activate()
            except Exception:
                pass  # activate falha em algumas condições; não é crítico
            return True, f"'{win.title[:40]}' → {region}"
        except Exception as e:
            return False, f"Falha ao reposicionar: {e}"
