# -*- coding: utf-8 -*-
"""O5: rotula o conjunto de treino com o professor local, treina e avalia o modelo de ODS.

Etapas (cada uma retoma de onde parou; caches em dados locais):
 1. conjunto de treino: todos os itens depositados em 2026 + uma amostra
    aleatoria dos demais ate completar ODS_TREINO_FRACAO do acervo (padrao 0,5:
    metade do repositorio, pedido do responsavel), sem os itens do gabarito e so
    com titulo + (resumo ou palavras-chave);
 2. sinais (ODSBahia + Qwen3-Embedding contra as metas) de treino e gabarito;
 3. professor (Qwen3.5-9B local) rotula o treino pelos criterios oficiais;
 4. treina o classificador (limiares por validacao cruzada);
 5. avalia no gabarito independente (dados/ods_gabarito.json) contra:
    o professor, o ODSBahia sozinho e a indexacao humana.
Saidas: saidas/avaliacao/avaliacao_ods.md e .json; modelo em dados locais.
"""
import gc
import json
import os
import random
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)

import numpy as np  # noqa: E402

from arca import config  # noqa: E402
from arca import ods_correcao as C  # noqa: E402
from arca import ods_metabusca as MB  # noqa: E402
from arca import ods_modelo as M  # noqa: E402
from arca import ods_professor as P  # noqa: E402
from arca import ods_sinais as S  # noqa: E402
from arca import ods_texto as T  # noqa: E402
from arca import ods_textocompleto as TC  # noqa: E402
from arca.decs_acervo import carregar_acervo  # noqa: E402

FRACAO = float(os.getenv("ODS_TREINO_FRACAO", "0.5"))


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def _data(r):
    d = [x.get("value") or "" for x in r.get("dc.date.accessioned") or []]
    return min(d) if d else ""


def conjunto(acervo, ouro):
    ok = [h for h, r in acervo.items() if h not in ouro and TC.tem_texto(r)]
    a26 = sorted(h for h in ok if _data(acervo[h]).startswith("2026"))
    resto = sorted(h for h in ok if not _data(acervo[h]).startswith("2026"))
    random.Random(2026).shuffle(resto)
    alvo = int(FRACAO * len(acervo))
    return a26 + resto[:max(alvo - len(a26), 0)]


def rotular_professor(handles, acervo, cache_sinais):
    cods = list(MB.metas())
    rot = P.carregar_cache()
    # refaz quem ganhou resumo do PDF depois (D10) ou foi rotulado com metas de outra versao dos sinais (D17)
    falta = [h for h in handles if h not in rot or rot[h].get("pdf", 0) != TC.marcador(acervo[h])
             or rot[h].get("sinais") != S.VERSAO_SINAIS or rot[h].get("modelo") != P.NOME or rot[h].get("prompt") not in P.PROMPTS_ACEITOS
             or rot[h].get("ods") is None]   # D19: rotulos de outro professor
    log("Professor: %d ja rotulados, %d a rotular" % (len(handles) - len(falta), len(falta)))
    t0 = time.time()
    if not P.servidor_ativo():
        log("  (servidor llama.cpp CUDA nao encontrado em %s: usando o modo lento, dentro do processo)" % P.SERVIDOR)
    for a in range(0, len(falta), 40):
        hs = falta[a:a + 40]
        pares = [(T.texto_professor(acervo[h]), MB.candidatas(cods, cache_sinais[h]["sim"].astype(np.float32)))
                 for h in hs]
        for h, r in zip(hs, P.rotular_lote(pares, MB.metas(), com_trecho=P.ROTULAR_COM_TRECHO)):
            rot[h] = {"ods": r, "modelo": P.NOME, "pdf": TC.marcador(acervo[h]), "sinais": S.VERSAO_SINAIS,
                      "prompt": P.PROMPT_VERSAO, "trecho": P.ROTULAR_COM_TRECHO}
        P.salvar_cache(rot)
        i = a + len(hs)
        log("  professor %d/%d (%.2fs/item; faltam ~%.1f h)" % (i, len(falta), (time.time() - t0) / i,
                                                            (time.time() - t0) / i * (len(falta) - i) / 3600))
    return {h: [o["n"] for o in rot[h]["ods"]]            # professor soberano: sem trava (D24)
            for h in handles if rot.get(h, {}).get("ods") is not None}


