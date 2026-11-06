# -*- coding: utf-8 -*-
"""Revisao humana do gabarito Sol + GPT-6 (500 registros; decisao da responsavel, 04/11/2026, D44).

Substitui A2 e B2 na planilha saidas/ods/revisao_gabarito_v8_qwen.xlsx (mesmo arquivo, ela revisa sempre nele).
  --gerar  500 linhas: primeiro as ja revisadas, depois as que o gabarito e o Qwen v8 discordam, depois as que
           concordam. Mantem as decisoes (copia da anterior em saidas/ods/copias/). Exige o arquivo fechado no Excel.
  --ler    grava dados/gabarito_revisado_500.json (so itens revisados).
"""
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import revisao_gabarito_v8 as V8  # noqa: E402
from revisao_gabarito import _nums, _ns, ordenar  # noqa: E402

RAIZ, P = V8.RAIZ, V8.PROF
XLSX = os.path.join(RAIZ, "saidas", "ods", "revisao_gabarito_v8_qwen.xlsx")
GAB = os.path.join(RAIZ, "dados", "gabarito_sol", "gabarito_500.json")
TEXTOS = os.path.join(RAIZ, "dados", "gabarito_sol", "amostra.json")
SAIDA = os.path.join(RAIZ, "dados", "gabarito_revisado_500.json")
ARQ = "comparacao_%s_Qwen3.5-35B-A3B-Q4_K_M_regua500_%s_50metas.json"
QW = [("v8", "v8tema_trecho", "tema + trecho"), ("v9", "v9", "descrição + trecho"), ("v10", "v10", "justificativa")]
COL_GAB = "Gabarito Sol + GPT-6 (ODS, meta)"
DECISAO, CORRETOS, OBS = V8.DECISAO, V8.CORRETOS, V8.OBS
JA = "Revisado antes (ODS ao lado)"
OPCOES = ["Gabarito está certo", "Qwen v8 está certo", "Qwen v9 está certo", "Qwen v10 está certo",
          "Nenhum (escreva ao lado)", JA]


def gabarito():
    g = json.load(open(GAB, encoding="utf-8"))
    metas = {h: [{"n": int(m.split(".")[0]), "meta": m} for m in v] for h, v in g["metas"].items()}
    return metas, g["modelo"]


def qwens():
    return {v: V8.qwen(os.path.join(P, ARQ % (v, r))) for v, r, _d in QW}


def decisoes(fonte):
    """{handle: (decisao, corretos, obs)} da planilha antiga (colunas A2/B2) ou desta (ja no formato novo)."""
    from openpyxl import load_workbook
    linhas = load_workbook(fonte, read_only=True)["Revisão"].iter_rows(values_only=True)
    cab = list(next(linhas))
    iD, iC, iO = (cab.index(c) for c in (DECISAO, CORRETOS, OBS))
    velha = "Rotulador A2 (ODS, meta)" in cab
    A, B = (V8.rotulos("A2"), V8.rotulos("B2")) if velha else ({}, {})
    Q9 = V8.qwen()[0] if velha else {}
    out = {}
    for r in linhas:
        h, dec, cor, obs = r[1], (r[iD] or "").strip(), r[iC], r[iO]
        if not h or not (dec or cor or obs):
            continue
        if velha and dec:
            ods = (_ns(A[h]) if dec.startswith("A2") else _ns(B[h]) if dec.startswith("B2") else
                   _ns(Q9[h]) if dec.startswith("Qwen") else
                   sorted(set(_ns(A[h])) | set(_ns(B[h]))) if dec.startswith("Os dois") else sorted(_nums(cor)))
            cor = ", ".join(map(str, sorted(ods))) or "nenhum"
            obs = "[decisão original: %s]%s" % (dec, " " + obs if obs else "")
            dec = JA
        out[h] = (dec or None, cor, obs)
    return out


