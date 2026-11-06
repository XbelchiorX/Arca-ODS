# -*- coding: utf-8 -*-
"""Revisao humana do gabarito v7 (D33): os rotuladores A e B lado a lado, para a especialista dizer quais ODS estao
certos. Declarado no artigo como "rotulado por IA (dois rotuladores independentes) e revisado por especialista".

  --gerar  planilha saidas/ods/revisao_gabarito_v7.xlsx, com as respostas do professor Qwen 35B (prompts v3 e v6,
           30 metas) nos 300 itens da regua, que vem primeiro. Com --forcar regera mantendo as linhas ja revisadas
           (e guarda copia da anterior). Ordem: primeiro os itens em que A e B discordam (onde a
           revisao mais importa), depois os que concordam; dentro de cada parte, intercalados por ODS e sorteados
           (semente 20261029), entao qualquer comeco e uma amostra equilibrada. Nunca sobrescreve (--forcar).
  --ler    le a planilha e grava dados/gabarito_revisado_v7.json (so itens revisados) e o resumo em
           publicacoes/artigo_ods/resultados/gabaritos/revisao_humana_v7.md.
Uso: python ferramentas/ods/avaliacao/revisao_gabarito.py --gerar | --ler
"""
import glob
import json
import os
import random
import re
import sys
from collections import Counter, defaultdict

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
V7 = os.path.join(RAIZ, "dados", "gabarito_v7")
XLSX = os.path.join(RAIZ, "saidas", "ods", "revisao_gabarito_v7.xlsx")
SAIDA_JSON = os.path.join(RAIZ, "dados", "gabarito_revisado_v7.json")
SAIDA_MD = os.path.join(RAIZ, "publicacoes", "artigo_ods", "resultados", "gabaritos", "revisao_humana_v7.md")
OPCOES = ["A está certo", "B está certo", "Os dois estão certos", "Professor v3 está certo",
          "Professor v6 está certo", "Nenhum (escreva ao lado)"]
ANTIGAS = {"Nenhum dos dois (escreva ao lado)": "Nenhum (escreva ao lado)"}   # planilha de 29/10
PROF = os.path.join(RAIZ, "publicacoes", "artigo_ods", "resultados", "professor")
PROFESSORES = [("Professor Qwen 35B, prompt v3, 30 metas (só nos 300 da régua)",
                "comparacao_v3_Qwen3.5-35B-A3B-Q4_K_M_regua_30.json"),
               ("Professor Qwen 35B, prompt v6, 30 metas (só nos 300 da régua)",
                "comparacao_v6_Qwen3.5-35B-A3B-Q4_K_M_regua_30.json")]
DECISAO, CORRETOS, OBS = "SUA DECISÃO", "ODS corretos, se nenhum está certo (ex.: 3, 18 ou nenhum)", "Observação"
CORRETOS_ANTIGO = "ODS corretos, se nenhum dos dois (ex.: 3, 18 ou nenhum)"
CAB = ["Ordem", "Handle", "A e B", "Texto (título, resumo, palavras-chave)", "Rotulador A (ODS, meta, trecho)",
       "Rotulador B (ODS, meta, trecho)", DECISAO, CORRETOS, OBS] + [n for n, _ in PROFESSORES]


def rotulos(r):
    out = {}
    for f in glob.glob(os.path.join(V7, "rotulos_" + r, "lote_*.jsonl")):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                x = json.loads(ln)
                out[x["handle"]] = x["ods"]
    return out


def _ns(lista):
    return sorted({o["n"] for o in lista})


def _norm(s):
    s = str(s or "").translate(str.maketrans("‘’“”", "''\"\""))
    return re.sub(r"\s+", " ", s).strip().lower()


def fmt(lista, texto=None):
    """Com o texto do documento, marca o trecho que nao esta nele (copiado da meta ou inventado)."""
    return "\n".join("ODS %s · meta %s — “%s”%s" % (
        o["n"], o.get("meta", ""), o.get("trecho", ""),
        " [TRECHO NÃO ESTÁ NO DOCUMENTO]" if texto is not None and _norm(o.get("trecho")) not in _norm(texto) else "")
        for o in lista) or "sem ODS"


def professores():
    out = {}
    for nome, arq in PROFESSORES:
        f = os.path.join(PROF, arq)
        if os.path.exists(f):
            out[nome] = {h: x["modelo"] for h, x in json.load(open(f, encoding="utf-8"))["itens"].items()}
    return out


def decisoes_anteriores():
    """Linhas ja revisadas na planilha atual, para nao perder trabalho ao regerar."""
    if not os.path.exists(XLSX):
        return {}
    from openpyxl import load_workbook
    linhas = load_workbook(XLSX, read_only=True)["Revisão"].iter_rows(values_only=True)
    cab = [CORRETOS if c == CORRETOS_ANTIGO else c for c in next(linhas)]
    i = [cab.index(c) for c in (DECISAO, CORRETOS, OBS)]
    out = {r[1]: [r[k] for k in i] for r in linhas if r[1] and any(r[k] for k in i)}
    for v in out.values():
        v[0] = ANTIGAS.get(v[0], v[0])
    return out


