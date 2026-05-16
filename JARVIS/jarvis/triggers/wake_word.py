"""
Wake word listener com OpenWakeWord.

Acurácia ~92% com baixa latência (~50ms por chunk de 80ms).
Detecta a frase "hey jarvis" (modelo pré-treinado) e dispara start_recording().

Coordenação de microfone com voice_ai:
- Mantém um InputStream próprio enquanto está em modo escuta.
- Ao detectar, FECHA o stream antes de chamar start_recording (que abre seu
  próprio stream). Espera o voice_ai terminar (recording=False, processing=False)
  e reabre o stream. Evita conflito de "stream already open" no PortAudio.
"""
import os
import threading
import time
import winsound

import numpy as np
import sounddevice as sd

from jarvis import state
from jarvis.constants import resource_path
from jarvis.triggers.voice_ai import start_recording, _voice_state

# Som tocado quando a wake word ativa. WAV embutido em jarvis/web/wake_chime.wav.
# resource_path() resolve corretamente em dev e em frozen (PyInstaller _MEIPASS).
_CHIME_PATH = resource_path("jarvis", "web", "wake_chime.wav")

# Configuração do modelo
WAKEWORD_NAME = "hey_jarvis"
SAMPLE_RATE = 16000
CHUNK_SIZE = 1280  # 80ms @ 16kHz — formato exigido pelo OpenWakeWord
DEFAULT_THRESHOLD = 0.35  # mais permissivo (era 0.5) — pega "ei jarvis" com sotaque PT
COOLDOWN_S = 2.0          # bloqueia novo trigger por X segundos depois de ativar

_model = None
# Threshold corrente, atualizável por set_threshold() na hora.
_threshold = DEFAULT_THRESHOLD


def set_threshold(value: float):
    """Ajusta sensibilidade do wake word. 0.30=permissivo, 0.50=padrão, 0.70=estrito."""
    global _threshold
    try:
        v = float(value)
    except Exception:
        return
    _threshold = max(0.20, min(0.90, v))


def get_threshold() -> float:
    return _threshold


def _play_chime():
    """
    Toca um chime curto pra indicar que a wake word foi reconhecida.
    Tenta o WAV custom primeiro; cai pro Beep do sistema se o arquivo sumir.
    SND_ASYNC: não bloqueia a thread do wake word.
    """
    try:
        if os.path.exists(_CHIME_PATH):
            winsound.PlaySound(
                _CHIME_PATH,
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
            )
            return
    except Exception as e:
        print(f"[Wake Word] PlaySound falhou ({e}), usando Beep como fallback.")
    try:
        winsound.Beep(880, 70)
    except Exception:
        pass


def _load_model():
    global _model
    if _model is not None:
        return _model
    try:
        from openwakeword.model import Model
        _model = Model(
            wakeword_models=[WAKEWORD_NAME],
            inference_framework="onnx",
        )
        return _model
    except Exception as e:
        print(f"[Wake Word] Falha ao carregar OpenWakeWord: {e}")
        return None


def _make_stream():
    """Cria e inicia um novo InputStream — útil pra abrir/fechar entre detecções."""
    s = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=CHUNK_SIZE,
    )
    s.start()
    return s


def _wait_voice_done():
    """Bloqueia até voice_ai liberar o microfone (gravação, processing OU follow-up)."""
    while not state.shutdown_event.is_set():
        if (not _voice_state.get("recording")
                and not _voice_state.get("processing")
                and not _voice_state.get("follow_up_listening")):
            return
        time.sleep(0.1)


def _wake_loop():
    print(f"[Wake Word] Carregando modelo '{WAKEWORD_NAME}'...")
    model = _load_model()
    if model is None:
        print("[Wake Word] Desabilitado por erro de modelo.")
        return
    print(f"[Wake Word] Pronto. Diga 'hey jarvis' para ativar.")

    last_trigger = 0.0
    stream = None

    try:
        stream = _make_stream()

        while not state.shutdown_event.is_set():
            # Se voice_ai está usando o mic (gravação, transcrição ou follow-up),
            # fecha nosso stream e espera ele liberar.
            if (_voice_state.get("recording")
                    or _voice_state.get("processing")
                    or _voice_state.get("follow_up_listening")):
                if stream is not None:
                    try:
                        stream.stop(); stream.close()
                    except Exception:
                        pass
                    stream = None
                _wait_voice_done()
                # Reabre depois que voice_ai liberar
                if state.shutdown_event.is_set():
                    break
                try:
                    stream = _make_stream()
                    model.reset()  # zera buffer pra não disparar com áudio velho
                except Exception as e:
                    print(f"[Wake Word] Falha ao reabrir stream: {e}")
                    time.sleep(1.0)
                continue

            try:
                chunk, _ = stream.read(CHUNK_SIZE)
            except Exception as e:
                print(f"[Wake Word] Erro lendo áudio: {e}")
                time.sleep(0.5)
                continue

            audio = chunk[:, 0] if chunk.ndim > 1 else chunk
            audio = np.asarray(audio, dtype=np.int16)

            try:
                predictions = model.predict(audio)
            except Exception as e:
                print(f"[Wake Word] Erro no predict: {e}")
                continue

            score = float(predictions.get(WAKEWORD_NAME, 0.0))

            if score > _threshold:
                now = time.time()
                if now - last_trigger < COOLDOWN_S:
                    continue
                last_trigger = now

                print(f"[Wake Word] >> DETECTADO 'hey jarvis' (score {score:.2f})")
                state.add_log("info", f"🎤 'hey jarvis' detectado — pode falar")
                _play_chime()
                model.reset()

                # Libera o mic pra voice_ai
                try:
                    stream.stop(); stream.close()
                except Exception:
                    pass
                stream = None

                # Dispara voice_ai (auto_stop fecha sozinho)
                threading.Thread(target=start_recording, args=(True,), daemon=True).start()

                # Espera voice_ai terminar e reabre stream
                _wait_voice_done()
                if state.shutdown_event.is_set():
                    break
                try:
                    stream = _make_stream()
                    model.reset()
                except Exception as e:
                    print(f"[Wake Word] Falha ao reabrir stream pós-trigger: {e}")
                    time.sleep(1.0)

    except Exception as e:
        print(f"[Wake Word] Erro fatal: {e}")
    finally:
        if stream is not None:
            try:
                stream.stop(); stream.close()
            except Exception:
                pass


def start_wake_word_listener():
    t = threading.Thread(target=_wake_loop, daemon=True)
    t.start()
    return t
