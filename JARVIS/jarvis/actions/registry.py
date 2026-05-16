import os
import importlib.util
from jarvis.constants import SCRIPT_DIR

# Dicionário global que armazena os tipos de ação registrados
# Formato: { "type_id": ActionClassInstance }
ACTION_REGISTRY = {}

# Lista de definições de UI para o Editor
# Formato: [{ "type": "type_id", "label": "Nome", "icon": "icone", "fields": [...] }]
ACTION_UI_DEFINITIONS = []

def register_action(type_id, action_instance, ui_definition):
    """Registra uma nova ação no sistema."""
    ACTION_REGISTRY[type_id] = action_instance
    
    # Atualiza ou adiciona a definição da UI
    existing = next((item for item in ACTION_UI_DEFINITIONS if item["type"] == type_id), None)
    if existing:
        ACTION_UI_DEFINITIONS.remove(existing)
    ACTION_UI_DEFINITIONS.append(ui_definition)

def get_action(type_id):
    """Retorna a instância da ação pelo tipo."""
    return ACTION_REGISTRY.get(type_id)

def get_all_ui_definitions():
    """Retorna todas as definições para a interface."""
    return ACTION_UI_DEFINITIONS


def get_action_specs():
    """Mapping {type_id -> ui_definition} usado pelo validator."""
    return {d["type"]: d for d in ACTION_UI_DEFINITIONS}

def load_core_actions():
    """Carrega as ações nativas do JARVIS."""
    from jarvis.actions.open_url import OpenUrlAction
    from jarvis.actions.open_app import OpenAppAction
    from jarvis.actions.open_folder import OpenFolderAction
    from jarvis.actions.run_command import RunCommandAction
    from jarvis.actions.open_terminal import OpenTerminalAction
    from jarvis.actions.close_app import CloseAppAction
    from jarvis.actions.set_volume import SetVolumeAction
    from jarvis.actions.arrange_window import ArrangeWindowAction
    from jarvis.actions.wait import WaitAction

    register_action("open_url", OpenUrlAction(), {
        "type": "open_url", "label": "Abrir Site ou Link", "icon": "🌐",
        "hint": "Cole aqui o link de qualquer site ou playlist. Exemplo: abra o Spotify, copie o link da sua playlist favorita e cole aqui.",
        "fields": [{"key": "url", "label": "Link da página ou Playlist", "placeholder": "Ex: https://open.spotify.com/playlist/...", "required": True}]
    })
    register_action("open_app", OpenAppAction(), {
        "type": "open_app", "label": "Abrir Aplicativo", "icon": "🚀",
        "hint": "Clique em 'Procurar' e selecione o aplicativo (.exe) ou atalho (.lnk) que você deseja abrir.",
        "fields": [{"key": "target", "label": "Local do Aplicativo", "placeholder": "Ex: C:\\Aplicativos\\app.exe", "picker": "file", "required": True}]
    })
    register_action("open_folder", OpenFolderAction(), {
        "type": "open_folder", "label": "Abrir Pasta", "icon": "📁",
        "hint": "Clique em 'Procurar' para selecionar a pasta que o JARVIS deve abrir no seu computador.",
        "fields": [{"key": "path", "label": "Local da Pasta", "placeholder": "Ex: C:\\Users\\SeuNome\\Documentos", "picker": "folder", "required": True}]
    })
    register_action("run_command", RunCommandAction(), {
        "type": "run_command", "label": "Rodar Comando (Background)", "icon": "⚙️",
        "hint": "Para usuários avançados. Digite o comando exato que você rodaria no Terminal. O comando roda invisível em segundo plano.",
        "fields": [
            {"key": "command", "label": "Comando a ser executado", "placeholder": "Ex: npm run start", "required": True},
            {"key": "working_dir", "label": "Pasta de Execução (Opcional)", "placeholder": "Ex: C:\\MeuProjeto", "picker": "folder"}
        ]
    })
    register_action("open_terminal", OpenTerminalAction(), {
        "type": "open_terminal", "label": "Abrir Terminal", "icon": "💻",
        "hint": "Abre uma janela preta de terminal. Você pode digitar um comando automático ou só escolher a pasta onde ele vai abrir.",
        "fields": [
            {"key": "command", "label": "Comando a digitar (Opcional)", "placeholder": "Ex: code ."},
            {"key": "working_dir", "label": "Pasta Alvo", "placeholder": "Ex: C:\\MeuProjeto", "picker": "folder", "required": True}
        ]
    })
    register_action("close_app", CloseAppAction(), {
        "type": "close_app", "label": "Fechar Aplicativo", "icon": "❌",
        "hint": "Fecha um aplicativo aberto pelo nome do executável. Útil pra Modo Foco (fecha Discord/Slack) e Modo Encerrar.",
        "fields": [
            {"key": "target", "label": "Nome do app (.exe)", "placeholder": "Ex: Discord.exe ou Spotify.exe", "required": True}
        ]
    })
    register_action("set_volume", SetVolumeAction(), {
        "type": "set_volume", "label": "Ajustar Volume", "icon": "🔊",
        "hint": "Ajusta o volume mestre do Windows. Valores: 0-100 (absoluto), +N ou -N (relativo), 'mute' ou 'unmute'.",
        "fields": [
            {"key": "level", "label": "Volume (0-100, +N, -N, mute, unmute)", "placeholder": "Ex: 30 ou -20 ou mute", "required": True}
        ]
    })
    register_action("arrange_window", ArrangeWindowAction(), {
        "type": "arrange_window", "label": "Posicionar Janela", "icon": "🪟",
        "hint": "Move e redimensiona uma janela já aberta. Útil pra Modo Trabalho (VSCode na esquerda + browser na direita). Espera até 5s pra janela aparecer.",
        "fields": [
            {"key": "title",  "label": "Título da janela (parte do nome)", "placeholder": "Ex: Code  ou  Spotify  ou  Chrome", "required": True},
            {"key": "region", "label": "Região (left, right, top, bottom, top-left, top-right, bottom-left, bottom-right, center, fullscreen, maximize)", "placeholder": "Ex: left", "required": True}
        ]
    })
    register_action("wait", WaitAction(), {
        "type": "wait", "label": "Aguardar (Tempo)", "icon": "⏳",
        "hint": "Pausa o JARVIS por alguns segundos antes de executar a próxima ação. Útil para esperar um app abrir antes de fazer outra coisa.",
        "fields": [{"key": "seconds", "label": "Segundos", "type": "number", "placeholder": "Ex: 2", "required": True}]
    })

