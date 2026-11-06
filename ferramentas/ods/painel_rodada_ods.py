# -*- coding: utf-8 -*-
"""Painel da rodada ODS (so leitura): etapa, barras de progresso, velocidade e previsao de termino.
Atualiza a cada 30 s. Fechar esta janela NAO afeta a rodada. Uso: python ferramentas/ods/painel_rodada_ods.py
"""
import json
import os
import re
import subprocess
import time
from datetime import datetime, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG = os.path.join(RAIZ, "logs", "rodada_acervo.log")
CACHE = os.path.join(os.getenv("LOCALAPPDATA"), "CuradoriaARCA", "cache")


def barra(f, n=40):
    f = max(0.0, min(1.0, f))
    return "[" + "#" * int(f * n) + "." * (n - int(f * n)) + "] %5.1f%%" % (100 * f)


def ler_log():
    try:
        return open(LOG, encoding="utf-8").read().splitlines()
    except OSError:
        return []


def rodando():
    """A rodada grava o proprio PID em logs/rodada_acervo.pid enquanto esta ativa."""
    try:
        pid = open(os.path.join(RAIZ, "logs", "rodada_acervo.pid")).read().strip()
    except OSError:
        return False
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "(Get-CimInstance Win32_Process -Filter 'ProcessId=%s').CommandLine" % pid],
                       capture_output=True, text=True)
    return "ods_rodada_acervo" in r.stdout


def quando(seg):
    if seg is None or seg <= 0:
        return "-"
    fim = datetime.now() + timedelta(seconds=seg)
    h = seg / 3600
    return "%s (faltam %s)" % (fim.strftime("%d/%m %H:%M"), ("%.1f h" % h) if h >= 1 else ("%d min" % (seg / 60)))


def painel():
    linhas = ler_log()
    ini = max((i for i, l in enumerate(linhas) if "=== rodada do acervo iniciada" in l), default=0)
    atual = linhas[ini:]
    etapa = "?"
    for l in atual:
        m = re.search(r"ETAPA (\d)", l)
        if m:
            etapa = m.group(1)
    if any("=== FIM" in l for l in atual):
        etapa = "FIM"
    out = ["", "  PAINEL DA RODADA ODS  -  %s" % datetime.now().strftime("%d/%m %H:%M:%S"),
           "  rodada: %s" % ("RODANDO" if rodando() else "PARADA (abra o atalho 'Retomar ODS')"), ""]
    # etapa 1: resumos do PDF
    res = [l for l in atual if re.search(r"\[\d+/\d+\] icict", l)]
    m = re.search(r"\[(\d+)/(\d+)\]", res[-1]) if res else None
    if m:
        f, n = int(m.group(1)), int(m.group(2))
        t0 = datetime.strptime(res[0][:14], "%d/%m %H:%M:%S")
        t1 = datetime.strptime(res[-1][:14], "%d/%m %H:%M:%S")
        vel = (t1 - t0).total_seconds() / max(len(res) - 1, 1)
        seg1 = vel * (n - f)
    else:
        mi = [re.search(r"Resumo do PDF \(D10\): (\d+)", l) for l in atual]
        mi = [x for x in mi if x]
        f, n = 0, (int(mi[-1].group(1)) if mi else 0)
        vel = 13.0 if n else None          # media medida em 05/10 (~13 s/item), ate sair o 1o item
        seg1 = vel * n if n else None
    out.append("  1) Resumos dos PDFs   %s  %d de %d" % (barra(f / n if n else (1 if etapa in "23FIM" else 0)), f, n))
    if vel and etapa == "1":
        out.append("     %.1f s por item  |  termina %s" % (vel, quando(seg1)))
    out.append("  2) Embedding          %s" % ("feito" if etapa in ("3", "FIM") else ("em andamento" if etapa == "2" else "aguardando")))
    # etapa 3: professor
    prof = [l for l in atual if "professor " in l and "s/item" in l]
    try:
        rot = json.load(open(os.path.join(CACHE, "ods_professor.json"), encoding="utf-8"))
        feitos = sum(1 for v in rot.values() if v.get("prompt") in (2, 3) and v.get("ods") is not None)
    except (OSError, ValueError):
        feitos = 0
    total = 69178
    out.append("  3) Gemma rotulando    %s  %d de %d" % (barra(feitos / total), feitos, total))
    seg3 = None
    if prof:
        m = re.search(r"\(([\d.]+)s/item; faltam ~([\d.]+) h\)", prof[-1])
        if m:
            seg3 = float(m.group(2)) * 3600
            out.append("     %s s por item  |  termina %s" % (m.group(1), quando(seg3)))
    elif etapa in ("1", "2"):
        seg3 = (total - feitos) * 4.1
        out.append("     (estimativa: ~4,1 s por item depois dos resumos)")
    fim = (seg1 or 0) * (etapa == "1") + (3 * 3600 if etapa in ("1", "2") else 0) + (seg3 or 0)
    out += ["", "  PREVISAO DE TERMINO DA RODADA: %s" % ("concluida!" if etapa == "FIM" else quando(fim)), "",
            "  ultimas linhas do registro:"]
    out += ["    " + l[:110] for l in linhas[-6:]]
    out += ["", "  (atualiza a cada 30 s; fechar esta janela NAO para a rodada)"]
    return "\n".join(out)


if __name__ == "__main__":
    os.system("title Painel da rodada ODS")
    while True:
        try:
            txt = painel()
        except Exception as e:      # o painel nunca derruba nada; so tenta de novo
            txt = "  erro ao ler o andamento (%s); tentando de novo..." % e
        os.system("cls")
        print(txt, flush=True)
        time.sleep(30)
