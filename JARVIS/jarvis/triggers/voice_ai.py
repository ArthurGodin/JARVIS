"""
voice_ai.py — Módulo de Reconhecimento de Voz com IA

Fluxo:
  1. UI clica "Microfone" → start_recording()
  2. Áudio capturado via sounddevice
  3. UI clica novamente → stop_recording()
  4. Áudio enviado para Whisper API → texto
  5. Texto + lista de modos enviado para GPT-4o-mini → mode_id
  6. execute_mode(mode_id)
"""
import io
import time
import threading
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav

from jarvis import state

# Taxa de amostragem de voz — 16kHz é o padrão do Whisper
SAMPLE_RATE = 16000

# Estado interno do módulo de voz
_voice_state = {
    "recording": False,
    "audio_chunks": [],
    "thread": None,
    "last_transcript": "",
    "last_matched_mode": "",
    "last_response": "",       # resposta falada (texto) — útil quando type=chat
    "last_response_type": "",  # "mode" | "chat" | ""
    "status": "idle",   # idle | recording | transcribing | follow_up | done | error
    "error": "",
    "processing": False,        # True enquanto _transcribe_and_match estiver rodando
    "current_rms": 0.0,         # RMS atual do áudio capturado (0..~3000), pra UI/aura
    "follow_up_listening": False,  # True durante janela de follow-up (sem hey jarvis)
}

# Janela de follow-up: depois de uma resposta, o JARVIS continua escutando
# por X segundos. Se detectar voz, grava direto. Se passar do tempo, libera o mic.
FOLLOW_UP_WINDOW_S = 12.0

_voice_lock = threading.Lock()

# Timeouts (em segundos) para chamadas de rede ao Groq
TRANSCRIBE_TIMEOUT = 25
LLM_TIMEOUT = 20


_NON_SERIALIZABLE_KEYS = {"audio_chunks", "thread"}


def get_voice_state() -> dict:
    """Estado serializável (sem o objeto Thread nem os chunks de áudio)."""
    return {k: v for k, v in _voice_state.items() if k not in _NON_SERIALIZABLE_KEYS}


def _get_api_key() -> str:
    config = state.runtime_config_state.get("data") or {}
    return config.get("voice_ai", {}).get("api_key", "")


def _get_system_prompt(modes: list) -> str:
    import datetime
    mode_list = "\n".join(
        f'- ID: "{m["id"]}" → Nome: "{m["name"]}" ({m.get("description", "")})'
        for m in modes
    ) or "(nenhum modo cadastrado)"

    now = datetime.datetime.now()
    weekdays = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
                "sexta-feira", "sábado", "domingo"]
    months = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
              "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
    context = (
        f"CONTEXTO ATUAL (use quando relevante, sem narrar à toa):\n"
        f"- Data: {weekdays[now.weekday()]}, {now.day} de {months[now.month-1]} de {now.year}\n"
        f"- Hora: {now.strftime('%H:%M')}\n"
        f"- Sistema: Windows\n\n"
    )

    return (
        "Você é o JARVIS, assistente pessoal estilo Tony Stark — irônico, super inteligente, "
        "leal, eficiente. Sempre PT-BR. Tom: educado, ligeiramente sarcástico, direto.\n\n"
        + context +
        "O usuário falou algo. Você precisa decidir entre 3 caminhos:\n\n"
        "**A) ATIVAR MODO** — quando ele pediu para iniciar/abrir/ativar uma rotina da lista.\n"
        "   Exemplos: 'jarvis modo trabalho', 'abre o modo foco', 'ativa o projeto X'.\n\n"
        "**B) CHAT** — pergunta, comentário, ou conversa que NÃO é modo nem comando de sistema.\n"
        "   Exemplos: 'que horas são', 'me conta uma piada', 'qual a capital da França'.\n\n"
        "**C) SISTEMA** — comandos para controlar o próprio JARVIS.\n"
        "   - 'shutdown': encerrar/desligar/fechar o JARVIS por completo.\n"
        "     Gatilhos: 'encerra você', 'se desliga', 'fecha o jarvis', 'tchau jarvis',\n"
        "     'vai dormir', 'se encerra', 'pode fechar', 'pode se desligar'.\n\n"
        f"Modos disponíveis:\n{mode_list}\n\n"
        "REGRAS DE RESPOSTA:\n"
        "- Responda SEMPRE em JSON válido, sem markdown.\n"
        "- Para CHAT: útil, direto, máximo 3 frases. Se não souber, admita.\n"
        "- Para MODO: confirme curtinho, 1 frase.\n"
        "- Para SISTEMA shutdown: despedida curta no seu estilo (ex: 'Até logo, senhor.').\n"
        "- Na dúvida entre modo e chat, prefira CHAT.\n\n"
        "Formato para ATIVAR MODO:\n"
        '{"type": "mode", "mode_id": "id_exato_do_modo", "resposta_falada": "Como queira, senhor. Ativando..."}\n\n'
        "Formato para CHAT:\n"
        '{"type": "chat", "resposta_falada": "Resposta direta aqui."}\n\n'
        "Formato para SISTEMA:\n"
        '{"type": "system", "command": "shutdown", "resposta_falada": "Até logo, senhor."}'
    )


