# -*- coding: utf-8 -*-
"""Confere as respostas dos rotuladores do gabarito v3 (dados/gabarito_v3/respostas/lote_NNN.jsonl).

Para cada lote: JSON valido, 1 linha por documento na ordem do lote, cada ODS com sua atribuicao, metas
existentes no Ipea 2026 e do ODS certo, trecho LITERAL presente no texto do documento, travas dos ODS 17 e 18.
Uso: python ferramentas/ods/avaliacao/conferir_gabarito_v3.py [NNN ...]   (sem argumento: todos os lotes prontos)
"""
import glob
import json
import os
import re
import sys
import unicodedata

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, RAIZ)
from arca.ods_criterios import travar  # noqa: E402

BASE = os.path.join(RAIZ, "dados", "gabarito_v3")
METAS = json.load(open(os.path.join(RAIZ, "dados", "ods_referencia", "metas_2026.json"), encoding="utf-8"))


def norm(s):
    s = unicodedata.normalize("NFC", s or "")
    s = s.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", s).strip().lower()


def ler_lote(n):
    t = open(os.path.join(BASE, "lotes", "lote_%03d.txt" % n), encoding="utf-8").read()
    docs = re.split(r"########## DOCUMENTO \d+/\d+ \| handle: ", t)[1:]
    return [(d.split("\n", 1)[0].strip(), d.split("\n", 1)[1]) for d in docs]


def conferir(n):
    docs = ler_lote(n)
    arq = os.path.join(BASE, "respostas", "lote_%03d.jsonl" % n)
    if not os.path.exists(arq):
        return None
    linhas = [x for x in open(arq, encoding="utf-8").read().splitlines() if x.strip()]
    prob = []
    if len(linhas) != len(docs):
        prob.append("linhas: %d de %d" % (len(linhas), len(docs)))
    n_ods = n_trecho_ruim = 0
    for i, (h, txt) in enumerate(docs):
        if i >= len(linhas):
            break
        try:
            r = json.loads(linhas[i])
        except ValueError as e:
            prob.append("%s: JSON invalido (%s)" % (h, e))
            continue
        if r.get("handle") != h:
            prob.append("linha %d: handle %s, esperado %s" % (i + 1, r.get("handle"), h))
        ods = r.get("ods") or []
        at = {a.get("ods"): a for a in r.get("atribuicoes") or []}
        if sorted(ods) != sorted(at):
            prob.append("%s: 'ods' %s difere das atribuicoes %s" % (h, ods, sorted(at)))
        for o in ods:
            a = at.get(o) or {}
            n_ods += 1
            for m in a.get("metas") or []:
                m = str(m).lower()
                if m not in METAS:
                    prob.append("%s: meta %s inexistente" % (h, m))
                elif METAS[m]["ods"] != o:
                    prob.append("%s: meta %s nao e do ODS %d" % (h, m, o))
            if not a.get("metas"):
                prob.append("%s: ODS %d sem meta" % (h, o))
            tr = norm(a.get("trecho"))
            if not tr or tr not in norm(txt):
                n_trecho_ruim += 1
                prob.append("%s: ODS %d trecho nao literal: %r" % (h, o, (a.get("trecho") or "")[:80]))
        trav = travar(ods, txt)
        if sorted(trav) != sorted(ods):
            prob.append("%s: trava removeria %s" % (h, sorted(set(ods) - set(trav))))
    return {"lote": n, "linhas": len(linhas), "esperado": len(docs), "ods_atribuidos": n_ods,
            "trechos_nao_literais": n_trecho_ruim, "problemas": prob}


if __name__ == "__main__":
    ns = [int(x) for x in sys.argv[1:]] or sorted(int(re.search(r"(\d+)", os.path.basename(f)).group(1))
                                                 for f in glob.glob(os.path.join(BASE, "respostas", "lote_*.jsonl")))
    for n in ns:
        r = conferir(n)
        if r is None:
            print("lote %03d: sem resposta" % n)
            continue
        print("lote %03d: %d/%d linhas, %d ODS, %d trechos nao literais, %d problemas" % (
            n, r["linhas"], r["esperado"], r["ods_atribuidos"], r["trechos_nao_literais"], len(r["problemas"])))
        for p in r["problemas"][:15]:
            print("   -", p)
