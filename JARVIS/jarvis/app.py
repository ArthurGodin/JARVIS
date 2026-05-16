import sys
import json
import os

# Força UTF-8 em stdout/stderr — evita UnicodeEncodeError ao printar emojis/setas
# em terminais cp1252 (Windows). Sem isso, prints com '→' '✔' matam threads
# silenciosamente e modos travam em "Executando..." pra sempre.
try:
    if sys.stdout is not None:
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.stderr is not None:
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# Adiciona o diretorio pai ao sys.path para garantir que imports funcionem
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Redireciona prints pra %APPDATA%/JARVIS/logs/jarvis.log (essencial no .exe
# sem console; em dev, tee mantém o console também).
from jarvis.runtime.logging_setup import setup_file_logging
setup_file_logging()

from jarvis import state
from jarvis.constants import MODES_FILE
from jarvis.config.loader import load_runtime_config, apply_runtime_settings
from jarvis.runtime.process_control import enforce_single_instance, check_cli_args
from jarvis.runtime.ipc import start_ipc_server
from jarvis.runtime import history
from jarvis.runtime.scheduler import start_scheduler
from jarvis.triggers.hotkey import start_hotkey_listener
from jarvis.ui.tray import start_tray
from jarvis.ui.panel import open_panel, force_destroy_panel
from jarvis.recipes.executor import execute_mode
from jarvis.recipes.validator import validate_modes
from jarvis.actions.registry import init_actions, init_plugins, get_action_specs


def load_modes():
    try:
        with open(MODES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            state.runtime_modes_state["data"] = data
            state.runtime_modes_state["mode_index"] = {m["id"]: m for m in data.get("modes", [])}
            state.runtime_modes_state["loaded"] = True

            # Validação não bloqueante: avisa no log/console mas mantém o modo na lista.
            errors_by_mode = validate_modes(data.get("modes", []), get_action_specs())
            for mode_id, errors in errors_by_mode.items():
                for err in errors:
                    msg = f"Modo '{mode_id}' inválido: {err}"
                    state.add_log("warn", msg)
                    print(f"[!] {msg}")
    except Exception as e:
        print(f"Erro ao carregar modos: {e}")


def run_default_mode(source="desconhecido"):
    active_id = state.active_default_mode_id
    modes_index = state.runtime_modes_state.get("mode_index", {})

    if active_id in modes_index:
        execute_mode(modes_index[active_id], source)
    else:
        print(f"Modo padrao {active_id} nao encontrado nas configuracoes.")


def run_mode_by_id(mode_id, source="hotkey-modo"):
    modes_index = state.runtime_modes_state.get("mode_index", {})
    mode = modes_index.get(mode_id)
    if mode:
        execute_mode(mode, source)
    else:
        print(f"Modo {mode_id} nao encontrado.")


def on_trigger_activate(source="hotkey"):
    run_default_mode(source)


def on_stop():
    print("\n[!] Encerrando JARVIS...")
    state.shutdown_event.set()
    force_destroy_panel()


def on_voice_hotkey():
    from jarvis.triggers.voice_ai import toggle_recording
    toggle_recording()


# ─── IPC handlers ─────────────────────────────────────────────────
def _ipc_stop_handler(msg):
    state.shutdown_event.set()
    force_destroy_panel()
    return {"ok": True}


def _ipc_status_handler(msg):
    session = state.runtime_session_state
    return {
        "ok": True,
        "data": {
            "running": True,
            "active_mode_id": session.get("active_mode_id"),
            "active_mode_name": session.get("active_mode_name"),
            "default_mode_id": state.active_default_mode_id,
            "last_status": session.get("last_status", "Aguardando"),
            "last_started_at": session.get("last_started_at", ""),
        },
    }


def main():
    # CLI primeiro: --stop/--status falam com a instância ativa via IPC e saem.
    if check_cli_args():
        sys.exit(0)

    if not enforce_single_instance():
        sys.exit(0)

    print("Iniciando JARVIS V3 (Modular)...")
    init_actions()              # core actions (não dependem de config)
    load_runtime_config()
    apply_runtime_settings()    # propaga voz/wake threshold pros módulos
    init_plugins()              # plugins respeitam runtime.plugins_allowlist
    load_modes()
    history.init_db()  # cria DB se não existe; gravação só ocorre se history_enabled=True

    start_ipc_server({
        "stop": _ipc_stop_handler,
        "status": _ipc_status_handler,
    })

    start_hotkey_listener(on_trigger_activate, on_stop, on_voice_hotkey, run_mode_by_id)

    from jarvis.triggers.wake_word import start_wake_word_listener
    start_wake_word_listener()

    start_tray(on_trigger_activate, on_stop)

    # Scheduler de modos com campo `schedule` preenchido. Modos sem schedule não disparam.
    start_scheduler(lambda mode: execute_mode(mode, "schedule"))

    print(f"JARVIS pronto. Modo padrao atual: {state.active_default_mode_id}")
    print("Abrindo painel de controle...")

    # Abre o painel — pywebview.start() precisa rodar na thread principal.
    # O X só esconde; só sai daqui quando a tray "Sair" chamar force_destroy_panel().
    try:
        open_panel()
    except KeyboardInterrupt:
        pass
    finally:
        state.shutdown_event.set()

    print("JARVIS encerrado.")


if __name__ == "__main__":
    main()
