# -*- coding: utf-8 -*-
"""Gabarito v8 de ODS (30/10): os 300 itens da regua usados nos testes do prompt v8 (semente 100), rotulados de novo
SEM trecho, com o MESMO texto do prompt v8 texto do professor (arca/ods_professor.py, FIXO_V8_TEXTO e
_fixo_v8_texto(0)). Diferencas so estruturais: as 180 metas em vez das candidatas (o gabarito nao pode herdar os
erros da busca de candidatas), 10 documentos por lote ("julgue cada documento separadamente") e o handle na resposta.
Saem do gabarito v7 as frases que o professor nao recebe ("nao use nenhum criterio..." e "confira cada ODS...").

Dois rotuladores independentes (A2 e B2), lotes de 10, ordem sorteada propria (sementes 3 e 4).
  --preparar       grava dados/gabarito_v8/instrucao_e_metas.txt, lotes_A2/, lotes_B2/
  --conferir A2|B2 confere rotulos_<r>/lote_NNN.jsonl: JSON, um registro por handle do lote, meta existente e do ODS
Uso: python ferramentas/ods/avaliacao/gabarito_v8.py --preparar | --conferir A2
"""
import json
import os
import random
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from arca.ods_metas import OBJETIVOS  # noqa: E402
from arca.ods_professor import _ESTRUTURA_V8, _ROT_V8, _partes_meta  # noqa: E402
from gabarito_v7 import AMOSTRA, METAS, _quebrar  # noqa: E402

PASTA = os.path.join(RAIZ, "dados", "gabarito_v8")
TAM_LOTE = 10

INSTRUCAO = (
    "Você classifica documentos de um repositório institucional pelos Objetivos de Desenvolvimento Sustentável "
    "(ODS).\n\n" + _ESTRUTURA_V8 + "\n\nOS 18 ODS:\n" + "\n".join("%d: %s" % (n, t) for n, t in OBJETIVOS.items()) +
    "\n\nCOMO AS METAS SÃO APRESENTADAS: cada meta vem com o seu código e até três partes:\n"
    "- META ONU: o texto global da meta, da ONU.\n"
    "- META IPEA: o texto da mesma meta adaptado ao Brasil pelo Ipea (2026); pode mudar ou acrescentar temas ao "
    "texto da ONU.\n"
    "- CONCEITOS IPEA: a explicação, pelo Ipea, dos termos usados na meta.\n"
    "Quando o Ipea manteve o texto da ONU, aparece uma parte só, META ONU E IPEA. As metas que só existem no Brasil "
    "(por exemplo, as do ODS 18) não têm META ONU. Algumas metas não têm CONCEITOS IPEA. Em algumas metas, a META "
    "IPEA é dividida em submetas (por exemplo, 5.b.1 e 5.b.2br); a meta a indicar é sempre o código da meta (5.b).\n\n"
    "TAREFA: leia cada documento e as metas abaixo. Julgue cada documento separadamente. O documento pode se "
    "relacionar com nenhum, um ou mais ODS. Atribua um ODS somente se o documento trata do que uma das metas "
    "descreve, na META ONU ou na META IPEA; indique essa meta. Se nenhuma se aplica, devolva a lista vazia.\n\n"
    "RESPONDA SÓ com JSON, uma linha por documento, inclusive os sem ODS, sem texto fora dele, um item por ODS "
    "atribuído:\n"
    '{"handle": "<handle>", "ods": [{"n": 3, "meta": "3.3"}]}\n'
    'Lista vazia se nenhum ODS se aplica: {"handle": "<handle>", "ods": []}')


def itens_300():
    itens = json.load(open(AMOSTRA, encoding="utf-8"))["itens"]
    hs = random.Random(100).sample(sorted(itens), 300)       # a mesma amostra de rodar_regua.py (ODS_REGUA_N=300)
    return {h: itens[h] for h in hs}