def main():
    acervo = carregar_acervo()
    ouro = M.gabarito()
    # D10: resumo do PDF inteiro para itens sem resumo ou com resumo curto (professor na GPU; desliga no fim)
    TC.preparar(list(acervo.values()), aviso=log)
    treino = conjunto(acervo, ouro)
    log("Treino: %d itens (%.0f%% do acervo de %d). Gabarito: %d itens." % (len(treino), 100 * FRACAO, len(acervo), len(ouro)))

    # sinais e professor disputam a GPU (8 GB): primeiro os sinais, com o servidor parado
    P.parar_servidor()
    log("Sinais (ODSBahia + metas) de todo o acervo com texto...")
    todos = [] if os.getenv("ODS_SO_TREINO") else [h for h, r in acervo.items() if TC.tem_texto(r)]
    cache = S.calcular(treino + sorted(ouro) + todos, acervo, aviso=log)
    S._M.clear()
    MB.liberar()
    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:
        pass

    P.iniciar_servidor(aviso=log)
    rot = rotular_professor(treino + sorted(ouro), acervo, cache)
    P.parar_servidor()
    P._M.clear()
    gc.collect()
    rot_treino = {h: v for h, v in rot.items() if h in set(treino)}

    pacote = M.treinar(rot_treino, cache, aviso=log)
    pacote["professor"] = P.NOME
    M.salvar(pacote)

    # avaliacao no gabarito independente
    hs = sorted(ouro)
    Pm, pred = M.prever(pacote, hs, cache)
    res = {"n_gabarito": len(hs), "n_treino": pacote["n_treino"], "limiares": pacote["limiares"],
           "cv_vs_professor": pacote["cv_vs_professor"]}
    bahia = {h: [int(np.argmax(cache[h]["bahia"][:18])) + 1] for h in hs}
    humano = {h: C.humano(acervo[h]) for h in hs}
    prof = {h: rot.get(h, []) for h in hs}
    for nome, pv in (("modelo final", pred), ("professor Qwen3.5-9B", prof), ("ODSBahia (1o ODS)", bahia),
                     ("indexacao humana", humano)):
        res[nome] = {"geral": M.metricas(pv, ouro, hs), "sem_ODS_3": M.metricas(pv, ouro, hs, excluir=(3,)),
                     "ods_por_item": round(float(np.mean([len(pv[h]) for h in hs])), 2)}
    por = {}
    for o in range(1, 19):
        tp = sum(o in pred[h] and o in ouro[h] for h in hs)
        fp = sum(o in pred[h] and o not in ouro[h] for h in hs)
        fn = sum(o not in pred[h] and o in ouro[h] for h in hs)
        por[o] = {"no_gabarito": tp + fn, "acertos": tp, "a_mais": fp, "faltando": fn}
    res["por_ods_modelo_final"] = por
    os.makedirs(config.SAIDAS_AVALIACAO, exist_ok=True)
    with open(os.path.join(config.SAIDAS_AVALIACAO, "avaliacao_ods.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    linhas = ["# Avaliacao do modelo de ODS (%s)" % pacote["data"], "",
              "Gabarito independente: %d itens de 2026 rotulados pelos criterios oficiais (arca/ods_criterios.py),"
              " nunca usados no treino. Treino: %d itens rotulados pelo professor %s." % (len(hs), pacote["n_treino"], P.NOME), "",
              "| Metodo | Precisao | Recall | F1 | F1 sem ODS 3 | ODS/item |", "|---|---|---|---|---|---|"]
    for nome in ("modelo final", "professor Qwen3.5-9B", "ODSBahia (1o ODS)", "indexacao humana"):
        r = res[nome]
        linhas.append("| %s | %.2f | %.2f | %.2f | %.2f | %.2f |" % (nome, r["geral"]["precisao"], r["geral"]["recall"],
                                                                    r["geral"]["f1"], r["sem_ODS_3"]["f1"], r["ods_por_item"]))
    linhas += ["", "Por ODS (modelo final): " + "; ".join("%d: %d/%d (+%d)" % (o, v["acertos"], v["no_gabarito"], v["a_mais"])
                                                         for o, v in por.items() if v["no_gabarito"] or v["a_mais"])]
    with open(os.path.join(config.SAIDAS_AVALIACAO, "avaliacao_ods.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")
    print("\n".join(linhas))


if __name__ == "__main__":
    main()
