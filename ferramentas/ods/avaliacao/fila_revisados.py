# -*- coding: utf-8 -*-
"""Fila da GPU (02/11, pedido da responsavel): os prompts finalistas nos registros que ela ja revisou, em 4 modelos.
Finalistas (v8): tema + trecho como prova, resumo livre sem trecho, nota 0-100; v3 com trecho so como referencia.
Modelos: Qwen3.5-35B (atual), Gemma 4 26B, Qwen3.8-27B, Llama-3.1-8B e (base dos pequenos) Gemma 4 E4B e E2B. Todos com as metas corrigidas (28/10), sem
raciocinio, 20 metas. Teste ja gravado e pulado. Estado em dados/gabarito_v8/fila_revisados_status.txt.
Uso: python ferramentas/ods/avaliacao/fila_revisados.py
"""
import os
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PROF = os.path.join(RAIZ, "publicacoes", "artigo_ods", "resultados", "professor")
STATUS = os.path.join(RAIZ, "dados", "gabarito_v8", "fila_revisados_status.txt")
GAB = os.path.join(RAIZ, "dados", "gabarito_v8", "revisados_parcial.json")
NOMES = {"qwen3.5-35b": "Qwen3.5-35B-A3B-Q4_K_M", "gemma4-26b": "gemma-4-26B-A4B-it-qat-q4_0",
         "qwen3.8-27b": "Qwen3.8-27B-UD-Q4_K_M", "llama3.1-8b": "Meta-Llama-3.1-8B-Instruct-Q4_K_M",
         "gemma4-e4b": "gemma-4-E4B-it-qat-q4_0", "gemma4-e2b": "gemma-4-E2B-it-qat-q4_0"}
# (prompt, forma do v8, com trecho)
FORMAS = [(8, "tema_trecho", True), (8, "tema_livre", False), (8, "nota", False), (3, "", True),
          (8, "duas_etapas", True),   # 02/11: tema numa 1a chamada, sem ver as metas
          (8, "descricao_trecho", True), (9, "", True)]   # v9 = descricao + trecho   # 02/11: tema + trecho com a descricao sem limite no lugar do tema
# 02/11: Qwen3.8-27B e Llama-3.1-8B descartados pela responsavel (resultados guardados); ficam os outros 4
MODELOS = ("qwen3.5-35b", "gemma4-26b", "gemma4-e4b", "gemma4-e2b")
V9 = [(m, 9, "", True) for m in MODELOS]   # 02/11: so o v9 nos modelos locais (pedido da responsavel)
# 02/11: a abordagem nova (duas etapas, descricao sem limite) primeiro, nos 4 modelos; depois o que faltar das outras
NOVAS = ("descricao_trecho", "duas_etapas")   # a mais nova primeiro
TESTES = ([(m, p, f, t) for f0 in NOVAS for m in MODELOS for p, f, t in FORMAS if f == f0] +
          [(m, p, f, t) for m in MODELOS for p, f, t in FORMAS if f not in NOVAS])
PROGRESSO = os.path.join(RAIZ, "dados", "gabarito_v8", "fila_revisados_progresso.txt")   # "feitos total" (monitor)


def rotulo(p, f):
    return "_revisados_metas2026_" + ("v8" + f if p == 8 else "v%d" % p)


def arquivo(m, p, f, t):
    return os.path.join(PROF, "comparacao_v%d_%s%s%s.json" % (p, NOMES[m], "" if t else "_sem_trecho", rotulo(p, f)))


def estado(s):
    open(STATUS, "w", encoding="utf-8").write("%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), s))
    print(time.strftime("%H:%M"), s, flush=True)


def main():
    atual = None
    for i, (m, p, f, t) in enumerate(V9 if "--v9" in sys.argv else TESTES, 1):
        if os.path.exists(arquivo(m, p, f, t)):
            print("ja feito:", os.path.basename(arquivo(m, p, f, t)), flush=True)
            continue
        if m != atual:      # outro modelo: derruba o servidor do anterior
            subprocess.run(["taskkill", "/IM", "llama-server.exe", "/F"], capture_output=True)
            time.sleep(5)
            atual = m
        open(PROGRESSO, "w").write("0 11")
        estado("teste %d de %d: %s, prompt v%d %s" % (i, len(TESTES), m, p, f))
        env = dict(os.environ, ODS_PROFESSOR=m, ODS_PROMPT=str(p), ODS_V8=f or "texto", ODS_V8_TEMA="0",
                   ODS_COM_TRECHO="sim" if t else "nao", ODS_PENSAR="nao", ODS_N_METAS="20", ODS_GABARITO=GAB,
                   ODS_ROTULO=rotulo(p, f), ODS_LLM_ESPERA="1800", PYTHONIOENCODING="utf-8",
                   ODS_PROGRESSO=PROGRESSO)
        env.pop("ODS_N", None)
        subprocess.run([sys.executable, os.path.join(RAIZ, "ferramentas", "ods", "avaliacao", "comparar_professores_v3.py")],
                       cwd=RAIZ, env=env)
        if not os.path.exists(arquivo(m, p, f, t)):
            print("AVISO: teste sem arquivo de saida:", arquivo(m, p, f, t), flush=True)
    subprocess.run(["taskkill", "/IM", "llama-server.exe", "/F"], capture_output=True)
    estado("FIM")


if __name__ == "__main__":
    main()
