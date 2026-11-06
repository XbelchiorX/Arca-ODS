# -*- coding: utf-8 -*-
"""Planilha de curadoria manual dos ARQUIVOS (so leitura, COM o login do responsavel no Brave: so GET): itens cujo texto completo nao pode ser lido.

Para cada item sem resumo/resumo curto em que o resumo do PDF (D10) nao saiu, confere com o login cada arquivo
do bundle ORIGINAL e classifica:
  restrito       — o servidor nega o arquivo mesmo com o login (401/403);
  corrompido     — o servidor entrega, mas nao e PDF valido ou nao abre;
  so_imagem      — PDF abre, mas sem camada de texto (escaneado): vai para OCR (D23);
  video_audio    — so video/audio: vai para transcricao (D23);
  sem_arquivo    — item sem nenhum arquivo;
  outros_formatos— so imagens, slides, docx, zip...;
  item_inacessivel — nem a lista de arquivos e acessivel (item privado/retirado?).
Saida: saidas/ods/curadoria/curadoria_arquivos.xlsx
"""
import collections
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, RAIZ)
from arca import config, dspace, ods_textocompleto as TC  # noqa: E402
from arca.decs_acervo import carregar_acervo  # noqa: E402

API = config.BASE_URL
VIDAUD = (".mp4", ".avi", ".mov", ".wmv", ".mkv", ".webm", ".flv", ".mpg", ".mpeg", ".m4v",
          ".mp3", ".wav", ".m4a", ".ogg", ".wma")
_C = {}


def _get(url, **kw):
    """GET com a sessao autenticada (refaz o login sozinho se expirar)."""
    if "c" not in _C:
        _C["c"] = dspace.conectar()
    kw.setdefault("timeout", 60)
    return _C["c"]._pedir("GET", url, **kw)


def _titulo(it):
    t = it.get("titulos") or []
    return t[0]["v"] if t else ""


def _conferir_pdf(x):
    """(situacao, codigo HTTP) de um PDF."""
    try:
        r = _get(API + "/core/bitstreams/%s/content" % x["uuid"], timeout=600, stream=True)
    except Exception as e:
        return "erro_rede: %s" % e, None
    if r.status_code in (401, 403):
        r.close()
        return "restrito", r.status_code
    if r.status_code != 200:
        r.close()
        return "http_%d" % r.status_code, r.status_code
    dados = r.content
    if not dados.startswith(b"%PDF"):
        return "corrompido (nao e PDF)", 200
    import fitz
    try:
        doc = fitz.open(stream=dados, filetype="pdf")
        n = len(doc)
        palavras = sum(len(p.get_text().split()) for p in doc)
    except Exception as e:
        return "corrompido (nao abre: %s)" % str(e)[:80], 200
    return ("so_imagem" if palavras < 50 else "ok_com_texto"), 200, n


def examinar(h, it):
    try:
        rb = _get(API + "/core/items/%s/bundles" % it["uuid"], timeout=60)
        if rb.status_code != 200 or "_embedded" not in rb.json():
            return {"categoria": "item_inacessivel", "detalhe": "lista de arquivos HTTP %d" % rb.status_code, "arquivos": []}
        arqs = []
        for bd in rb.json()["_embedded"]["bundles"]:
            if bd["name"] != "ORIGINAL":
                continue
            arqs += _get(API + "/core/bundles/%s/bitstreams" % bd["uuid"], params={"size": 100},
                           timeout=60).json()["_embedded"]["bitstreams"]
    except Exception as e:
        return {"categoria": "erro_rede", "detalhe": str(e)[:120], "arquivos": []}
    if not arqs:
        return {"categoria": "sem_arquivo", "detalhe": "", "arquivos": []}
    info = []
    for x in arqs:
        nome = x.get("name") or ""
        d = {"nome": nome, "MB": round((x.get("sizeBytes") or 0) / 1e6, 1)}
        if nome.lower().endswith(".pdf"):
            r = _conferir_pdf(x)
            d["situacao"] = r[0]
            if len(r) > 2:
                d["paginas"] = r[2]
        info.append(d)
    sit = [d.get("situacao") for d in info if "situacao" in d]
    if any(s and s.startswith("corrompido") for s in sit):
        cat = "corrompido"
    elif any(s == "so_imagem" for s in sit):
        cat = "so_imagem"
    elif sit and all(s == "restrito" for s in sit):
        cat = "restrito"
    elif any(s == "ok_com_texto" for s in sit):
        cat = "ok_com_texto"
    elif any(d["nome"].lower().endswith(VIDAUD) for d in info):
        cat = "video_audio"
    elif sit:
        cat = "pdf_" + "_".join(sorted(set(s for s in sit if s)))
    else:
        cat = "outros_formatos"
    return {"categoria": cat, "detalhe": "; ".join(sorted(set(s for s in sit if s))), "arquivos": info}


