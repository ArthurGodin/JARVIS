import os
from jarvis.actions.base import BaseAction


class OpenFolderAction(BaseAction):
    def execute(self, action_config: dict, global_config: dict):
        path = (action_config.get("path") or "").strip()
        if not path:
            return False, "Local da pasta não preenchido"
        if not os.path.isdir(path):
            return False, f"Pasta não encontrada: {path}"
        try:
            os.startfile(path)
            return True, f"Pasta aberta: {path}"
        except Exception as e:
            return False, f"Erro ao abrir pasta: {e}"
