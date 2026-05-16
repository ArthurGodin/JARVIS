import sys
import ctypes
from jarvis.runtime.ipc import send_ipc_command

_mutex = None


def enforce_single_instance(mutex_name="JarvisV3_SingleInstance"):
    """
    Usa um Mutex do Windows para garantir que apenas uma instancia do JARVIS rode.
    Retorna True se for a unica instancia, False se ja estiver rodando.
    """
    global _mutex
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
    last_error = ctypes.windll.kernel32.GetLastError()

    if last_error == 183:  # ERROR_ALREADY_EXISTS
        print("JARVIS ja esta rodando! Verifique a bandeja do sistema.")
        return False
    return True


def check_cli_args():
    """
    Trata --stop / --status conectando-se à instância ativa via IPC.
    Retorna True se um comando foi processado e o processo deve sair.
    """
    if len(sys.argv) <= 1:
        return False

    arg = sys.argv[1].lower()

    if arg == "--stop":
        result = send_ipc_command({"cmd": "stop"})
        if result.get("ok"):
            print("JARVIS encerrado com sucesso.")
        else:
            print(f"Falha ao encerrar JARVIS: {result.get('error', 'erro desconhecido')}")
        return True

    if arg == "--status":
        result = send_ipc_command({"cmd": "status"})
        if result.get("ok"):
            data = result.get("data", {})
            running = data.get("running", False)
            mode = data.get("active_mode_name") or data.get("default_mode_id") or "—"
            last = data.get("last_status", "—")
            print(f"JARVIS: {'rodando' if running else 'inativo'}")
            print(f"  modo atual : {mode}")
            print(f"  status     : {last}")
        else:
            print(f"JARVIS nao esta rodando ({result.get('error', '')}).")
        return True

    return False
