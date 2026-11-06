# -*- coding: utf-8 -*-
"""Rodada do acervo inteiro (somente leitura do ARCA; nada e gravado no repositorio):

  1) resumos do PDF (D10) que faltam — feitos pelo Qwen3.5-9B (cabe inteiro na GPU, ~4x mais rapido para
     escrever; mesmo modelo dos resumos ja existentes);
  2) sinais (ODSBahia + Qwen3-Embedding-8B) dos itens cujo texto mudou com o resumo do PDF;
  3) o professor (D28: Qwen3.5-9B por padrao; --professor gemma4-26b para o Gemma) rotula com o prompt v3 e o
     trecho literal todos os itens ainda sem rotulo valido (um arquivo de rotulos por professor).

Tudo e salvo item a item / lote a lote, com gravacao atomica: se a luz cair, rodar de novo continua de onde
parou. Uma trava impede duas rodadas ao mesmo tempo. Registro em logs/rodada_acervo.log.
Uso: python ferramentas/ods/ods_rodada_acervo.py
"""
import os
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "ferramentas", "ods"))
LOG = os.path.join(RAIZ, "logs", "rodada_acervo.log")
TRAVA = os.path.join(RAIZ, "logs", "rodada_acervo.pid")


def log(msg):
    linha = time.strftime("%d/%m %H:%M:%S ") + msg
    print(linha, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def _rodando(pid):
    """O PID e reaproveitado pelo Windows apos reiniciar: confere se o processo e mesmo esta rodada."""
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "(Get-CimInstance Win32_Process -Filter 'ProcessId=%d').CommandLine" % pid],
                       capture_output=True, text=True)
    return "ods_rodada_acervo" in r.stdout


def etapa_resumos():
    """Roda em processo proprio com ODS_PROFESSOR=qwen3.5-9b (a escolha do modelo e feita na importacao)."""
    from arca import ods_professor as P, ods_textocompleto as TC
    from arca.decs_acervo import carregar_acervo
    ac = carregar_acervo()
    log("ETAPA 1: resumos do PDF (%s)" % P.NOME)
    TC.preparar(list(ac.values()), aviso=log)
    P.parar_servidor()


def principal():
    if os.path.exists(TRAVA):
        try:
            pid = int(open(TRAVA).read().strip())
            if pid != os.getpid() and _rodando(pid):
                log("outra rodada ja esta ativa (PID %d); esta nao inicia" % pid)
                return
        except ValueError:
            pass
    open(TRAVA, "w").write(str(os.getpid()))
    # D28: professor da rodada (o modelo e escolhido na importacao de ods_professor). Padrao: Qwen3.5-9B, o primeiro
    # a rotular o acervo com o prompt v3; depois o Gemma, com --professor gemma4-26b, para a votacao.
    if "--professor" in sys.argv:
        os.environ["ODS_PROFESSOR"] = sys.argv[sys.argv.index("--professor") + 1]
    os.environ.setdefault("ODS_PROFESSOR", "qwen3.5-9b")
    try:
        log("=== rodada do acervo iniciada/retomada ===")
        from arca import config
        for _ in range(60):          # logo apos ligar o computador o arquivo pode ainda nao estar acessivel
            if os.path.exists(config.ACERVO_JSON):
                break
            time.sleep(10)
        else:
            log("acervo nao encontrado em %s apos 10 min; rode o atalho 'Retomar ODS' de novo" % config.ACERVO_JSON)
            return
        amb = dict(os.environ, ODS_PROFESSOR="qwen3.5-9b")
        r = subprocess.run([sys.executable, "-u", os.path.abspath(__file__), "--resumos"], env=amb)
        if r.returncode != 0:
            log("etapa 1 terminou com erro (codigo %d); sigo com o que ja ficou pronto" % r.returncode)
        from arca import ods_metabusca as MB, ods_professor as P, ods_sinais as S, ods_textocompleto as TC
        from arca.decs_acervo import carregar_acervo
        import ods_treinar_avaliar as TA
        TA.log = log
        ac = carregar_acervo()
        hs = sorted(ac)
        log("ETAPA 2: sinais dos itens cujo texto mudou (embedding %s)" % MB.MODELO)
        P.parar_servidor()
        cache = S.calcular(hs, ac, aviso=log)
        MB.liberar()
        S._M.clear()
        rot = P.carregar_cache()
        falta = [h for h in hs if h not in rot or rot[h].get("pdf", 0) != TC.marcador(ac[h])
                 or rot[h].get("sinais") != S.VERSAO_SINAIS or rot[h].get("modelo") != P.NOME
                 or rot[h].get("prompt") not in P.PROMPTS_ACEITOS or rot[h].get("ods") is None]
        log("ETAPA 3: professor %s, prompt v%d: %d de %d itens a rotular" % (P.NOME, P.PROMPT_VERSAO, len(falta), len(hs)))
        if falta:
            if not P.iniciar_servidor(aviso=log):
                log("professor nao subiu; rode de novo mais tarde")
                return
            TA.rotular_professor(falta, ac, cache)
            P.parar_servidor()
        rot = P.carregar_cache()
        ok = sum(1 for h in hs if rot.get(h, {}).get("ods") is not None and rot[h].get("modelo") == P.NOME
                 and rot[h].get("prompt") in P.PROMPTS_ACEITOS)
        log("=== FIM: %d de %d itens rotulados pelo professor ===" % (ok, len(hs)))
    finally:
        if os.path.exists(TRAVA) and open(TRAVA).read().strip() == str(os.getpid()):
            os.remove(TRAVA)


if __name__ == "__main__":
    if "--resumos" in sys.argv:
        etapa_resumos()
    else:
        principal()
