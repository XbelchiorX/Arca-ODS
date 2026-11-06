# -*- coding: utf-8 -*-
"""Testa varias formas de prompt num registro so, no professor aberto pelo conversar_professor.py (porta 8090, sem
raciocinio, temperatura 0), com 20 e com mais metas candidatas (02/11, pedido da responsavel: caso dos pescadores
artesanais, icict/34355). So le; nada e gravado no Arca.
Uso: python ferramentas/ods/avaliacao/testar_prompts_item.py icict/34355 [20 50]
"""
import json
import os
import re
import sys
import urllib.request

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
os.environ.setdefault("ODS_PROMPT", "8")
from arca import ods_metabusca as MB, ods_sinais as S, ods_texto as T  # noqa: E402
from arca import ods_professor as P  # noqa: E402
from arca.decs_acervo import carregar_acervo  # noqa: E402

URL = "http://127.0.0.1:8090/v1/chat/completions"
SAIDA_TRECHO = ('{"descricao": "<descrição>", "ods": [{"meta": "3.3", "n": 3, "trecho": "<trecho copiado>"}]}\n'
                'Lista vazia se nenhum ODS se aplica: {"descricao": "<descrição>", "ods": []}<|im_end|>\n')
DESCR = ("Primeiro, descreva o documento como um todo, sem copiar frases: do que ele trata; o que estuda, apresenta ou "
         "propõe; sobre quem ou onde, quando houver; e a que resultados ou conclusões chega, quando houver (descrição). ")
TRECHO = ("indique essa meta e copie do documento, sem alterar nenhuma palavra e no idioma original, um trecho de até 20 "
          "palavras que comprove. O trecho é só a prova: a decisão vem do documento inteiro, não de uma frase isolada. ")
# v10a: varredura por aspecto (procedimento; nao muda o criterio D32)
V10A = ("TAREFA: leia o documento e as metas candidatas. O documento pode se relacionar com nenhum, um ou mais ODS. "
        + DESCR + "Depois, para cada aspecto dessa descrição (o objeto do estudo, a população, o problema, as causas, as "
        "consequências e as propostas), verifique se alguma meta candidata trata dele, na META ONU ou na META IPEA, lendo "
        "o texto inteiro de cada meta. Atribua todos os ODS que se aplicam, não só o mais evidente; para cada ODS "
        "atribuído, " + TRECHO + "Use somente as metas candidatas. Se nenhuma se aplica, devolva a lista vazia.\n\n")
# v10b: v10a + objetivo do ODS quando nao ha meta exata (MUDA o criterio D32: decisao da responsavel)
V10B = V10A.replace("Use somente as metas candidatas.",
                    "Se o tema central do documento corresponde ao objetivo de um ODS (o título do ODS), mas nenhuma "
                    "meta candidata o descreve exatamente, atribua esse ODS indicando a meta candidata mais próxima "
                    "dele. Use somente as metas candidatas.")
FORMAS = {"v8 tema + trecho": "tema_trecho", "v9 descrição + trecho": "descricao_trecho",
          "v10a varredura por aspecto": V10A, "v10b varredura + objetivo do ODS (muda D32)": V10B}


def prompt(forma, txt, cand, metas):
    if forma in ("tema_trecho", "descricao_trecho"):
        P.V8 = forma
        return P._prompt_v8_texto(txt, cand, metas)
    P.V8 = "descricao_trecho"
    p = P._prompt_v8_texto(txt, cand, metas)
    ini, fim = p.index("TAREFA:"), p.index("RESPONDA SÓ")
    p = p[:ini] + forma + p[fim:]
    return re.sub(r'\{"descricao": "<descrição>".*?<\|im_end\|>\n', lambda m: SAIDA_TRECHO, p, count=1, flags=re.S)


def perguntar(p):
    corpo = {"messages": P.mensagens(p), "max_tokens": 2500, "temperature": 0, "seed": 0,
             "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(URL, json.dumps(corpo).encode(), {"Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=900))
    return r["choices"][0]["message"].get("content") or ""


def main():
    h = sys.argv[1]
    ks = [int(k) for k in sys.argv[2:]] or [20, 50]
    ac, cache, metas = carregar_acervo(), S.carregar_cache(), MB.metas()
    txt = T.texto_professor(ac[h])
    for k in ks:
        cand = MB.candidatas(list(metas), cache[h]["sim"].astype(np.float32), k)
        for nome, forma in FORMAS.items():
            out = P._ler_json(perguntar(prompt(forma, txt, cand, metas)))
            ods = sorted({o["n"] for o in out}) if out is not None else "FALHA"
            mts = [o["meta"] for o in out] if out is not None else []
            print("%2d candidatas | %-45s | ODS %s | metas %s" % (k, nome, ods, mts), flush=True)
            if out is not None and getattr(out, "tema", ""):
                print("   descrição/tema: %s" % out.tema[:400], flush=True)



