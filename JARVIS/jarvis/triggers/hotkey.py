import threading
import ctypes
from ctypes import wintypes
from jarvis import state
from jarvis.constants import HOTKEY_MODIFIERS, HOTKEY_SPECIAL_KEYS

user32 = ctypes.windll.user32

WM_HOTKEY = 0x0312
HOTKEY_TRIGGER_ID = 1
HOTKEY_STOP_ID = 2
HOTKEY_VOICE_ID = 3
HOTKEY_MODE_BASE_ID = 100

# id win32 -> mode_id (registrado dinamicamente)
_mode_hotkey_map = {}


def parse_hotkey(hotkey_str):
    modifiers = 0
    vk = 0
    parts = [p.strip().lower() for p in hotkey_str.split('+')]

    for part in parts:
        if part in HOTKEY_MODIFIERS:
            modifiers |= HOTKEY_MODIFIERS[part]
        elif part in HOTKEY_SPECIAL_KEYS:
            vk = HOTKEY_SPECIAL_KEYS[part]
        elif len(part) == 1:
            vk = ord(part.upper())

    return modifiers, vk


def _hotkey_str(value, default):
    """Aceita config como dict {combination: ..., enabled: ...} ou string crua."""
    if isinstance(value, dict):
        if value.get("enabled") is False:
            return None
        return value.get("combination", default)
    if isinstance(value, str):
        return value
    return default


def _register_global_hotkeys():
    global_config = state.runtime_config_state.get("data") or {}
    hotkeys_config = global_config.get("hotkeys", {})

    activate = _hotkey_str(hotkeys_config.get("activate"), "ctrl+alt+j")
    stop = _hotkey_str(hotkeys_config.get("stop"), "ctrl+alt+shift+j")
    voice = _hotkey_str(hotkeys_config.get("voice"), "ctrl+alt+v")

    for combo, hk_id in ((activate, HOTKEY_TRIGGER_ID), (stop, HOTKEY_STOP_ID), (voice, HOTKEY_VOICE_ID)):
        if not combo:
            continue
        mod, vk = parse_hotkey(combo.replace("<", "").replace(">", ""))
        if vk:
            user32.RegisterHotKey(None, hk_id, mod, vk)


def _register_mode_hotkeys():
    """Registra hotkeys individuais definidas em cada modo (mode['hotkey'])."""
    _mode_hotkey_map.clear()
    modes = (state.runtime_modes_state.get("data") or {}).get("modes", [])
    next_id = HOTKEY_MODE_BASE_ID
    for mode in modes:
        combo = (mode.get("hotkey") or "").strip() if isinstance(mode, dict) else ""
        if not combo:
            continue
        mod, vk = parse_hotkey(combo.replace("<", "").replace(">", ""))
        if not vk:
            continue
        if user32.RegisterHotKey(None, next_id, mod, vk):
            _mode_hotkey_map[next_id] = mode["id"]
            next_id += 1
        else:
            err = ctypes.windll.kernel32.GetLastError()
            print(f"[Hotkey] Falha ao registrar '{combo}' para modo '{mode.get('id')}' (err {err})")


def _register_all():
    _register_global_hotkeys()
    _register_mode_hotkeys()


def _unregister_all():
    user32.UnregisterHotKey(None, HOTKEY_TRIGGER_ID)
    user32.UnregisterHotKey(None, HOTKEY_STOP_ID)
    user32.UnregisterHotKey(None, HOTKEY_VOICE_ID)
    for hk_id in list(_mode_hotkey_map.keys()):
        user32.UnregisterHotKey(None, hk_id)
    _mode_hotkey_map.clear()


def _hotkey_loop(on_activate, on_stop, on_voice, on_mode_id):
    _register_all()

    msg = wintypes.MSG()
    while not state.shutdown_event.is_set():
        if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):  # PM_REMOVE = 1
            if msg.message == WM_HOTKEY:
                hotkey_id = msg.wParam
                if hotkey_id == HOTKEY_TRIGGER_ID:
                    threading.Thread(target=on_activate, daemon=True).start()
                elif hotkey_id == HOTKEY_STOP_ID:
                    threading.Thread(target=on_stop, daemon=True).start()
                elif hotkey_id == HOTKEY_VOICE_ID:
                    threading.Thread(target=on_voice, daemon=True).start()
                elif hotkey_id in _mode_hotkey_map and on_mode_id:
                    mode_id = _mode_hotkey_map[hotkey_id]
                    threading.Thread(target=on_mode_id, args=(mode_id,), daemon=True).start()

            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        else:
            state.shutdown_event.wait(0.1)

            if state.config_reloaded_event.is_set():
                _unregister_all()
                _register_all()
                state.config_reloaded_event.clear()

    _unregister_all()


def start_hotkey_listener(on_activate, on_stop, on_voice, on_mode_id=None):
    t = threading.Thread(
        target=_hotkey_loop,
        args=(on_activate, on_stop, on_voice, on_mode_id),
        daemon=True,
    )
    t.start()
    return t
