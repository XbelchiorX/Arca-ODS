# -*- coding: utf-8 -*-
"""Teste (D16): outro professor LOCAL (padrao: Gemma 4 26B-A4B QAT q4_0, Google, Apache-2.0) x Qwen3.5-9B
no gabarito cego (149 itens). Mesmo texto, mesmas 15 metas candidatas e mesmas instrucoes do professor
atual; so o formato de conversa e o do proprio modelo (/v1/chat/completions do llama-server).
O Qwen roda de novo nos mesmos prompts (mesmas metas do Qwen3-Embedding-8B), lado a lado.

Pre-requisitos: sinais do gabarito no cache (rodar antes o piloto ou a O4) e a GPU livre (o servidor do
Qwen e desligado aqui). Os "experts" do modelo MoE ficam na RAM (--n-cpu-moe) porque nao cabem nos 8 GB.
Uso: python ferramentas/ods/avaliacao/professor_local_gabarito.py [--n-cpu-moe N]
"""
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import requests

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, RAIZ)
from arca import config, ods_metabusca as MB, ods_modelo as M, ods_professor as P, ods_sinais as S  # noqa: E402
from arca import ods_texto as T, ods_textocompleto as TC  # noqa: E402
from arca.ods_criterios import travar  # noqa: E402
from arca.decs_acervo import carregar_acervo  # noqa: E402

NOME = "gemma-4-26B-A4B-it-qat-q4_0"
REPO, ARQ = "google/gemma-4-26B-A4B-it-qat-q4_0-gguf", "gemma-4-26B_q4_0-it.gguf"
PORTA = 8090
URL = "http://127.0.0.1:%d" % PORTA
SAIDA = os.path.join(RAIZ, "publicacoes", "artigo_ods", "resultados", "professor")


def mensagens(prompt_qwen):
    import re
    sis = re.search(r"<\|im_start\|>system\n(.*?)<\|im_end\|>", prompt_qwen, re.S).group(1)
    usr = re.search(r"<\|im_start\|>user\n(.*?)<\|im_end\|>", prompt_qwen, re.S).group(1)
    return sis, usr


