# -*- coding: utf-8 -*-
"""Planilha de conferencia humana do professor (D21): N itens sorteados do acervo inteiro, com os rotulos JA
GUARDADOS da rodada (cache/ods_professor.json; o Gemma nao e chamado de novo). Nada e cortado: texto entregue
ao professor e texto das metas inteiros. Resposta do Gemma como veio, sem trava depois (D24).
Uso: python ferramentas/ods/avaliacao/planilha_revisao_professor.py [N=1000]
"""
import json
import os
import random
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, RAIZ)
from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Alignment, Font, PatternFill  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402
from arca import config, ods_correcao as C, ods_metabusca as MB, ods_professor as P, ods_texto as T  # noqa: E402
from arca.decs_acervo import carregar_acervo  # noqa: E402

SEMENTE = 20261010


def main(n):
    ac = carregar_acervo()
    rot = P.carregar_cache()
    metas = MB.metas()
    cur = {}
    arq = os.path.join(config.CACHE, "ods_curadoria_arquivos.json")
    if os.path.exists(arq):
        with open(arq, encoding="utf-8") as f:
            cur = json.load(f)
    validos = sorted(h for h in ac if rot.get(h, {}).get("ods") is not None and rot[h].get("prompt") in P.PROMPTS_ACEITOS)
    hs = random.Random(SEMENTE).sample(validos, n)
    wb = Workbook()
    ws = wb.active
    ws.title = "Revisao %d" % n
    cab = ["#", "Link ARCA", "Título", "Texto entregue ao Gemma (INTEIRO)", "ODS do Gemma",
           "Meta escolhida (ONU + Brasil Ipea 2026, INTEIRO)", "ODS do catalogador (atual no ARCA)",
           "Texto vai mudar? (OCR/vídeo/restrito)", "Você concorda? (S/N/Parcial)", "ODS que você daria", "Comentário"]
    ws.append(cab)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F4E79")
    for i, h in enumerate(hs, 1):
        txt = T.texto_professor(ac[h])
        r = rot[h]["ods"]
        itens = r                                  # resposta do Gemma como veio (D24: sem trava)
        ods_s = "\n".join(C.VALOR[o["n"]] for o in itens) or "(nenhum)"
        mts = "\n\n".join("%s: %s" % (o["meta"], MB.texto_metas(metas[o["meta"].lower()]))
                          if (o.get("meta") or "").lower() in metas else "ODS %d: (meta nao informada)" % o["n"]
                          for o in itens)
        muda = {"so_imagem": "sim (OCR)", "video_audio": "sim (transcrição)",
                "ok_com_texto": "sim (PDF restrito, lido com login)"}.get(cur.get(h, {}).get("categoria"), "")
        ws.append([i, "https://arca.fiocruz.br/handle/" + h, T._escolher(ac[h].get("titulos"), "pt"), txt, ods_s, mts,
                   "\n".join(C.VALOR.get(o, str(o)) for o in C.humano(ac[h])) or "(vazio)", muda, "", "", ""])
        ws.cell(row=i + 1, column=2).hyperlink = "https://arca.fiocruz.br/handle/" + h
    for col, w in zip("ABCDEFGHIJK", (5, 22, 40, 90, 28, 80, 26, 16, 14, 18, 35)):
        ws.column_dimensions[col].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    dv = DataValidation(type="list", formula1='"S,N,Parcial"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add("I2:I%d" % (n + 1))
    ws.freeze_panes = "D2"
    ws.auto_filter.ref = "A1:K%d" % (n + 1)
    leg = wb.create_sheet("Leia")
    for k, t in enumerate([
            "%d documentos sorteados ao acaso do acervo inteiro (semente %d), entre os %d rotulados pelo Gemma." % (n, SEMENTE, len(validos)),
            "Professor: Gemma 4 26B, prompt versão 2. Rótulos da rodada de 06–10/10/2026, exatamente como o Gemma respondeu (nenhuma trava depois).",
            "Coluna D: o texto exatamente como foi entregue ao Gemma (com o resumo gerado do PDF quando houve). Nada cortado.",
            "Coluna F: o texto inteiro da meta escolhida. Coluna G: o que está hoje no ARCA (catalogador), só para comparação.",
            "Coluna H: itens cujo texto ainda vai mudar (OCR, transcrição de vídeo, PDF restrito lido com login) e serão rotulados de novo.",
            "Preencha I (S/N/Parcial), J (ODS que você daria) e K (comentário). Não precisa fazer todos: o que você fizer já entra na conta."], 1):
        leg.cell(row=k, column=1, value=t)
    leg.column_dimensions["A"].width = 150
    pasta = os.path.join(config.SAIDAS, "ods")
    saida = os.path.join(pasta, "revisao_professor_%d.xlsx" % n)
    wb.save(saida)
    with open(os.path.join(pasta, "revisao_professor_%d_rotulos.json" % n), "w", encoding="utf-8") as f:
        json.dump({h: rot[h] for h in hs}, f, ensure_ascii=False, indent=1)
    print("OK", saida)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1000)
