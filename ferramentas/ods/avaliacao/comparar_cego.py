# -*- coding: utf-8 -*-
"""Tres vias na amostra cega (150): Claude (metas oficiais, registro inteiro) x humano x maquina
(combinacao treinada SO no gabarito IA, sem rotulo humano; modelos lendo o resumo completo)."""
import json, os, re, numpy as np
ac = json.load(open(os.path.expandvars(r"%LOCALAPPDATA%\CuradoriaARCA\acervo_arca.json"), encoding="utf-8"))
A = json.load(open("amostra_cega.json", encoding="utf-8")); g = {}; exec(open(os.environ.get("ROTULOS","rotulos_cegos.py"), encoding="utf-8").read(), g); C = g["C"]
a26 = json.load(open("a26.json")); P = np.load("P_ia_2026.npy"); idx = {h: i for i, h in enumerate(a26)}
num = lambda v: (lambda m: int(m.group(1)) if m else None)(re.match(r"\s*(\d+)", str(v)))
T = float(os.environ.get("LIMIAR", "0.4"))
lin = []
for x in A:
    h = x["handle"]; c = C[x["i"]][0]
    if not c: continue
    hu = sorted({num(v) for v in ac[h].get("ods") or [] if num(v)})
    p = P[idx[h]]; mq = [int(o) + 1 for o in np.argsort(-p) if p[o] >= T][:3] or [int(np.argmax(p)) + 1]
    lin.append(dict(i=x["i"], h=h, claude=c, humano=hu, maquina=mq))
def prf(ref, pv, excl=()):
    tp = fp = fn = 0
    for r in lin:
        a = set(r[ref]) - set(excl); b = set(r[pv]) - set(excl)
        tp += len(a & b); fp += len(b - a); fn += len(a - b)
    p = tp / max(tp + fp, 1); rr = tp / max(tp + fn, 1); return p, rr, 2 * p * rr / max(p + rr, 1e-9)
print("itens avaliaveis:", len(lin), "| limiar maquina", T)
print("ODS por item: claude %.2f humano %.2f maquina %.2f" % tuple(np.mean([len(r[k]) for r in lin]) for k in ("claude", "humano", "maquina")))
for ref, pv in (("claude", "humano"), ("claude", "maquina"), ("humano", "maquina")):
    a = prf(ref, pv); b = prf(ref, pv, (3,))
    print("ref=%-7s vs %-8s P=%.2f R=%.2f F1=%.2f | sem ODS 3: P=%.2f R=%.2f F1=%.2f" % (ref, pv, *a, *b))
from collections import Counter
print("\nPor ODS (contagem): claude / humano / maquina | humano certo/errado segundo claude")
for o in range(1, 19):
    c = sum(o in r["claude"] for r in lin); hh = sum(o in r["humano"] for r in lin); m = sum(o in r["maquina"] for r in lin)
    hf = sum(o in r["humano"] and o not in r["claude"] for r in lin); hm = sum(o in r["claude"] and o not in r["humano"] for r in lin)
    if c or hh or m: print("ODS %2d  %3d / %3d / %3d | humano marcou sem base: %2d | humano deixou de marcar: %2d" % (o, c, hh, m, hf, hm))
json.dump(lin, open("comparacao_cega.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
