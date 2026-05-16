"""
Bridge API: expõe funções Python para o JavaScript da interface chamar.
"""
import json
import uuid
import threading
from jarvis import state
from jarvis.constants import MODES_FILE
from jarvis.recipes.executor import execute_mode
from jarvis.recipes.validator import validate_mode
from jarvis.config.loader import save_runtime_config_data
from jarvis.triggers import voice_ai
from jarvis.actions.registry import get_all_ui_definitions, get_action_specs


def _persist_modes(modes_list):
    """Salva a lista de modos no arquivo JSON do usuário."""
    data = {"modes": modes_list}
    with open(MODES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    # Atualiza estado em memória
    state.runtime_modes_state["data"] = data
    state.runtime_modes_state["mode_index"] = {m["id"]: m for m in modes_list}


class JarvisAPI:
    # ─── Status / Dados ─────────────────────────────────────────
    def get_status(self):
        """Retorna o estado atual da sessão em JSON."""
        import datetime
        session = state.runtime_session_state
        return json.dumps({
            "active_mode_id":       session.get("active_mode_id"),
            "active_mode_name":     session.get("active_mode_name"),
            "last_status":          session.get("last_status", "Aguardando"),
            "last_trigger_source":  session.get("last_trigger_source", ""),
            "last_started_at":      session.get("last_started_at", ""),
            "last_finished_at":     session.get("last_finished_at", ""),
            "recent_events":        session.get("recent_events", []),
            "last_error":           session.get("last_error", ""),
            "last_error_time":      session.get("last_error_time", ""),
            "default_mode_id":      state.active_default_mode_id,
            "current_time":         datetime.datetime.now().strftime("%H:%M"),
        })

    def get_modes(self):
        """Retorna a lista de modos disponíveis em JSON."""
        modes_data = state.runtime_modes_state.get("data") or {}
        return json.dumps(modes_data.get("modes", []))

    def get_logs(self):
        """Retorna o log de execucao em tempo real."""
        with state.state_lock:
            return json.dumps(list(state.execution_log))

    def clear_logs(self):
        """Limpa o log de execucao."""
        with state.state_lock:
            state.execution_log.clear()
        return "ok"

    def get_config(self):
        """Retorna a configuração atual em JSON (inclui voice_ai p/ a UI saber se a key foi setada)."""
        config = state.runtime_config_state.get("data") or {}
        return json.dumps({
            "voice":     config.get("voice", {}),
            "voice_ai":  config.get("voice_ai", {}),
            "tts":       config.get("tts", {}),
            "wake_word": config.get("wake_word", {}),
            "hotkeys":   config.get("hotkeys", {}),
            "modes":     config.get("modes", {}),
            "runtime":   config.get("runtime", {}),
        })

    # ─── Voz (TTS / Wake Word) ──────────────────────────────────
    def list_tts_voices(self):
        """Lista vozes Edge TTS pt-BR disponíveis."""
        try:
            from jarvis.output import tts
            return json.dumps({"ok": True, "voices": tts.list_voices("pt-BR")})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e), "voices": []})

    def preview_tts(self, voice: str = None, text: str = None):
        """Toca uma frase de teste com a voz informada (sem persistir nada)."""
        try:
            from jarvis.output import tts
            sample = (text or "Olá, eu sou o Jarvis. Em que posso ajudar?").strip()
            old_voice = tts.get_voice()
            old_provider = tts.get_provider()
            try:
                if voice:
                    tts.set_voice(voice)
                tts.set_provider("edge")
                tts.speak(sample)
                tts.wait_until_idle(timeout=20.0)
            finally:
                tts.set_voice(old_voice)
                tts.set_provider(old_provider)
            return json.dumps({"ok": True})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    def save_config(self, config_json: str):
        """Atualiza a configuração com um dicionário parcial."""
        try:
            partial_config = json.loads(config_json)
            save_runtime_config_data(partial_config)
            return json.dumps({"ok": True})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    def get_action_types(self):
        """Retorna os tipos de ações suportados pelo editor e plugins."""
        return json.dumps(get_all_ui_definitions())

    # ─── Ativar ─────────────────────────────────────────────────
    def activate_mode(self, mode_id: str):
        """Ativa um modo específico pelo seu ID."""
        mode_index = state.runtime_modes_state.get("mode_index", {})
        mode = mode_index.get(mode_id)
        if not mode:
            err = f"Modo '{mode_id}' não encontrado"
            state.add_log("error", err)
            print(f"[API] activate_mode: {err}")
            return json.dumps({"ok": False, "error": err})

        actions_count = len(mode.get("actions", []))
        state.add_log("info", f"⏵ Comando 'Ativar' recebido: {mode.get('name')} ({actions_count} ações)")
        print(f"[API] activate_mode: {mode_id} ({actions_count} ações)")

        def _run_safe():
            try:
                execute_mode(mode, "painel")
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                print(f"[API] EXCEPÇÃO em execute_mode: {e}\n{tb}")
                state.add_log("error", f"✖ Erro ao executar modo: {e}")

        threading.Thread(target=_run_safe, daemon=True).start()
        return json.dumps({"ok": True})

    def activate_default_mode(self):
        """Ativa o modo padrão atual."""
        return self.activate_mode(state.active_default_mode_id)

    # ─── Criar / Editar Modo ────────────────────────────────────
    def save_mode(self, mode_json: str):
        """
        Cria ou atualiza um modo.
        Recebe o objeto modo como JSON string.
        Se não tiver 'id', gera um automaticamente.
        """
        try:
            mode = json.loads(mode_json)
        except Exception as e:
            return json.dumps({"ok": False, "error": f"JSON inválido: {e}"})

        modes_data = state.runtime_modes_state.get("data") or {}
        modes_list = list(modes_data.get("modes", []))

        # Garante que o modo tem um ID
        if not mode.get("id"):
            safe_name = mode.get("name", "novo_modo").lower().replace(" ", "_")
            mode["id"] = f"{safe_name}_{uuid.uuid4().hex[:6]}"

        # Garante estrutura mínima
        mode.setdefault("name", "Novo Modo")
        mode.setdefault("description", "")
        mode.setdefault("icon", "")
        mode.setdefault("hotkey", "")
        mode.setdefault("schedule", "")
        mode.setdefault("actions", [])
        mode.setdefault("triggers", {})

        # Validação bloqueante: campos obrigatórios não vazios + tipos conhecidos
        errors = validate_mode(mode, get_action_specs())
        if errors:
            return json.dumps({"ok": False, "error": "Modo inválido", "errors": errors})

        # Atualiza se já existe, insere se é novo
        idx = next((i for i, m in enumerate(modes_list) if m["id"] == mode["id"]), None)
        if idx is not None:
            modes_list[idx] = mode
        else:
            modes_list.append(mode)

        _persist_modes(modes_list)
        # Sinaliza ao listener de hotkeys para re-registrar (modo pode ter alterado hotkey)
        state.config_reloaded_event.set()
        return json.dumps({"ok": True, "mode_id": mode["id"]})

    # ─── Deletar Modo ───────────────────────────────────────────
    def delete_mode(self, mode_id: str):
        """Remove um modo pelo ID."""
        modes_data = state.runtime_modes_state.get("data") or {}
        modes_list = [m for m in modes_data.get("modes", []) if m["id"] != mode_id]
        _persist_modes(modes_list)
        state.config_reloaded_event.set()  # libera hotkey antes registrada para esse modo
        return json.dumps({"ok": True})

    # ─── Pickers ───────────────────────────────────────────
    def pick_file(self):
        """Abre a janela nativa do Windows para escolher um arquivo."""
        import webview
        try:
            # Pega a janela ativa para ancorar o modal nela
            window = webview.windows[0]
            # OPEN_DIALOG = 10, permite selecionar arquivo (incluindo atalhos)
            result = window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False)
            if result and len(result) > 0:
                return json.dumps({"ok": True, "path": result[0]})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})
        return json.dumps({"ok": False})

    def pick_folder(self):
        """Abre a janela nativa do Windows para escolher uma pasta."""
        import webview
        try:
            window = webview.windows[0]
            # FOLDER_DIALOG = 20
            result = window.create_file_dialog(webview.FOLDER_DIALOG, allow_multiple=False)
            if result and len(result) > 0:
                return json.dumps({"ok": True, "path": result[0]})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})
        return json.dumps({"ok": False})

    # ─── Voz IA ───────────────────────────────────────────
    def start_voice_listen(self):
        """
        Inicia gravação com auto-stop por silêncio.
        O usuário só clica uma vez — quando ele para de falar, o JARVIS encerra,
        transcreve e responde sozinho. Não precisa clicar 'Parar'.
        """
        voice_ai.start_recording(auto_stop=True)
        return json.dumps({"ok": True})

    def stop_voice_listen(self):
        """Para a gravação manualmente (caso o usuário clique 'Parar' antes do silêncio)."""
        voice_ai.stop_recording()
        return json.dumps({"ok": True})

    def get_voice_status(self):
        """Retorna o estado atual do módulo de voz (status, transcript, mode)."""
        return json.dumps(voice_ai.get_voice_state())

    def get_voice_rms(self):
        """RMS atual do áudio capturado, em string. Chamada de alta frequência (80ms)."""
        return str(round(voice_ai._voice_state.get("current_rms", 0.0)))

    # ─── Importar / Exportar modos ──────────────────────────────
    def export_modes(self):
        """
        Salva os modos atuais em arquivo JSON via diálogo nativo Save As.
        Retorna o caminho escolhido ou {ok: False} se o user cancelou.
        """
        import webview
        try:
            window = webview.windows[0]
            result = window.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename="jarvis-modos.json",
                file_types=("Arquivo JSON (*.json)",),
            )
            if not result:
                return json.dumps({"ok": False, "error": "Cancelado"})
            path = result if isinstance(result, str) else result[0]
            modes_data = state.runtime_modes_state.get("data") or {"modes": []}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(modes_data, f, indent=2, ensure_ascii=False)
                f.write("\n")
            return json.dumps({"ok": True, "path": path, "count": len(modes_data.get("modes", []))})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    def import_modes(self, replace: bool = False):
        """
        Lê um arquivo JSON via diálogo nativo Open e injeta os modos.
        replace=True substitui tudo; replace=False adiciona aos existentes
        (gerando novos IDs em caso de colisão).
        """
        import webview
        try:
            window = webview.windows[0]
            result = window.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=("Arquivo JSON (*.json)",),
            )
            if not result:
                return json.dumps({"ok": False, "error": "Cancelado"})
            path = result[0] if isinstance(result, (list, tuple)) else result

            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            incoming = data.get("modes") if isinstance(data, dict) else None
            if not isinstance(incoming, list):
                return json.dumps({"ok": False, "error": "JSON inválido (esperado {\"modes\": [...]})"})

            # Valida cada modo entrante antes de aceitar
            from jarvis.recipes.validator import validate_mode
            specs = get_action_specs()
            errors = []
            for idx, m in enumerate(incoming):
                errs = validate_mode(m, specs)
                if errs:
                    mid = m.get("id") if isinstance(m, dict) else f"#{idx}"
                    errors.append(f"{mid}: {'; '.join(errs)}")
            if errors:
                return json.dumps({"ok": False, "error": "Modos inválidos no arquivo", "errors": errors})

            current = state.runtime_modes_state.get("data") or {"modes": []}
            current_modes = list(current.get("modes", []))

            if replace:
                final_modes = list(incoming)
            else:
                # Append, gerando ID novo em caso de colisão
                existing_ids = {m.get("id") for m in current_modes if isinstance(m, dict)}
                final_modes = list(current_modes)
                for m in incoming:
                    if m.get("id") in existing_ids:
                        m["id"] = f"{m.get('id', 'modo')}_{uuid.uuid4().hex[:6]}"
                    final_modes.append(m)
                    existing_ids.add(m.get("id"))

            _persist_modes(final_modes)
            state.config_reloaded_event.set()  # re-registra hotkeys
            return json.dumps({"ok": True, "imported": len(incoming), "total": len(final_modes)})
        except json.JSONDecodeError as e:
            return json.dumps({"ok": False, "error": f"JSON malformado: {e}"})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    # ─── Autostart (Windows logon) ──────────────────────────────
    def get_autostart_status(self):
        from jarvis.runtime import autostart
        return json.dumps({
            "enabled": autostart.is_enabled(),
            "command": autostart.get_command_preview(),
        })

    def set_autostart(self, enabled: bool):
        from jarvis.runtime import autostart
        if enabled:
            ok, msg = autostart.enable()
        else:
            ok, msg = autostart.disable()
        return json.dumps({"ok": ok, "message": msg, "enabled": autostart.is_enabled()})

    # ─── Feedback do usuário ────────────────────────────────────
    def get_feedback_status(self):
        """Retorna se o canal de feedback foi configurado pelo desenvolvedor."""
        from jarvis.runtime import feedback
        return json.dumps({"configured": feedback.is_configured()})

    def send_feedback(self, text: str, name: str = ""):
        """
        Envia feedback síncrono (a chamada do JS é async pelo bridge — não trava UI).
        Retorna {ok, message}.
        """
        from jarvis.runtime import feedback
        ok, msg = feedback.send(text or "", name or "")
        return json.dumps({"ok": ok, "message": msg})

    # ─── Onboarding ─────────────────────────────────────────────
    def get_onboarding_status(self):
        """Retorna {done: bool} pra UI decidir se mostra o wizard inicial."""
        cfg = state.runtime_config_state.get("data") or {}
        done = bool(cfg.get("runtime", {}).get("onboarding_done", False))
        # Se já tem chave Groq, considera onboarding completo (caso de upgrade
        # de versão antiga sem a flag).
        has_voice = bool(cfg.get("voice_ai", {}).get("api_key"))
        return json.dumps({"done": done or has_voice, "has_voice": has_voice})

    def mark_onboarding_done(self):
        """Marca o wizard como concluído."""
        cfg = state.runtime_config_state.get("data") or {}
        cfg.setdefault("runtime", {})["onboarding_done"] = True
        save_runtime_config_data(cfg)
        return json.dumps({"ok": True})

    # ─── Histórico de uso ───────────────────────────────────────
    def get_history_stats(self):
        """Retorna stats consolidadas do histórico (total, top modos, por hora, recentes)."""
        from jarvis.runtime import history
        return json.dumps(history.get_stats())

    def clear_history(self):
        """Apaga TODAS as execuções gravadas. Irreversível."""
        from jarvis.runtime import history
        removed = history.clear_all()
        return json.dumps({"ok": True, "removed": removed})

    def set_history_enabled(self, enabled: bool):
        """Liga/desliga gravação de novas execuções. Não apaga as já gravadas."""
        cfg = state.runtime_config_state.get("data") or {}
        cfg.setdefault("runtime", {})["history_enabled"] = bool(enabled)
        save_runtime_config_data(cfg)
        return json.dumps({"ok": True, "enabled": bool(enabled)})

    # ─── Tema do sistema ────────────────────────────────────────
    def get_system_theme(self):
        """
        Retorna 'light' ou 'dark' baseado no tema atual do Windows.
        Lê HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize\\AppsUseLightTheme.
        Default: 'dark' (mais comum entre devs).
        """
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return json.dumps({"theme": "light" if value == 1 else "dark"})
        except Exception:
            return json.dumps({"theme": "dark"})

    # ─── Browser externo ────────────────────────────────────────
    def open_external_url(self, url: str):
        """
        Abre uma URL no NAVEGADOR DO SISTEMA (não dentro do PyWebView).
        Usado pelo onboarding pra abrir o console.groq.com sem aprisionar
        o user na webview embutida.
        """
        import webbrowser
        try:
            webbrowser.open(url, new=2)
            return json.dumps({"ok": True})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    # ─── Janela ─────────────────────────────────────────────────
    def hide_panel(self):
        """Esconde o painel sem encerrar o JARVIS (botão X da UI)."""
        from jarvis.ui.panel import hide_panel
        hide_panel()
        return json.dumps({"ok": True})

    # ─── Encerrar ───────────────────────────────────────────────
    def stop_jarvis(self):
        """Encerra o JARVIS de fato (para chamadas explícitas tipo 'Sair')."""
        from jarvis.ui.panel import force_destroy_panel
        state.shutdown_event.set()
        force_destroy_panel()
        return json.dumps({"ok": True})