def ordenar(hs, A, B, semente):
    estratos = defaultdict(list)
    for h in hs:
        ns = set(_ns(A[h])) | set(_ns(B[h]))
        estratos["sem ODS" if not ns else "so 3" if ns == {3} else "ODS %d" % min(ns - {3})].append(h)
    rnd = random.Random(semente)
    for k in sorted(estratos):
        rnd.shuffle(estratos[k])
    nomes = sorted(estratos)
    rnd.shuffle(nomes)
    ordem = []
    while any(estratos.values()):
        for k in nomes:
            if estratos[k]:
                ordem.append(estratos[k].pop())
    return ordem


def gerar():
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    if os.path.exists(XLSX) and "--forcar" not in sys.argv:
        sys.exit("ja existe %s (pode ter revisao feita); nada foi sobrescrito" % XLSX)
    antes = decisoes_anteriores()
    if antes:
        import shutil
        import time
        copia = XLSX.replace(".xlsx", "_ate_%s.xlsx" % time.strftime("%Y%m%d_%H%M%S"))
        shutil.copy2(XLSX, copia)
        print("%d linhas ja revisadas mantidas; copia da planilha anterior: %s" % (len(antes), copia))
    textos = json.load(open(os.path.join(V7, "amostra.json"), encoding="utf-8"))["itens"]
    A, B = rotulos("A"), rotulos("B")
    prof = professores()
    hs = sorted(set(A) & set(B))
    regua = set.intersection(*(set(p) for p in prof.values())) if prof else set()
    disc = [h for h in hs if _ns(A[h]) != _ns(B[h])]
    conc = [h for h in hs if _ns(A[h]) == _ns(B[h])]
    # primeiro os itens em que o professor foi medido (300 da regua), depois o resto; discordantes antes
    ordem = (ordenar([h for h in disc if h in regua], A, B, 20261029) +
             ordenar([h for h in conc if h in regua], A, B, 20261030) +
             ordenar([h for h in disc if h not in regua], A, B, 20261029) +
             ordenar([h for h in conc if h not in regua], A, B, 20261030))
    wb = Workbook()
    ws0 = wb.active
    ws0.title = "Leia primeiro"
    for linha in [
        "REVISÃO DO GABARITO DE ODS v7 (dois rotuladores de IA independentes, A e B)",
        "",
        "Cada linha é um documento do Arca. A e B atribuíram ODS às cegas, cada um sozinho, só pelo texto das metas",
        "(aba 'Metas'). A coluna D é exatamente o texto que eles receberam.",
        "",
        "As primeiras %d linhas são os documentos em que o professor (Qwen 35B) foi medido; as colunas J e K" % len(regua),
        "mostram as respostas dele com os prompts v3 e v6 (só para comparar, não são gabarito). Dentro delas,",
        "primeiro os documentos em que A e B DISCORDAM, depois os que concordam. Depois vêm os demais",
        "documentos, na mesma lógica (no total, %d discordam e %d concordam)." % (len(disc), len(conc)),
        "Dentro de cada parte a ordem é sorteada e intercalada por ODS: revise de cima para baixo e pare quando",
        "quiser; qualquer começo é uma amostra equilibrada.",
        "",
        "Para cada linha, escolha na coluna SUA DECISÃO:",
        "  A está certo / B está certo / Os dois estão certos (quando concordam e estão certos)",
        "  Professor v3 está certo / Professor v6 está certo (só nas linhas em que há resposta do professor)",
        "  Nenhum: escreva na coluna H os ODS corretos (ex.: 3, 18) ou 'nenhum'.",
        "Nas colunas do professor, [TRECHO NÃO ESTÁ NO DOCUMENTO] marca trecho que não aparece no texto",
        "(em geral copiado do texto da meta).",
        "",
        "Critério: só o texto das metas (aba 'Metas'): o ODS vale quando o documento trata do que uma meta descreve.",
        "Não apague nem reordene linhas. O handle (coluna B) abre o item no Arca.",
    ]:
        ws0.append([linha])
    ws0.column_dimensions["A"].width = 120
    ws0["A1"].font = Font(bold=True, size=13)
    ws = wb.create_sheet("Revisão")
    ws.append(CAB)
    for i, h in enumerate(ordem, 1):
        ws.append([i, h, "discordam" if h in disc else "concordam", textos[h]["texto"], fmt(A[h]), fmt(B[h])] +
                  (antes.get(h) or [None, None, None]) +
                  [fmt(p[h] or [], textos[h]["texto"]) if h in p else "" for p in prof.values()])
        ws.cell(row=i + 1, column=2).hyperlink = "https://arca.fiocruz.br/handle/" + h
    for c, w in enumerate([7, 14, 11, 80, 45, 45, 22, 22, 35] + [45] * len(prof), 1):
        ws.column_dimensions[ws.cell(row=1, column=c).column_letter].width = w
    topo = Alignment(wrap_text=True, vertical="top")
    amarelo, cinza = PatternFill("solid", fgColor="FFF2CC"), PatternFill("solid", fgColor="FCE4D6")
    for row in ws.iter_rows():
        for cel in row:
            cel.alignment = topo
    for c in range(1, len(CAB) + 1):
        ws.cell(row=1, column=c).font = Font(bold=True)
    for r in range(2, ws.max_row + 1):
        ws.row_dimensions[r].height = 150
        for c in (7, 8, 9):
            ws.cell(row=r, column=c).fill = amarelo
        if ws.cell(row=r, column=3).value == "discordam":
            ws.cell(row=r, column=3).fill = cinza
    dv = DataValidation(type="list", formula1='"%s"' % ",".join(OPCOES), allow_blank=True)
    ws.add_data_validation(dv)
    dv.add("G2:G%d" % ws.max_row)
    ws.freeze_panes = "E2"
    ws.auto_filter.ref = "A1:%s%d" % (ws.cell(row=1, column=len(CAB)).column_letter, ws.max_row)
    wm = wb.create_sheet("Metas (180)")
    wm.append(["Meta", "ONU", "Brasil (Ipea 2026)", "Conceitos (Ipea 2026)"])
    for c, m in json.load(open(os.path.join(RAIZ, "dados", "ods_referencia", "metas_2026.json"), encoding="utf-8")).items():
        wm.append([c, m.get("onu") or "", m.get("brasil") or "", m.get("conceitos") or ""])
    for col, w in zip("ABCD", (8, 60, 60, 90)):
        wm.column_dimensions[col].width = w
    for row in wm.iter_rows():
        for cel in row:
            cel.alignment = topo
    wm.freeze_panes = "A2"
    os.makedirs(os.path.dirname(XLSX), exist_ok=True)
    wb.active = 1
    wb.save(XLSX)
    print("%d itens (%d discordam, %d concordam); %s" % (len(ordem), len(disc), len(conc), XLSX))


