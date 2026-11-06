# -*- coding: utf-8 -*-
"""Resumo gerado do texto completo (PDF) para itens sem resumo ou com resumo curto (decisao D10).

1. baixa SEM login todos os PDFs publicos do bundle ORIGINAL do item (restrito/embargado nao entra);
2. extrai o texto inteiro (PyMuPDF) — nada e cortado, nem as referencias;
3. divide em partes que cabem no contexto do professor (contadas em tokens pelo proprio servidor),
   em quebras de linha, sem perder nenhum trecho;
4. o professor resume cada parte e depois junta os resumos parciais num resumo unico.
O resumo fica em cache (JSON por handle) e entra no texto do professor ao lado do resumo original.
PDF so de imagem (sem camada de texto) fica marcado; OCR nao e feito.
"""
import json
import math
import os
from concurrent.futures import ThreadPoolExecutor

from . import config
from . import ods_professor as P

VERSAO = 1
RESUMO_CURTO = 400          # caracteres: abaixo disso (ou sem resumo) o item recebe resumo do PDF
TOKENS_PARTE = 7000         # texto por parte; com margem para instrucao + resposta + modelo de conversa nas 12.288 da vaga (9000 estourou num livro)
API = config.BASE_URL
PASTA_TXT = os.path.join(config.DADOS_LOCAIS, "pdf_texto")
CACHE_JSON = os.path.join(config.CACHE, "ods_resumos_pdf.json")
_C = {}

INSTR_PARTE = (
    "<|im_start|>system\nVoce e bibliotecario(a) que le producao cientifica. Recebe UMA PARTE (%d de %d) do texto "
    "completo de um documento. Resuma em portugues, em ate 250 palavras, so o que esta no texto: objetivo, tema, "
    "populacao/local, metodos, resultados, conclusoes e recomendacoes. Nao invente; se a parte for so "
    "referencias, sumario ou anexos, diga isso em uma linha.<|im_end|>\n"
    "<|im_start|>user\n%s<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n")
INSTR_JUNTAR = (
    "<|im_start|>system\nVoce e bibliotecario(a). Abaixo estao resumos, em ordem, das partes do texto completo de "
    "um documento cientifico (titulo: %s). Escreva UM resumo do documento inteiro, em portugues, em ate 300 palavras, "
    "no estilo de resumo de artigo: objetivo, tema, populacao/local, metodos, resultados e conclusoes. Use so o que "
    "esta nos resumos.<|im_end|>\n<|im_start|>user\n%s<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n")


def precisa(item):
    from .ods_texto import _escolher
    return len(_escolher(item.get("resumos"), "pt")) < RESUMO_CURTO


def carregar_cache():
    if "c" not in _C:
        _C["c"] = {}
        if os.path.exists(CACHE_JSON):
            with open(CACHE_JSON, encoding="utf-8") as f:
                _C["c"] = json.load(f)
    return _C["c"]


def salvar_cache():
    tmp = CACHE_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(carregar_cache(), f, ensure_ascii=False)
    os.replace(tmp, CACHE_JSON)


def resumo_gerado(handle):
    r = carregar_cache().get(handle or "")
    return r["resumo"] if r and r.get("status") == "ok" else ""


def marcador(item):
    """Muda quando o texto do item muda por causa do PDF: invalida sinais e rotulo do professor."""
    return VERSAO if precisa(item) and resumo_gerado(item.get("handle")) else 0


def tem_texto(item):
    """Titulo e (resumo, palavras-chave ou resumo gerado do PDF)."""
    from .decs_acervo import tem_texto_suficiente
    return tem_texto_suficiente(item) or bool(resumo_gerado(item.get("handle")))


def preparar(itens, aviso=print, parar=True):
    """Passo do fluxo final: gera os resumos do PDF que faltam (sobe o professor se preciso) e,
    com parar=True, desliga o professor no fim para liberar a GPU para os sinais."""
    cache = carregar_cache()
    falta = [it for it in itens if it.get("uuid") and precisa(it) and cache.get(it["handle"], {}).get("versao") != VERSAO]
    if not falta:
        return
    aviso("Resumo do PDF (D10): %d item(ns) sem resumo ou com resumo curto ainda nao lidos." % len(falta))
    if not P.iniciar_servidor(aviso=aviso):
        aviso("Professor indisponivel: itens seguem sem resumo do PDF.")
        return
    try:
        processar(falta, aviso=aviso)
    finally:
        if parar:
            P.parar_servidor()


def baixar_texto(item, sessao):
    """(texto, [nomes dos PDFs]) dos PDFs publicos do item; texto inteiro, todos os PDFs."""
    os.makedirs(PASTA_TXT, exist_ok=True)
    destino = os.path.join(PASTA_TXT, item["handle"].replace("/", "_") + ".json")
    if os.path.exists(destino):
        with open(destino, encoding="utf-8") as f:
            d = json.load(f)
        return d["texto"], d["pdfs"]
    import fitz
    textos, nomes = [], []
    bds = sessao.get(API + "/core/items/%s/bundles" % item["uuid"], timeout=60).json()["_embedded"]["bundles"]
    for bd in bds:
        if bd["name"] != "ORIGINAL":
            continue
        bs = sessao.get(API + "/core/bundles/%s/bitstreams" % bd["uuid"], params={"size": 100},
                        timeout=60).json()["_embedded"]["bitstreams"]
        for x in bs:
            if not (x.get("name") or "").lower().endswith(".pdf"):
                continue
            r = sessao.get(API + "/core/bitstreams/%s/content" % x["uuid"], timeout=600)
            if r.status_code != 200 or not r.content.startswith(b"%PDF"):
                continue                          # restrito/embargado
            try:
                doc = fitz.open(stream=r.content, filetype="pdf")
                textos.append("\n".join(p.get_text() for p in doc))
                nomes.append(x["name"])
            except Exception:
                pass
    d = {"texto": "\n\n".join(textos), "pdfs": nomes}
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    return d["texto"], d["pdfs"]