# 02/11 (hipotese da responsavel): sem o filtro do embedding; o professor recebe as 180 metas (texto ONU e Ipea, sem os
# conceitos, 21,8 mil tokens) ANTES do documento, para o servidor reaproveitar esse prefixo entre documentos.
def bloco_meta(metas, c):
    return "[%s] " % c + " | ".join("%s: %s" % (P._ROT_V8[r], t) for r, t in P._partes_meta(metas[c]) if r != "conceitos_ipea")


def prompt_180(forma, txt, metas):
    P.V8 = forma
    fixo = P._fixo_v8_texto(0).replace("metas candidatas", "metas").replace("meta candidata", "meta")
    fixo = fixo.replace("cada meta candidata vem com o seu código e até três partes", "cada meta vem com o seu código e até duas partes")
    lista = "\n".join(bloco_meta(metas, c) for c in metas)
    return (fixo + "<|im_start|>user\nAS 180 METAS:\n" + lista + "\n\nDOCUMENTO:\n" + txt +
            "\n\nResponda só o JSON.<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n")


def main_180(hs):
    ac, metas = carregar_acervo(), MB.metas()
    for h in hs:
        for forma in ("tema_trecho", "descricao_trecho"):
            out = P._ler_json(perguntar(prompt_180(forma, T.texto_professor(ac[h]), metas)))
            print("%s | 180 metas | %-16s | ODS %s | metas %s" % (h, forma, sorted({o["n"] for o in out}) if out is not None
                  else "FALHA", [o["meta"] for o in out] if out is not None else []), flush=True)



def main_k(k, hs):
    """Filtro do embedding com k candidatas, v8 tema e v9 descricao, nos registros dados."""
    ac, cache, metas = carregar_acervo(), S.carregar_cache(), MB.metas()
    for h in hs:
        cand = MB.candidatas(list(metas), cache[h]["sim"].astype(np.float32), k)
        for forma in ("tema_trecho", "descricao_trecho"):
            out = P._ler_json(perguntar(prompt(forma, T.texto_professor(ac[h]), cand, metas)))
            print("%s | %d candidatas | %-16s | ODS %s | metas %s" % (h, k, forma, sorted({o["n"] for o in out}) if out
                  is not None else "FALHA", [o["meta"] for o in out] if out is not None else []), flush=True)



# 02/11 (hipotese da responsavel, forma B): as 180 metas RESUMIDAS (rascunho em resultados/metas_resumidas_rascunho_v1.json,
# a aprovar pela responsavel), sem o filtro do embedding
RESUMOS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                       "publicacoes", "artigo_ods", "resultados", "metas_resumidas_rascunho_v1.json")


def prompt_resumo(forma, txt):
    P.V8 = forma
    res = {k: v for k, v in json.load(open(RESUMOS, encoding="utf-8")).items() if not k.startswith("_")}
    fixo = P._fixo_v8_texto(0)
    ini, fim = fixo.index("COMO AS METAS SÃO APRESENTADAS"), fixo.index("TAREFA:")
    fixo = (fixo[:ini] + "COMO AS METAS SÃO APRESENTADAS: as 180 metas vêm com o seu código e um resumo que junta o texto "
            "global da ONU e o texto adaptado ao Brasil pelo Ipea (2026).\n\n" + fixo[fim:])
    fixo = fixo.replace("metas candidatas", "metas").replace("meta candidata", "meta").replace(", na META ONU ou na META IPEA", "")
    lista = "\n".join("[%s] %s" % (k, v) for k, v in res.items())
    return (fixo + "<|im_start|>user\nAS 180 METAS (resumo):\n" + lista + "\n\nDOCUMENTO:\n" + txt +
            "\n\nResponda só o JSON.<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n")


def main_resumo(hs):
    ac = carregar_acervo()
    for h in hs:
        for forma in ("tema_trecho", "descricao_trecho"):
            out = P._ler_json(perguntar(prompt_resumo(forma, T.texto_professor(ac[h]))))
            print("%s | resumo 180 | %-16s | ODS %s | metas %s" % (h, forma, sorted({o["n"] for o in out}) if out is not None
                  else "FALHA", [o["meta"] for o in out] if out is not None else []), flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "--180":
        main_180(sys.argv[2:])
    elif sys.argv[1] == "--resumo":
        main_resumo(sys.argv[2:])
    elif sys.argv[1] == "--k":
        main_k(int(sys.argv[2]), sys.argv[3:])
    else:
        main()
