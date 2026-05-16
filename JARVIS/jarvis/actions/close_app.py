"""
Fecha aplicativo(s) por nome do executável.

Aceita:
- "Spotify.exe", "spotify.exe", "spotify" — todos casam com o processo Spotify.exe
- Caminho absoluto: usa só o basename
- Match é case-insensitive

Retorna sucesso se fechou 1+ processos, falha se nenhum estava rodando.
"""
import os
import psutil
from jarvis.actions.base import BaseAction

# Timeout pra terminate gentil antes de kill forçado
TERMINATE_TIMEOUT_S = 2.0


class CloseAppAction(BaseAction):
    def execute(self, action_config: dict, global_config: dict):
        target = (action_config.get("target") or "").strip()
        if not target:
            return False, "Nome do app não preenchido"

        # Normaliza: pega só o basename, força .exe minúsculo, e gera variações aceitas
        basename = os.path.basename(target).lower()
        if not basename.endswith(".exe"):
            basename_with_ext = basename + ".exe"
            basename_no_ext = basename
        else:
            basename_with_ext = basename
            basename_no_ext = basename[:-4]

        # Coleta processos que casam
        targets = []
        for proc in psutil.process_iter(["name"]):
            try:
                pname = (proc.info.get("name") or "").lower()
                if pname == basename_with_ext or pname == basename_no_ext:
                    targets.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not targets:
            return False, f"'{basename}' não está rodando"

        # Tenta terminate (gentil), depois kill nos sobreviventes
        for proc in targets:
            try:
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        gone, alive = psutil.wait_procs(targets, timeout=TERMINATE_TIMEOUT_S)
        for proc in alive:
            try:
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        return True, f"Fechou {len(targets)} processo(s) de {basename_with_ext}"