def _tokens(txt):
    import requests
    r = requests.post(P.SERVIDOR + "/tokenize", json={"content": txt}, headers=_cab(), timeout=300)
    r.raise_for_status()
    return len(r.json()["tokens"])


def _cab():
    with open(P.CHAVE_ARQ) as f:
        return {"Authorization": "Bearer " + f.read().strip()}


def partes(txt):
    """Divide em quebras de linha em partes de ate TOKENS_PARTE tokens. Junta tudo = texto original."""
    n = _tokens(txt)
    k = max(1, math.ceil(n / TOKENS_PARTE))
    # linha gigante (PDF sem quebras) nunca caberia numa parte: quebra nos espacos, sem perder nada
    linhas = []
    for ln in txt.split("\n"):
        while len(ln) > 8000:
            corte = ln.rfind(" ", 0, 8000)
            corte = corte if corte > 0 else 8000
            linhas.append(ln[:corte])
            ln = ln[corte:].lstrip(" ")
        linhas.append(ln)
    txt = "\n".join(linhas)
    for _ in range(50):                       # nunca fica preso: se nao convergir, o item e pulado
        linhas = txt.split("\n")
        alvo = len(txt) / k
        out, atual, tam = [], [], 0
        for ln in linhas:
            if atual and tam + len(ln) > alvo and len(out) < k - 1:
                out.append("\n".join(atual))
                atual, tam = [], 0
            atual.append(ln)
            tam += len(ln) + 1
        out.append("\n".join(atual))
        if all(_tokens(p) <= TOKENS_PARTE for p in out):
            return out
        k += 1
    raise RuntimeError("nao consegui dividir o texto em partes que caibam no contexto")


def _gerar(prompt):
    return P._completar(prompt, 0, n_predict=700).strip()


def resumir(item, txt):
    ps = partes(txt)
    with ThreadPoolExecutor(max_workers=P.PARALELO) as ex:
        parciais = list(ex.map(lambda ip: _gerar(INSTR_PARTE % (ip[0] + 1, len(ps), ip[1])), enumerate(ps)))
    if len(parciais) == 1:
        return parciais[0], 1
    from .ods_texto import _escolher
    titulo = _escolher(item.get("titulos"), "pt")
    # resumos parciais demais para uma vaga: junta em grupos, quantas rodadas forem precisas
    while True:
        juntos = "\n\n".join("PARTE %d: %s" % (i + 1, p) for i, p in enumerate(parciais))
        if _tokens(juntos) <= TOKENS_PARTE:
            return _gerar(INSTR_JUNTAR % (titulo, juntos)), len(ps)
        g = max(2, math.ceil(len(parciais) / math.ceil(_tokens(juntos) / TOKENS_PARTE)))
        grupos = [parciais[i:i + g] for i in range(0, len(parciais), g)]
        with ThreadPoolExecutor(max_workers=P.PARALELO) as ex:
            parciais = list(ex.map(lambda gr: _gerar(INSTR_JUNTAR % (titulo, "\n\n".join(gr))), grupos))


def processar(itens, aviso=print):
    """Gera (ou le do cache) o resumo do PDF de cada item que precisa. Devolve {handle: registro}."""
    import requests
    cache = carregar_cache()
    s = requests.Session()
    feitos = {}
    alvo = [it for it in itens if precisa(it)]
    for i, it in enumerate(alvo, 1):
        h = it["handle"]
        if cache.get(h, {}).get("versao") == VERSAO:
            feitos[h] = cache[h]
            continue
        try:
            txt, pdfs = baixar_texto(it, s)
        except Exception as e:
            aviso("  %s: erro ao baixar (%s)" % (h, e))
            continue
        if not pdfs:
            reg = {"status": "sem_pdf_publico"}
        elif len(txt.split()) < 50:
            reg = {"status": "pdf_sem_texto", "pdfs": pdfs}
        else:
            try:
                resumo, k = resumir(it, txt)
            except Exception as e:      # um PDF problematico (ex.: livro inteiro) nao para os demais
                aviso("  %s: erro ao resumir (%d palavras): %s" % (h, len(txt.split()), str(e)[:200]))
                continue                # fica sem registro: sera tentado de novo na proxima rodada
            reg = {"status": "ok", "resumo": resumo, "pdfs": pdfs, "partes": k,
                   "palavras_pdf": len(txt.split())}
        reg["versao"] = VERSAO
        reg["modelo"] = P.NOME
        cache[h] = feitos[h] = reg
        salvar_cache()
        aviso("  [%d/%d] %s: %s%s" % (i, len(alvo), h, reg["status"],
                                     " (%d partes)" % reg["partes"] if reg.get("partes") else ""))
    return feitos
