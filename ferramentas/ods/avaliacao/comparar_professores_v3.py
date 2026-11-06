# -*- coding: utf-8 -*-
"""Compara professores com o prompt v3 (so metas, D25) contra o gabarito v4 (dados/gabarito_claude_v4/gabarito_v4.json:
150 itens sorteados do acervo, rotulados as cegas meta a meta pelas 180 metas Ipea 2026; ODS_GABARITO troca o arquivo).

Uso (um modelo por processo, porque o modelo e escolhido na importacao):
  set ODS_PROFESSOR=qwen3.5-9b && python ferramentas/ods/avaliacao/comparar_professores_v3.py
  python ferramentas/ods/avaliacao/comparar_professores_v3.py --resumo     (tabela com todos os ja rodados)
Mede: precisao/recall/F1 (micro) com e sem ODS 3, F1 por ODS, s/item e projecao para o acervo inteiro,
trecho literal, ODS fora das 20 candidatas, falhas de JSON. Os textos sao os mesmos do fluxo (nada cortado).
"""
import glob
import json
import os
import re
import sys
import time
import unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, RAIZ)
PASTA = os.path.join(RAIZ, "publicacoes", "artigo_ods", "resultados", "professor")
ACERVO_N = 69178
COM_TRECHO = os.getenv("ODS_COM_TRECHO", "sim") != "nao"     # ODS_COM_TRECHO=nao mede sem o trecho literal
# gabarito v4 (D26): 150 itens sorteados, rotulados por Claude as cegas, meta a meta, so pelas metas Ipea 2026
N_ITENS = int(os.getenv("ODS_N", "0"))                       # ODS_N=50: so os N primeiros itens do gabarito (teste rapido)
GABARITO = os.getenv("ODS_GABARITO", os.path.join(RAIZ, "dados", "gabarito_claude_v4", "gabarito_v4.json"))


def _metricas(gold, pred, sem3=False):
    tp = fp = fn = 0
    for h, g in gold.items():
        g = {o for o in g if not (sem3 and o == 3)}
        p = {o for o in pred.get(h, []) if not (sem3 and o == 3)}
        tp += len(g & p)
        fp += len(p - g)
        fn += len(g - p)
    pr = tp / max(tp + fp, 1)
    rc = tp / max(tp + fn, 1)
    return {"precisao": round(pr, 3), "recall": round(rc, 3), "f1": round(2 * pr * rc / max(pr + rc, 1e-9), 3)}


def rodar():
    import numpy as np
    from arca import ods_metabusca as MB, ods_professor as P, ods_sinais as S, ods_texto as T
    from arca.decs_acervo import carregar_acervo
    gold = json.load(open(GABARITO, encoding="utf-8"))["itens"]
    ac = carregar_acervo()
    cache = S.carregar_cache()
    metas = MB.metas()
    cods = list(metas)
    hs = [h for h in sorted(gold) if h in ac and h in cache]
    if N_ITENS:
        hs = hs[:N_ITENS]
        gold = {h: gold[h] for h in hs}
    pares, cands = [], {}
    for h in hs:
        c = MB.candidatas(cods, cache[h]["sim"].astype(np.float32))
        cands[h] = {k for k, _s in c}
        pares.append((T.texto_professor(ac[h]), c))
    if not P.iniciar_servidor(espera_s=max(600, int(os.getenv("ODS_LLM_ESPERA", "0")))):
        sys.exit("servidor nao subiu")
    P.rotular_lote(pares[:2], metas, com_trecho=COM_TRECHO)            # aquecimento (nao entra no tempo)
    t0 = time.time()
    out = P.rotular_lote(pares, metas, com_trecho=COM_TRECHO)
    seg = (time.time() - t0) / len(hs)
    P.parar_servidor()
    norm = lambda s: re.sub(r"\s+", " ", unicodedata.normalize("NFC", s or "")).strip().lower()
    pred, falhas, fora, trechos, literais = {}, 0, 0, 0, 0
    det = {}
    for h, (txt, _c), r in zip(hs, pares, out):
        if r is None:
            falhas += 1
            r = []
        pred[h] = sorted({o["n"] for o in r})
        for o in r:
            if o.get("meta") and o["meta"].lower() not in cands[h]:
                fora += 1
            if o.get("trecho"):
                trechos += 1
                literais += all(norm(t) in norm(txt) for t in o["trecho"].split(" [...] "))
        det[h] = {"gabarito": gold[h], "modelo": r}
        if getattr(r, "tema", ""):
            det[h]["tema"] = r.tema
    g = {h: gold[h] for h in hs}
    por = {}
    for o in range(1, 19):
        gg = {h: [o] if o in v else [] for h, v in g.items()}
        pp = {h: [o] if o in pred.get(h, []) else [] for h in hs}
        if any(gg.values()) or any(pp.values()):
            por[o] = dict(_metricas(gg, pp), n_gabarito=sum(1 for v in gg.values() if v),
                          n_modelo=sum(1 for v in pp.values() if v))
    res = {"modelo": P.NOME + ("" if COM_TRECHO else " (sem trecho)"), "prompt": P.PROMPT_VERSAO, "com_trecho": COM_TRECHO, "itens": len(hs), "s_por_item": round(seg, 2),
           "dias_acervo_inteiro": round(seg * ACERVO_N / 86400, 2),
           "com_ods3": _metricas(g, pred), "sem_ods3": _metricas(g, pred, sem3=True), "por_ods": por,
           "falhas_json": falhas, "ods_fora_das_candidatas": fora,
           "trechos_literais": "%d de %d" % (literais, trechos)}
    print(json.dumps({k: v for k, v in res.items() if k != "por_ods"}, ensure_ascii=False, indent=1))
    with open(os.path.join(PASTA, "comparacao_v%d_%s%s%s.json" % (P.PROMPT_VERSAO, P.NOME, "" if COM_TRECHO else "_sem_trecho",
                                                          ("_n%d" % N_ITENS if N_ITENS else "") + os.getenv("ODS_ROTULO", ""))), "w", encoding="utf-8") as f:
        json.dump({"resumo": res, "itens": det}, f, ensure_ascii=False, indent=1)


def resumo():
    for f in sorted(glob.glob(os.path.join(PASTA, "comparacao_v3_*.json"))):
        r = json.load(open(f, encoding="utf-8"))["resumo"]
        print("%-32s F1 %.3f | sem ODS3: P %.3f R %.3f F1 %.3f | %.2f s/item = %.1f dias | trechos literais %s | fora %d | falhas %d"
              % (r["modelo"], r["com_ods3"]["f1"], r["sem_ods3"]["precisao"], r["sem_ods3"]["recall"],
                 r["sem_ods3"]["f1"], r["s_por_item"], r["dias_acervo_inteiro"], r["trechos_literais"],
                 r["ods_fora_das_candidatas"], r["falhas_json"]))


if __name__ == "__main__":
    resumo() if "--resumo" in sys.argv else rodar()
