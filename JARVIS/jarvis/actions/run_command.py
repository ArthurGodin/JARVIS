import os
import subprocess
from jarvis.actions.base import BaseAction


class RunCommandAction(BaseAction):
    def execute(self, action_config: dict, global_config: dict):
        command = (action_config.get("command") or "").strip()
        working_dir = (action_config.get("working_dir") or "").strip()

        if not command:
            return False, "Comando não preenchido"

        kwargs = {"shell": True}
        if working_dir:
            if not os.path.isdir(working_dir):
                return False, f"Pasta de execução não encontrada: {working_dir}"
            kwargs["cwd"] = working_dir

        try:
            subprocess.Popen(command, **kwargs)
            return True, f"Comando: {command[:60]}"
        except Exception as e:
            return False, f"Erro ao executar comando: {e}"
