import os
import time
import datetime
from jarvis import state
from jarvis.recipes.resolver import resolve_action_config
from jarvis.actions.registry import get_action
from jarvis.runtime import history


def _action_label(action: dict) -> str:
    """Gera um rótulo legível pra logs/UI quando description estiver vazia."""
    type_id = (action.get("type") or "").strip()
    if type_id == "open_app":
        target = action.get("target") or ""
        nice = os.path.basename(target) if target else ""
        return f"Abrir {nice}" if nice else "Abrir aplicativo"
    if type_id == "close_app":
        target = action.get("target") or ""
        nice = os.path.basename(target) if target else ""
        return f"Fechar {nice}" if nice else "Fechar aplicativo"
    if type_id == "open_url":
        url = (action.get("url") or "").strip()
        if not url:
            return "Abrir link"
        return f"Abrir {url[:60]}"
    if type_id == "open_folder":
        path = action.get("path") or ""
        nice = os.path.basename(path.rstrip("/\\")) or path
        return f"Abrir pasta {nice}" if nice else "Abrir pasta"
    if type_id == "run_command":
        cmd = (action.get("command") or "").strip()
        return f"Comando: {cmd[:60]}" if cmd else "Rodar comando"
    if type_id == "open_terminal":
        wd = action.get("working_dir") or ""
        nice = os.path.basename(wd.rstrip("/\\")) or wd
        return f"Terminal em {nice}" if nice else "Abrir terminal"
    if type_id == "wait":
        sec = action.get("seconds")
        return f"Aguardar {sec}s" if sec is not None else "Aguardar"
    if type_id == "set_volume":
        level = action.get("level")
        return f"Volume → {level}" if level not in (None, "") else "Ajustar volume"
    if type_id == "arrange_window":
        title = (action.get("title") or "").strip()
        region = (action.get("region") or "").strip()
        if title and region:
            return f"Posicionar '{title[:30]}' → {region}"
        return "Posicionar janela"
    return type_id or "ação"


def _normalize_result(result):
    """Aceita bool ou (bool, str). Retorna sempre (bool, str)."""
    if isinstance(result, tuple) and len(result) >= 2:
        return bool(result[0]), str(result[1] or "")
    if isinstance(result, bool):
        return result, ""
    # Qualquer outro retorno = sucesso silencioso (compat com código antigo)
    return True, ""


def execute_mode(mode: dict, source: str = "unknown"):
    """Executa as ações de um modo, com cooldown, logs claros e contagem de erros."""
    global_config = state.runtime_config_state.get("data", {})
    cooldown = global_config.get("runtime", {}).get("cooldown_seconds", 15)

    with state.state_lock:
        now = time.time()
        if now - state.last_triggered < cooldown:
            remaining = max(1, int(cooldown - (now - state.last_triggered)))
            msg = f"Em cooldown — aguarde {remaining}s para ativar de novo."
            state.add_log("error", msg)
            print(f"[Executor] {msg}")
            return False

        state.last_triggered = now
        started_ts = now
        started_dt = datetime.datetime.now()

        mode_id = mode.get("id", "unknown")
        mode_name = mode.get("name", mode_id)
        print(f"[Executor] >> Iniciando '{mode_name}' (id={mode_id}, source={source}, actions={len(mode.get('actions', []) or [])})")

        state.runtime_session_state["last_mode_id"] = state.runtime_session_state.get("active_mode_id")
        state.runtime_session_state["last_mode_name"] = state.runtime_session_state.get("active_mode_name")
        state.runtime_session_state["active_mode_id"] = mode_id
        state.runtime_session_state["active_mode_name"] = mode_name
        state.runtime_session_state["last_trigger_source"] = source
        state.runtime_session_state["last_started_at"] = datetime.datetime.now().isoformat()
        state.runtime_session_state["last_status"] = f"Executando {mode_name}"

        state.add_log("info", f"▶ Iniciando: {mode_name} (via {source})")
        print(f"\n>> ATIVANDO MODO: {mode_name} (via {source})")

    actions = mode.get("actions", []) or []
    success_count = 0
    error_count = 0

    for action_def in actions:
        if state.shutdown_event.is_set():
            break

        action_type = action_def.get("type")
        # Description: prioriza o campo do user; cai num label automático bonitinho
        description = (action_def.get("description") or "").strip() or _action_label(action_def)

        action_impl = get_action(action_type)
        if not action_impl:
            error_count += 1
            msg = f"Ação desconhecida: '{action_type}'"
            state.add_log("error", f"✖ {description}: {msg}")
            print(f"  [Executor] [!] {msg}")
            continue

        resolved_config = resolve_action_config(action_def, global_config)
        print(f"  [Executor] >> executando {action_type}: {resolved_config}")

        try:
            raw = action_impl.execute(resolved_config, global_config)
            print(f"  [Executor] << retornou: {raw!r}")
            ok, detail = _normalize_result(raw)
            if ok:
                success_count += 1
                state.add_log("success", f"✔ {description}" + (f" — {detail}" if detail else ""))
            else:
                error_count += 1
                state.add_log("error", f"✖ {description}" + (f" — {detail}" if detail else ""))
                with state.state_lock:
                    state.runtime_session_state["last_error"] = detail or description
                    state.runtime_session_state["last_error_time"] = datetime.datetime.now().isoformat()
        except Exception as e:
            error_count += 1
            err_msg = f"Exceção em {action_type}: {e}"
            state.add_log("error", f"✖ {description} — {err_msg}")
            print(f"  [!] {err_msg}")
            with state.state_lock:
                state.runtime_session_state["last_error"] = err_msg
                state.runtime_session_state["last_error_time"] = datetime.datetime.now().isoformat()

    duration_ms = int((time.time() - started_ts) * 1000)
    finished_at = datetime.datetime.now()

    with state.state_lock:
        state.runtime_session_state["last_finished_at"] = finished_at.isoformat()
        if error_count == 0:
            state.runtime_session_state["last_status"] = f"{mode_name} concluído"
            state.add_log("success", f"■ {mode_name} concluído ({success_count} ações).")
        else:
            state.runtime_session_state["last_status"] = (
                f"{mode_name}: {success_count} ok / {error_count} erro(s)"
            )
            state.add_log(
                "warn",
                f"■ {mode_name} terminou com {error_count} erro(s) e {success_count} sucesso(s).",
            )
        print(f"<< MODO {mode_name} CONCLUIDO ({success_count} ok / {error_count} err)\n")

        # Populate recent_events ring (UI lê via get_status). Mantém os 20 mais novos.
        events = state.runtime_session_state.setdefault("recent_events", [])
        events.insert(0, {
            "time": started_dt.strftime("%H:%M:%S"),
            "mode_id": mode_id,
            "mode_name": mode_name,
            "source": source,
            "success": success_count,
            "errors": error_count,
            "duration_ms": duration_ms,
        })
        del events[20:]

    # Histórico opt-in (history_enabled em runtime config; default True)
    history.record_execution(
        mode_id=mode_id,
        mode_name=mode_name,
        source=source,
        started_at=started_dt,
        duration_ms=duration_ms,
        success=success_count,
        errors=error_count,
    )

    return error_count == 0
