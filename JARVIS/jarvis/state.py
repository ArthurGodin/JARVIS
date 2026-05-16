import threading

# Controle Global de Execucao
shutdown_event = threading.Event()
config_reloaded_event = threading.Event()
lock = threading.Lock()
# RLock (re-entrante): permite que a mesma thread reaquira o lock — necessário
# pois execute_mode segura state_lock e chama add_log() (que também o adquire).
# Com Lock simples isso virava deadlock e a execução do modo travava silenciosa.
state_lock = threading.RLock()

# Ultima vez que o JARVIS foi ativado (para gerenciar Cooldown)
last_triggered = 0

# Estado da Bandeja (System Tray)
tray_state = {
    "hwnd": None, 
    "thread_id": None, 
    "run_mode_commands": {}, 
    "default_mode_commands": {}
}
tray_wndproc = None

# Estado de Configuracoes
runtime_config_state = {
    "path": None, 
    "loaded": False, 
    "created": False, 
    "data": None
}

# Estado dos Modos Ativos
runtime_modes_state = {
    "path": None,
    "loaded": False,
    "created": False,
    "data": None,
    "mode_index": {},
    "voice_triggers": [],
    "hotkey_index": {},
}

# Informacoes do Motor em Execucao
runtime_session_state = {
    "active_mode_id": None,
    "active_mode_name": None,
    "last_mode_id": None,
    "last_mode_name": None,
    "last_trigger_source": "",
    "last_started_at": "",
    "last_finished_at": "",
    "last_status": "Aguardando",
    "recent_events": [],
}

active_default_mode_id = "modo_padrao"

# Log de execucao em tempo real (max 100 entradas)
execution_log = []
EXECUTION_LOG_MAX = 100

def add_log(level: str, message: str):
    """Adiciona uma entrada ao log global em tempo real."""
    import datetime
    entry = {
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "level": level,  # info | success | error | warn
        "msg": message
    }
    with state_lock:
        execution_log.append(entry)
        if len(execution_log) > EXECUTION_LOG_MAX:
            execution_log.pop(0)
