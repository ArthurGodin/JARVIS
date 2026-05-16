"""
TTS com Edge TTS (vozes neurais Microsoft) e fallback pra Windows SAPI.

Por que Edge TTS:
- Vozes pt-BR neurais, qualidade quase humana (AntonioNeural, ThalitaNeural...).
- Gratuito, sem API key. Usa o serviço público de TTS do Edge.
- Síntese rápida (~0.5-1s pra frase curta).

Por que manter SAPI como fallback:
- Edge TTS precisa de internet. Se cair, o JARVIS continua falando (offline).
- Em máquinas com firewall corporativo bloqueando o endpoint do Edge.

Reprodução:
- Edge TTS gera MP3 → tocamos via mciSendString (winmm.dll, nativo Windows).
  Sem dependência extra de pygame/playsound.
- SAPI fala direto via System.Speech (sem arquivo intermediário).

Coordenação com follow-up de voz:
- _tts_busy é um Event SETADO SINCRONAMENTE em speak(), antes de spawnar a thread.
  Evita o follow-up captar a própria fala do JARVIS quando wait_until_idle()
  é chamado logo após speak().
"""
import asyncio
import ctypes
import os
import subprocess
import tempfile
import threading
import time
import uuid

# Lock global serializa as falas: evita 2 vozes sobrepostas (sequencializa speak()).
_tts_lock = threading.Lock()
# Event marca "tem fala pendente OU em execução". Setado em speak() na thread atual,
# limpo na thread daemon ao final. Garante semântica correta de "idle".
_tts_busy = threading.Event()
# Padding após o áudio terminar — buffer residual do sistema de som.
_TTS_TAIL_PADDING_S = 0.15

# Voz padrão. Outras boas: pt-BR-ThalitaNeural (fem), pt-BR-FranciscaNeural (fem),
# pt-BR-MacerioMultilingualNeural (masc multilingual). Lista completa em list_voices().
DEFAULT_VOICE = "pt-BR-AntonioNeural"

# Provider em uso. "edge" tenta neural; "sapi" força SAPI. Atualizado por set_provider().
_provider = "edge"
# Voz atual (pode ser sobrescrita por set_voice()).
_voice = DEFAULT_VOICE
# Cache do último flag "edge funcionou" — se falhar uma vez, loga só uma vez por sessão.
_edge_failed_logged = False


def set_provider(provider: str):
    """'edge' (neural, online) ou 'sapi' (offline, robótico)."""
    global _provider
    if provider in ("edge", "sapi"):
        _provider = provider


def set_voice(voice: str):
    """Define a voz atual. Só usado pelo provider 'edge'."""
    global _voice
    if voice and isinstance(voice, str):
        _voice = voice


def get_voice() -> str:
    return _voice


def get_provider() -> str:
    return _provider


# ── Edge TTS ──────────────────────────────────────────────────────

async def _edge_synth(text: str, voice: str, out_path: str):
    import edge_tts
    comm = edge_tts.Communicate(text, voice)
    await comm.save(out_path)


def _play_mp3_blocking(filepath: str):
    """Toca MP3 via mciSendString (winmm.dll). Bloqueia até terminar."""
    winmm = ctypes.windll.winmm
    alias = f"jarvis_tts_{uuid.uuid4().hex[:8]}"
    # Usa Unicode (W) pra suportar paths com acento
    send = winmm.mciSendStringW

    def _cmd(s: str) -> int:
        return send(s, None, 0, None)

    # type mpegvideo é o que MCI usa pra MP3
    if _cmd(f'open "{filepath}" type mpegvideo alias {alias}') != 0:
        # Tenta sem 'type' (deixa o MCI auto-detectar)
        if _cmd(f'open "{filepath}" alias {alias}') != 0:
            raise RuntimeError("MCI: falha ao abrir o áudio")
    try:
        if _cmd(f'play {alias} wait') != 0:
            raise RuntimeError("MCI: falha ao tocar o áudio")
    finally:
        _cmd(f'close {alias}')