def gerar():
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    from arca.ods_professor import _ROT_V8, _partes_meta
    trava = os.path.join(os.path.dirname(XLSX), "~$" + os.path.basename(XLSX))
    if os.path.exists(trava):
        sys.exit("planilha aberta no Excel; nada foi feito")
    antes = decisoes(XLSX)
    pasta = os.path.join(os.path.dirname(XLSX), "copias")
    os.makedirs(pasta, exist_ok=True)
    copia = os.path.join(pasta, "revisao_gabarito_v8_qwen_ate_%s.xlsx" % time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(XLSX, copia)
    json.dump(antes, open(copia.replace(".xlsx", "_decisoes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    G, modelo = gabarito()
    Q = qwens()
    textos = json.load(open(TEXTOS, encoding="utf-8"))["itens"]
    ja = [h for h in antes if h in G]
    resto = [h for h in G if h not in antes]
    q8 = Q["v8"][0]
    disc = [h for h in resto if set(_ns(G[h])) != set(_ns(q8.get(h, [])))]
    conc = [h for h in resto if h not in disc]
    vz = {h: q8.get(h, []) for h in G}
    ordem = ja + ordenar(disc, G, vz, 20261104) + ordenar(conc, G, vz, 20261105)
    cab = ["Ordem", "Handle", "Gabarito x Qwen v8", "Texto (título, resumo, palavras-chave)", "Modelo do gabarito", COL_GAB]
    cab += ["Qwen 35B prompt %s (%s), 50 metas" % (v, d) for v, _r, d in QW] + [DECISAO, CORRETOS, OBS]
    wb = Workbook()
    ws0 = wb.active
    ws0.title = "Leia primeiro"
    for linha in [
        "REVISÃO DO GABARITO DE ODS: Sol + GPT-6 (500 registros)",
        "",
        "O gabarito tem 165 registros do GPT-6.1 Sol e 335 do GPT-6 (Copilot, sem Work IQ, só o texto das 180 metas).",
        "A coluna E diz qual modelo classificou cada registro. Os dois não classificaram nenhum registro em comum.",
        "",
        "Primeiro vêm as %d linhas que você já revisou, com as suas respostas guardadas." % len(ja),
        "Depois, %d registros em que o gabarito e o Qwen v8 discordam, e por fim %d em que concordam." % (len(disc), len(conc)),
        "",
        "Para cada linha, escolha SUA DECISÃO: Gabarito está certo / Qwen v8, v9 ou v10 está certo /",
        "Nenhum (escreva ao lado os ODS corretos, ex.: 3, 18, ou 'nenhum').",
        "",
        "Critério: só o texto das metas: o ODS vale quando o documento trata do que uma meta descreve.",
        "Não apague nem reordene linhas. O handle (coluna B) abre o item no Arca.",
    ]:
        ws0.append([linha])
    ws0.column_dimensions["A"].width = 120
    ws0["A1"].font = Font(bold=True, size=13)
    ws = wb.create_sheet("Revisão")
    ws.append(cab)
    rot = {"sol": "GPT-6.1 Sol", "gpt6": "GPT-6"}
    for i, h in enumerate(ordem, 1):
        cols = []
        for v, _r, _d in QW:
            q, t = Q[v]
            cols.append(V8.fmt(q[h], t.get(h)) if h in q else "(não rodou neste registro)")
        est = "já revisado" if h in antes else "discordam" if h in disc else "concordam"
        ws.append([i, h, est, textos[h]["texto"], rot[modelo[h]], V8.fmt(G[h])] + cols + list(antes.get(h) or (None, None, None)))
        ws.cell(row=i + 1, column=2).hyperlink = "https://arca.fiocruz.br/handle/" + h
    for c, w in enumerate([7, 14, 12, 80, 12, 55, 60, 60, 60, 22, 22, 35], 1):
        ws.column_dimensions[ws.cell(row=1, column=c).column_letter].width = w
    topo = Alignment(wrap_text=True, vertical="top")
    amarelo, laranja = PatternFill("solid", fgColor="FFF2CC"), PatternFill("solid", fgColor="FCE4D6")
    for row in ws.iter_rows():
        for cel in row:
            cel.alignment = topo
    for c in range(1, len(cab) + 1):
        ws.cell(row=1, column=c).font = Font(bold=True)
    for r in range(2, ws.max_row + 1):
        ws.row_dimensions[r].height = 300
        for c in (10, 11, 12):
            ws.cell(row=r, column=c).fill = amarelo
        if ws.cell(row=r, column=3).value == "discordam":
            ws.cell(row=r, column=3).fill = laranja
    dv = DataValidation(type="list", formula1='"%s"' % ",".join(OPCOES), allow_blank=True)
    ws.add_data_validation(dv)
    dv.add("J2:J%d" % ws.max_row)
    ws.freeze_panes = "E2"
    ws.auto_filter.ref = "A1:L%d" % ws.max_row
    wm = wb.create_sheet("Metas (180)")
    wm.append(["Meta", "Texto"])
    for c, m in json.load(open(os.path.join(RAIZ, "dados", "ods_referencia", "metas_2026.json"), encoding="utf-8")).items():
        wm.append([c, "\n".join("%s: %s" % (_ROT_V8[r], t) for r, t in _partes_meta(m) if r != "conceitos_ipea")])
    wm.column_dimensions["A"].width, wm.column_dimensions["B"].width = 8, 160
    for row in wm.iter_rows():
        for cel in row:
            cel.alignment = topo
    wm.freeze_panes = "A2"
    wb.active = 1
    wb.save(XLSX)
    maior = max(len(str(c.value or "")) for row in ws.iter_rows() for c in row)
    print("%d linhas: %d revisadas, %d discordam, %d concordam; maior celula %d caracteres; copia: %s"
          % (len(ordem), len(ja), len(disc), len(conc), maior, copia))


def ler():
    from openpyxl import load_workbook
    linhas = load_workbook(XLSX, read_only=True)["Revisão"].iter_rows(values_only=True)
    cab = list(next(linhas))
    iD, iC, iO = (cab.index(c) for c in (DECISAO, CORRETOS, OBS))
    G, _m = gabarito()
    Q = qwens()
    itens, det = {}, {}
    for r in linhas:
        h, dec = r[1], (r[iD] or "").strip()
        if not h or dec not in OPCOES:
            continue
        if dec.startswith("Gabarito"):
            ods = _ns(G[h])
        elif dec.startswith("Qwen"):
            ods = _ns(Q[dec.split()[1]][0].get(h, []))
        else:
            ods = sorted(_nums(r[iC]))
        itens[h] = sorted(ods)
        det[h] = {"decisao": dec, "observacao": r[iO] or ""}
    json.dump({"descricao": "Gabarito Sol + GPT-6 revisado pela especialista; so itens revisados.", "itens": itens, "detalhe": det},
              open(SAIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(itens), "itens revisados ->", SAIDA)


if __name__ == "__main__":
    ler() if "--ler" in sys.argv else gerar()