def _record_audio(auto_stop=False):
    """
    Grava em tempo real e expõe `current_rms` no estado para feedback visual.
    Se auto_stop=True, encerra automaticamente quando detectar silêncio sustentado.

    Robustez:
      - Threshold adaptativo: calibra baseline com os 2 primeiros chunks (500ms) de ambiente.
      - Timeout absoluto de 15s — sempre conclui o ciclo, mesmo em mic mudo.
      - Se nenhuma voz for detectada em 6s, encerra com erro útil.
    """
    _voice_state["audio_chunks"] = []
    _voice_state["status"] = "recording"
    _voice_state["current_rms"] = 0.0

    chunk_size = SAMPLE_RATE // 4   # 250ms por chunk
    max_silence_frames = 4          # 1.0s de silêncio para auto-stop
    min_voice_frames = 1            # 250ms acima do threshold = fala detectada
    max_total_frames = 60           # 15s de gravação total (timeout absoluto)
    max_no_voice_frames = 24        # 6s sem voz = "não captei nada"

    silence_frames = 0
    voice_frames = 0
    total_frames = 0
    baseline_rms = 0.0
    threshold = 450.0  # fallback enquanto calibração não fecha

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16") as stream:
        while _voice_state["recording"] and not state.shutdown_event.is_set():
            chunk, _ = stream.read(chunk_size)
            _voice_state["audio_chunks"].append(chunk.copy())
            total_frames += 1

            rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
            _voice_state["current_rms"] = rms

            # Calibração: primeiros 2 chunks (500ms) viram baseline de ruído ambiente.
            if total_frames <= 2:
                baseline_rms = max(baseline_rms, rms)
                if total_frames == 2:
                    threshold = max(baseline_rms * 2.5, 250.0)
                    print(f"[Voz IA] Baseline RMS={baseline_rms:.1f} → threshold={threshold:.1f}")
                continue

            if not auto_stop:
                continue

            if rms >= threshold:
                voice_frames += 1
                silence_frames = 0
            elif voice_frames >= min_voice_frames:
                silence_frames += 1

            # Caminho normal: detectou voz e depois 1s de silêncio.
            if voice_frames >= min_voice_frames and silence_frames >= max_silence_frames:
                print(f"[Voz IA] Silêncio sustentado (RMS {rms:.1f} < {threshold:.1f}), encerrando.")
                _voice_state["recording"] = False
                _voice_state["current_rms"] = 0.0
                _spawn_transcribe()
                return

            # Timeout absoluto — sempre conclui.
            if total_frames >= max_total_frames:
                print(f"[Voz IA] Timeout de gravação ({max_total_frames * 0.25:.1f}s), encerrando.")
                _voice_state["recording"] = False
                _voice_state["current_rms"] = 0.0
                if voice_frames >= min_voice_frames:
                    _spawn_transcribe()
                else:
                    _voice_state["status"] = "error"
                    _voice_state["error"] = "Não captei sua voz. Verifique o microfone e tente de novo."
                return

            # Nada captado em 6s — encerra com erro útil.
            if voice_frames == 0 and total_frames >= max_no_voice_frames:
                print(f"[Voz IA] Nenhuma voz detectada em {max_no_voice_frames * 0.25:.1f}s.")
                _voice_state["recording"] = False
                _voice_state["current_rms"] = 0.0
                _voice_state["status"] = "error"
                _voice_state["error"] = "Não captei sua voz. Verifique o microfone e tente de novo."
                return

    _voice_state["current_rms"] = 0.0


