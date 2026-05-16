"""
IPC simples via socket localhost para CLI (--stop, --status).

Protocolo: 1 conexão = 1 linha JSON de comando + 1 linha JSON de resposta.
Comandos suportados: {"cmd": "stop"} e {"cmd": "status"}.
"""
import json
import socket
import threading
from jarvis import state

IPC_HOST = "127.0.0.1"
IPC_PORT = 35417  # porta arbitrária no range "user"
RECV_LIMIT = 4096


def _handle_client(conn, handlers):
    try:
        conn.settimeout(2.0)
        data = conn.recv(RECV_LIMIT)
        if not data:
            return
        try:
            msg = json.loads(data.decode("utf-8").strip())
        except Exception:
            conn.sendall(b'{"ok":false,"error":"invalid json"}\n')
            return

        cmd = msg.get("cmd", "")
        handler = handlers.get(cmd)
        if not handler:
            conn.sendall(json.dumps({"ok": False, "error": f"unknown cmd: {cmd}"}).encode("utf-8") + b"\n")
            return

        try:
            response = handler(msg)
        except Exception as e:
            response = {"ok": False, "error": str(e)}

        conn.sendall(json.dumps(response).encode("utf-8") + b"\n")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _server_loop(handlers):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((IPC_HOST, IPC_PORT))
    except OSError as e:
        print(f"[IPC] Falha ao abrir porta {IPC_PORT}: {e}")
        return

    sock.listen(4)
    sock.settimeout(0.5)
    print(f"[IPC] Servidor ouvindo em {IPC_HOST}:{IPC_PORT}")

    while not state.shutdown_event.is_set():
        try:
            conn, _ = sock.accept()
        except socket.timeout:
            continue
        except OSError:
            break
        threading.Thread(target=_handle_client, args=(conn, handlers), daemon=True).start()

    try:
        sock.close()
    except Exception:
        pass


def start_ipc_server(handlers):
    """Inicia o servidor IPC em uma thread daemon."""
    t = threading.Thread(target=_server_loop, args=(handlers,), daemon=True)
    t.start()
    return t


def send_ipc_command(cmd_payload, timeout=2.0):
    """Cliente: envia uma linha JSON e devolve o dict de resposta (ou {'ok': False, 'error': ...})."""
    try:
        with socket.create_connection((IPC_HOST, IPC_PORT), timeout=timeout) as sock:
            sock.sendall(json.dumps(cmd_payload).encode("utf-8") + b"\n")
            sock.settimeout(timeout)
            data = b""
            while True:
                chunk = sock.recv(RECV_LIMIT)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break
            text = data.decode("utf-8").strip()
            if not text:
                return {"ok": False, "error": "empty response"}
            return json.loads(text)
    except (ConnectionRefusedError, socket.timeout, OSError) as e:
        return {"ok": False, "error": f"sem instância ativa ({e})"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
