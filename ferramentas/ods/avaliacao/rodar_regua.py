# -*- coding: utf-8 -*-
"""Roda os professores nos 1.192 itens da regua (gabarito v7, D33) com o prompt em uso (v4, D34; ODS_PROMPT=3 para
o v3), com trecho. Um modelo por vez (a GPU de 8 GB nao comporta dois).

Os modelos nao veem os rotulos: o arquivo de itens entregue ao comparador so tem a lista de handles. As notas saem
depois, contra o gabarito v7, em notas_regua.py (com a indexacao humana atual como linha de base).
Feche o menu da suite (executar.py) antes: com ele aberto, o professor fica ~10x mais lento (22/10).
Uso: python ferramentas/ods/avaliacao/rodar_regua.py [modelo ...]
"""
import json
import os
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
ITENS = os.path.join(RAIZ, "dados", "gabarito_v7", "itens_regua.json")   # so a lista de handles, sem rotulo
MODELOS = sys.argv[1:] or ["qwen3.5-9b", "gemma4-26b", "qwen3.5-35b", "gpt-oss-20b"]


def main():
    hs = sorted(json.load(open(os.path.join(RAIZ, "dados", "gabarito_v7", "amostra.json"), encoding="utf-8"))["itens"])
    if os.getenv("ODS_REGUA_N"):     # amostra fixa da regua (semente 100), a mesma para todos os modelos
        import random
        hs = random.Random(100).sample(hs, int(os.environ["ODS_REGUA_N"]))
    json.dump({"itens": {h: [] for h in hs}}, open(ITENS, "w", encoding="utf-8"))
    print("%d itens da regua (gabarito v7); prompt v%s" % (len(hs), os.getenv("ODS_PROMPT", "4")), flush=True)
    for m in MODELOS:
        t0 = time.time()
        print("=== %s: inicio %s" % (m, time.strftime("%H:%M")), flush=True)
        env = dict(os.environ, ODS_PROFESSOR=m, ODS_GABARITO=ITENS, ODS_ROTULO=os.getenv("ODS_ROTULO_REGUA", "_regua"), PYTHONIOENCODING="utf-8")
        r = subprocess.run([sys.executable, "-W", "ignore", os.path.join(RAIZ, "ferramentas", "ods", "avaliacao",
                                                                         "comparar_professores_v3.py")],
                           cwd=RAIZ, env=env)
        print("=== %s: fim (rc=%d) em %.0f min" % (m, r.returncode, (time.time() - t0) / 60), flush=True)


if __name__ == "__main__":
    main()