def _speak_edge(text: str) -> bool:
    """Tenta sintetizar+tocar via Edge TTS. Retorna True se foi, False se falhou."""
    global _edge_failed_logged
    tmp = os.path.join(tempfile.gettempdir(), f"jarvis_tts_{uuid.uuid4().hex}.mp3")
    try:
        # asyncio.run porque edge-tts é assíncrono
        asyncio.run(_edge_synth(text, _voice, tmp))
    except Exception as e:
        if not _edge_failed_logged:
            print(f"[TTS] Edge TTS falhou ({type(e).__name__}: {e}). Caindo pro SAPI.")
            _edge_failed_logged = True
        try:
            os.remove(tmp)
        except Exception:
            pass
        return False

    try:
        _play_mp3_blocking(tmp)
        return True
    except Exception as e:
        print(f"[TTS] Reprodução MP3 falhou ({e}). Caindo pro SAPI.")
        return False
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass


# ── SAPI (fallback) ───────────────────────────────────────────────

def _build_sapi_command(text: str) -> str:
    safe = text.replace("'", "''").replace("\r", " ").replace("\n", " ")
    return (
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "try {"
        " $pt = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'pt*' } | Select-Object -First 1;"
        " if ($pt) { $s.SelectVoice($pt.VoiceInfo.Name) }"
        "} catch {}"
        "$s.Rate = 0;"
        "$s.Volume = 100;"
        f"$s.Speak('{safe}');"
    )


def _speak_sapi(text: str):
    cmd = _build_sapi_command(text)
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=30,
        )
    except FileNotFoundError:
        print("[TTS] powershell.exe não encontrado no PATH.")
    except subprocess.TimeoutExpired:
        print("[TTS] timeout ao falar via SAPI (>30s).")
    except Exception as e:
        print(f"[TTS] erro SAPI: {e}")


# ── API pública ───────────────────────────────────────────────────

def speak(text: str, _voice_arg: str = None):
    """
    Fala 'text' em background. Não bloqueia.
    Marca _tts_busy ANTES de spawnar a thread — garante que wait_until_idle()
    chamado logo depois sempre vai esperar.
    """
    if not text or not text.strip():
        return

    text = text.strip()
    _tts_busy.set()

    def _run():
        try:
            with _tts_lock:
                played = False
                if _provider == "edge":
                    played = _speak_edge(text)
                if not played:
                    _speak_sapi(text)
                time.sleep(_TTS_TAIL_PADDING_S)
        finally:
            _tts_busy.clear()

    threading.Thread(target=_run, daemon=True).start()


def wait_until_idle(timeout: float = 15.0) -> bool:
    """
    Bloqueia até o TTS estar 100% idle. True se ficou idle, False em timeout.
    Usado pelo follow-up: precisamos esperar o JARVIS terminar antes de escutar.
    """
    deadline = time.time() + timeout
    while _tts_busy.is_set():
        remaining = deadline - time.time()
        if remaining <= 0:
            return False
        time.sleep(0.05)
    return True


def list_voices(lang_prefix: str = "pt-BR"):
    """
    Lista vozes Edge TTS disponíveis (filtradas por idioma).
    Retorna [{short_name, friendly, gender}]. Em caso de falha, lista só a default.
    """
    try:
        import edge_tts

        async def _list():
            return await edge_tts.list_voices()

        all_voices = asyncio.run(_list())
    except Exception as e:
        print(f"[TTS] list_voices falhou: {e}")
        return [{"short_name": DEFAULT_VOICE, "friendly": "Antonio (default)", "gender": "Male"}]

    out = []
    for v in all_voices:
        sn = v.get("ShortName", "")
        if not sn.startswith(lang_prefix):
            continue
        # ShortName: "pt-BR-AntonioNeural" → friendly "Antonio"
        friendly = sn.split("-", 2)[-1].replace("Neural", "").replace("Multilingual", "")
        out.append({
            "short_name": sn,
            "friendly": friendly,
            "gender": v.get("Gender", ""),
        })
    return out
