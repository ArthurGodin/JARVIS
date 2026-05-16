import time
from jarvis.actions.base import BaseAction


class WaitAction(BaseAction):
    def execute(self, action_config: dict, global_config: dict):
        raw = action_config.get("seconds")
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return False, "Tempo (segundos) não preenchido"
        try:
            seconds = float(raw)
        except (TypeError, ValueError):
            return False, f"Valor inválido para segundos: '{raw}'"
        if seconds < 0:
            return False, "Tempo deve ser positivo"
        time.sleep(seconds)
        return True, f"Aguardou {seconds}s"
