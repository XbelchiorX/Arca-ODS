# -*- coding: utf-8 -*-
"""Gabarito de ODS com o GPT-6.1 Sol no Copilot (03/11, decisao da responsavel): 500 itens = os 300 da regua (mesma
amostra de gabarito_v8.py) + 200 sorteados do restante da amostra v7 (semente 101). Mesma instrucao do gabarito v8
(180 metas, lotes de 10), mas SEM os CONCEITOS IPEA (decisao da responsavel: so a meta). Lote acima do limite do
Copilot (~120 mil caracteres) e dividido. Cada arquivo de dados/gabarito_sol/mensagens/ e a mensagem de um chat novo.
  --preparar   grava amostra.json e mensagens/lote_NNN.txt (ordem sorteada, semente 5)
"""
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gabarito_v8 import AMOSTRA, RAIZ, TAM_LOTE, _quebrar, cabecalho, itens_300  # noqa: E402

PASTA = os.path.join(RAIZ, "dados", "gabarito_sol")
N_EXTRA = 200
LIMITE = 115000


def sem_conceitos(cab):
    cab = re.sub(r"\n\s*CONCEITOS IPEA:.*?(?=\n\n\[|\Z)", "", cab, flags=re.S)
    cab = cab.replace("até três partes", "até duas partes")
    cab = re.sub(r"- CONCEITOS IPEA:.*?\n", "", cab)
    return cab.replace(" Algumas metas não têm CONCEITOS IPEA.", "")


def preparar():
    todos = json.load(open(AMOSTRA, encoding="utf-8"))["itens"]
    base = itens_300()
    resto = sorted(set(todos) - set(base))
    if len(resto) < N_EXTRA:
        sys.exit("amostra v7 so tem %d itens alem dos 300" % len(resto))
    itens = dict(base)
    itens.update({h: todos[h] for h in random.Random(101).sample(resto, N_EXTRA)})
    pasta = os.path.join(PASTA, "mensagens")
    if os.path.exists(pasta):
        sys.exit("ja existe %s; nada foi sobrescrito" % pasta)
    cab = sem_conceitos(_quebrar(cabecalho()))
    if "CONCEITOS" in cab:
        sys.exit("sobrou CONCEITOS na instrucao")
    os.makedirs(pasta)
    json.dump({"itens": itens}, open(os.path.join(PASTA, "amostra.json"), "w", encoding="utf-8"), ensure_ascii=False)
    hs = sorted(itens)
    random.Random(5).shuffle(hs)

    def grupos(lote):
        doc = "DOCUMENTOS:\n\n" + "\n\n".join("[handle: %s]\n%s" % (h, itens[h]["texto"]) for h in lote)
        msg = cab + "\n" + _quebrar(doc) + "\n"
        if len(msg) <= LIMITE or len(lote) == 1:
            return [msg]
        return grupos(lote[:len(lote) // 2]) + grupos(lote[len(lote) // 2:])

    n = 0
    for k in range(0, len(hs), TAM_LOTE):
        for msg in grupos(hs[k:k + TAM_LOTE]):
            n += 1
            open(os.path.join(pasta, "lote_%03d.txt" % n), "w", encoding="utf-8").write(msg)
    print(len(hs), "itens,", n, "mensagens")


def ampliar():
    """04/11 (responsavel): 1000 registros para medir o F1. Mais 500 sorteados do resto da amostra v7 (semente 102), nas mensagens lote_101 em diante."""
    pasta = os.path.join(PASTA, "mensagens")
    atual = json.load(open(os.path.join(PASTA, "amostra.json"), encoding="utf-8"))["itens"]
    saida = os.path.join(PASTA, "amostra_1000.json")
    if os.path.exists(saida):
        sys.exit("ja existe %s; nada foi sobrescrito" % saida)
    todos = json.load(open(AMOSTRA, encoding="utf-8"))["itens"]
    novos = random.Random(102).sample(sorted(set(todos) - set(atual)), 500)
    cab = sem_conceitos(_quebrar(cabecalho()))
    if "CONCEITOS" in cab:
        sys.exit("sobrou CONCEITOS na instrucao")
    itens = dict(atual)
    itens.update({h: todos[h] for h in novos})
    json.dump({"itens": itens}, open(saida, "w", encoding="utf-8"), ensure_ascii=False)
    random.Random(6).shuffle(novos)

    def grupos(lote):
        doc = "DOCUMENTOS:\n\n" + "\n\n".join("[handle: %s]\n%s" % (h, itens[h]["texto"]) for h in lote)
        msg = cab + "\n" + _quebrar(doc) + "\n"
        if len(msg) <= LIMITE or len(lote) == 1:
            return [msg]
        return grupos(lote[:len(lote) // 2]) + grupos(lote[len(lote) // 2:])

    n = 100
    for k in range(0, len(novos), TAM_LOTE):
        for msg in grupos(novos[k:k + TAM_LOTE]):
            n += 1
            open(os.path.join(pasta, "lote_%03d.txt" % n), "w", encoding="utf-8").write(msg)
    print(len(itens), "itens no total; mensagens lote_101 a lote_%03d" % n)


if __name__ == "__main__":
    ampliar() if "--ampliar" in sys.argv else preparar()
