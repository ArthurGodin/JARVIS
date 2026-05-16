def resolve_value(value, global_config: dict):
    """
    Resolve uma variavel de template do modo contra a configuracao global.
    Exemplo: '$config.actions.app' -> 'caminho/do/app.exe'
    """
    if not isinstance(value, str):
        return value
        
    if value.startswith("$config.actions."):
        key = value.replace("$config.actions.", "")
        actions_config = global_config.get("actions", {})
        return actions_config.get(key, value)
        
    return value

def resolve_action_config(action_config: dict, global_config: dict):
    """
    Resolve todas as variaveis dentro de uma configuracao de acao.
    """
    resolved = {}
    for k, v in action_config.items():
        resolved[k] = resolve_value(v, global_config)
    return resolved
