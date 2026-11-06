# -*- coding: utf-8 -*-
"""Monitor da regua v7: rotuladores A e B (lotes gravados) e fila da GPU (professor atual, itens feitos, ritmo,
tempo restante e hora prevista). Atualiza a cada 30 s.
Uso: python ferramentas/ods/avaliacao/monitor_regua_v7.py
"""
import os
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PASTA = os.path.join(RAIZ, "dados", "gabarito_v7")
S_POR_ITEM = {"qwen3.5-9b": 6.4, "gemma4-26b": 8.5, "qwen3.5-35b": 10.9, "gpt-oss-20b": 17.5}   # medidos em 27-28/10
ORDEM = list(S_POR_ITEM)
N = 1192


def barra(f, n=30):
    f = max(0.0, min(1.0, f))
    return "[" + "#" * int(f * n) + "." * (n - int(f * n)) + "] %5.1f%%" % (100 * f)


def hora(seg):
    return time.strftime("%d/%m %H:%M", time.localtime(time.time() + seg))


def rotuladores():
    out = []
    for r in "AB":
        p = os.path.join(PASTA, "rotulos_" + r)
        arqs = [os.path.join(p, a) for a in os.listdir(p)] if os.path.isdir(p) else []
        n = len(arqs)
        linha = "Rotulador %s: %3d/120 lotes %s" % (r, n, barra(n / 120))
        if n >= 2:
            ts = sorted(os.path.getmtime(a) for a in arqs)
            ritmo = (ts[-1] - ts[0]) / (n - 1)
            if n < 120:
                linha += " | %.1f min/lote | faltam ~%.0f min | previsto %s" % (ritmo / 60, ritmo * (120 - n) / 60,
                                                                              hora(ritmo * (120 - n)))
        out.append(linha)
    return out


def gpu():
    st = open(os.path.join(PASTA, "fila_status.txt"), encoding="utf-8").read() if os.path.exists(
        os.path.join(PASTA, "fila_status.txt")) else "fila ainda nao iniciada"
    out = ["GPU: " + st]
    if "professor " in st:
        m = st.split("professor ")[-1].strip()
        feitos, total = 0, N
        pg = os.path.join(PASTA, "progresso_professor.txt")
        if os.path.exists(pg) and os.path.getmtime(pg) > time.mktime(time.strptime(st[:19], "%Y-%m-%d %H:%M:%S")):
            feitos, total = map(int, open(pg).read().split())
        inicio = time.mktime(time.strptime(st[:19], "%Y-%m-%d %H:%M:%S"))
        ritmo = (time.time() - inicio) / feitos if feitos > 20 else S_POR_ITEM.get(m, 10)
        resto = ritmo * (total - feitos) + sum(S_POR_ITEM[x] * N for x in ORDEM[ORDEM.index(m) + 1:] if m in ORDEM)
        out.append("  %s: %d/%d %s | %.1f s/item" % (m, feitos, total, barra(feitos / max(total, 1)), ritmo))
        out.append("  4 professores: modelo %d de 4 | faltam ~%.1f h | previsto %s" % (ORDEM.index(m) + 1 if m in ORDEM
                                                                                     else 0, resto / 3600, hora(resto)))
    return out


def main():
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print("REGUA v7 (gabarito A e B + professores, prompt v4)   %s\n" % time.strftime("%H:%M:%S"))
        print("\n".join(rotuladores() + [""] + gpu()))
        time.sleep(30)


if __name__ == "__main__":
    main()
