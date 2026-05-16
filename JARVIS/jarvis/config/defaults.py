"""
Configuração padrão e detecção de apps instalados.

Quando o JARVIS roda pela primeira vez (sem ~/.appdata/JARVIS/jarvis.modes.json),
o build_default_modes_config() detecta apps comuns e gera 4-5 modos prontos
que JÁ FUNCIONAM, em vez do template antigo cheio de $config.actions.X vazio.
"""
import os
import glob

from jarvis.constants import FALLBACK_MODE_ID


def _first_existing(paths):
    """Retorna o primeiro path da lista que existe, ou None."""
    for p in paths:
        expanded = os.path.expandvars(p)
        if os.path.exists(expanded):
            return expanded
    return None


def detect_apps():
    """
    Detecta apps populares instalados localmente.
    Retorna {nome_curto: caminho_absoluto} apenas pros encontrados.
    """
    apps = {}

    # ── Spotify ───────────────────────────────────────────
    sp = _first_existing([
        r"%APPDATA%\Spotify\Spotify.exe",
        r"%LOCALAPPDATA%\Microsoft\WindowsApps\Spotify.exe",
    ])
    if sp:
        apps["spotify"] = sp

    # ── VSCode ────────────────────────────────────────────
    vsc = _first_existing([
        r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe",
        r"%PROGRAMFILES%\Microsoft VS Code\Code.exe",
        r"%PROGRAMFILES(X86)%\Microsoft VS Code\Code.exe",
    ])
    if vsc:
        apps["vscode"] = vsc

    # ── Chrome ────────────────────────────────────────────
    chrome = _first_existing([
        r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe",
        r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe",
        r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
    ])
    if chrome:
        apps["chrome"] = chrome

    # ── Edge ──────────────────────────────────────────────
    edge = _first_existing([
        r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe",
        r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe",
    ])
    if edge:
        apps["edge"] = edge

    # ── Discord (versão fica em pasta dinâmica app-X.Y.Z) ─
    disc_glob = glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Discord\app-*\Discord.exe"))
    if disc_glob:
        apps["discord"] = sorted(disc_glob)[-1]

    # ── Slack ─────────────────────────────────────────────
    slack = _first_existing([
        r"%LOCALAPPDATA%\slack\slack.exe",
    ])
    if slack:
        apps["slack"] = slack

    # ── Steam ─────────────────────────────────────────────
    steam = _first_existing([
        r"%PROGRAMFILES(X86)%\Steam\steam.exe",
        r"%PROGRAMFILES%\Steam\steam.exe",
    ])
    if steam:
        apps["steam"] = steam

    return apps


def build_default_config():
    return {
        "metadata": {
            "config_version": 3,
            "profile_name": "Default",
        },
        "voice": {
            "phrases": ["Jarvis"],
            "similarity": 0.78,
            "language": "pt-BR",
            "audio_input_device": "Grupo de microfones",
            "sample_rate": 16000,
            "chunk_seconds": 2.5,
            "silence_threshold": 0.02,
            "noise_calibration_seconds": 1.5,
            "silence_multiplier": 2.8,
        },
        "voice_ai": {
            "api_key": "",
            "porcupine_key": "",
            "microphone_index": None,
        },
        "tts": {
            # 'edge' = vozes neurais Microsoft (online, qualidade humana)
            # 'sapi' = Windows SAPI (offline, robótico) — fallback automático se Edge falhar
            "provider": "edge",
            "voice": "pt-BR-AntonioNeural",
        },
        "wake_word": {
            # 0.20=muito permissivo (mais falsos positivos)
            # 0.35=padrão (pega sotaque PT)
            # 0.50=balanceado
            # 0.70=estrito (só pronúncia inglesa quase perfeita)
            "threshold": 0.35,
        },
        "hotkeys": {
            "activate": {"enabled": True, "combination": "ctrl+alt+j"},
            "stop":     {"enabled": True, "combination": "ctrl+alt+shift+j"},
            "voice":    {"enabled": True, "combination": "ctrl+alt+v"},
        },
        "tray": {"enabled": True},
        "modes": {"default_mode": FALLBACK_MODE_ID},
        "actions": {},
        "runtime": {
            "cooldown_seconds": 2,
            "history_enabled": True,         # opt-out: pode desligar em Configurações
            "plugins_allowlist": [],         # opt-in: plugins .py em plugins/ NÃO carregam
                                             # se não estiverem listados aqui (segurança).
            "onboarding_done": False,        # vira True após o user completar o wizard
        },
        "feedback": {
            # URL do canal pra onde os feedbacks dos usuários vão.
            # Discord webhook do desenvolvedor — recebe formatado como embed.
            # Override em dev: variável de ambiente JARVIS_FEEDBACK_URL.
            # Se virar spam: rotacione no Discord (Editar canal → Integrações → Webhooks).
            "endpoint": "https://discord.com/api/webhooks/1499473659180351623/f1sICtnOF_myQEpzhEEtGgMaWHmlGsb1Msr9BBEyDzI2WiQJdAkueGzfuentqEhKpEEv",
        },
    }


