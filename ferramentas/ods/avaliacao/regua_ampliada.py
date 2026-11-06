# -*- coding: utf-8 -*-
"""Regua ampliada para escolher o professor de ODS (D29, decisao do responsavel em 2026-10-27).

O gabarito v4 (150 itens sorteados) tem de 1 a 12 exemplos dos ODS raros. A regua ampliada acrescenta 40 itens por
ODS (exceto o 3, que ja aparece em 114 dos 150 do v4), sorteados (semente 20261027) dos estratos montados em
04/10 para o gabarito v3 (dados/gabarito_v3/selecao.json): 180 candidatos por ODS escolhidos por sinais indiretos
(embedding Qwen3-Embedding-8B e ODSBahia), nunca por rotulo humano ou de modelo. O estrato diz so onde PROCURAR: o
rotulo e dado as cegas, meta a meta, como no v4 (o item do estrato do ODS 7 pode nao ter ODS 7).
Fora da amostra: os 150 do v4 e os 1.000 da planilha de revisao do professor.

Saida: dados/gabarito_claude_v5/ (amostra.json com o texto exato entregue, lote_NN.txt de 25 itens, metas_completas.txt)
Uso: python ferramentas/ods/avaliacao/regua_ampliada.py
"""
import json
import os
import random
import shutil
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, RAIZ)
from arca import config, decs_acervo  # noqa: E402
from arca.ods_texto import texto_professor  # noqa: E402

SEMENTE = 20261027
POR_ODS = 40
LOTE = 25
SAIDA = os.path.join(RAIZ, "dados", "gabarito_claude_v5")
V4 = os.path.join(RAIZ, "dados", "gabarito_claude_v4")


def main():
    sel = json.load(open(os.path.join(RAIZ, "dados", "gabarito_v3", "selecao.json"), encoding="utf-8"))["itens"]
    fora = set(json.load(open(os.path.join(V4, "amostra.json"), encoding="utf-8"))["itens"])
    fora |= set(json.load(open(os.path.join(config.SAIDAS, "ods", "revisao_professor_1000_rotulos.json"),
                               encoding="utf-8")))
    acervo = decs_acervo.carregar_acervo()
    rnd = random.Random(SEMENTE)
    escolhidos, estrato = [], {}
    for n in [x for x in range(1, 19) if x != 3]:
        pool = sorted(h for h, v in sel.items() if v["origem"] == "estratificado_ods%d" % n
                      and h not in fora and h in acervo and h not in estrato)
        rnd.shuffle(pool)
        for h in pool[:POR_ODS]:
            estrato[h] = n
            escolhidos.append(h)
        print("ODS %2d: %d candidatos, %d escolhidos" % (n, len(pool), min(POR_ODS, len(pool))))
    rnd.shuffle(escolhidos)                  # lotes misturam estratos: o rotulador nao sabe de qual estrato veio
    textos = {h: texto_professor(acervo[h]) for h in escolhidos}
    os.makedirs(SAIDA, exist_ok=True)
    # o estrato fica FORA da pasta dos rotuladores (rotulagem as cegas)
    json.dump({"semente": SEMENTE, "estrato": estrato}, open(SAIDA + "_estratos.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump({"semente": SEMENTE, "descricao": __doc__.split("\n\n")[0], "itens": escolhidos, "textos": textos},
              open(os.path.join(SAIDA, "amostra.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    shutil.copy(os.path.join(V4, "metas_completas.txt"), os.path.join(SAIDA, "metas_completas.txt"))
    for k in range(0, len(escolhidos), LOTE):
        with open(os.path.join(SAIDA, "lote_%02d.txt" % (k // LOTE + 1)), "w", encoding="utf-8") as f:
            for i, h in enumerate(escolhidos[k:k + LOTE], 1):
                f.write("=== [%d] %s ===\n%s\n\n" % (i, h, textos[h]))
    print("%d itens em %d lotes: %s" % (len(escolhidos), -(-len(escolhidos) // LOTE), SAIDA))


if __name__ == "__main__":
    main()
