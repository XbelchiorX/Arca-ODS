# -*- coding: utf-8 -*-
"""Planilha para a responsavel ver o professor escolhido (D35: Qwen3.5-35B, prompt v3) item a item, ao lado dos
rotuladores A e B do gabarito v7. Le a resposta ja gravada pela regua (nao roda modelo).

Amostra: N itens sorteados (semente 20261029), intercalados por ODS do professor, mais os handles passados na linha
de comando. Saida: saidas/ods/teste_professor_qwen35.xlsx (nao sobrescreve sem --forcar).
Uso: python ferramentas/ods/avaliacao/amostra_professor_v7.py [N] [icict/123 ...]
"""
import glob
import json
import os
import random
import sys
from collections import defaultdict

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
V7 = os.path.join(RAIZ, "dados", "gabarito_v7")
PROF = os.path.join(RAIZ, "publicacoes", "artigo_ods", "resultados", "professor",
                    "comparacao_v3_Qwen3.5-35B-A3B-Q4_K_M_regua_metasnovas.json")
SAIDA = os.path.join(RAIZ, "saidas", "ods", "teste_professor_qwen35.xlsx")


def rotulos(r):
    out = {}
    for f in glob.glob(os.path.join(V7, "rotulos_" + r, "lote_*.jsonl")):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                x = json.loads(ln)
                out[x["handle"]] = x["ods"]
    return out


def fmt(lista):
    return "\n".join("ODS %s · meta %s — “%s”" % (o.get("n"), o.get("meta", ""), o.get("trecho", "")) for o in lista) \
        or "sem ODS"


def main():
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    if os.path.exists(SAIDA) and "--forcar" not in sys.argv:
        sys.exit("ja existe %s; nada foi sobrescrito" % SAIDA)
    args = [a for a in sys.argv[1:] if a != "--forcar"]
    n = int(args[0]) if args and args[0].isdigit() else 30
    pedidos = [a for a in args if a.startswith("icict/")]
    prof = json.load(open(PROF, encoding="utf-8"))["itens"]
    textos = json.load(open(os.path.join(V7, "amostra.json"), encoding="utf-8"))["itens"]
    A, B = rotulos("A"), rotulos("B")
    estratos = defaultdict(list)
    for h, d in prof.items():
        ns = sorted({o["n"] for o in d["modelo"] or []})
        estratos["sem ODS" if not ns else "so 3" if ns == [3] else "ODS %d" % max(set(ns) - {3})].append(h)
    rnd = random.Random(20261029)
    for k in sorted(estratos):
        rnd.shuffle(estratos[k])
    nomes = sorted(estratos)
    rnd.shuffle(nomes)
    ordem = [h for h in pedidos if h in prof]
    while len(ordem) < n + len(pedidos) and any(estratos.values()):
        for k in nomes:
            if estratos[k] and len(ordem) < n + len(pedidos):
                h = estratos[k].pop()
                if h not in ordem:
                    ordem.append(h)
    wb = Workbook()
    ws = wb.active
    ws.title = "Professor Qwen 35B"
    cab = ["Handle", "Texto entregue ao professor", "Professor Qwen3.5-35B (prompt v3)", "Rotulador A", "Rotulador B",
           "SUA AVALIAÇÃO do professor", "Observação"]
    ws.append(cab)
    topo = Alignment(wrap_text=True, vertical="top")
    for h in ordem:
        ws.append([h, textos[h]["texto"], fmt(prof[h]["modelo"] or []), fmt(A.get(h, [])), fmt(B.get(h, [])), None, None])
        ws.cell(row=ws.max_row, column=1).hyperlink = "https://arca.fiocruz.br/handle/" + h
    for c, w in enumerate([14, 90, 45, 45, 45, 20, 40], 1):
        ws.column_dimensions[ws.cell(row=1, column=c).column_letter].width = w
    amarelo = PatternFill("solid", fgColor="FFF2CC")
    for row in ws.iter_rows():
        for cel in row:
            cel.alignment = topo
    for r in range(2, ws.max_row + 1):
        ws.row_dimensions[r].height = 160
        for c in (6, 7):
            ws.cell(row=r, column=c).fill = amarelo
    for c in range(1, len(cab) + 1):
        ws.cell(row=1, column=c).font = Font(bold=True)
    dv = DataValidation(type="list", formula1='"Certo,Certo em parte,Errado"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add("F2:F%d" % ws.max_row)
    ws.freeze_panes = "C2"
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    wb.save(SAIDA)
    print("%d itens; %s" % (len(ordem), SAIDA))


if __name__ == "__main__":
    main()
