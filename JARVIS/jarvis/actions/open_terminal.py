import os
import subprocess
from jarvis.actions.base import BaseAction


class OpenTerminalAction(BaseAction):
    def execute(self, action_config: dict, global_config: dict):
        working_dir = (action_config.get("working_dir") or "").strip()
        command = (action_config.get("command") or "").strip()

        if not working_dir:
            return False, "Pasta alvo não preenchida"
        if not os.path.isdir(working_dir):
            return False, f"Pasta alvo não encontrada: {working_dir}"

        try:
            full_cmd = f'start cmd /k "{command}"' if command else 'start cmd'
            subprocess.Popen(full_cmd, cwd=working_dir, shell=True)
            return True, f"Terminal aberto em {working_dir}"
        except Exception as e:
            return False, f"Erro ao abrir terminal: {e}"
