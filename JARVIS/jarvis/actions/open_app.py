import os
import subprocess
from jarvis.actions.base import BaseAction


class OpenAppAction(BaseAction):
    def execute(self, action_config: dict, global_config: dict):
        target = (action_config.get("target") or "").strip()
        if not target:
            return False, "Local do aplicativo não preenchido"

        # Caminho absoluto: arquivo deve existir
        if os.path.isabs(target) or os.path.sep in target or ":" in target:
            if not os.path.exists(target):
                return False, f"Arquivo não encontrado: {target}"
            try:
                os.startfile(target)
                return True, f"Aberto: {os.path.basename(target)}"
            except Exception as e:
                return False, f"Erro ao abrir: {e}"

        # Comando simples no PATH (ex: notepad, calc)
        try:
            os.startfile(target)
            return True, f"Aberto: {target}"
        except FileNotFoundError:
            try:
                subprocess.Popen(target, shell=True)
                return True, f"Aberto: {target}"
            except Exception as e:
                return False, f"'{target}' não encontrado: {e}"
        except Exception as e:
            return False, f"Erro ao abrir '{target}': {e}"
