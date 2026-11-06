# -*- coding: utf-8 -*-
"""Backup do dc.subject.ods de TODOS os itens do ARCA, lido ao vivo da API (so leitura).

Saida 1 (restauravel pelo DSpace, "Importar metadados" / metadata-import):
    id (uuid do item), dc.subject.ods[idioma]..., dc.date.accessioned — valores multiplos com "||";
    celula vazia = item sem ODS (na importacao, apaga o que tiver sido gravado depois).
Saida 2 (para ler): handle, titulo, os mesmos valores com "||", data de entrada.
Uso:  python ferramentas/ods/backup/backup_ods.py [rotulo]
"""
import csv
import os
import sys
from collections import defaultdict
from datetime import datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, RAIZ)
os.environ["ARCA_SOMENTE_LEITURA"] = "sim"
from arca import config, dspace  # noqa: E402

CAMPO = "dc.subject.ods"


def main(rotulo):
    cli = dspace.conectar()
    itens, idiomas = [], set()
    params = {"query": "*:*", "dsoType": "ITEM", "size": 100, "page": 0}
    total = 1
    while params["page"] < total:
        sr = cli.get("/discover/search/objects", params=params)["_embedded"]["searchResult"]
        total = int(sr["page"]["totalPages"])
        for o in sr["_embedded"].get("objects", []):
            obj = o["_embedded"]["indexableObject"]
            if obj.get("type") != "item":
                continue
            md = obj.get("metadata") or {}
            vals = defaultdict(list)
            for x in md.get(CAMPO) or []:
                lang = x.get("language") or ""
                vals[lang].append(x["value"])
                idiomas.add(lang)
            tit = ((md.get("dc.title") or [{}])[0]).get("value", "")
            ent = "||".join(x["value"] for x in md.get("dc.date.accessioned") or [])
            itens.append((obj["uuid"], obj.get("handle", ""), tit, vals, ent))
        params["page"] += 1
        if params["page"] % 50 == 0:
            print("  pagina %d/%d (%d itens)" % (params["page"], total, len(itens)), flush=True)
    langs = sorted(idiomas)
    col = lambda l: CAMPO + ("[%s]" % l if l else "")
    pasta = os.path.join(config.SAIDAS, "ods", "backup")
    os.makedirs(pasta, exist_ok=True)
    data = datetime.now().strftime("%Y-%m-%d_%H%M")
    f1 = os.path.join(pasta, "backup_ods_%s_%s_IMPORTAVEL_DSPACE.csv" % (rotulo, data))
    f2 = os.path.join(pasta, "backup_ods_%s_%s_LEITURA.csv" % (rotulo, data))
    with open(f1, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id"] + [col(l) for l in langs] + ["dc.date.accessioned"])
        for u, h, t, v, e in itens:
            w.writerow([u] + ["||".join(v.get(l, [])) for l in langs] + [e])
    with open(f2, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["handle", "id", "titulo", CAMPO + " (todos os idiomas)", "idiomas", "dc.date.accessioned"])
        for u, h, t, v, e in itens:
            w.writerow([h, u, t, "||".join(x for l in langs for x in v.get(l, [])),
                        "||".join(l or "(sem)" for l in langs if v.get(l)), e])
    com = sum(1 for x in itens if x[3])
    print("OK: %d itens, %d com ODS, idiomas %s\n%s\n%s" % (len(itens), com, langs, f1, f2), flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "antes_ipea2026")