def build_default_modes_config():
    """
    Gera 4 modos prontos que funcionam de cara, ajustados ao que está
    instalado na máquina. Tudo que não for detectado cai num fallback web
    (URL ou URI scheme), garantindo execução bem-sucedida.
    """
    apps = detect_apps()

    def app_action(label, key, web_fallback_url=None, uri_fallback=None):
        """Gera open_app se o app foi detectado; senão open_url no fallback."""
        if key in apps:
            return {
                "type": "open_app",
                "target": apps[key],
                "description": f"Abrir {label}",
            }
        if uri_fallback:
            return {
                "type": "open_url",
                "url": uri_fallback,
                "description": f"Abrir {label}",
            }
        if web_fallback_url:
            return {
                "type": "open_url",
                "url": web_fallback_url,
                "description": f"Abrir {label} (web)",
            }
        return None

    spotify = app_action("Spotify", "spotify", uri_fallback="spotify:")
    vscode = app_action("VSCode", "vscode", web_fallback_url="https://vscode.dev")
    discord = app_action("Discord", "discord", web_fallback_url="https://discord.com/app")
    steam = app_action("Steam", "steam", uri_fallback="steam://open/main")

    modes = []

    # ── Modo padrão = só Spotify (mais simples possível, sempre funciona) ──
    modes.append({
        "id": FALLBACK_MODE_ID,
        "name": "Modo padrao",
        "icon": "⚡",
        "description": "Abre o Spotify rapidinho.",
        "hotkey": "",
        "triggers": {},
        "actions": [spotify] if spotify else [],
    })

    # ── Modo Trabalho ──
    work_actions = []
    if vscode:
        work_actions.append(vscode)
    work_actions.append({
        "type": "open_url",
        "url": "https://github.com",
        "description": "Abrir GitHub",
    })
    if spotify:
        work_actions.append({"type": "wait", "seconds": 1, "description": "Aguardar"})
        work_actions.append(spotify)
    modes.append({
        "id": "trabalho",
        "name": "Modo Trabalho",
        "icon": "💼",
        "description": "Editor + GitHub + música pra produzir.",
        "hotkey": "ctrl+alt+1",
        "triggers": {},
        "actions": work_actions,
    })

    # ── Modo Foco ──
    focus_actions = []
    if spotify:
        focus_actions.append(spotify)
    focus_actions.append({
        "type": "open_url",
        "url": "https://open.spotify.com/playlist/37i9dQZF1DWWQRwui0ExPn",
        "description": "Tocar lo-fi de foco",
    })
    modes.append({
        "id": "foco",
        "name": "Modo Foco",
        "icon": "🎯",
        "description": "Lo-fi pra concentrar e zero distração.",
        "hotkey": "ctrl+alt+2",
        "triggers": {},
        "actions": focus_actions,
    })

    # ── Modo Reuniao ──
    modes.append({
        "id": "reuniao",
        "name": "Modo Reuniao",
        "icon": "🎙️",
        "description": "Abre Google Meet e suas notas.",
        "hotkey": "ctrl+alt+3",
        "triggers": {},
        "actions": [
            {
                "type": "open_url",
                "url": "https://meet.google.com",
                "description": "Abrir Google Meet",
            },
            {
                "type": "open_url",
                "url": "https://docs.google.com",
                "description": "Abrir suas notas no Docs",
            },
        ],
    })

    # ── Modo Jogo (se Discord ou Steam estiver instalado) ──
    if discord or steam:
        gaming_actions = []
        if discord:
            gaming_actions.append(discord)
        if steam:
            gaming_actions.append(steam)
        if spotify:
            gaming_actions.append({"type": "wait", "seconds": 1, "description": "Aguardar"})
            gaming_actions.append(spotify)
        modes.append({
            "id": "jogo",
            "name": "Modo Jogo",
            "icon": "🎮",
            "description": "Discord, Steam e música pra zerar tudo.",
            "hotkey": "ctrl+alt+4",
            "triggers": {},
            "actions": gaming_actions,
        })

    return {
        "metadata": {"modes_version": 2},
        "modes": modes,
    }
