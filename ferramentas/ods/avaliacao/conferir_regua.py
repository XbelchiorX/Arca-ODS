# -*- coding: utf-8 -*-
"""Confere e junta os rotulos da regua ampliada (D29; dados/gabarito_claude_v5/rotulos_NN.json).

Checagens (cada problema sai listado; nada e corrigido sozinho):
  - todo item da amostra rotulado uma vez, com o handle exato, e nada a mais;
  - n de 1 a 18, sem ODS repetido no item; meta existente nas 180 metas e do mesmo ODS (3.b e do ODS 3);
  - trecho literal: aparece no texto entregue ao rotulador (espacos normalizados, sem diferenciar caixa).
Junta no formato do gabarito v4: gabarito_v5.json {"descricao", "itens": {handle: [ods]}, "detalhe": {...}}.
Uso: python ferramentas/ods/avaliacao/conferir_regua.py [--versao v6]
"""
import glob
import json
import os
import re
import sys
from collections import Counter

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
VERSAO = sys.argv[sys.argv.index("--versao") + 1] if "--versao" in sys.argv else "v5"   # v6: ODS raros
PASTA = os.path.join(RAIZ, "dados", "gabarito_claude_" + VERSAO)


def norm(s):
    s = (s or "").replace(" ", " ").replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip().casefold()


def main():
    amostra = json.load(open(os.path.join(PASTA, "amostra.json"), encoding="utf-8"))
    metas = set(re.findall(r"^\[(\d+\.[0-9a-z]+)\]", open(os.path.join(PASTA, "metas_completas.txt"),
                                                           encoding="utf-8").read(), re.M))
    detalhe, problemas, vistos = {}, [], Counter()
    for arq in sorted(glob.glob(os.path.join(PASTA, "rotulos_*.json"))):
        try:
            dados = json.load(open(arq, encoding="utf-8"))
        except ValueError as e:
            problemas.append("%s: JSON invalido (%s)" % (os.path.basename(arq), e))
            continue
        for h, r in dados.items():
            vistos[h] += 1
            if h not in amostra["textos"]:
                problemas.append("%s: %s nao esta na amostra" % (os.path.basename(arq), h))
                continue
            txt = norm(amostra["textos"][h])
            ns = [o.get("n") for o in r.get("ods", [])]
            if len(ns) != len(set(ns)):
                problemas.append("%s: ODS repetido %s" % (h, ns))
            for o in r.get("ods", []):
                n, meta, trecho = o.get("n"), str(o.get("meta", "")), o.get("trecho", "")
                if not isinstance(n, int) or not 1 <= n <= 18:
                    problemas.append("%s: n invalido %r" % (h, n))
                if meta not in metas or meta.split(".")[0] != str(n):
                    problemas.append("%s: meta %s nao e do ODS %s" % (h, meta, n))
                if not trecho or norm(trecho) not in txt:
                    problemas.append("%s: trecho nao literal (ODS %s): %s" % (h, n, trecho[:90]))
            detalhe[h] = r
    faltam = [h for h in amostra["itens"] if h not in vistos]
    duplos = [h for h, c in vistos.items() if c > 1]
    if faltam:
        problemas.append("faltam %d itens: %s" % (len(faltam), ", ".join(faltam[:15])))
    if duplos:
        problemas.append("rotulados mais de uma vez: %s" % ", ".join(duplos))
    por_ods = Counter(o["n"] for r in detalhe.values() for o in r.get("ods", []))
    print("rotulados: %d de %d; sem ODS: %d" % (len(detalhe), len(amostra["itens"]),
                                                 sum(1 for r in detalhe.values() if not r.get("ods"))))
    print("exemplos por ODS:", dict(sorted(por_ods.items())))
    print("problemas: %d" % len(problemas))
    for p in problemas:
        print("  -", p)
    if not faltam and not problemas:
        g = {"descricao": amostra.get("descricao", "") + " Rotulados as cegas, meta a meta, contra as 180 metas Ipea 2026.",
             "itens": {h: sorted({o["n"] for o in detalhe[h].get("ods", [])}) for h in amostra["itens"]},
             "detalhe": {h: detalhe[h] for h in amostra["itens"]}}
        json.dump(g, open(os.path.join(PASTA, "gabarito_%s.json" % VERSAO), "w", encoding="utf-8"), ensure_ascii=False,
                  indent=1)
        print("gravado: gabarito_%s.json" % VERSAO)
    return 1 if problemas or faltam else 0


if __name__ == "__main__":
    sys.exit(main())
