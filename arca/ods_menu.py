# -*- coding: utf-8 -*-
"""Opcoes O do menu: indexacao de ODS (1-18) de ponta a ponta.

Como no DECS, tudo roda em SIMULACAO por padrao (gera o CSV do plano em
saidas/ods/) e gravar exige confirmacao a cada execucao.
"""
import os
import re
import time
from collections import Counter

from rich import box
from rich.prompt import Confirm, Prompt
from rich.table import Table

from . import config
from . import ods_correcao as C
from . import ods_modelo as M
from . import ods_sinais as S
from . import ods_textocompleto as TC
from .ui import aviso, console, erro, info, ler_lista_colada, ok, titulo

METODO = ("ODSBahia (UFSB) + Qwen3-Embedding contra as metas ONU + Ipea 2026 (com ODS 18) + classificador "
          "treinado com rotulos do LLM local Qwen3.5-9B pelos criterios oficiais; sem resumo ou resumo curto: "
          "resumo gerado do texto completo (PDF)")
_CTX = {}


def _modelo():
    if "pacote" not in _CTX:
        p = M.carregar()
        if p is None:
            raise RuntimeError("Modelo de ODS nao treinado. Rode a opcao O5.")
        _CTX["pacote"] = p
    return _CTX["pacote"]


def _acervo():
    if "acervo" not in _CTX:
        from .decs_acervo import carregar_acervo
        _CTX["acervo"] = carregar_acervo()
    return _CTX["acervo"]


def _cliente():
    from . import dspace
    return dspace.conectar(aviso=info)


def _pode_gravar():
    if config.SOMENTE_LEITURA:
        aviso("Modo SOMENTE-LEITURA (ARCA_SOMENTE_LEITURA=sim): o resultado sera uma SIMULACAO.")
        return False
    return Confirm.ask("[bold red]Gravar no ARCA de verdade?[/bold red]", default=False)


def _modo():
    console.print("[bold]substituir[/bold]: o campo fica so com os ODS do modelo. "
                  "[bold]complementar[/bold]: mantem os ODS do catalogador e acrescenta os que faltam.")
    return Prompt.ask("Modo", choices=["substituir", "complementar"], default="substituir")


def _mostrar(handle, linhas):
    tab = Table(title="ODS de %s" % handle, box=box.SIMPLE_HEAVY)
    for c in ("Acao", "ODS", "Prob.", "Valor"):
        tab.add_column(c)
    cor = {"MANTER": "dim", "ADICIONAR": "green", "RETIRAR": "red"}
    for l in linhas:
        if l["ods"] == "":
            tab.add_row("SEM_ODS", "", "", "")
            continue
        k = cor.get(l["acao"], "")
        tab.add_row("[%s]%s[/%s]" % (k, l["acao"], k), str(l["ods"]), l["probabilidade"], C.VALOR[l["ods"]])
    console.print(tab)


def processar(handles, rotulo, ao_vivo=False, mostrar_cada=False):
    pacote = _modelo()
    modo = _modo()
    gravar = _pode_gravar()
    cliente = _cliente() if (gravar or ao_vivo) else None
    acervo = {} if ao_vivo else _acervo()
    rel = C.Relatorio(rotulo)
    status = Counter()
    objs = {}
    if ao_vivo or gravar:
        info("Lendo os itens no ARCA (agora)...")
        from .decs_correcao import item_do_dspace
        for h in handles:
            obj = cliente.item_por_handle(h)
            if not obj:
                status["NAO_ENCONTRADO"] += 1
                continue
            hh = obj.get("handle") or h
            objs[hh] = obj
            acervo[hh] = item_do_dspace(obj)
        handles = list(objs)
    handles = [h for h in handles if h in acervo]
    # sinais: itens lidos agora sao recalculados (o texto pode ter mudado)
    cache = S.carregar_cache() if not (ao_vivo or gravar) else {}
    t0 = time.time()
    TC.preparar([acervo[h] for h in handles], aviso=info)   # D10, antes dos sinais (mesma GPU)
    info("Calculando sinais de %d item(ns)..." % len(handles))
    cache = S.calcular(handles, acervo, cache=cache, aviso=info)
    for a in range(0, len(handles), 500):
        lote = handles[a:a + 500]
        P, pred = M.prever(pacote, lote, cache)
        for k, h in enumerate(lote):
            auto = pred[h]                    # sem trava pos-modelo (D24)
            linhas, final = C.planejar(h, acervo[h], auto, P[k], modo)
            if mostrar_cada:
                _mostrar(h, linhas)
            try:
                if gravar:
                    st = C.gravar(cliente, objs[h], final, METODO)
                else:
                    st = "SIMULADO_" + ("COM" if final != C.humano(acervo[h]) else "SEM") + "_MUDANCA"
            except Exception as e:  # um item com problema nao para o lote
                st = "ERRO"
                erro("%s: %s" % (h, e))
            status[st] += 1
            rel.escrever(linhas)
        info("  %d/%d itens (%.0fs)" % (min(a + 500, len(handles)), len(handles), time.time() - t0))
    caminho = rel.fechar()
    ok("Plano salvo em %s" % caminho)
    for s, n in status.most_common():
        info("  %s: %d" % (s, n))
    tab = Table(title="Acoes", box=box.SIMPLE)
    tab.add_column("Acao")
    tab.add_column("ODS", justify="right")
    for a, n in rel.contagem.most_common():
        tab.add_row(a, str(n))
    console.print(tab)


