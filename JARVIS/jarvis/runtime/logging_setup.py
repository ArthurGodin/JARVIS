"""
Configura logging em arquivo quando o JARVIS roda empacotado (sem console).

Sem isso, todos os print() do app somem porque sys.stdout/stderr estão None
no exe sem console (PyInstaller --windowed). Este módulo redireciona stdout
e stderr pra %APPDATA%/JARVIS/logs/jarvis.log com rotação simples.

Em dev (rodando via `python -m jarvis.app`) o console funciona normal —
não substituímos os streams nesse caso.
"""
import os
import sys
import datetime

from jarvis.constants import LOG_DIR, IS_FROZEN

LOG_FILE = os.path.join(LOG_DIR, "jarvis.log")
LOG_PREV = os.path.join(LOG_DIR, "jarvis.prev.log")
MAX_LOG_BYTES = 2 * 1024 * 1024  # 2MB; rotaciona uma vez (jarvis.log → jarvis.prev.log)


def _rotate_if_big():
    """Se o log atual passou de MAX_LOG_BYTES, move pra .prev e começa um novo."""
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_LOG_BYTES:
            try:
                if os.path.exists(LOG_PREV):
                    os.remove(LOG_PREV)
                os.replace(LOG_FILE, LOG_PREV)
            except OSError:
                pass
    except OSError:
        pass


class _TeeWriter:
    """
    Escreve em arquivo + (opcionalmente) num stream original.
    Tolerante a stream original None (acontece em --windowed PyInstaller).
    """
    def __init__(self, file_obj, original=None, prefix=""):
        self._file = file_obj
        self._original = original
        self._prefix = prefix

    def write(self, text):
        try:
            if text and text.strip():
                stamp = datetime.datetime.now().strftime("%H:%M:%S")
                line = f"[{stamp}]{self._prefix} {text}"
                if not line.endswith("\n"):
                    line += "\n"
                self._file.write(line)
                self._file.flush()
            elif text:
                # Newlines puros — não anota timestamp duplo
                self._file.write(text)
                self._file.flush()
        except Exception:
            pass

        if self._original is not None:
            try:
                self._original.write(text)
            except Exception:
                pass

    def flush(self):
        try:
            self._file.flush()
        except Exception:
            pass
        if self._original is not None:
            try:
                self._original.flush()
            except Exception:
                pass

    def isatty(self):
        return False


def setup_file_logging():
    """
    Ativa o redirecionamento.
    - Frozen (PyInstaller --windowed): sempre redireciona, não há console.
    - Dev: redireciona pra arquivo MAS mantém também o stdout original (tee).
    """
    _rotate_if_big()
    try:
        f = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
    except OSError as e:
        # Não conseguiu abrir log — segue sem redirecionar pra não derrubar o app
        if not IS_FROZEN:
            print(f"[Logging] Falha ao abrir log file: {e}")
        return

    # Marca início do boot
    f.write(f"\n{'='*60}\n")
    f.write(f"=== JARVIS boot {datetime.datetime.now().isoformat()} ===\n")
    f.write(f"{'='*60}\n")
    f.flush()

    # Em frozen, sys.stdout/stderr podem ser None
    orig_out = sys.stdout if not IS_FROZEN else None
    orig_err = sys.stderr if not IS_FROZEN else None
    sys.stdout = _TeeWriter(f, orig_out, prefix="")
    sys.stderr = _TeeWriter(f, orig_err, prefix=" [ERR]")
