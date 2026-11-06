# -*- coding: utf-8 -*-
"""Fila da GPU dos testes do prompt v8 (30/10): os mesmos 300 itens da regua (semente 100), sem trecho, um teste por
vez, sozinha (nao depende do Claude). Espera a rotina diaria terminar antes de cada teste. Teste ja gravado e pulado.
Estado em dados/gabarito_v7/fila_v8_status.txt; progresso do teste atual em progresso_professor.txt (monitor_v8.py).
Uso: python ferramentas/ods/avaliacao/fila_v8.py
"""
import os
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fila_regua_v7 import rotina_rodando  # noqa: E402

PASTA = os.path.join(RAIZ, "dados", "gabarito_v7")
STATUS = os.path.join(PASTA, "fila_v8_status.txt")
PROF = os.path.join(RAIZ, "publicacoes", "artigo_ods", "resultados", "professor")
NOMES = {"qwen3.5-35b": "Qwen3.5-35B-A3B-Q4_K_M", "gemma4-26b": "gemma-4-26B-A4B-it-qat-q4_0"}
# (modelo, forma do v8, palavras do tema, metas candidatas). 31/10 (pedido da responsavel): sem raciocinio, Qwen 35B e
# Gemma 26B, todas as formas medidas nos 11 revisados (texto, tecnico, nota, tema_trecho, tema_livre), 20 metas.
# tema_trecho e a unica forma com trecho (como prova).
TESTES = [(m, f, 0, 20) for m in ("qwen3.5-35b", "gemma4-26b")
          for f in ("texto", "tecnico", "nota", "tema_trecho", "tema_livre")]


def rotulo(forma, tema, n):
    return "_regua300_v8%s%s_%dmetas" % (forma, "_tema%d" % tema if tema else "", n)


def arquivo(m, forma, tema, n):
    return os.path.join(PROF, "comparacao_v8_%s%s%s.json" % (NOMES[m], "" if forma == "tema_trecho" else "_sem_trecho",
                                                             rotulo(forma, tema, n)))


def estado(s):
    open(STATUS, "w", encoding="utf-8").write("%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), s))
    print(time.strftime("%H:%M"), s, flush=True)


def main():
    for i, (m, forma, tema, n) in enumerate(TESTES, 1):
        if os.path.exists(arquivo(m, forma, tema, n)):
            print("ja feito:", arquivo(m, forma, tema, n), flush=True)
            continue
        while rotina_rodando():
            estado("esperando a rotina diaria terminar (GPU ocupada)")
            time.sleep(60)
        estado("teste %d de %d: %s v8 %s, tema %s, %d metas" % (i, len(TESTES), m, forma, tema or "nao", n))
        env = dict(os.environ, ODS_PROMPT="8", ODS_V8=forma, ODS_V8_TEMA=str(tema), ODS_N_METAS=str(n),
                   ODS_REGUA_N="300", ODS_PENSAR="nao",
                   ODS_COM_TRECHO="sim" if forma == "tema_trecho" else "nao", ODS_ROTULO_REGUA=rotulo(forma, tema, n),
                   ODS_PROGRESSO=os.path.join(PASTA, "progresso_professor.txt"), PYTHONIOENCODING="utf-8")
        env.pop("ODS_N", None)
        subprocess.run([sys.executable, os.path.join(RAIZ, "ferramentas", "ods", "avaliacao", "rodar_regua.py"), m],
                       cwd=RAIZ, env=env)
        if not os.path.exists(arquivo(m, forma, tema, n)):
            print("AVISO: teste sem arquivo de saida:", arquivo(m, forma, tema, n), flush=True)
    estado("FIM")


if __name__ == "__main__":
    main()
