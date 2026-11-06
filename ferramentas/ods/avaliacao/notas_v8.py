# -*- coding: utf-8 -*-
"""Notas dos testes v8 (30/10) nos 300 itens da regua: professores (v8 texto/tecnico, com e sem tema; e, para
comparar, v3 com trecho 20 e 30 metas e v6 com trecho 30) contra o gabarito v8 sem trecho (A2, B2, consenso A2 = B2)
e contra o consenso do v7 com trecho (A = B). Tambem a concordancia entre rotuladores.
Le as respostas guardadas (nao roda modelo). Saida: publicacoes/artigo_ods/resultados/professor/notas_v8.md e .json
Uso: python ferramentas/ods/avaliacao/notas_v8.py
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comparar_professores_v3 import PASTA, _metricas  # noqa: E402
from notas_regua import kappa, por_ods  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def rotulos(pasta):
    out = {}
    for f in glob.glob(os.path.join(pasta, "lote_*.jsonl")):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                x = json.loads(ln)
                out[x["handle"]] = sorted({o["n"] for o in x["ods"]})
    return out


FORMAS = {"texto": "v8 texto", "tecnico": "v8 técnico", "nota": "nota 0-100", "tema_trecho": "tema + trecho como prova",
          "tema_livre": "resumo livre sem trecho"}
CORTES_NOTA = (50, 60, 70)      # a nota vira ODS a partir do corte; os tres aparecem (o corte ainda nao foi escolhido)


def professores(hs):
    arqs = sorted(glob.glob(os.path.join(PASTA, "comparacao_v8_*regua300_*.json")))
    arqs += [os.path.join(PASTA, "comparacao_v3_%s_regua.json" % m) for m in ("Qwen3.5-35B-A3B-Q4_K_M", "gemma-4-26B-A4B-it-qat-q4_0")]
    preds, tempos = {}, {}
    for f in arqs:
        if not os.path.exists(f):
            continue
        d = json.load(open(f, encoding="utf-8"))
        b = os.path.basename(f)
        mod = "Qwen 35B" if "Qwen" in b else "Gemma 26B"
        if "_v8" in b:
            forma = b.split("regua300_v8")[1].rsplit("_", 1)[0]
            nome = "%s %s" % (mod, FORMAS.get(forma, forma))
        else:
            forma, nome = "", "%s v3 com trecho" % mod
        itens = {h: x["modelo"] or [] for h, x in d["itens"].items() if h in hs}
        for corte in (CORTES_NOTA if forma == "nota" else (None,)):
            n = nome + (" (corte %d)" % corte if corte else "")
            preds[n] = {h: sorted({o["n"] for o in v if corte is None or o.get("nota", 0) >= corte}) for h, v in itens.items()}
            tempos[n] = d["resumo"]["s_por_item"]
    return preds, tempos

def main():
    A2, B2 = rotulos(os.path.join(RAIZ, "dados", "gabarito_v8", "rotulos_A2")), rotulos(os.path.join(RAIZ, "dados", "gabarito_v8", "rotulos_B2"))
    hs = sorted(set(A2) & set(B2))
    A, B = rotulos(os.path.join(RAIZ, "dados", "gabarito_v7", "rotulos_A")), rotulos(os.path.join(RAIZ, "dados", "gabarito_v7", "rotulos_B"))
    golds = {"Consenso A2 = B2 (sem trecho)": {h: A2[h] for h in hs if A2[h] == B2[h]},
             "Consenso A = B (v7, com trecho)": {h: A[h] for h in hs if A[h] == B[h]},
             "Rotulador A2": {h: A2[h] for h in hs}, "Rotulador B2": {h: B2[h] for h in hs}}
    parc = os.path.join(RAIZ, "dados", "gabarito_v8", "revisados_parcial.json")
    if os.path.exists(parc):       # 30/10: os 11 primeiros revisados (todos discordantes A2 x B2)
        golds = dict({"Revisados pela especialista (parcial)": json.load(open(parc, encoding="utf-8"))["itens"]}, **golds)
    rev = os.path.join(RAIZ, "dados", "gabarito_revisado_v8.json")
    if os.path.exists(rev):        # revisao da especialista (so os itens revisados), antes de todos
        golds = dict({"Revisado pela especialista": json.load(open(rev, encoding="utf-8"))["itens"]}, **golds)
    L = ["# Testes v8: professores nos 300 registros da régua", "", "## Concordância entre rotuladores (300 registros)", "",
         "| Par | idênticos | F1 com ODS 3 | F1 sem ODS 3 |", "|---|---|---|---|"]
    for n1, x, n2, y in (("A2", A2, "B2", B2), ("A", A, "B", B), ("A", A, "A2", A2), ("B", B, "B2", B2)):
        xx, yy = {h: x[h] for h in hs}, {h: y[h] for h in hs}
        L.append("| %s × %s | %d (%.0f%%) | %.3f | %.3f |" % (n1, n2, sum(xx[h] == yy[h] for h in hs),
                 100 * sum(xx[h] == yy[h] for h in hs) / len(hs), _metricas(xx, yy)["f1"], _metricas(xx, yy, sem3=True)["f1"]))
    L += ["", "Kappa por ODS, A2 × B2: " + ", ".join(
        "%d: %.2f" % (o, kappa(A2, B2, hs, o)) for o in range(1, 19) if any(o in A2[h] or o in B2[h] for h in hs)), ""]
    preds, tempos = professores(set(hs))
    res = {}
    for gnome, gold in golds.items():
        L += ["## Contra: %s (%d registros)" % (gnome, len(gold)), "",
              "| Professor | s/registro | P / R / F1 com ODS 3 | P / R / F1 sem ODS 3 | ODS por registro |", "|---|---|---|---|---|"]
        res[gnome] = {}
        for nome, pred in sorted(preds.items(), key=lambda kv: -_metricas({h: v for h, v in gold.items() if h in kv[1]}, kv[1], sem3=True)["f1"]):
            g = {h: v for h, v in gold.items() if h in pred}
            c, s = _metricas(g, pred), _metricas(g, pred, sem3=True)
            res[gnome][nome] = {"itens": len(g), "com_ods3": c, "sem_ods3": s, "por_ods": por_ods(g, pred)}
            L.append("| %s | %s | %.3f / %.3f / %.3f | %.3f / %.3f / %.3f | %.2f |" % (
                nome, tempos.get(nome, "-"), c["precisao"], c["recall"], c["f1"], s["precisao"], s["recall"], s["f1"],
                sum(len(pred[h]) for h in g) / max(len(g), 1)))
        L.append("")
    json.dump(res, open(os.path.join(PASTA, "notas_v8.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(PASTA, "notas_v8.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
