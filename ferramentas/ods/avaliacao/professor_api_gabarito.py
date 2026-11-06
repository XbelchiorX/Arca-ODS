# -*- coding: utf-8 -*-
"""Teste: professor de ponta (API da Anthropic) x Qwen3.5-9B local no gabarito cego (149 itens).

Mesmo prompt do professor local (criterios, objetivos, documento inteiro, 15 metas candidatas ONU + Ipea 2026),
so trocando o formato de chat. Le os sinais do cache (rode antes o piloto ou a O4). Somente leitura do ARCA.

Requer: pip install anthropic ; variavel de ambiente ANTHROPIC_API_KEY (criada pelo responsavel).
Uso:   python ferramentas/ods/avaliacao/professor_api_gabarito.py claude-sonnet-5-5 [claude-opus-5-5 ...]
Custo estimado: < US$ 2 por modelo (149 itens x ~4 mil tokens).
"""
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, RAIZ)
from arca import ods_metabusca as MB, ods_modelo as M, ods_professor as P, ods_sinais as S  # noqa: E402
from arca import ods_texto as T  # noqa: E402
from arca.ods_criterios import travar  # noqa: E402
from arca.decs_acervo import carregar_acervo  # noqa: E402

SAIDA = os.path.join(RAIZ, "publicacoes", "artigo_ods", "resultados", "professor")


def mensagens(prompt_qwen):
    """Prompt no formato do Qwen -> (system, user) para a API, sem mudar uma palavra."""
    sis = re.search(r"<\|im_start\|>system\n(.*?)<\|im_end\|>", prompt_qwen, re.S).group(1)
    usr = re.search(r"<\|im_start\|>user\n(.*?)<\|im_end\|>", prompt_qwen, re.S).group(1)
    return sis, usr


def main(modelos):
    import anthropic
    cli = anthropic.Anthropic()
    ac = carregar_acervo()
    ouro = M.gabarito()
    hs = sorted(h for h in ouro if h in ac)
    cache = S.carregar_cache()
    falta = [h for h in hs if (cache.get(h) or {}).get("v") != S.VERSAO_SINAIS]
    if falta:
        sys.exit("Sinais faltando para %d itens do gabarito: rode antes o piloto ou a opcao O4." % len(falta))
    metas = MB.metas()
    cods = list(metas)
    prompts = {h: P._prompt(T.texto_professor(ac[h]), MB.candidatas(cods, cache[h]["sim"].astype(np.float32)),
                            metas, com_trecho=False) for h in hs}
    for modelo in modelos:
        uso = {"entrada": 0, "saida": 0}

        def um(h):
            sis, usr = mensagens(prompts[h])
            for tent in range(4):
                try:
                    r = cli.messages.create(model=modelo, max_tokens=400, temperature=0,
                                            system=[{"type": "text", "text": sis, "cache_control": {"type": "ephemeral"}}],
                                            messages=[{"role": "user", "content": usr}])
                    uso["entrada"] += r.usage.input_tokens + (r.usage.cache_read_input_tokens or 0) + (r.usage.cache_creation_input_tokens or 0)
                    uso["saida"] += r.usage.output_tokens
                    return P._ler_json("".join(b.text for b in r.content if b.type == "text"))
                except anthropic.RateLimitError:
                    time.sleep(20 * (tent + 1))
            return None

        t0 = time.time()
        with ThreadPoolExecutor(max_workers=4) as ex:
            out = dict(zip(hs, ex.map(um, hs)))
        pv = {h: travar([o["n"] for o in (out[h] or [])], T.texto_professor(ac[h])) for h in hs}
        res = {"modelo": modelo, "n": len(hs), "falhas_json": sum(v is None for v in out.values()),
               "todos": M.metricas(pv, ouro, hs), "sem3": M.metricas(pv, ouro, hs, (3,)),
               "tokens": uso, "segundos": round(time.time() - t0)}
        print(json.dumps(res, ensure_ascii=False), flush=True)
        os.makedirs(SAIDA, exist_ok=True)
        with open(os.path.join(SAIDA, "api_gabarito_%s.json" % modelo), "w", encoding="utf-8") as f:
            json.dump({"resumo": res, "respostas": out}, f, ensure_ascii=False, indent=1)
    print("Referencia Qwen3.5-9B local (mesmo gabarito, Ipea 2026): F1 0,774; sem ODS 3: 0,65")


if __name__ == "__main__":
    main(sys.argv[1:] or ["claude-sonnet-5-5"])
