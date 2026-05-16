"""
Scheduler de modos: roda modos em horários fixos, sem precisar de hotkey/voz.

Tudo OPT-IN: modo só é agendado se tiver `schedule` preenchido. Vazio = não roda.

Formatos aceitos no campo `mode.schedule`:
- "09:00"                 → todo dia às 9h
- "mon-fri 09:00"         → segunda a sexta às 9h
- "mon,wed,fri 18:30"     → seg/qua/sex às 18:30
- "sat,sun 10:00"         → sáb/dom às 10h
- "weekdays 09:00"        → alias de mon-fri
- "weekend 11:00"         → alias de sat,sun

Múltiplos horários no mesmo modo: separe com `;`
- "mon-fri 09:00; mon-fri 14:00"

Loop: thread daemon que verifica a cada 30s. Marca o último (dia, hora, minuto)
de cada mode-rule pra disparar uma vez por minuto-alvo, mesmo com clock drift.
"""
import threading
import time
import datetime

from jarvis import state

# pt-BR e en-US — pra usuários nomearem em qualquer um
_DAY_TOKENS = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
    "seg": 0, "ter": 1, "qua": 2, "qui": 3, "sex": 4, "sab": 5, "dom": 6,
    "segunda": 0, "terça": 1, "terca": 1, "quarta": 2, "quinta": 3,
    "sexta": 4, "sabado": 5, "sábado": 5, "domingo": 6,
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

_DAY_ALIASES = {
    "weekdays": {0, 1, 2, 3, 4},
    "weekday":  {0, 1, 2, 3, 4},
    "uteis":    {0, 1, 2, 3, 4},
    "úteis":    {0, 1, 2, 3, 4},
    "weekend":  {5, 6},
    "weekends": {5, 6},
    "fimdesemana": {5, 6},
    "daily":    {0, 1, 2, 3, 4, 5, 6},
    "everyday": {0, 1, 2, 3, 4, 5, 6},
}


def _parse_days(token: str):
    """'mon-fri', 'mon,wed,fri', 'weekdays', 'sun' → set de weekdays (0=seg)."""
    token = token.strip().lower()
    if not token:
        return None
    if token in _DAY_ALIASES:
        return set(_DAY_ALIASES[token])

    days = set()
    for part in token.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            ai = _DAY_TOKENS.get(a.strip())
            bi = _DAY_TOKENS.get(b.strip())
            if ai is None or bi is None:
                return None
            # Range circular (sex-seg = sex,sab,dom,seg)
            i = ai
            while True:
                days.add(i)
                if i == bi:
                    break
                i = (i + 1) % 7
        else:
            di = _DAY_TOKENS.get(part)
            if di is None:
                return None
            days.add(di)
    return days or None


def _parse_time(token: str):
    """'09:30' → (9, 30); aceita '9:30' também."""
    token = token.strip()
    if ":" not in token:
        return None
    try:
        hh, mm = token.split(":", 1)
        h, m = int(hh), int(mm)
        if 0 <= h <= 23 and 0 <= m <= 59:
            return (h, m)
    except ValueError:
        pass
    return None


def parse_schedule(raw: str):
    """
    Retorna lista de (set_de_weekdays, hora, minuto). [] se schedule vazio.
    None significa erro de parse — caller deve logar e ignorar.
    """
    if not raw or not isinstance(raw, str):
        return []
    rules = []
    for rule_str in raw.split(";"):
        rule_str = rule_str.strip()
        if not rule_str:
            continue
        # Formato: "[dias ]HH:MM"
        parts = rule_str.split()
        if len(parts) == 1:
            time_part = parts[0]
            days = {0, 1, 2, 3, 4, 5, 6}  # diário
        elif len(parts) == 2:
            days = _parse_days(parts[0])
            time_part = parts[1]
            if days is None:
                return None
        else:
            return None
        t = _parse_time(time_part)
        if t is None:
            return None
        rules.append((days, t[0], t[1]))
    return rules


def validate_schedule_string(raw: str):
    """Retorna mensagem de erro ou None se válido."""
    if not raw:
        return None
    parsed = parse_schedule(raw)
    if parsed is None:
        return f"schedule inválido: '{raw}'"
    return None


# ─── Loop ─────────────────────────────────────────────────────────

# Pra cada (mode_id, hora, minuto), guardamos a última (data, hh, mm) já disparada,
# evitando dispara 2x se o loop rodar mais de uma vez no mesmo minuto.
_last_fired = {}


def _check_and_fire(now: datetime.datetime, on_fire):
    modes = (state.runtime_modes_state.get("data") or {}).get("modes", []) or []
    for mode in modes:
        if not isinstance(mode, dict):
            continue
        raw = (mode.get("schedule") or "").strip()
        if not raw:
            continue
        rules = parse_schedule(raw)
        if not rules:
            continue
        for days, h, m in rules:
            if now.weekday() not in days:
                continue
            if now.hour != h or now.minute != m:
                continue
            key = (mode.get("id"), h, m)
            stamp = (now.year, now.month, now.day, h, m)
            if _last_fired.get(key) == stamp:
                continue  # já disparado nesse minuto exato
            _last_fired[key] = stamp
            try:
                on_fire(mode)
            except Exception as e:
                print(f"[Scheduler] erro disparando {mode.get('id')}: {e}")


def _scheduler_loop(on_fire):
    print("[Scheduler] Iniciado — checando agendamentos a cada 30s.")
    while not state.shutdown_event.is_set():
        try:
            _check_and_fire(datetime.datetime.now(), on_fire)
        except Exception as e:
            print(f"[Scheduler] loop erro: {e}")
        # Espera 30s ou até shutdown — checa flag a cada 1s pra responder rápido
        for _ in range(30):
            if state.shutdown_event.is_set():
                return
            time.sleep(1)
    print("[Scheduler] Encerrado.")


def start_scheduler(on_fire):
    """Sobe o loop em thread daemon. on_fire(mode) é chamado quando disparar."""
    t = threading.Thread(target=_scheduler_loop, args=(on_fire,), daemon=True)
    t.start()
    return t
