"""
Canal de feedback dos usuários — vai pro desenvolvedor.

Endpoint configurável (em ordem de prioridade):
1. Variável de ambiente `JARVIS_FEEDBACK_URL` (override pra dev/teste)
2. config.feedback.endpoint
3. Default vazio → feature desabilitada (UI mostra mensagem clara)

Tipos de endpoint suportados:
- Discord webhook (URL contém "discord.com/api/webhooks/") — payload formatado
  com embed bonito, vai aparecer como mensagem num canal do Discord do dev.
- Endpoint genérico (qualquer URL) — POST com JSON simples. Pra Formspree,
  Slack incoming webhook, ou backend próprio.

Sempre roda em thread daemon — não trava a UI. Captura metadata útil:
texto, nome opcional, hora, versão, OS, idioma. Sem PII obrigatório, tudo
opt-in pelo user que escreve.
"""
import json
import os
import platform
import threading
import urllib.request
import urllib.error
import datetime

from jarvis import state

JARVIS_VERSION = "3.0"
HTTP_TIMEOUT = 8.0
MAX_LEN = 4000  # limite Discord embed = 4096; deixamos folga


def _get_endpoint() -> str:
    env = os.environ.get("JARVIS_FEEDBACK_URL", "").strip()
    if env:
        return env
    cfg = state.runtime_config_state.get("data") or {}
    return (cfg.get("feedback", {}).get("endpoint") or "").strip()


def is_configured() -> bool:
    return bool(_get_endpoint())


def _build_discord_payload(text: str, name: str) -> dict:
    """Formata como embed Discord com cor cyan e campos legíveis."""
    nome = (name or "").strip() or "anônimo"
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    return {
        "username": "JARVIS Feedback",
        "embeds": [
            {
                "title": "📬 Novo feedback",
                "description": text[:MAX_LEN],
                "color": 0x00D4FF,  # ciano JARVIS
                "fields": [
                    {"name": "De",      "value": nome,             "inline": True},
                    {"name": "Versão",  "value": f"v{JARVIS_VERSION}", "inline": True},
                    {"name": "OS",      "value": f"{platform.system()} {platform.release()}", "inline": True},
                    {"name": "Idioma",  "value": _detect_locale(), "inline": True},
                    {"name": "Quando",  "value": now,              "inline": True},
                ],
            }
        ],
    }


def _build_generic_payload(text: str, name: str) -> dict:
    return {
        "type": "jarvis_feedback",
        "name": (name or "").strip() or "anônimo",
        "message": text[:MAX_LEN],
        "version": JARVIS_VERSION,
        "os": f"{platform.system()} {platform.release()}",
        "locale": _detect_locale(),
        "timestamp": datetime.datetime.now().isoformat(),
    }


def _detect_locale() -> str:
    try:
        import locale
        loc = locale.getdefaultlocale()
        return loc[0] if loc and loc[0] else "?"
    except Exception:
        return "?"


def _post_json(url: str, payload: dict) -> tuple:
    """Retorna (ok: bool, msg: str)."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": f"JARVIS/{JARVIS_VERSION}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            code = resp.getcode()
            if 200 <= code < 300:
                return True, "Enviado!"
            return False, f"Servidor respondeu {code}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, f"Sem conexão: {e.reason}"
    except Exception as e:
        return False, f"Erro: {e}"


def send(text: str, name: str = "") -> tuple:
    """
    Envia o feedback de forma SÍNCRONA. Retorna (ok, mensagem).
    Pra não travar a UI, a chamada da API faz isso numa thread.
    """
    text = (text or "").strip()
    if not text:
        return False, "Mensagem vazia"
    if len(text) < 3:
        return False, "Mensagem muito curta"

    endpoint = _get_endpoint()
    if not endpoint:
        return False, (
            "Canal de feedback não configurado pelo desenvolvedor. "
            "Defina JARVIS_FEEDBACK_URL ou feedback.endpoint na config."
        )

    if "discord.com/api/webhooks/" in endpoint:
        payload = _build_discord_payload(text, name)
    else:
        payload = _build_generic_payload(text, name)

    return _post_json(endpoint, payload)


def send_async(text: str, name: str, on_done) -> None:
    """Versão não-bloqueante: chama on_done(ok, msg) quando terminar."""
    def _run():
        ok, msg = send(text, name)
        try:
            on_done(ok, msg)
        except Exception as e:
            print(f"[Feedback] callback erro: {e}")
    threading.Thread(target=_run, daemon=True).start()
