# -*- coding: utf-8 -*-
"""Atualiza a similaridade documento x meta no cache de sinais so nas metas cujo texto mudou (28/10: cabecalho de
pagina do PDF removido de 14 conceitos, ver extrair_metas_2026.py).

Recalcula o vetor (Qwen3-Embedding-8B) so dessas metas e refaz a coluna delas: sim = vetor do documento (guardado
no cache) . vetor novo da meta. As outras colunas nao mudam. Mostra quantas listas de 20 candidatas mudaram na regua.
Uso: python ferramentas/ods/referencia/atualizar_sim_metas.py <metas_2026.json antigo>
"""
import json
import os
import sys

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, RAIZ)
from arca import ods_metabusca as MB, ods_sinais as S  # noqa: E402


def main():
    antigo = json.load(open(sys.argv[1], encoding="utf-8"))
    novo = MB.metas()
    cods = list(novo)
    assert cods == list(antigo), "a ordem das metas mudou: refazer os sinais inteiros"
    mud = [j for j, c in enumerate(cods) if MB.texto_meta(c, antigo[c]) != MB.texto_meta(c, novo[c])]
    print("metas com texto mudado:", [cods[j] for j in mud], flush=True)
    if not mud:
        return
    vm = MB._encode([MB.texto_meta(cods[j], novo[cods[j]]) for j in mud], lote=4)
    MB.liberar()
    cache = S.carregar_cache()
    regua = json.load(open(os.path.join(RAIZ, "dados", "gabarito_v7", "amostra.json"), encoding="utf-8"))["itens"]
    mudou_cand, n = 0, 0
    for h, c in cache.items():
        if "sim" not in c or "vet" not in c:
            continue
        sim = c["sim"].astype(np.float32)
        antes = {k for k, _ in MB.candidatas(cods, sim)} if h in regua else None
        sim[mud] = vm @ c["vet"].astype(np.float32)
        c["sim"] = sim.astype(np.float16)
        n += 1
        if antes is not None:
            mudou_cand += antes != {k for k, _ in MB.candidatas(cods, sim)}
    S.salvar_cache(cache)
    print("%d itens atualizados; na regua, %d de %d listas de 20 candidatas mudaram"
          % (n, mudou_cand, sum(1 for h in regua if h in cache)), flush=True)


if __name__ == "__main__":
    main()
