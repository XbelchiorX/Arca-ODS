# -*- coding: utf-8 -*-
"""Amostra aleatoria de 150 registros de 2026 com ODS humana (fora dos 100 ja vistos) e visor CEGO:
mostra titulo, resumo completo e palavras-chave, sem ODS humana nem da maquina.
Uso: python amostra_cega.py criar | python amostra_cega.py ver ini fim"""
import json, os, random, sys
a26 = json.load(open("a26.json"))
if sys.argv[1] == "criar":
    import re
    ac = json.load(open(os.path.expandvars(r"%LOCALAPPDATA%\CuradoriaARCA\acervo_arca.json"), encoding="utf-8"))
    vistos = {x["handle"] for x in json.load(open("amostra_recentes.json", encoding="utf-8"))}
    com = [h for h in a26 if any(re.match(r"\s*\d", str(v)) for v in ac[h].get("ods") or []) and h not in vistos]
    sel = random.Random(18).sample(com, 150)
    out = []
    for i, h in enumerate(sel):
        r = ac[h]
        out.append({"i": i, "handle": h, "titulos": r["titulos"], "resumos": r["resumos"], "keywords": [k["v"] for k in r["keywords"]]})
    json.dump(out, open("amostra_cega.json", "w", encoding="utf-8"), ensure_ascii=False)
    print(len(out), "itens")
else:
    A = json.load(open("amostra_cega.json", encoding="utf-8"))
    for x in A[int(sys.argv[2]):int(sys.argv[3])]:
        t = next((t["v"] for t in x["titulos"] if (t["l"] or "").startswith("pt")), x["titulos"][0]["v"] if x["titulos"] else "")
        rs = [r for r in x["resumos"] if (r["l"] or "").startswith("pt")] or x["resumos"][:1]
        print("#%d %s\nT: %s\nR: %s\nK: %s\n" % (x["i"], x["handle"], t, " || ".join(r["v"] for r in rs), "; ".join(x["keywords"])))