def _spawn_transcribe():
    """Garante que apenas uma transcrição rode por gravação."""
    with _voice_lock:
        if _voice_state["processing"]:
            return
        _voice_state["processing"] = True
    threading.Thread(target=_transcribe_and_match, daemon=True).start()


def _start_follow_up():
    """
    Após uma resposta bem-sucedida, escuta passivamente por FOLLOW_UP_WINDOW_S
    segundos. Se detectar voz, dispara nova gravação SEM precisar de 'hey jarvis'.
    Se passar a janela em silêncio, libera o microfone pro wake word.
    """
    with _voice_lock:
        if _voice_state.get("follow_up_listening") or _voice_state.get("recording"):
            return
        _voice_state["follow_up_listening"] = True
    threading.Thread(target=_follow_up_loop, daemon=True).start()


def _follow_up_loop():
    """
    Loop de escuta passiva do follow-up.

    Fluxo otimizado pra responsividade:
      1. Espera a resposta principal terminar (não captar a própria fala).
      2. Fala 'Pronto.' como sinal AUDÍVEL de "pode falar agora".
      3. Calibra ruído ambiente em 250ms (1 chunk).
      4. Escuta até FOLLOW_UP_WINDOW_S, dispara nova gravação ao detectar voz.

    Threshold é ADAPTATIVO: baseline ambiente * 2.0, mínimo 80.
    """
    from jarvis.output import tts

    # 1) Espera o JARVIS terminar de falar a resposta principal.
    tts.wait_until_idle(timeout=15)

    if state.shutdown_event.is_set():
        _voice_state["follow_up_listening"] = False
        _voice_state["status"] = "idle"
        return

    _voice_state["status"] = "follow_up"

    # 2) Sinal audível "Pronto." — usuário sabe exatamente quando pode falar.
    # Síntese curta (~250ms via Edge TTS); mais ágil que esperar calibração silenciosa.
    tts.speak("Pronto.")
    tts.wait_until_idle(timeout=5)

    if state.shutdown_event.is_set():
        _voice_state["follow_up_listening"] = False
        _voice_state["status"] = "idle"
        return

    state.add_log("info", "🎤 Pode falar agora...")
    print(f"[Voz IA] Follow-up: escutando por {FOLLOW_UP_WINDOW_S}s sem precisar de 'hey jarvis'.")

    chunk_size = SAMPLE_RATE // 4   # 250ms por chunk
    voice_frames_needed = 1         # 250ms já basta — pegar inícios de fala
    calibration_frames = 1          # 250ms (era 500ms) — corte pela metade pra responsividade
    voice_frames = 0
    frames_done = 0
    baseline_rms = 0.0
    threshold = 200.0               # fallback enquanto calibração não fecha
    deadline = time.time() + FOLLOW_UP_WINDOW_S
    detected = False

    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16") as stream:
            while time.time() < deadline and not state.shutdown_event.is_set():
                chunk, _ = stream.read(chunk_size)
                rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
                _voice_state["current_rms"] = rms
                frames_done += 1

                # Calibração: usa 2 primeiros chunks como ruído ambiente
                if frames_done <= calibration_frames:
                    baseline_rms = max(baseline_rms, rms)
                    if frames_done == calibration_frames:
                        threshold = max(baseline_rms * 2.0, 80.0)
                        print(f"[Voz IA] Follow-up baseline RMS={baseline_rms:.1f} → threshold={threshold:.1f}")
                    continue

                if rms >= threshold:
                    voice_frames += 1
                    if voice_frames >= voice_frames_needed:
                        print(f"[Voz IA] Follow-up: voz detectada (RMS {rms:.1f} >= {threshold:.1f})")
                        detected = True
                        break
                else:
                    voice_frames = 0
    except Exception as e:
        print(f"[Voz IA] Follow-up erro: {e}")

    _voice_state["current_rms"] = 0.0
    _voice_state["follow_up_listening"] = False

    if detected and not state.shutdown_event.is_set():
        # Detectou voz — inicia gravação cheia (auto-stop por silêncio).
        # O stream do follow-up já fechou pelo `with`, então start_recording pode abrir o seu.
        print("[Voz IA] Follow-up: gravando comando...")
        start_recording(auto_stop=True)
    else:
        print("[Voz IA] Follow-up: silêncio. Liberando microfone pro wake word.")
        _voice_state["status"] = "idle"
        state.add_log("info", "🔇 Aguardando 'hey jarvis' novamente.")