def cabecalho():
    ms = json.load(open(METAS, encoding="utf-8"))
    blocos = ["[%s]\n" % c + "\n".join("  %s: %s" % (_ROT_V8[r], t) for r, t in _partes_meta(m)) for c, m in ms.items()]
    return INSTRUCAO + "\n\nMETAS (%d):\n" % len(ms) + "\n\n".join(blocos) + "\n"


def preparar():
    itens = itens_300()
    os.makedirs(PASTA, exist_ok=True)
    open(os.path.join(PASTA, "instrucao_e_metas.txt"), "w", encoding="utf-8").write(_quebrar(cabecalho()))
    json.dump({"itens": {h: v for h, v in itens.items()}}, open(os.path.join(PASTA, "amostra.json"), "w",
                                                                  encoding="utf-8"), ensure_ascii=False)
    for rot, semente in (("A2", 3), ("B2", 4)):
        pasta = os.path.join(PASTA, "lotes_" + rot)
        if os.path.exists(pasta):
            sys.exit("ja existe %s; nada foi sobrescrito" % pasta)
        os.makedirs(pasta)
        os.makedirs(os.path.join(PASTA, "rotulos_" + rot), exist_ok=True)
        hs = sorted(itens)
        random.Random(semente).shuffle(hs)
        for k in range(0, len(hs), TAM_LOTE):
            lote = hs[k:k + TAM_LOTE]
            open(os.path.join(pasta, "lote_%03d.txt" % (k // TAM_LOTE + 1)), "w", encoding="utf-8").write(
                _quebrar("DOCUMENTOS:\n\n" + "\n\n".join("[handle: %s]\n%s" % (h, itens[h]["texto"]) for h in lote) + "\n"))
        print(rot, len(hs), "itens,", (len(hs) + TAM_LOTE - 1) // TAM_LOTE, "lotes")


def conferir(rot):
    ms = json.load(open(METAS, encoding="utf-8"))
    pasta_l, pasta_r = os.path.join(PASTA, "lotes_" + rot), os.path.join(PASTA, "rotulos_" + rot)
    ok, falhas, faltam = 0, [], []
    for arq in sorted(os.listdir(pasta_l)):
        esperados = re.findall(r"^\[handle: (\S+)\]$", open(os.path.join(pasta_l, arq), encoding="utf-8").read(), re.M)
        saida = os.path.join(pasta_r, arq.replace(".txt", ".jsonl"))
        if not os.path.exists(saida):
            faltam.append(arq)
            continue
        vistos = {}
        for ln in open(saida, encoding="utf-8"):
            if ln.strip():
                try:
                    r = json.loads(ln)
                    vistos[r["handle"]] = r["ods"]
                except (ValueError, KeyError, TypeError):
                    falhas.append((arq, "?", "linha nao e JSON valido: " + ln[:80]))
        for h in esperados:
            if h not in vistos:
                falhas.append((arq, h, "sem resposta"))
                continue
            erro = None
            for o in vistos[h]:
                n, meta = o.get("n"), str(o.get("meta", ""))
                if not isinstance(n, int) or not 1 <= n <= 18:
                    erro = "ODS invalido: %r" % n
                elif meta not in ms or ms[meta]["ods"] != n:
                    erro = "meta %s nao existe ou nao e do ODS %s" % (meta, n)
                if erro:
                    break
            if erro:
                falhas.append((arq, h, erro))
            else:
                ok += 1
        for h in set(vistos) - set(esperados):
            falhas.append((arq, h, "handle fora do lote"))
    print("rotulador %s: %d itens aprovados; %d falhas; %d lotes sem resposta" % (rot, ok, len(falhas), len(faltam)))
    for f in falhas:
        print("  %s %s: %s" % f)
    return falhas, faltam


if __name__ == "__main__":
    if "--preparar" in sys.argv:
        preparar()
    elif "--conferir" in sys.argv:
        conferir(sys.argv[sys.argv.index("--conferir") + 1])