def main():
    ac = carregar_acervo()
    c = TC.carregar_cache()
    alvo = sorted(h for h, it in ac.items() if TC.precisa(it) and c.get(h, {}).get("status") != "ok")
    print("%d itens a conferir" % len(alvo), flush=True)
    _C["c"] = dspace.conectar()            # antes das threads: um login so
    feitos = {}
    with ThreadPoolExecutor(6) as ex:
        for i, (h, r) in enumerate(zip(alvo, ex.map(lambda h: examinar(h, ac[h]), alvo)), 1):
            feitos[h] = r
            if i % 250 == 0:
                print("  %d/%d" % (i, len(alvo)), flush=True)
    from openpyxl import Workbook
    from openpyxl.styles import Font
    acao = {"restrito": "Nem com o login o arquivo abre: conferir permissoes do arquivo",
            "corrompido": "Arquivo defeituoso: substituir pelo PDF correto",
            "so_imagem": "PDF escaneado: sera lido por OCR (D23); ideal subir versao pesquisavel",
            "video_audio": "Video/audio: sera transcrito (D23); ideal incluir resumo",
            "sem_arquivo": "Item sem arquivo: conferir se falta o documento ou incluir resumo",
            "outros_formatos": "So imagens/slides/outros: incluir resumo",
            "item_inacessivel": "Lista de arquivos inacessivel: conferir item (retirado/privado?)",
            "ok_com_texto": "PDF abre e tem texto: sem problema de arquivo (falha passageira na rodada)"}
    cont = collections.Counter(r["categoria"] for r in feitos.values())
    wb = Workbook()
    ws = wb.active
    ws.title = "resumo"
    ws.append(["categoria", "itens", "o que fazer"])
    for k, n in cont.most_common():
        ws.append([k, n, acao.get(k, "conferir")])
    for k, _n in cont.most_common():
        w = wb.create_sheet(k[:31])
        w.append(["handle", "link", "titulo", "o que fazer", "situacao dos PDFs", "arquivos (nome | MB | situacao)"])
        for h in sorted(x for x, r in feitos.items() if r["categoria"] == k):
            r = feitos[h]
            arqs = " || ".join("%s | %s MB%s%s" % (d["nome"], d["MB"], (" | " + d["situacao"]) if "situacao" in d else "",
                                                   (" | %d pag" % d["paginas"]) if "paginas" in d else "")
                               for d in r["arquivos"])
            w.append([h, "https://arca.fiocruz.br/handle/" + h, _titulo(ac[h]), acao.get(k, "conferir"), r["detalhe"], arqs])
            w.cell(w.max_row, 2).hyperlink = "https://arca.fiocruz.br/handle/" + h
    for w in wb.worksheets:
        for cel in w[1]:
            cel.font = Font(bold=True)
    pasta = os.path.join(config.SAIDAS, "ods", "curadoria")
    os.makedirs(pasta, exist_ok=True)
    wb.save(os.path.join(pasta, "curadoria_arquivos.xlsx"))
    with open(os.path.join(config.CACHE, "ods_curadoria_arquivos.json"), "w", encoding="utf-8") as f:
        json.dump(feitos, f, ensure_ascii=False)
    print(dict(cont.most_common()))


if __name__ == "__main__":
    main()
