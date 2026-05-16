"""
Validador de modos.

Valida a estrutura mínima e os campos obrigatórios declarados pelas ações
no registry, em tempo de save (api.save_mode) e em tempo de boot (app.load_modes).
"""
from jarvis.constants import HOTKEY_MODIFIERS, HOTKEY_SPECIAL_KEYS


def _validate_hotkey_string(hk):
    if not isinstance(hk, str) or not hk.strip():
        return "hotkey deve ser string não-vazia"
    parts = [p.strip().lower() for p in hk.split("+") if p.strip()]
    if not parts:
        return "hotkey vazia"
    has_key = False
    for part in parts:
        if part in HOTKEY_MODIFIERS:
            continue
        if part in HOTKEY_SPECIAL_KEYS or len(part) == 1:
            has_key = True
            continue
        return f"token '{part}' não reconhecido"
    if not has_key:
        return "hotkey precisa de pelo menos uma tecla além dos modificadores"
    return None


def _is_blank(value):
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def validate_mode(mode, action_specs_or_known_types):
    """
    `action_specs_or_known_types` aceita dois formatos:
    - dict {type_id: ui_definition}: usa fields[].required pra validar campos obrigatórios.
    - set de type_ids: validação simples (compatibilidade com chamadas antigas).
    """
    errors = []

    if not isinstance(mode, dict):
        return ["modo deve ser um objeto"]

    mode_id = mode.get("id")
    if not isinstance(mode_id, str) or not mode_id.strip():
        errors.append("campo 'id' ausente ou vazio")

    name = mode.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("campo 'name' ausente ou vazio")

    # Normaliza specs
    if isinstance(action_specs_or_known_types, dict):
        specs = action_specs_or_known_types
        known_types = set(specs.keys())
    else:
        specs = {}
        known_types = set(action_specs_or_known_types)

    actions = mode.get("actions", [])
    if not isinstance(actions, list):
        errors.append("'actions' deve ser uma lista")
    else:
        if len(actions) == 0:
            errors.append("o modo precisa de pelo menos 1 ação")

        for idx, action in enumerate(actions):
            num = idx + 1
            if not isinstance(action, dict):
                errors.append(f"ação #{num}: deve ser um objeto")
                continue
            atype = action.get("type")
            if not atype:
                errors.append(f"ação #{num}: 'type' ausente")
                continue
            if atype not in known_types:
                errors.append(f"ação #{num}: tipo '{atype}' não registrado")
                continue

            # Valida campos required do spec, se houver
            spec = specs.get(atype)
            if spec:
                action_label = spec.get("label", atype)
                for field in spec.get("fields", []):
                    if not field.get("required"):
                        continue
                    val = action.get(field["key"])
                    if _is_blank(val):
                        errors.append(
                            f"ação #{num} ({action_label}): preencha '{field['label']}'"
                        )

    hotkey = mode.get("hotkey")
    if hotkey not in (None, ""):
        err = _validate_hotkey_string(hotkey)
        if err:
            errors.append(f"hotkey: {err}")

    schedule = mode.get("schedule")
    if schedule not in (None, ""):
        from jarvis.runtime.scheduler import validate_schedule_string
        err = validate_schedule_string(schedule)
        if err:
            errors.append(err)

    return errors


def validate_modes(modes, action_specs_or_known_types):
    """Retorna dict mode_id -> lista de erros, apenas para modos com erros."""
    out = {}
    for idx, mode in enumerate(modes or []):
        mode_id = mode.get("id") if isinstance(mode, dict) else f"#{idx}"
        errors = validate_mode(mode, action_specs_or_known_types)
        if errors:
            out[mode_id or f"#{idx}"] = errors
    return out
