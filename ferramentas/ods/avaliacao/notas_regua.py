# -*- coding: utf-8 -*-
"""Notas na regua contra o gabarito v7 (D33): rotulador A, rotulador B e os itens em que A e B dao exatamente os
mesmos ODS (consenso); depois da revisao humana, tambem o gabarito revisado (dados/gabarito_revisado_v7.json).

Le as respostas guardadas (nao roda modelo nenhum):
- professores: publicacoes/artigo_ods/resultados/professor/comparacao_v<prompt>_<modelo>_regua.json (v3 e v4);
  pares concordando e votacao k de n, dentro de cada versao do prompt;
- indexacao humana atual do Arca (linha de base);
- ODSBahia sozinho (odsbahia_prob.json, do jeito dos autores: p >= 0,5), so pelo texto do professor.
Tambem mede a concordancia entre A e B (itens identicos, F1 de um contra o outro, kappa por ODS).

Saida: publicacoes/artigo_ods/resultados/professor/notas_regua_v7.json e .md
Uso: python ferramentas/ods/avaliacao/notas_regua.py
"""
import glob
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from comparar_professores_v3 import PASTA, _metricas  # noqa: E402

V7 = os.path.join(RAIZ, "dados", "gabarito_v7")


def ler_rotulador(r):
    out = {}
    for f in sorted(glob.glob(os.path.join(V7, "rotulos_" + r, "lote_*.jsonl"))):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                x = json.loads(ln)
                out[x["handle"]] = sorted({o["n"] for o in x["ods"]})
    return out


def por_ods(gold, pred):
    out = {}
    for o in range(1, 19):
        gg = {h: [o] if o in v else [] for h, v in gold.items()}
        pp = {h: [o] if o in pred.get(h, []) else [] for h in gold}
        if any(gg.values()) or any(pp.values()):
            out[o] = dict(_metricas(gg, pp), n=sum(1 for v in gg.values() if v))
    return out


def kappa(a, b, hs, o):
    n = len(hs)
    pa = [o in a[h] for h in hs]
    pb = [o in b[h] for h in hs]
    po = sum(x == y for x, y in zip(pa, pb)) / n
    pe = (sum(pa) / n) * (sum(pb) / n) + (1 - sum(pa) / n) * (1 - sum(pb) / n)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def professores():
    preds, tempos = {}, {}
    for f in sorted(glob.glob(os.path.join(PASTA, "comparacao_v[3456]_*_regua.json")) +
                    glob.glob(os.path.join(PASTA, "comparacao_v[3456]_*_regua_metasnovas.json")) +
                    glob.glob(os.path.join(PASTA, "comparacao_v[3456]_*_regua_30.json"))):   # sem os testes de 10
        d = json.load(open(f, encoding="utf-8"))
        tag = "v%d%s" % (d["resumo"].get("prompt", 3), " metas corrigidas" if "metasnovas" in f else
                         " 30 metas" if f.endswith("_30.json") else "")
        nome = "%s (prompt %s)" % (d["resumo"]["modelo"], tag)
        preds[nome] = {h: sorted({o["n"] for o in (x["modelo"] or [])}) for h, x in d["itens"].items()}
        tempos[nome] = (d["resumo"]["s_por_item"], d["resumo"]["dias_acervo_inteiro"])
    for v in ("v3", "v4", "v3 metas corrigidas", "v5", "v6"):
        ind = [n for n in list(preds) if n.endswith("(prompt %s)" % v) and " + " not in n and " de " not in n]
        curto = {n: n.split("-Q")[0].split("-it")[0].split("-MXFP4")[0] for n in ind}
        for i, a in enumerate(ind):
            for b in ind[i + 1:]:
                preds["%s + %s concordam (%s)" % (curto[a], curto[b], v)] = {
                    h: sorted(set(preds[a][h]) & set(preds[b].get(h, []))) for h in preds[a] if h in preds[b]}
        if len(ind) >= 3:
            comuns = set.intersection(*(set(preds[n]) for n in ind))
            for k in range(2, len(ind) + 1):
                preds["%d ou mais de %d (%s)" % (k, len(ind), v)] = {
                    h: sorted(o for o in range(1, 19) if sum(o in preds[n][h] for n in ind) >= k) for h in comuns}
    return preds, tempos


