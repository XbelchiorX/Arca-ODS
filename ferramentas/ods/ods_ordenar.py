# -*- coding: utf-8 -*-
"""Poe os valores de dc.subject.ods em ordem crescente (1 a 18) em cada item (pedido do responsavel, 2026-10-27).

So REORDENA: nenhum valor e renomeado ou acrescentado; so sai a copia exata de um valor repetido. Lingua, autoridade
e confianca de cada valor ficam. Valor sem numero de ODS reconhecivel vai para o fim, na ordem em que estava (e aparece
no relatorio). dc.description.provenance e a nota [ODS-AUTO] nao sao tocados.

  (padrao)  le o acervo inteiro AO VIVO e simula
  --gravar  grava: rele cada item antes, faz backup e confere depois de gravar
  --item    so estes itens (handles), para testar
Saidas: saidas/ods/ordem_ods_<simulacao|gravacao>_<data>.csv e backup_ordem_ods_<data>.csv
Uso: python ferramentas/ods/ods_ordenar.py [--gravar] [--item icict/123 ...]
"""
import argparse
import csv
import os
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)
from rich.progress import (BarColumn, MofNCompleteColumn, Progress, TextColumn,  # noqa: E402
                           TimeElapsedColumn, TimeRemainingColumn)
from arca import config  # noqa: E402
from arca.ods_correcao import CAMPO  # noqa: E402

PASTA = os.path.join(config.SAIDAS, "ods")


def numero(valor):
    """Numero do ODS (1-18) no comeco do valor: "03 Saude...", "3 - Saude", "ODS 3", "ODS-3"; senao None."""
    m = re.match(r"\s*(?:ODS\s*[-:.]?\s*)?(\d{1,2})(?!\d)", str(valor or ""), re.I)
    n = int(m.group(1)) if m else None
    return n if n and 1 <= n <= 18 else None


def ordenado(vals):
    """Os mesmos valores, com numero de ODS em ordem crescente e os sem numero no fim (sort estavel); copia
    exata repetida ("03 Saude e Bem-Estar" duas vezes) sai."""
    out, vistos = [], set()
    for x in sorted(vals, key=lambda x: (numero(x.get("value")) is None, numero(x.get("value")) or 0)):
        if x.get("value") not in vistos:
            vistos.add(x.get("value"))
            out.append(x)
    return out


def plano(md):
    """(novos_valores ou None, observacao)."""
    vals = md.get(CAMPO) or []
    nums = [numero(x.get("value")) for x in vals]
    obs = []
    if None in nums:
        obs.append("sem numero: " + " | ".join(x.get("value", "") for x, n in zip(vals, nums) if n is None))
    rep = [n for n, c in Counter(n for n in nums if n).items() if c > 1]
    if rep:
        obs.append("repetido: " + ", ".join(map(str, sorted(rep))))
    novos = ordenado(vals)
    if [x.get("value") for x in novos] == [x.get("value") for x in vals]:
        return None, "; ".join(obs)
    return novos, "; ".join(obs)


def valor_para_patch(x):
    v = {"value": x.get("value"), "language": x.get("language")}
    if x.get("authority"):
        v["authority"] = x["authority"]
        v["confidence"] = x.get("confidence", -1)
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gravar", action="store_true")
    ap.add_argument("--item", nargs="+")
    a = ap.parse_args()
    from arca import idiomas as I
    if a.item:
        cli0 = I.criar_cliente()._c
        itens = [x for x in (cli0.item_por_handle(h) for h in a.item) if x]
    else:
        itens = I.mapear_objetos(I.criar_cliente(), 100, 8)
    com_ods = [it for it in itens if (it.get("metadata") or {}).get(CAMPO)]
    alvo = [it for it in com_ods if plano(it.get("metadata") or {})[0] is not None]
    print("%d itens lidos; %d com ODS; %d fora de ordem" % (len(itens), len(com_ods), len(alvo)), flush=True)
    os.makedirs(PASTA, exist_ok=True)
    agora = datetime.now().strftime("%Y%m%d_%H%M")
    modo = "gravacao" if a.gravar else "simulacao"
    fr = open(os.path.join(PASTA, "ordem_ods_%s_%s.csv" % (modo, agora)), "w", encoding="utf-8-sig", newline="")
    wr = csv.writer(fr, delimiter=";")
    wr.writerow(["handle", "antes", "depois", "observacao", "situacao"])
    if not a.gravar:
        for it in alvo:
            md = it.get("metadata") or {}
            novos, obs = plano(md)
            wr.writerow([it.get("handle"), " || ".join(x.get("value", "") for x in md[CAMPO]),
                         " || ".join(x.get("value", "") for x in novos), obs, "a_gravar"])
        fr.close()
        print("relatorio:", fr.name)
        return

    fb = open(os.path.join(PASTA, "backup_ordem_ods_%s.csv" % agora), "w", encoding="utf-8-sig", newline="")
    wb = csv.writer(fb, delimiter=";")
    wb.writerow(["id", "handle", "dc.date.accessioned", CAMPO])
    cli = I.criar_cliente()._c
    cont = Counter()

    def um(it):
        try:
            obj = cli.get("/core/items/" + it["uuid"])                      # AO VIVO
            md = obj.get("metadata") or {}
            novos, obs = plano(md)
            if novos is None:
                return obj, md, None, obs, "nada (ja em ordem)"
            ops = [{"op": "remove", "path": "/metadata/" + CAMPO}]
            ops += [{"op": "add", "path": "/metadata/%s/-" % CAMPO, "value": valor_para_patch(x)} for x in novos]
            cli.patch("/core/items/" + obj["uuid"], ops)
            depois = (cli.get("/core/items/" + obj["uuid"]).get("metadata") or {}).get(CAMPO) or []
            ok = [x.get("value") for x in depois] == [x.get("value") for x in novos]
            return obj, md, novos, obs, "OK" if ok else "DIVERGENTE"
        except Exception as e:
            return it, it.get("metadata") or {}, None, "", "erro: %s" % str(e)[:150]

    with Progress(TextColumn("[bold]Ordem ODS -> Arca"), BarColumn(), MofNCompleteColumn(), TimeElapsedColumn(),
                  TimeRemainingColumn(), TextColumn("{task.percentage:.1f}%")) as pr, ThreadPoolExecutor(6) as ex:
        t = pr.add_task("", total=len(alvo))
        for obj, md, novos, obs, sit in ex.map(um, alvo):
            pr.advance(t)
            cont[sit.split(":")[0]] += 1
            antes = " || ".join(x.get("value", "") for x in md.get(CAMPO) or [])
            if novos is not None:
                wb.writerow([obj.get("uuid"), obj.get("handle"),
                             (md.get("dc.date.accessioned") or [{}])[0].get("value", ""),
                             "||".join(x.get("value", "") for x in md.get(CAMPO) or [])])
            wr.writerow([obj.get("handle"), antes, " || ".join(x.get("value", "") for x in novos or []), obs, sit])
            fr.flush()
            fb.flush()
    print("FIM %s" % dict(cont))
    print("relatorio:", fr.name)


if __name__ == "__main__":
    main()