def o1_um_item():
    titulo("O1 - ODS de um item")
    h = Prompt.ask("Handle, UUID ou URL do item").strip()
    processar([h], "item", ao_vivo=True, mostrar_cada=True)


def o2_lista():
    titulo("O2 - ODS de uma lista de itens")
    colado = ler_lista_colada("Cole handles/UUIDs/URLs (ou o caminho de um .txt). Linha vazia termina.")
    caminho = " ".join(colado).strip('"') if len(colado) <= 3 else ""
    if caminho and os.path.isfile(caminho):
        with open(caminho, encoding="utf-8") as f:
            handles = [x for x in re.split(r"[\s,;]+", f.read().strip()) if x]
    else:
        handles = colado
    info("%d item(ns)." % len(handles))
    processar(handles, "lista", ao_vivo=len(handles) <= 200, mostrar_cada=len(handles) <= 10)


def o3_todos():
    titulo("O3 - ODS do acervo inteiro (a partir do acervo coletado na D4)")
    acervo = _acervo()
    desde = Prompt.ask("Itens depositados a partir de (AAAA-MM-DD, vazio = todos)", default="")
    hs = sorted(acervo)
    if desde:
        hs = [h for h in hs if any((d.get("value") or "")[:10] >= desde for d in acervo[h].get("dc.date.accessioned", []))]
    qual = Prompt.ask("Quais itens?", choices=["todos", "com_ods", "sem_ods"], default="todos")
    if qual == "com_ods":
        hs = [h for h in hs if acervo[h].get("ods")]
    elif qual == "sem_ods":
        hs = [h for h in hs if not acervo[h].get("ods")]
    info("%d item(ns)." % len(hs))
    processar(hs, "todos")


def o4_sinais():
    titulo("O4 - Calcular os sinais de ODS do acervo (somente leitura, GPU)")
    acervo = _acervo()
    TC.preparar(list(acervo.values()), aviso=info)
    S.calcular(sorted(acervo), acervo, aviso=info)
    ok("Sinais em %s" % S.CACHE_PKL)


def o5_treinar():
    titulo("O5 - Rotular com o professor, treinar e avaliar o modelo de ODS")
    import runpy
    runpy.run_path(os.path.join(config.RAIZ, "ferramentas", "ods", "ods_treinar_avaliar.py"), run_name="__main__")
    _CTX.pop("pacote", None)


