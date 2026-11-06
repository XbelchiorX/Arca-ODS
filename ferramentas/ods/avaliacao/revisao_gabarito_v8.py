# -*- coding: utf-8 -*-
"""Revisao humana do gabarito v8 (sem trecho; rotuladores A2 e B2, os 300 itens da regua dos testes v8).

  --gerar  planilha saidas/ods/revisao_gabarito_v8.xlsx: primeiro os itens em que A2 e B2 discordam, depois os que
           concordam (intercalados por ODS e sorteados, como no v7); com as respostas dos professores v8 que ja
           existirem (so para comparar). Com --forcar regera mantendo as linhas ja revisadas (copia da anterior).
  --ler    grava dados/gabarito_revisado_v8.json (so itens revisados) e revisao_humana_v8.md.
Uso: python ferramentas/ods/avaliacao/revisao_gabarito_v8.py --gerar | --ler
"""
import glob
import json
import os
import shutil
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from revisao_gabarito import _nums, _ns, ordenar  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, RAIZ)
V8 = os.path.join(RAIZ, "dados", "gabarito_v8")
XLSX = os.getenv("ODS_REVISAO_XLSX", os.path.join(RAIZ, "saidas", "ods", "revisao_gabarito_v8.xlsx"))   # a responsavel trabalha na copia _ate_20261030_110912
SAIDA_JSON = os.path.join(RAIZ, "dados", "gabarito_revisado_v8.json")
SAIDA_MD = os.path.join(RAIZ, "publicacoes", "artigo_ods", "resultados", "gabaritos", "revisao_humana_v8.md")
PROF = os.path.join(RAIZ, "publicacoes", "artigo_ods", "resultados", "professor")
OPCOES = ["A2 está certo", "B2 está certo", "Os dois estão certos", "Qwen está certo", "Nenhum (escreva ao lado)"]
# 02/11 (responsavel): coluna do professor Qwen 35B (50 metas candidatas, v8 tema + trecho, D43) ao lado de A2 e B2,
# com a opcao "Qwen está certo"; as decisoes anteriores vem de ODS_REVISAO_ANTERIOR (a planilha em que ela trabalha)
_P = os.path.join(RAIZ, "publicacoes", "artigo_ods", "resultados", "professor")
# 02/11: a responsavel escolheu o prompt v9 (descricao + trecho) com 50 candidatas para a coluna do Qwen
QWEN = os.path.join(_P, "comparacao_v9_Qwen3.5-35B-A3B-Q4_K_M_regua300_v9_50metas.json")
COL_QWEN = "Professor Qwen 35B (50 metas, prompt v9: descrição + trecho)"
QWEN8 = os.path.join(_P, "comparacao_v8_Qwen3.5-35B-A3B-Q4_K_M_regua300_v8tema_trecho_50metas.json")   # comparacao
COL_QWEN8 = "Professor Qwen 35B (50 metas, prompt v8: tema + trecho), só para comparar"
QWEN10 = os.path.join(_P, "comparacao_v10_Qwen3.5-35B-A3B-Q4_K_M_regua300_v10_50metas.json")   # 03/11: comparacao
COL_QWEN10 = "Professor Qwen 35B (50 metas, prompt v10: justificativa), só para comparar"
ANTERIOR = os.getenv("ODS_REVISAO_ANTERIOR", "")
DECISAO, CORRETOS, OBS = "SUA DECISÃO", "ODS corretos, se nenhum está certo (ex.: 3, 18 ou nenhum)", "Observação"


def rotulos(r):
    out = {}
    for f in glob.glob(os.path.join(V8, "rotulos_" + r, "lote_*.jsonl")):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                x = json.loads(ln)
                out[x["handle"]] = x["ods"]
    return out


_METAS = {}


def texto_meta(cod):
    """Texto inteiro da meta (META ONU / META IPEA, como os rotuladores receberam); conceitos ficam na aba Metas."""
    from arca.ods_professor import _ROT_V8, _partes_meta
    if not _METAS:
        _METAS.update(json.load(open(os.path.join(RAIZ, "dados", "ods_referencia", "metas_2026.json"), encoding="utf-8")))
    m = _METAS.get(cod)
    return "\n".join("  %s: %s" % (_ROT_V8[r], t) for r, t in _partes_meta(m) if r != "conceitos_ipea") if m else ""


def fmt(lista, tema=None):
    from arca.ods_correcao import VALOR     # nomes curtos, os mesmos gravados no Arca ("01 Erradicação da pobreza")
    s = "\n\n".join("ODS %s – %s · meta %s%s%s\n%s" % (o["n"], VALOR.get(o["n"], "   ")[3:], o.get("meta", ""),
                                                " — justificativa: " + o["justificativa"] if o.get("justificativa") else "",
                                                "\n  TRECHO: \"%s\"" % o["trecho"] if o.get("trecho") else "",
                                                texto_meta(o.get("meta", ""))) for o in lista)
    return (("TEMA: " + tema + "\n\n") if tema else "") + (s or "sem ODS")


