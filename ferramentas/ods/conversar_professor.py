# -*- coding: utf-8 -*-
"""Abre o professor de ODS (Qwen3.5-35B-A3B, mesma configuracao da GPU) para conversar no navegador (02/11, pedido da
responsavel). Interface do proprio llama.cpp em http://127.0.0.1:8090, so neste computador. Fechar: feche a janela do
servidor ou rode de novo com --parar.
Uso: python ferramentas/ods/conversar_professor.py
"""
import os
import subprocess
import sys
import time
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("ODS_PROFESSOR", "qwen3.5-35b")
from arca import ods_professor as P  # noqa: E402

PORTA = "8090"
if "--parar" in sys.argv:
    subprocess.run(["taskkill", "/IM", "llama-server.exe", "/F"], capture_output=True)
    sys.exit("servidor parado")
amb = dict(os.environ)
try:
    import torch
    amb["PATH"] = os.path.join(os.path.dirname(torch.__file__), "lib") + os.pathsep + amb.get("PATH", "")
except Exception:
    pass
cmd = [P.LLAMA_SERVER, "-m", P._caminho(), "-c", "32768", "-np", "1", "-fa", "on", "--host", "127.0.0.1",
       "--port", PORTA, "--jinja"] + P._CFG["args"]
subprocess.Popen(cmd, env=amb, creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
import urllib.request  # noqa: E402
for _ in range(180):
    try:
        urllib.request.urlopen("http://127.0.0.1:%s/health" % PORTA, timeout=2)
        break
    except Exception:
        time.sleep(2)
webbrowser.open("http://127.0.0.1:%s" % PORTA)
print("Professor no ar: http://127.0.0.1:%s" % PORTA)
