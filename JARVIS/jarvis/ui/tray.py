import threading
import pystray
from PIL import Image, ImageDraw
from jarvis import state

def _create_image():
    # Cria uma imagem generica simples para o icone (placeholder)
    # Num produto final, poderiamos carregar um jarvis.ico do disco
    width = 64
    height = 64
    color1 = (0, 212, 255)
    color2 = (124, 58, 237)
    
    image = Image.new('RGB', (width, height), color1)
    dc = ImageDraw.Draw(image)
    dc.rectangle((width // 4, height // 4, width * 3 // 4, height * 3 // 4), fill=color2)
    return image

def _tray_loop(on_trigger_now, on_exit):
    state.tray_state["on_trigger_now"] = on_trigger_now
    state.tray_state["on_exit"] = on_exit

    def on_activate(icon, item):
        if on_trigger_now:
            threading.Thread(target=on_trigger_now, daemon=True).start()

    def on_open_panel(icon, item):
        from jarvis.ui.panel import show_panel
        show_panel()

    def on_open_settings(icon, item):
        # Mesma janela; o usuário troca a aba dentro do painel.
        from jarvis.ui.panel import show_panel
        show_panel()

    def on_quit(icon, item):
        from jarvis.ui.panel import force_destroy_panel
        state.shutdown_event.set()
        force_destroy_panel()
        icon.stop()
        if on_exit:
            on_exit()

    menu = pystray.Menu(
        pystray.MenuItem("Ativar Modo Padrão", on_activate, default=True),
        pystray.MenuItem("Abrir Painel", on_open_panel),
        pystray.MenuItem("Configurações", on_open_settings),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Sair", on_quit)
    )

    icon = pystray.Icon("JARVIS", _create_image(), "JARVIS V3", menu)
    state.tray_state["icon"] = icon

    # Monitora o shutdown event para fechar o tray externamente
    def _monitor_shutdown():
        state.shutdown_event.wait()
        try:
            icon.stop()
        except:
            pass

    threading.Thread(target=_monitor_shutdown, daemon=True).start()

    # O run bloqueia a thread, entao chamamos em background
    icon.run()

def start_tray(on_trigger_now, on_exit):
    t = threading.Thread(target=_tray_loop, args=(on_trigger_now, on_exit), daemon=True)
    t.start()
    return t