def main():
    A, B = ler_rotulador("A"), ler_rotulador("B")
    ambos = sorted(set(A) & set(B))
    golds = {"Rotulador A": A, "Rotulador B": B,
             "Consenso A = B": {h: A[h] for h in ambos if A[h] == B[h]}}
    rev = os.path.join(RAIZ, "dados", "gabarito_revisado_v7.json")
    if os.path.exists(rev):
        golds["Revisado pela especialista"] = json.load(open(rev, encoding="utf-8"))["itens"]
    L = ["# Régua v7: professores contra o gabarito v7 (A, B, consenso)", "",
         "## Concordância entre os rotuladores A e B", "",
         "Itens rotulados pelos dois: %d; com exatamente os mesmos ODS: %d (%.1f%%)."
         % (len(ambos), len(golds["Consenso A = B"]), 100 * len(golds["Consenso A = B"]) / max(len(ambos), 1)), ""]
    ab = {h: A[h] for h in ambos}
    c, s = _metricas(ab, {h: B[h] for h in ambos}), _metricas(ab, {h: B[h] for h in ambos}, sem3=True)
    L += ["B contra A: F1 com ODS 3 %.3f; sem ODS 3 %.3f." % (c["f1"], s["f1"]), "",
          "| ODS | itens em A | itens em B | kappa |", "|---|---|---|---|"]
    kap = {}
    for o in range(1, 19):
        na, nb = sum(o in A[h] for h in ambos), sum(o in B[h] for h in ambos)
        if na or nb:
            kap[o] = round(kappa(A, B, ambos, o), 3)
            L.append("| %d | %d | %d | %.2f |" % (o, na, nb, kap[o]))
    L.append("")

    preds, tempos = professores()
    from arca import decs_acervo
    from arca.ods_correcao import numero
    ac = decs_acervo.carregar_acervo()
    preds["Indexação atual do Arca (humana)"] = {
        h: sorted({n for n in (numero(x.get("v") if isinstance(x, dict) else x) for x in ac[h].get("ods") or []) if n})
        for h in ambos if h in ac}
    pb = os.path.join(PASTA, "odsbahia_prob.json")
    if os.path.exists(pb):
        for e, ps in json.load(open(pb, encoding="utf-8")).items():
            if e.startswith("texto do professor"):
                preds["ODSBahia (%s)" % e.replace("texto do professor, ", "")] = {
                    h: [n + 1 for n in range(18) if p[n] >= 0.5] for h, p in ps.items()}

    res = {"concordancia_A_B": {"itens": len(ambos), "identicos": len(golds["Consenso A = B"]),
                                "f1_com_ods3": c["f1"], "f1_sem_ods3": s["f1"], "kappa_por_ods": kap}}
    for gnome, gold in golds.items():
        L += ["## Contra: %s" % gnome, "", "| Indexador | itens | s/item | dias no acervo | P / R / F1 com ODS 3 | "
              "P / R / F1 sem ODS 3 |", "|---|---|---|---|---|---|"]
        res[gnome] = {}
        for nome, pred in preds.items():
            g = {h: v for h, v in gold.items() if h in pred}
            if not g:
                continue
            c2, s2 = _metricas(g, pred), _metricas(g, pred, sem3=True)
            res[gnome][nome] = {"itens": len(g), "com_ods3": c2, "sem_ods3": s2, "por_ods": por_ods(g, pred)}
            t = tempos.get(nome)
            L.append("| %s | %d | %s | %s | %.3f / %.3f / %.3f | %.3f / %.3f / %.3f |" % (
                nome, len(g), t[0] if t else "-", t[1] if t else "-", c2["precisao"], c2["recall"], c2["f1"],
                s2["precisao"], s2["recall"], s2["f1"]))
        cols = [n for n in res[gnome] if " + " not in n and not n.startswith("ODSBahia")]
        L += ["", "F1 por ODS (n = exemplos neste gabarito):", "", "| ODS | n | " + " | ".join(cols) + " |",
              "|---|---|" + "---|" * len(cols)]
        for o in range(1, 19):
            linha = [res[gnome][n]["por_ods"].get(o) for n in cols]
            n_ex = sum(1 for v in gold.values() if o in v)
            L.append("| %d | %d | %s |" % (o, n_ex, " | ".join("%.2f" % x["f1"] if x else "-" for x in linha)))
        L.append("")
    json.dump(res, open(os.path.join(PASTA, "notas_regua_v7.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(PASTA, "notas_regua_v7.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