def load_plugins():
    """
    Lê a pasta plugins/ e carrega APENAS .py listados em
    runtime.plugins_allowlist da config (default: lista vazia).

    Carregar arbitrariamente qualquer .py é vetor de RCE — qualquer pessoa que
    drope um arquivo na pasta plugins/ executa código arbitrário no boot.
    Por isso o user precisa adicionar o nome do arquivo explicitamente:

      "runtime": { "plugins_allowlist": ["meu_plugin.py"] }

    Plugins fora da allowlist viram aviso ('encontrado mas não autorizado').
    """
    from jarvis import state

    plugins_dir = os.path.join(SCRIPT_DIR, "plugins")
    if not os.path.exists(plugins_dir):
        os.makedirs(plugins_dir)
        with open(os.path.join(plugins_dir, "exemplo.py.disabled"), "w", encoding="utf-8") as f:
            f.write(
                '"""\nExemplo de Plugin JARVIS.\n'
                'Renomeie para .py E adicione o nome em '
                'runtime.plugins_allowlist na config para ativar.\n"""\n'
            )

    config = state.runtime_config_state.get("data") or {}
    allowlist = set(config.get("runtime", {}).get("plugins_allowlist", []) or [])

    for filename in os.listdir(plugins_dir):
        if not filename.endswith(".py") or filename.startswith("__"):
            continue

        if filename not in allowlist:
            print(
                f"[Plugin] Ignorado (não está em runtime.plugins_allowlist): {filename} — "
                f"adicione \"{filename}\" à allowlist em Configurações pra carregar."
            )
            continue

        filepath = os.path.join(plugins_dir, filename)
        module_name = f"jarvis.plugins.{filename[:-3]}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, "setup_plugin"):
                module.setup_plugin(ACTION_REGISTRY, ACTION_UI_DEFINITIONS)
                print(f"[Plugin] Carregado (autorizado): {filename}")
            else:
                print(f"[Plugin] Ignorado (sem setup_plugin): {filename}")
        except Exception as e:
            print(f"[Plugin] ERRO ao carregar {filename}: {e}")

def init_actions():
    """
    Inicializa apenas as ações nativas (não depende de config).
    Plugins são carregados separadamente em init_plugins() depois que a
    config está disponível, pra respeitar runtime.plugins_allowlist.
    """
    load_core_actions()


def init_plugins():
    """Carrega plugins externos. DEVE ser chamado após load_runtime_config()."""
    load_plugins()
