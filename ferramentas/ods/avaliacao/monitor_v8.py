# -*- coding: utf-8 -*-
"""Monitor dos testes v8 (30/10): fila da GPU (teste atual, itens feitos, ritmo, tempo restante, hora prevista) e
rotuladores A2 e B2 do gabarito sem trecho (lotes gravados). Atualiza a cada 30 s.
Uso: python ferramentas/ods/avaliacao/monitor_v8.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fila_v8 import PASTA, STATUS, TESTES, arquivo  # noqa: E402

V8 = os.path.join(os.path.dirname(PASTA), "gabarito_v8")
N, LOTES = 300, 30
S_ITEM = {("texto", 0): 9, ("texto", 30): 11.5, ("tecnico", 0): 15, ("tecnico", 30): 17}   # estimativas; gemma ~8


def barra(f, n=30):
    f = max(0.0, min(1.0, f))
    return "[" + "#" * int(f * n) + "." * (n - int(f * n)) + "] %5.1f%%" % (100 * f)


def hora(seg):
    return time.strftime("%d/%m %H:%M", time.localtime(time.time() + seg))


def gpu():
    st = open(STATUS, encoding="utf-8").read() if os.path.exists(STATUS) else "fila ainda nao iniciada"
    feitos_testes = sum(os.path.exists(arquivo(*t)) for t in TESTES)
    out = ["GPU: " + st, "  testes concluidos: %d de %d %s" % (feitos_testes, len(TESTES), barra(feitos_testes / len(TESTES)))]
    if "teste " in st and "FIM" not in st:
        inicio = time.mktime(time.strptime(st[:19], "%Y-%m-%d %H:%M:%S"))
        pg = os.path.join(PASTA, "progresso_professor.txt")
        feitos, total = 0, N
        if os.path.exists(pg) and os.path.getmtime(pg) > inicio:
            feitos, total = map(int, open(pg).read().split())
        atual = [t for t in TESTES if not os.path.exists(arquivo(*t))]
        est = lambda t: S_ITEM.get((t[1], t[2]), 12) * N
        ritmo = (time.time() - inicio) / feitos if feitos > 10 else (est(atual[0]) / N if atual else 10)
        resto = ritmo * (total - feitos) + sum(est(t) for t in atual[1:])
        out.append("  teste atual: %d/%d %s | %.1f s/item" % (feitos, total, barra(feitos / max(total, 1)), ritmo))
        out.append("  fila inteira: faltam ~%.1f h | previsto %s" % (resto / 3600, hora(resto)))
    return out


def rotuladores():
    out = []
    for r in ("A2", "B2"):
        p = os.path.join(V8, "rotulos_" + r)
        arqs = [os.path.join(p, a) for a in os.listdir(p)] if os.path.isdir(p) else []
        n = len(arqs)
        linha = "Rotulador %s: %2d/%d lotes %s" % (r, n, LOTES, barra(n / LOTES))
        if 2 <= n < LOTES:
            ts = sorted(os.path.getmtime(a) for a in arqs)
            ritmo = (ts[-1] - ts[0]) / (n - 1)
            linha += " | %.1f min/lote | previsto %s" % (ritmo / 60, hora(ritmo * (LOTES - n)))
        out.append(linha)
    return out


def main():
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print("TESTES v8 (300 registros, sem trecho) e GABARITO A2/B2   %s\n" % time.strftime("%H:%M:%S"))
        print("\n".join(gpu() + [""] + rotuladores()))
        print("\n(o gabarito A2/B2 usa a cota do Claude; se ela acabar, a GPU continua sozinha)")
        time.sleep(30)


if __name__ == "__main__":
    main()
