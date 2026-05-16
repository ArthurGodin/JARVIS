"""
Janela desktop do JARVIS usando PyWebView.
Abre um painel HUD flutuante com a interface HTML/CSS/JS.

Modelo de ciclo de vida:
- O painel pode ser aberto/fechado N vezes; fechar (X) apenas esconde.
- O processo só termina quando a tray dispara "Sair" e chama force_destroy_panel().

Cache-bust: a cada boot, gera um build_id (mtime do app.js) e injeta como query
string nos links/scripts do HTML — assim o WebView2 não serve JS/CSS antigos
do cache local após mudanças.
"""
import os
import re
import time
import webview
from jarvis import state
from jarvis.ui.api import JarvisAPI
from jarvis.constants import resource_path

_window = None
_force_close = False
# Em dev: aponta pra jarvis/web/. Em frozen: pra _MEIPASS/jarvis/web/.
_web_dir = resource_path("jarvis", "web")


def _get_html_path():
    return os.path.join(_web_dir, "index.html")


def _build_id() -> str:
    """ID baseado no mtime de app.js — muda automaticamente a cada save."""
    try:
        return str(int(os.path.getmtime(os.path.join(_web_dir, "app.js"))))
    except OSError:
        return str(int(time.time()))


def _prepare_html(build_id: str) -> str:
    """Lê o index.html e injeta build_id em href/src de style.css e app.js."""
    html_path = _get_html_path()
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    # Adiciona ?v=BUILD em style.css e app.js para furar o cache do WebView2
    html = re.sub(r'href="(style\.css)(\?[^"]*)?"', f'href="\\1?v={build_id}"', html)
    html = re.sub(r'src="(app\.js)(\?[^"]*)?"', f'src="\\1?v={build_id}"', html)
    cache_meta = (
        '<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />\n'
        '  <meta http-equiv="Pragma" content="no-cache" />\n'
        '  <meta http-equiv="Expires" content="0" />\n'
    )
    html = html.replace("<head>", "<head>\n  " + cache_meta, 1)
    return html


def _on_closing():
    """Handler de close do pywebview. Retornar False cancela o fechamento."""
    if _force_close:
        return True
    if _window:
        try:
            _window.hide()
        except Exception:
            pass
    return False


def _panel_loop(api_instance):
    global _window
    build_id = _build_id()
    print(f"[Panel] build_id={build_id} (cache-bust de assets)")

    # Para os assets relativos (style.css?v=..., app.js?v=...) resolverem,
    # carregamos por URL com base no diretório web/, mas com query string variando.
    html_path = _get_html_path()
    url = f"file:///{html_path.replace(os.sep, '/')}?v={build_id}"

    # Reescreve o HTML com cache-bust e meta tags em arquivo cache local.
    cache_html = os.path.join(_web_dir, "_index.cache.html")
    try:
        with open(cache_html, "w", encoding="utf-8") as f:
            f.write(_prepare_html(build_id))
        url = f"file:///{cache_html.replace(os.sep, '/')}"
    except OSError as e:
        print(f"[Panel] falha ao gerar cache-bust HTML ({e}); usando index.html direto.")

    icon_path = os.path.join(_web_dir, "jarvis.ico")

    _window = webview.create_window(
        title="JARVIS — Control Panel",
        url=url,
        js_api=api_instance,
        width=440,
        height=720,
        resizable=True,
        min_size=(380, 580),
        on_top=True,
        shadow=True,
        focus=True,
        background_color="#07070d",
        confirm_close=False,
    )

    _window.events.closing += _on_closing

    webview.start(
        debug=False,
        icon=icon_path if os.path.exists(icon_path) else None,
    )


def _cleanup_cache_html():
    """Remove o _index.cache.html gerado por boot (transiente)."""
    cache_html = os.path.join(_web_dir, "_index.cache.html")
    try:
        if os.path.exists(cache_html):
            os.remove(cache_html)
    except OSError as e:
        print(f"[Panel] cache cleanup falhou (não-crítico): {e}")


def open_panel():
    """
    Abre o painel de controle do JARVIS.
    DEVE ser chamada da thread principal pois pywebview.start() bloqueia.
    Quando o user clica X, o painel apenas esconde — o processo segue vivo na tray.
    Só retorna de fato quando force_destroy_panel() for chamado pela tray "Sair".
    """
    api = JarvisAPI()
    try:
        _panel_loop(api)
    finally:
        _cleanup_cache_html()
    # Quando webview.start() retorna, é shutdown real.
    state.shutdown_event.set()


def show_panel():
    """Mostra o painel (usado pela tray)."""
    if _window is not None:
        try:
            _window.show()
            _window.restore()
        except Exception:
            pass


def hide_panel():
    """Esconde o painel sem matar o JARVIS (usado pelo botão X via JS)."""
    if _window is not None:
        try:
            _window.hide()
        except Exception:
            pass


def force_destroy_panel():
    """Destrói a janela de fato e libera o webview.start() — usado pela tray 'Sair'."""
    global _force_close
    _force_close = True
    if _window is not None:
        try:
            _window.destroy()
        except Exception:
            pass