def qwen(arq=QWEN):
    """ODS do professor Qwen (50 metas) nos 300: {handle: lista de {n, meta, trecho}} e os temas/descricoes."""
    d = json.load(open(arq, encoding="utf-8"))["itens"]
    return {h: x["modelo"] or [] for h, x in d.items()}, {h: x.get("tema") for h, x in d.items()}


def decisoes_anteriores():
    fonte = ANTERIOR or XLSX
    if not os.path.exists(fonte):
        return {}
    from openpyxl import load_workbook
    linhas = load_workbook(fonte, read_only=True)["Revisão"].iter_rows(values_only=True)
    cab = list(next(linhas))
    i = [cab.index(c) for c in (DECISAO, CORRETOS, OBS)]
    return {r[1]: [r[k] for k in i] for r in linhas if r[1] and any(r[k] for k in i)}


def gerar():
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    from arca.ods_professor import _ROT_V8, _partes_meta
    if os.path.exists(XLSX) and "--forcar" not in sys.argv:
        sys.exit("ja existe %s (pode ter revisao feita); nada foi sobrescrito" % XLSX)
    antes = decisoes_anteriores()
    if antes and os.path.exists(XLSX):     # planilha nova a partir de outra (ODS_REVISAO_ANTERIOR): nada a copiar
        copia = XLSX.replace(".xlsx", "_ate_%s.xlsx" % time.strftime("%Y%m%d_%H%M%S"))
        shutil.copy2(XLSX, copia)
        print("%d linhas ja revisadas mantidas; copia da anterior: %s" % (len(antes), copia))
    textos = json.load(open(os.path.join(V8, "amostra.json"), encoding="utf-8"))["itens"]
    A, B = rotulos("A2"), rotulos("B2")
    Q, temas_q = qwen()
    Q8, temas_q8 = qwen(QWEN8) if os.path.exists(QWEN8) else ({}, {})
    Q10, _t = qwen(QWEN10) if os.path.exists(QWEN10) else ({}, {})
    hs = sorted(set(A) & set(B))
    disc = [h for h in hs if _ns(A[h]) != _ns(B[h])]
    conc = [h for h in hs if _ns(A[h]) == _ns(B[h])]
    ordem = ordenar(disc, A, B, 20261030) + ordenar(conc, A, B, 20261031)
    cab = ["Ordem", "Handle", "A2 e B2", "Texto (título, resumo, palavras-chave)", "Rotulador A2 (ODS, meta)",
           "Rotulador B2 (ODS, meta)", COL_QWEN, DECISAO, CORRETOS, OBS] + ([COL_QWEN8] if Q8 else []) + ([COL_QWEN10] if Q10 else [])
    wb = Workbook()
    ws0 = wb.active
    ws0.title = "Leia primeiro"
    for linha in [
        "REVISÃO DO GABARITO DE ODS v8 (sem trecho; dois rotuladores de IA independentes, A2 e B2)",
        "",
        "Cada linha é um documento do Arca, dos 300 usados nos testes do professor. A2 e B2 atribuíram ODS às cegas,",
        "cada um sozinho, só pelo texto das metas (aba 'Metas'), com a mesma instrução do prompt v8 texto do professor.",
        "A coluna D é exatamente o texto que eles receberam. Nas colunas E e F, cada ODS atribuído vem com o texto",
        "inteiro da meta (META ONU e META IPEA); os CONCEITOS IPEA de cada meta estão na aba 'Metas (180)'.",
        "",
        "As primeiras %d linhas são os documentos em que A2 e B2 DISCORDAM: é onde a sua revisão mais importa." % len(disc),
        "Depois vêm os %d em que concordam. Dentro de cada parte a ordem é sorteada e intercalada por ODS." % len(conc),
        "",
        "Para cada linha, escolha na coluna SUA DECISÃO:",
        "  A2 está certo / B2 está certo / Os dois estão certos (quando concordam e estão certos) / Qwen está certo",
        "  Nenhum: escreva na coluna H os ODS corretos (ex.: 3, 18) ou 'nenhum'.",
        "A coluna G é o professor Qwen 35B (50 metas candidatas, prompt v9: descrição + trecho): a DESCRIÇÃO do",
        "documento que ele escreveu e, para cada ODS, a meta e o TRECHO copiado. Se ele estiver certo e A2/B2 não,",
        "escolha 'Qwen está certo'.",
        "",
        "Critério: só o texto das metas: o ODS vale quando o documento trata do que uma meta descreve.",
        "Não apague nem reordene linhas. O handle (coluna B) abre o item no Arca.",
    ]:
        ws0.append([linha])
    ws0.column_dimensions["A"].width = 120
    ws0["A1"].font = Font(bold=True, size=13)
    ws = wb.create_sheet("Revisão")
    ws.append(cab)
    for i, h in enumerate(ordem, 1):
        ws.append([i, h, "discordam" if h in disc else "concordam", textos[h]["texto"], fmt(A[h]), fmt(B[h]),
                   fmt(Q.get(h, []), "DESCRIÇÃO: " + temas_q[h] if temas_q.get(h) else None)] +
                  (antes.get(h) or [None, None, None]) + ([fmt(Q8.get(h, []), temas_q8.get(h))] if Q8 else []) +
                  ([fmt(Q10.get(h, []))] if Q10 else []))
        ws.cell(row=i + 1, column=2).hyperlink = "https://arca.fiocruz.br/handle/" + h
    for c, w in enumerate([7, 14, 11, 80, 55, 55, 65, 22, 22, 35, 60, 60], 1):
        ws.column_dimensions[ws.cell(row=1, column=c).column_letter].width = w
    topo = Alignment(wrap_text=True, vertical="top")
    amarelo, cinza = PatternFill("solid", fgColor="FFF2CC"), PatternFill("solid", fgColor="FCE4D6")
    for row in ws.iter_rows():
        for cel in row:
            cel.alignment = topo
    for c in range(1, len(cab) + 1):
        ws.cell(row=1, column=c).font = Font(bold=True)
    for r in range(2, ws.max_row + 1):
        ws.row_dimensions[r].height = 300
        for c in (8, 9, 10):
            ws.cell(row=r, column=c).fill = amarelo
        if ws.cell(row=r, column=3).value == "discordam":
            ws.cell(row=r, column=3).fill = cinza
    dv = DataValidation(type="list", formula1='"%s"' % ",".join(OPCOES), allow_blank=True)
    ws.add_data_validation(dv)
    dv.add("H2:H%d" % ws.max_row)
    ws.freeze_panes = "E2"
    ws.auto_filter.ref = "A1:%s%d" % (ws.cell(row=1, column=len(cab)).column_letter, ws.max_row)
    wm = wb.create_sheet("Metas (180)")
    wm.append(["Meta", "Texto (como os rotuladores receberam)"])
    for c, m in json.load(open(os.path.join(RAIZ, "dados", "ods_referencia", "metas_2026.json"), encoding="utf-8")).items():
        wm.append([c, "\n".join("%s: %s" % (_ROT_V8[r], t) for r, t in _partes_meta(m))])
    wm.column_dimensions["A"].width, wm.column_dimensions["B"].width = 8, 160
    for row in wm.iter_rows():
        for cel in row:
            cel.alignment = topo
    wm.freeze_panes = "A2"
    os.makedirs(os.path.dirname(XLSX), exist_ok=True)
    wb.active = 1
    wb.save(XLSX)
    print("%d itens (%d discordam, %d concordam), %d decisoes transferidas; %s" % (len(ordem), len(disc), len(conc),
                                                                               len(antes), XLSX))


