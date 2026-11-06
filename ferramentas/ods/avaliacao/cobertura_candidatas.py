# -*- coding: utf-8 -*-
"""O filtro das 20 metas candidatas (Qwen3-Embedding-8B) perde ODS do gabarito? Cobertura por ODS e por meta nas
reguas v4/v5/v6 e quantos erros dos professores vem de ODS fora das candidatas (pergunta do responsavel, 28/10).
Uso: python ferramentas/ods/avaliacao/cobertura_candidatas.py"""
import json, os, sys, glob
import numpy as np
sys.path.insert(0, os.getcwd())
from arca import ods_metabusca as MB, ods_sinais as S
cache = S.carregar_cache(); cods = list(MB.metas())
P = "publicacoes/artigo_ods/resultados/professor/"
preds = {}
for f in glob.glob(P + "comparacao_v3_*_regua.json"):
    d = json.load(open(f, encoding="utf-8"))
    preds[d["resumo"]["modelo"][:5]] = {h: {o["n"] for o in (x["modelo"] or [])} for h, x in d["itens"].items()}
for v in ["v4", "v5", "v6"]:
    g = json.load(open("dados/gabarito_claude_%s/gabarito_%s.json" % (v, v), encoding="utf-8"))
    tot = {k: [0, 0] for k in ["ods", "ods_s3", "meta", "meta_s3"]}
    perdas = {m: [0, 0, 0, 0] for m in preds}  # FN fora, FN dentro, total fora, total dentro (sem ODS3)
    for h, det in g["detalhe"].items():
        if h not in cache: continue
        c = [x[0] for x in MB.candidatas(cods, cache[h]["sim"].astype(np.float32))]
        ods_c = {int(x.split(".")[0]) for x in c}
        for o in det.get("ods", []):
            n, meta = o["n"], str(o["meta"])
            dentro_ods, dentro_meta = n in ods_c, meta in c
            for k, ok in (("ods", dentro_ods), ("meta", dentro_meta)):
                tot[k][0] += ok; tot[k][1] += 1
                if n != 3: tot[k + "_s3"][0] += ok; tot[k + "_s3"][1] += 1
            if n != 3:
                for m, pr in preds.items():
                    acertou = n in pr.get(h, set())
                    i = 0 if not dentro_ods else 1
                    perdas[m][i + 2] += 1
                    perdas[m][i] += not acertou
    print("== %s" % v)
    for k, (a, b) in tot.items(): print("  %-8s cobertura %d/%d = %.1f%%" % (k, a, b, 100 * a / b))
    for m, (f0, f1, t0, t1) in perdas.items():
        print("  %s (sem ODS3): ODS fora das candidatas %d, ele acertou %d; dentro %d, perdeu %d (%.0f%%)" % (m, t0, t0 - f0, t1, f1, 100*f1/max(t1,1)))
