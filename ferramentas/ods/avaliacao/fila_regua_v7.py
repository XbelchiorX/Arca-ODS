# -*- coding: utf-8 -*-
"""Fila da GPU para a regua v7 (28/10): espera a rotina diaria terminar, atualiza a similaridade das 14 metas
corrigidas e roda os 4 professores com o prompt v4. Estado em dados/gabarito_v7/fila_status.txt (lido pelo monitor).
Uso: python ferramentas/ods/avaliacao/fila_regua_v7.py
"""
import os
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PASTA = os.path.join(RAIZ, "dados", "gabarito_v7")
STATUS = os.path.join(PASTA, "fila_status.txt")
METAS_ANTIGAS = r"\\SEU_NAS\compartilhamento\tmp\arca_ods_gabaritos_v4_v6_descartados_20261028" \
                r"\metas_2026_com_cabecalhos\metas_2026.json"


def estado(s):
    open(STATUS, "w", encoding="utf-8").write("%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), s))
    print(time.strftime("%H:%M"), s, flush=True)


def rotina_rodando():
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | Where-Object { "
                        "$_.CommandLine -like '*rotina_diaria.py*' }"   # so python: o proprio powershell tem o texto
                        " | Measure-Object | Select-Object -ExpandProperty Count"], capture_output=True, text=True)
    return r.stdout.strip() not in ("", "0")


def main():
    while rotina_rodando():
        estado("esperando a rotina diaria terminar (GPU ocupada)")
        time.sleep(60)
    estado("atualizando a similaridade das metas corrigidas")
    r = subprocess.run([sys.executable, os.path.join(RAIZ, "ferramentas", "ods", "referencia", "atualizar_sim_metas.py"),
                        METAS_ANTIGAS], cwd=RAIZ)
    if r.returncode:
        estado("ERRO ao atualizar a similaridade das metas (rc=%d); professores nao rodaram" % r.returncode)
        sys.exit(1)
    env = dict(os.environ, ODS_PROMPT="4", ODS_PROGRESSO=os.path.join(PASTA, "progresso_professor.txt"))
    for m in ["qwen3.5-9b", "gemma4-26b", "qwen3.5-35b", "gpt-oss-20b"]:
        estado("professor %s" % m)
        subprocess.run([sys.executable, os.path.join(RAIZ, "ferramentas", "ods", "avaliacao", "rodar_regua.py"), m],
                       cwd=RAIZ, env=env)
    estado("FIM")


if __name__ == "__main__":
    main()