def ler():
    from openpyxl import load_workbook
    linhas = load_workbook(XLSX, read_only=True)["Revisão"].iter_rows(values_only=True)
    cab = list(next(linhas))
    iD, iC, iO = (cab.index(c) for c in (DECISAO, CORRETOS, OBS))
    A, B = rotulos("A2"), rotulos("B2")
    Q = qwen()[0] if os.path.exists(QWEN) else {}
    rev, cont = {}, Counter()
    for r in linhas:
        h, dec = r[1], (r[iD] or "").strip()
        if not h or dec not in OPCOES:
            continue
        cont[dec] += 1
        certo = (_ns(A[h]) if dec.startswith("A2") else _ns(B[h]) if dec.startswith("B2") else
                 _ns(Q[h]) if dec.startswith("Qwen") else
                 sorted(set(_ns(A[h])) | set(_ns(B[h]))) if dec.startswith("Os dois") else sorted(_nums(r[iC])))
        rev[h] = {"revisado": certo, "A2": _ns(A[h]), "B2": _ns(B[h]), "decisao": dec, "observacao": r[iO] or ""}
    if not rev:
        sys.exit("nenhuma linha revisada ainda")
    json.dump({"descricao": "Gabarito v8 (sem trecho) revisado pela especialista; so itens revisados.",
               "itens": {h: v["revisado"] for h, v in rev.items()}, "detalhe": rev},
              open(SAIDA_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n = len(rev)
    L = ["# Revisão humana do gabarito v8", "", "Itens revisados: %d" % n, "", "| Decisão | Itens | % |", "|---|---|---|"] + \
        ["| %s | %d | %.1f%% |" % (o, cont[o], 100 * cont[o] / n) for o in OPCOES]
    os.makedirs(os.path.dirname(SAIDA_MD), exist_ok=True)
    open(SAIDA_MD, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    ler() if "--ler" in sys.argv else gerar()
