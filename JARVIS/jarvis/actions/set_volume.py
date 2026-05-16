"""
Ajusta o volume mestre do Windows via Core Audio API (pycaw).

Aceita:
- 0..100 — porcentagem absoluta
- "+10" / "-10" — incremento/decremento relativo ao volume atual
- "mute" / "unmute" — silenciar/dessilenciar
"""
from pycaw.pycaw import AudioUtilities

from jarvis.actions.base import BaseAction


def _get_volume_interface():
    """Retorna a interface IAudioEndpointVolume do dispositivo de saída padrão."""
    devices = AudioUtilities.GetSpeakers()
    return devices.EndpointVolume


class SetVolumeAction(BaseAction):
    def execute(self, action_config: dict, global_config: dict):
        raw = action_config.get("level")
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return False, "Volume não preenchido (use 0-100, +N, -N, mute, unmute)"

        try:
            vol = _get_volume_interface()
        except Exception as e:
            return False, f"Não foi possível acessar o volume do sistema: {e}"

        text = str(raw).strip().lower()

        try:
            if text in ("mute", "silencio", "silêncio", "calar"):
                vol.SetMute(1, None)
                return True, "Volume mutado"

            if text in ("unmute", "ativar", "som"):
                vol.SetMute(0, None)
                return True, "Volume reativado"

            # Relativo: "+15" / "-20"
            if text.startswith(("+", "-")):
                try:
                    delta = int(text)
                except ValueError:
                    return False, f"Valor relativo inválido: '{text}' (esperado +N ou -N)"
                current = vol.GetMasterVolumeLevelScalar() * 100.0
                new_level = max(0.0, min(100.0, current + delta))
                vol.SetMasterVolumeLevelScalar(new_level / 100.0, None)
                return True, f"Volume {int(current)}% → {int(new_level)}%"

            # Absoluto 0..100
            try:
                level = int(text)
            except ValueError:
                return False, f"Valor inválido: '{text}' (esperado 0-100, +N, -N, mute)"
            if not 0 <= level <= 100:
                return False, "Volume deve ser entre 0 e 100"
            vol.SetMute(0, None)  # garante que sai do mute ao definir absoluto
            vol.SetMasterVolumeLevelScalar(level / 100.0, None)
            return True, f"Volume ajustado pra {level}%"

        except Exception as e:
            return False, f"Falha ao ajustar volume: {e}"
