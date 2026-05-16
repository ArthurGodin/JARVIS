import os
import webbrowser
import subprocess
from jarvis.actions.base import BaseAction


def _is_http_url(url: str) -> bool:
    return url.startswith(("http://", "https://"))


def _is_uri_scheme(url: str) -> bool:
    """Detecta protocol handlers tipo spotify:, mailto:, ms-settings:, vscode:, etc."""
    if "://" in url:
        return True
    if ":" in url:
        head = url.split(":", 1)[0]
        # Schemes válidos: letras + dígitos + . - +
        return bool(head) and all(c.isalnum() or c in "+-." for c in head)
    return False


class OpenUrlAction(BaseAction):
    """
    Abre links HTTP/HTTPS no navegador padrão; URIs (spotify:, mailto:, vscode:...)
    via shell do Windows (`os.startfile` / `start`), que é como o Windows resolve
    protocol handlers de forma confiável. webbrowser.open() trava em URIs não-HTTP.
    """

    def execute(self, action_config: dict, global_config: dict):
        url = (action_config.get("url") or "").strip()
        if not url:
            return False, "Link não preenchido"

        try:
            if _is_http_url(url):
                ok = webbrowser.open(url)
                if not ok:
                    return False, f"Sistema não conseguiu abrir: {url}"
                return True, f"Aberto: {url[:80]}"

            if _is_uri_scheme(url):
                # Protocol handler: usa shell do Windows
                try:
                    os.startfile(url)
                    return True, f"Aberto: {url[:80]}"
                except OSError:
                    # Fallback: shell start (não bloqueia)
                    subprocess.Popen(
                        ["cmd", "/c", "start", "", url],
                        shell=False,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                    return True, f"Aberto: {url[:80]}"

            # Não é HTTP nem URI scheme — assume http://
            normalized = "http://" + url
            ok = webbrowser.open(normalized)
            if not ok:
                return False, f"URL inválida: {url}"
            return True, f"Aberto: {normalized[:80]}"

        except Exception as e:
            return False, f"Erro ao abrir '{url}': {e}"