def _nums(s):
    return {int(n) for n in re.findall(r"\b(1[0-8]|[1-9])\b", str(s or ""))}


def ler():
    from openpyxl import load_workbook
    ws = load_workbook(XLSX, read_only=True)["Revisão"]
    A, B = rotulos("A"), rotulos("B")
    prof = {n.split(",")[1].strip().replace("prompt ", "Professor "): {h: _ns(v or []) for h, v in p.items()}
            for n, p in professores().items()}   # "Professor v3", "Professor v6"
    rev, cont = {}, Counter()
    linhas = ws.iter_rows(values_only=True)
    cab = [CORRETOS if c == CORRETOS_ANTIGO else c for c in next(linhas)]
    iD, iC, iO = (cab.index(c) for c in (DECISAO, CORRETOS, OBS))
    for r in linhas:
        h, dec = r[1], ANTIGAS.get((r[iD] or "").strip(), (r[iD] or "").strip())
        if not h or dec not in OPCOES:
            continue
        cont[dec] += 1
        if dec.startswith("Professor"):
            p = prof.get(dec.replace(" está certo", ""), {})
            if h not in p:
                print("aviso: %s marcado '%s', mas o professor nao rodou nesse item; ignorado" % (h, dec))
                cont[dec] -= 1
                continue
            certo = p[h]
        elif dec.startswith("A"):
            certo = _ns(A[h])
        elif dec.startswith("B"):
            certo = _ns(B[h])
        elif dec.startswith("Os dois"):
            certo = sorted(set(_ns(A[h])) | set(_ns(B[h])))
        else:
            certo = sorted(_nums(r[iC]))
        rev[h] = {"revisado": certo, "A": _ns(A[h]), "B": _ns(B[h]), "decisao": dec, "observacao": r[iO] or ""}
    if not rev:
        sys.exit("nenhuma linha revisada ainda")
    json.dump({"descricao": "Gabarito v7 revisado pela especialista; so itens revisados.",
               "itens": {h: v["revisado"] for h, v in rev.items()}, "detalhe": rev},
              open(SAIDA_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n = len(rev)
    L = ["# Revisão humana do gabarito v7", "", "Itens revisados: %d" % n, "",
         "| Decisão | Itens | % |", "|---|---|---|"] + \
        ["| %s | %d | %.1f%% |" % (o, cont[o], 100 * cont[o] / n) for o in OPCOES]
    for nome, rot in (("A", A), ("B", B)):
        tp = sum(len(set(_ns(rot[h])) & set(v["revisado"])) for h, v in rev.items())
        pa = sum(len(_ns(rot[h])) for h in rev)
        pr = sum(len(v["revisado"]) for v in rev.values())
        L.append("\nRotulador %s contra a revisão: precisão %.3f, recall %.3f" % (nome, tp / max(pa, 1), tp / max(pr, 1)))
    os.makedirs(os.path.dirname(SAIDA_MD), exist_ok=True)
    open(SAIDA_MD, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    ler() if "--ler" in sys.argv else gerar()
