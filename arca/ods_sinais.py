# -*- coding: utf-8 -*-
"""Sinais por documento usados pelo classificador final de ODS.

1. ODSBahia (odsbahia/odsbahia-ptbr; UFSB, 2024): BERTimbau ajustado com 20
   rotulos (ODS 1-17, 18 igualdade racial, 19 arte/cultura/comunicacao, 20 povos
   originarios e comunidades tradicionais). Texto em portugues, resumo inteiro
   em janelas de 510 tokens (media das probabilidades).
2. Qwen3-Embedding-8B: vetor do documento (4096 dimensoes) e similaridade com
   as 185 metas (ods_metabusca).

Tudo fica em cache por handle (dados locais, fora do OneDrive): rodar de novo
so calcula os itens novos.
"""
import os
import pickle

import numpy as np

from . import config
from . import ods_metabusca as MB
from . import ods_texto as T

CACHE_PKL = os.path.join(config.CACHE, "ods_sinais.pkl")
BAHIA = "odsbahia/odsbahia-ptbr"
VERSAO_SINAIS = 4      # 4: Qwen3-Embedding-8B (D17); 3: metas Ipea 2026 (ONU + Brasil); 2: documento e metas inteiros; v1 cortava
_M = {}


def carregar_cache():
    if os.path.exists(CACHE_PKL):
        with open(CACHE_PKL, "rb") as f:
            return pickle.load(f)
    return {}


def salvar_cache(c):
    tmp = CACHE_PKL + ".tmp"
    with open(tmp, "wb") as f:
        pickle.dump(c, f)
    os.replace(tmp, CACHE_PKL)


def _bahia():
    if "bahia" not in _M:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        tok = AutoTokenizer.from_pretrained(BAHIA)
        md = AutoModelForSequenceClassification.from_pretrained(BAHIA).to(dev).eval()
        if dev.type == "cuda":
            md.half()
        ordem = [int(str(md.config.id2label[i]).replace("ODS", "").strip()) for i in range(md.config.num_labels)]
        _M["bahia"] = (tok, md, dev, ordem)
    return _M["bahia"]


def prob_bahia(itens, lote=16):
    """Matriz (n x 20): probabilidade media do ODSBahia nas janelas de cada item."""
    import torch
    tok, md, dev, ordem = _bahia()
    textos, dono = [], []
    for i, it in enumerate(itens):
        for w in T.janelas(tok, T.texto(it, "pt") or " "):
            textos.append(w)
            dono.append(i)
    out = np.zeros((len(itens), 20), dtype=np.float32)
    cont = np.zeros(len(itens))
    for a in range(0, len(textos), lote):
        enc = tok(textos[a:a + lote], padding=True, truncation=True, max_length=512, return_tensors="pt").to(dev)
        with torch.no_grad():
            pr = torch.softmax(md(**enc).logits.float(), -1).cpu().numpy()
        for k, p in enumerate(pr):
            i = dono[a + k]
            v = np.zeros(20, dtype=np.float32)
            for j, n in enumerate(ordem):
                v[n - 1] = p[j]
            out[i] += v
            cont[i] += 1
    return out / np.maximum(cont, 1)[:, None]


def calcular(handles, acervo, cache=None, lote=64, aviso=print):
    """Garante no cache os sinais de cada handle. Devolve o cache.

    Duas etapas, porque o ODSBahia e o Qwen3-Embedding-8B nao cabem juntos nos 8 GB da GPU:
    1) ODSBahia em todos os itens que faltam (depois libera a GPU); 2) embedding (metas + vetor)."""
    from .ods_textocompleto import marcador
    cache = carregar_cache() if cache is None else cache
    # refaz quando o metodo muda ou quando o item ganhou (ou perdeu) o resumo gerado do PDF (D10)
    falta = [h for h in dict.fromkeys(handles)
             if h in acervo and ((cache.get(h) or {}).get("v") != VERSAO_SINAIS
                                 or (cache.get(h) or {}).get("pdf", 0) != marcador(acervo[h]))]
    if not falta:
        return cache
    bahia = {}
    for a in range(0, len(falta), lote):
        hs = falta[a:a + lote]
        for h, p in zip(hs, prob_bahia([acervo[h] for h in hs])):
            bahia[h] = p
        if (a // lote) % 80 == 79 or a + lote >= len(falta):
            aviso("  ODSBahia: %d/%d itens" % (min(a + lote, len(falta)), len(falta)))
    _M.pop("bahia", None)
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:
        pass
    for a in range(0, len(falta), lote):
        hs = falta[a:a + lote]
        its = [acervo[h] for h in hs]
        cods, sim = MB.pontuar([T.texto_professor(it) for it in its])
        vd = MB.ultimo_vetor_documentos()
        for k, h in enumerate(hs):
            cache[h] = {"v": VERSAO_SINAIS, "bahia": bahia[h], "sim": sim[k].astype(np.float16),
                        "vet": vd[k].astype(np.float16), "pdf": marcador(its[k])}
        if (a // lote) % 80 == 79 or a + lote >= len(falta):     # ~5 mil itens por gravacao
            salvar_cache(cache)
            aviso("  embedding: %d/%d itens" % (min(a + lote, len(falta)), len(falta)))
    return cache


def matriz(handles, cache):
    """Atributos do classificador: [ODSBahia 20 | similaridade maxima por ODS 18 | vetor 4096]."""
    cods = list(MB.metas())
    linhas = []
    for h in handles:
        c = cache[h]
        sim = c["sim"].astype(np.float32)[None, :]
        linhas.append(np.concatenate([c["bahia"], MB.por_ods(cods, sim)[0], c["vet"].astype(np.float32)]))
    return np.asarray(linhas, dtype=np.float32)
