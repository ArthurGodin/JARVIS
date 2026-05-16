import os
import json
import shutil
from jarvis.constants import CONFIG_FILE, MODES_FILE, FALLBACK_MODE_ID, SCRIPT_DIR
from jarvis.config.defaults import build_default_config, build_default_modes_config
from jarvis import state

def deep_merge_config(base, override):
    if not isinstance(base, dict):
        return override if override is not None else base

    result = {}
    override = override if isinstance(override, dict) else {}

    for key, base_value in base.items():
        override_value = override.get(key)
        if isinstance(base_value, dict):
            result[key] = deep_merge_config(base_value, override_value)
        elif key in override:
            result[key] = override_value
        else:
            result[key] = base_value

    for key, value in override.items():
        if key not in result:
            result[key] = value

    return result

def _config_string(value, default, allow_empty=False):
    if isinstance(value, str):
        text = value.strip()
        if text or allow_empty:
            return text
    return default

def _config_string_list(value, default):
    if isinstance(value, list):
        items = []
        for item in value:
            text = str(item).strip()
            if text:
                items.append(text)
        if items:
            return items
    return list(default)

def _config_bool(value, default):
    return value if isinstance(value, bool) else default

def _config_number(value, default, cast=float, minimum=None, maximum=None):
    try:
        number = cast(value)
    except (TypeError, ValueError):
        return default
    if minimum is not None and number < minimum:
        return default
    if maximum is not None and number > maximum:
        return default
    return number

def _config_input_device(value, default):
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text:
            return text
    return default

def write_runtime_config_file(config_data, path=CONFIG_FILE):
    with open(path, "w", encoding="utf-8") as config_file:
        json.dump(config_data, config_file, indent=2, ensure_ascii=False)
        config_file.write("\n")

def ensure_runtime_files():
    created = False
    
    # Garantir config.json
    if not os.path.exists(CONFIG_FILE):
        original_config = os.path.join(SCRIPT_DIR, "jarvis.config.json")
        if os.path.exists(original_config):
            shutil.copy2(original_config, CONFIG_FILE)
        else:
            write_runtime_config_file(build_default_config())
        created = True
        state.runtime_config_state["created"] = True

    # Garantir modes.json — primeiro boot gera modos detectando apps instalados
    if not os.path.exists(MODES_FILE):
        original_modes = os.path.join(SCRIPT_DIR, "jarvis.modes.json")
        if os.path.exists(original_modes):
            shutil.copy2(original_modes, MODES_FILE)
        else:
            # Sem fonte? Gera 4-5 modos prontos detectando Spotify/VSCode/Discord/etc
            with open(MODES_FILE, "w", encoding="utf-8") as f:
                json.dump(build_default_modes_config(), f, indent=2, ensure_ascii=False)
                f.write("\n")
        created = True
                
    return created

def load_runtime_config():
    created = ensure_runtime_files()
    default_config = build_default_config()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as config_file:
            user_config = json.load(config_file)
        if not isinstance(user_config, dict):
            raise ValueError("O arquivo precisa conter um objeto JSON na raiz")
    except Exception as e:
        print(f"  ERRO  Falha ao ler configuracao ({e}). Usando padrao.")
        merged_config = default_config
    else:
        merged_config = deep_merge_config(default_config, user_config)

    # Nao precisamos aplicar em variaveis globais individuais como na V2
    # O estado sera acessado via state.runtime_config_state["data"]
    state.runtime_config_state["loaded"] = True
    state.runtime_config_state["created"] = created
    state.runtime_config_state["data"] = merged_config
    state.runtime_config_state["path"] = CONFIG_FILE
    
    # Preencher active_default_mode_id no estado
    modes = merged_config.get("modes", {})
    state.active_default_mode_id = _config_string(modes.get("default_mode"), FALLBACK_MODE_ID)
    
    return merged_config

def apply_runtime_settings():
    """
    Aplica em runtime as configs que módulos lazy-load consomem
    (TTS, wake word). Chamado no boot e a cada save_runtime_config_data().
    """
    cfg = state.runtime_config_state.get("data") or {}

    tts_cfg = cfg.get("tts") or {}
    try:
        from jarvis.output import tts
        tts.set_provider(tts_cfg.get("provider", "edge"))
        tts.set_voice(tts_cfg.get("voice", "pt-BR-AntonioNeural"))
    except Exception as e:
        print(f"[Config] aplicar tts falhou: {e}")

    wake_cfg = cfg.get("wake_word") or {}
    try:
        from jarvis.triggers import wake_word
        wake_word.set_threshold(wake_cfg.get("threshold", 0.35))
    except Exception as e:
        print(f"[Config] aplicar wake_word falhou: {e}")


def save_runtime_config_data(config_data):
    current_config = state.runtime_config_state.get("data") or build_default_config()
    merged_config = deep_merge_config(current_config, config_data if isinstance(config_data, dict) else {})
    write_runtime_config_file(merged_config)
    
    state.runtime_config_state["loaded"] = True
    state.runtime_config_state["created"] = False
    state.runtime_config_state["data"] = merged_config
    
    modes = merged_config.get("modes", {})
    state.active_default_mode_id = _config_string(modes.get("default_mode"), FALLBACK_MODE_ID)
    
    apply_runtime_settings()
    state.config_reloaded_event.set()

    return merged_config