def subir(n_cpu_moe, vagas=2):
    from huggingface_hub import hf_hub_download
    gguf = hf_hub_download(REPO, ARQ)
    with open(P.CHAVE_ARQ) as f:
        chave = f.read().strip()
    amb = dict(os.environ)
    import torch
    amb["PATH"] = os.path.join(os.path.dirname(torch.__file__), "lib") + os.pathsep + amb.get("PATH", "")
    log = open(os.path.join(config.LOGS, "llama_server_gemma.log"), "w")
    subprocess.Popen([P.LLAMA_SERVER, "-m", gguf, "-ngl", "99", "--n-cpu-moe", str(n_cpu_moe),
                      "-c", str(P.CONTEXTO * vagas), "-np", str(vagas), "-fa", "on", "--host", "127.0.0.1",
                      "--port", str(PORTA), "--reasoning-budget", "0", "--api-key", chave, "--jinja"],
                     env=amb, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(200):
        try:
            if requests.get(URL + "/health", timeout=3).status_code == 200:
                return chave
        except Exception:
            pass
        time.sleep(3)
    sys.exit("Servidor do Gemma nao subiu: veja logs/llama_server_gemma.log")


def main():
    n_cpu_moe = int(sys.argv[sys.argv.index("--n-cpu-moe") + 1]) if "--n-cpu-moe" in sys.argv else 99
    ac = carregar_acervo()
    ouro = M.gabarito()
    hs = sorted(h for h in ouro if h in ac)
    cache = S.carregar_cache()
    falta = [h for h in hs if (cache.get(h) or {}).get("v") != S.VERSAO_SINAIS
             or cache[h].get("pdf", 0) != TC.marcador(ac[h])]
    if falta:
        sys.exit("Sinais faltando/desatualizados para %d itens do gabarito: rode antes o piloto ou a O4." % len(falta))
    metas = MB.metas()
    cods = list(metas)
    prompts = {h: P._prompt(T.texto_professor(ac[h]), MB.candidatas(cods, cache[h]["sim"].astype(np.float32)),
                            metas, com_trecho=False) for h in hs}
    # Qwen3.5-9B com os MESMOS prompts (mesmas metas candidatas), para a comparacao ser justa
    MB.liberar()
    P.iniciar_servidor()
    t0 = time.time()
    rq = P.rotular_lote([(T.texto_professor(ac[h]), MB.candidatas(cods, cache[h]["sim"].astype(np.float32)))
                         for h in hs], metas)
    seg_q = (time.time() - t0) / len(hs)
    P.parar_servidor()
    time.sleep(5)
    chave = subir(n_cpu_moe)
    cab = {"Authorization": "Bearer " + chave}

    def um(h):
        sis, usr = mensagens(prompts[h])
        for tent in range(2):
            r = requests.post(URL + "/v1/chat/completions", headers=cab, timeout=1800, json={
                "messages": [{"role": "system", "content": sis}, {"role": "user", "content": usr}],
                "max_tokens": 300, "temperature": 0 if tent == 0 else 0.3, "seed": 0,
                "chat_template_kwargs": {"enable_thinking": False}})
            r.raise_for_status()
            d = r.json()
            out = P._ler_json(d["choices"][0]["message"].get("content") or "")
            if out is not None:
                return out
        return None

    t0 = time.time()
    out = {}
    with ThreadPoolExecutor(max_workers=2) as ex:
        for i, (h, r) in enumerate(zip(hs, ex.map(um, hs)), 1):
            out[h] = r
            if i % 25 == 0:
                print("  %d/%d (%.1f s/item)" % (i, len(hs), (time.time() - t0) / i), flush=True)
    seg = (time.time() - t0) / len(hs)
    subprocess.run(["taskkill", "/IM", "llama-server.exe", "/F"], capture_output=True)
    pg = {h: travar([o["n"] for o in (out[h] or [])], T.texto_professor(ac[h])) for h in hs}
    pq = {h: travar([o["n"] for o in (r or [])], T.texto_professor(ac[h])) for h, r in zip(hs, rq)}
    comum = hs
    res = {"gemma": {"modelo": NOME, "todos": M.metricas(pg, ouro, hs), "sem3": M.metricas(pg, ouro, hs, (3,)),
                     "falhas_json": sum(v is None for v in out.values()), "s_por_item": round(seg, 2),
                     "horas_acervo_69mil": round(seg * 69178 / 3600, 1), "n_cpu_moe": n_cpu_moe},
           "qwen_mesmo_texto": {"n": len(comum), "todos": M.metricas(pq, ouro, comum), "sem3": M.metricas(pq, ouro, comum, (3,)),
                                "falhas_json": sum(r is None for r in rq), "s_por_item": round(seg_q, 2),
                                "horas_acervo_69mil": round(seg_q * 69178 / 3600, 1)},
           "gemma_vs_qwen": M.metricas(pg, pq, comum)}
    por = {}
    for o in range(1, 19):
        n = sum(o in ouro[h] for h in comum)
        if n:
            por[o] = {"gabarito": n,
                      "qwen_acertos": sum(o in pq[h] and o in ouro[h] for h in comum), "qwen_a_mais": sum(o in pq[h] and o not in ouro[h] for h in comum),
                      "gemma_acertos": sum(o in pg[h] and o in ouro[h] for h in comum), "gemma_a_mais": sum(o in pg[h] and o not in ouro[h] for h in comum)}
    res["por_ods"] = por
    print(json.dumps(res, ensure_ascii=False, indent=1), flush=True)
    os.makedirs(SAIDA, exist_ok=True)
    with open(os.path.join(SAIDA, "gemma_vs_qwen_gabarito.json"), "w", encoding="utf-8") as f:
        json.dump({"resumo": res, "respostas_gemma": out, "respostas_qwen": dict(zip(hs, rq))}, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