def o6_professor_v3():
    """Testa o professor (prompt v3 fechado em 22/10: lista dos 18 ODS + 20 metas candidatas + trecho literal) em
    itens escolhidos. Mostra o resultado e, se o usuario confirmar, o campo de ODS do item passa a ser EXATAMENTE o do
    metodo (entra o que falta, sai o que o metodo nao contempla; pedido do responsavel, 22/10). O ODS anterior fica
    guardado uma vez so em [ODS-ORIGINAL] e a nota [ODS-AUTO] e atualizada."""
    import numpy as np
    from . import dspace, ods_metabusca as MB, ods_professor as P, ods_sinais as S, ods_texto as T
    from .decs_correcao import item_do_dspace
    from .ui import titulo
    titulo("O6 - Professor v3 (%s): mostra e, se confirmar, deixa so os ODS do metodo" % P.NOME)
    # como o D2: varias linhas, tabulacao, virgula, ponto e virgula ou espaco; links do Arca; ou o caminho de um .txt
    from .decs_menu import _ler_handles
    colado = ler_lista_colada("Cole os handles, UUIDs ou URLs (um por linha, ou separados por tabulacao, virgula, "
                              "ponto e virgula ou espaco) OU o caminho de um .txt. Linha vazia termina.")
    caminho = " ".join(colado).strip('"') if len(colado) <= 3 else ""
    if caminho and os.path.isfile(caminho):
        with open(caminho, encoding="utf-8") as f:
            hs = _ler_handles(f.read())
    else:
        hs = colado
    info("%d item(ns)." % len(hs))
    cli = dspace.conectar()
    itens = {}
    for h in hs:
        obj = cli.item_por_handle(h)
        if obj:
            itens[obj.get("handle") or h] = item_do_dspace(obj)
    if not itens:
        return
    cache = S.calcular(list(itens), itens)                  # embedding das metas (GPU), depois libera
    MB.liberar()
    metas = MB.metas()
    if not P.iniciar_servidor():
        console.print("Professor nao subiu (veja logs/llama_server.log).")
        return
    try:
        for h, it in itens.items():
            cand = MB.candidatas(list(metas), cache[h]["sim"].astype(np.float32))
            r = P.rotular(T.texto_professor(it), cand, metas, com_trecho=True)
            tab = Table(title="%s  %s" % (h, (it.get("titulos") or [{}])[0].get("v", "")[:90]), box=box.SIMPLE)
            for c in ("ODS", "Meta", "Trecho do documento"):
                tab.add_column(c)
            for o in r or []:
                tab.add_row(str(o["n"]), o.get("meta", ""), o.get("trecho", ""))
            console.print(tab if r else "%s: nenhum ODS (lista vazia)%s" % (h, "" if r is not None else " - falha"))
            console.print("  ODS atuais no Arca: %s" % (", ".join(str(v) for v in it.get("ods") or []) or "(nenhum)"))
            prof = sorted({o["n"] for o in r or []}) if r is not None else None
            if prof is None:
                console.print("  o professor falhou neste item: nada muda")
                continue
            atual = C.humano(it)
            if prof == atual:
                console.print("  nada a mudar: o registro ja tem exatamente esses ODS")
                continue
            entra, sai = sorted(set(prof) - set(atual)), sorted(set(atual) - set(prof))
            if config.SOMENTE_LEITURA or not Confirm.ask("  Gravar no Arca? entra %s, sai %s (fica %s)"
                                                         % (entra or "-", sai or "-", prof or "nenhum"), default=False):
                continue
            obj = cli.item_por_handle(h)                       # le AGORA, antes de gravar
            md = obj.get("metadata") or {}
            antes = [x.get("value", "") for x in md.get(C.CAMPO) or []]
            ops = []
            if C.R.ler_original(md, prefixo=C.R.PREFIXO_ODS_ORIGINAL) is None:
                # o ODS humano fica guardado uma vez so, antes da 1a mudanca (como o [DECS-ORIGINAL])
                ops.append(C.R.op_adicionar_linha(C.R.linha_original(antes, prefixo=C.R.PREFIXO_ODS_ORIGINAL)))
            ops += C.operacoes(md, prof, "professor %s, prompt v3 (O6)" % P.NOME)
            cli.patch("/core/items/" + obj["uuid"], ops)
            depois = [x.get("value", "") for x in (cli.get("/core/items/" + obj["uuid"]).get("metadata") or {})
                      .get(C.CAMPO) or []]
            console.print("  %s: agora %s" % ("gravado" if depois == [C.VALOR[n] for n in prof] else "DIVERGENTE",
                                               prof or "nenhum ODS"))
    finally:
        P.parar_servidor()


OPCOES = [
    ("O1", "ODS - Um item", "Mostra o plano e grava se confirmar", o1_um_item),
    ("O2", "ODS - Lista", "Handles colados ou .txt", o2_lista),
    ("O3", "ODS - Acervo inteiro", "Filtro por data e por ter/nao ter ODS", o3_todos),
    ("O4", "ODS - Preparar sinais", "Resumo do PDF + ODSBahia + metas (GPU), so leitura", o4_sinais),
    ("O5", "ODS - Treinar e avaliar", "Professor local + classificador + avaliacao", o5_treinar),
    ("O6", "ODS - Testar professor v3", "Lista dos ODS + 20 metas + trecho; se confirmar, grava so os ODS do metodo", o6_professor_v3),
]