def _trigger_follow_up_after_response():
    """Após resposta de sucesso, agenda o follow-up listening."""
    if state.shutdown_event.is_set():
        return
    _start_follow_up()


def _transcribe_and_match():
    """Junta o áudio, envia ao Whisper e usa LLM para mapear ao modo correto."""
    try:
        _do_transcribe_and_match()
    finally:
        with _voice_lock:
            _voice_state["processing"] = False


def _do_transcribe_and_match():
    from groq import Groq

    _voice_state["status"] = "transcribing"

    api_key = _get_api_key()
    if not api_key:
        _voice_state["status"] = "error"
        _voice_state["error"] = "API key do Groq não configurada. Acesse Configurações → Voz IA."
        return

    client = Groq(api_key=api_key, timeout=LLM_TIMEOUT)

    # Monta o arquivo WAV em memória
    chunks = _voice_state["audio_chunks"]
    if not chunks:
        _voice_state["status"] = "error"
        _voice_state["error"] = "Nenhum áudio gravado."
        return

    audio_data = np.concatenate(chunks, axis=0)
    buf = io.BytesIO()
    wav.write(buf, SAMPLE_RATE, audio_data)
    buf.seek(0)
    buf.name = "jarvis_audio.wav"  # openai sdk precisa do .name

    # ── Etapa 1: Whisper → Transcrição ──────────────────────
    try:
        transcript_response = client.with_options(timeout=TRANSCRIBE_TIMEOUT).audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=(buf.name, buf.read()),
            language="pt",
        )
        transcript = transcript_response.text.strip()
        _voice_state["last_transcript"] = transcript
        print(f"[Voz IA] Transcrição: '{transcript}'")
    except Exception as e:
        _voice_state["status"] = "error"
        _voice_state["error"] = f"Whisper: {str(e)}"
        return

    if not transcript:
        _voice_state["status"] = "error"
        _voice_state["error"] = "Não consegui entender o que foi dito."
        return

    # ── Etapa 2: Groq LLaMA → Intenção (mode | chat) ───────
    modes = (state.runtime_modes_state.get("data") or {}).get("modes", [])

    try:
        chat_response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": _get_system_prompt(modes)},
                {"role": "user", "content": transcript},
            ],
            max_tokens=400,
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        content = chat_response.choices[0].message.content.strip()
        import json
        llm_data = json.loads(content)

        # Aceita "type" novo ou apenas "mode_id" legado.
        response_type = llm_data.get("type")
        if not response_type:
            response_type = "mode" if llm_data.get("mode_id") else "chat"

        resposta = llm_data.get("resposta_falada", "Sim senhor.")
        mode_id = llm_data.get("mode_id", "")

        _voice_state["last_response"] = resposta
        _voice_state["last_response_type"] = response_type
        _voice_state["last_matched_mode"] = mode_id if response_type == "mode" else "chat"

        print(f"[Voz IA] type={response_type} | mode={mode_id} | resposta='{resposta}'")
    except Exception as e:
        _voice_state["status"] = "error"
        _voice_state["error"] = f"LLM: {str(e)}"

        from jarvis.output.tts import speak
        speak("Tive um problema de conexão com o cérebro.")
        return

    from jarvis.output.tts import speak
    from jarvis.output import tts

    # ── Etapa 3-system: comandos do próprio JARVIS ─────────
    if response_type == "system":
        command = (llm_data.get("command") or "").strip().lower()
        if command == "shutdown":
            print("[Voz IA] Comando SHUTDOWN reconhecido. Encerrando JARVIS por voz...")
            state.add_log("info", "👋 Encerrando JARVIS por voz...")
            speak(resposta or "Até logo, senhor.")
            # Espera o JARVIS terminar de falar a despedida antes de fechar
            tts.wait_until_idle(timeout=10)
            _voice_state["status"] = "done"
            state.runtime_session_state["last_status"] = "Encerrado por voz"
            # Não dispara follow-up (vai fechar mesmo)
            state.shutdown_event.set()
            try:
                from jarvis.ui.panel import force_destroy_panel
                force_destroy_panel()
            except Exception as e:
                print(f"[Voz IA] força destroy panel falhou: {e}")
            return
        # comando system desconhecido — trata como chat normal
        print(f"[Voz IA] Comando system desconhecido: {command!r} — caindo no chat.")
        speak(resposta)
        _voice_state["status"] = "done"
        state.runtime_session_state["last_status"] = f"Chat: '{transcript}'"
        _trigger_follow_up_after_response()
        return

    # ── Etapa 3a: CHAT — só fala, não executa modo ─────────
    if response_type == "chat":
        speak(resposta)
        _voice_state["status"] = "done"
        state.runtime_session_state["last_status"] = f"Chat: '{transcript}'"
        # Inicia follow-up: continua escutando 6s sem precisar de 'hey jarvis'
        _trigger_follow_up_after_response()
        return

    # ── Etapa 3b: MODE — fala confirmação e executa ────────
    mode_index = state.runtime_modes_state.get("mode_index", {})
    mode = mode_index.get(mode_id)

    if mode:
        speak(resposta)
        from jarvis.recipes.executor import execute_mode
        threading.Thread(target=execute_mode, args=(mode, "voz_ia"), daemon=True).start()
        _voice_state["status"] = "done"
        state.runtime_session_state["last_status"] = f"Voz IA: '{transcript}' → {mode['name']}"
        # Inicia follow-up
        _trigger_follow_up_after_response()
    else:
        speak("Desculpe senhor, não encontrei nenhum protocolo que atenda a essa solicitação.")
        _voice_state["status"] = "error"
        _voice_state["error"] = f"Modo '{mode_id}' não encontrado."


def start_recording(auto_stop=False):
    """Inicia a gravação de áudio em background. Sem TTS de aviso (zera latência)."""
    if _voice_state["recording"] or _voice_state["processing"]:
        return

    _voice_state["recording"] = True
    _voice_state["status"] = "recording"
    _voice_state["error"] = ""
    _voice_state["last_transcript"] = ""
    _voice_state["last_matched_mode"] = ""
    _voice_state["last_response"] = ""
    _voice_state["last_response_type"] = ""
    t = threading.Thread(target=_record_audio, args=(auto_stop,), daemon=True)
    _voice_state["thread"] = t
    t.start()


def stop_recording():
    """Para a gravação e dispara a transcrição + inferência de modo."""
    if not _voice_state["recording"]:
        return
    _voice_state["recording"] = False
    # Aguarda a thread de gravação terminar
    if _voice_state["thread"]:
        _voice_state["thread"].join(timeout=2)
    # _spawn_transcribe é idempotente: se a auto-stop já disparou, ignora.
    _spawn_transcribe()

def toggle_recording():
    """Alterna a gravação (usado pelo atalho de teclado global)."""
    if _voice_state["recording"]:
        stop_recording()
    else:
        start_recording()
