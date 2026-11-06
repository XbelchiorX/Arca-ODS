# -*- coding: utf-8 -*-
"""Plano e gravacao de dc.subject.ods.

Decisoes do responsavel (2026-10-02):
- sem backup do humano e sem opcao de desfazer para ODS;
- uma unica nota em dcterms.provenance, "[ODS-AUTO] ...", com a data e o
  metodo; cada nova indexacao apaga a nota anterior e grava a nova;
- ODS 18 e gravado como "18 Igualdade Étnico-Racial" (grafia definida pelo responsavel; os 15 itens com "étnico" minusculo sao corrigidos na regravacao).

Modos de decisao:
  substituir  -> o campo fica com os ODS do modelo (o humano so serve de comparacao);
  complementar-> mantem o humano e acrescenta os ODS do modelo que faltam.
"""
import csv
import os
import re
from collections import Counter
from datetime import datetime

from . import config
from . import decs_rastreabilidade as R

CAMPO = "dc.subject.ods"
PREFIXO_AUTO = R.PREFIXO_ODS_AUTO
VALOR = {
    1: "01 Erradicação da pobreza", 2: "02 Fome zero e agricultura sustentável",
    3: "03 Saúde e Bem-Estar", 4: "04 Educação de qualidade", 5: "05 Igualdade de gênero",
    6: "06 Água potável e saneamento", 7: "07 Energia limpa e acessível",
    8: "08 Trabalho decente e crescimento econômico", 9: "09 Indústria, inovação e infraestrutura",
    10: "10 Redução das desigualdades", 11: "11 Cidades e comunidades sustentáveis",
    12: "12 Consumo e produção responsáveis", 13: "13 Ação contra a mudança global do clima",
    14: "14 Vida na água", 15: "15 Vida terrestre", 16: "16 Paz, justiça e instituições eficazes",
    17: "17 Parcerias e meios de implementação", 18: "18 Igualdade Étnico-Racial",
}
CAMPOS_PLANO = ["handle", "titulo", "acao", "ods", "probabilidade", "humano", "modelo", "final"]


def numero(valor):
    m = re.match(r"\s*(\d+)", str(valor))
    n = int(m.group(1)) if m else None
    return n if n and 1 <= n <= 18 else None


def humano(item):
    return sorted({n for n in (numero(v) for v in item.get("ods") or []) if n})


def planejar(handle, item, auto, probs, modo="substituir"):
    """Linhas do plano e lista final (numeros, em ordem crescente)."""
    hum = humano(item)
    final = sorted(set(auto) | set(hum)) if modo == "complementar" else sorted(set(auto))
    tit = next((t["v"] for t in item.get("titulos") or []), "")
    linhas = []
    for n in sorted(set(hum) | set(final)):
        acao = "MANTER" if (n in hum and n in final) else ("ADICIONAR" if n in final else "RETIRAR")
        linhas.append({"handle": handle, "titulo": tit, "acao": acao, "ods": n,
                       "probabilidade": "%.2f" % probs[n - 1] if probs is not None else "",
                       "humano": ",".join(map(str, hum)), "modelo": ",".join(map(str, sorted(auto))),
                       "final": ",".join(map(str, final))})
    if not linhas:
        linhas.append({"handle": handle, "titulo": tit, "acao": "SEM_ODS", "ods": "", "probabilidade": "",
                       "humano": "", "modelo": "", "final": ""})
    return linhas, final


def nota(final, metodo):
    return ("%s Indexacao ODS assistida por IA em %s. ODS: %s. Metodo: %s (script v%s)."
            % (PREFIXO_AUTO, datetime.now().strftime("%Y-%m-%d"), ", ".join(map(str, final)) or "nenhum",
               metodo, config.VERSAO))


def operacoes(md, final, metodo):
    """PATCH: troca o dc.subject.ods pela lista final e substitui a nota [ODS-AUTO]."""
    ops = R.ops_remover_linhas(md, (PREFIXO_AUTO,))
    ops.append(R.op_adicionar_linha(nota(final, metodo)))
    if md.get(CAMPO):
        ops.append({"op": "remove", "path": "/metadata/%s" % CAMPO})
    for n in final:
        ops.append({"op": "add", "path": "/metadata/%s/-" % CAMPO, "value": {"value": VALOR[n], "language": None}})
    return ops


def gravar(cliente, obj, final, metodo):
    """Grava e confere. Devolve OK, SEM_ALTERACAO ou DIVERGENTE."""
    md = obj.get("metadata") or {}
    atuais = [x.get("value", "") for x in md.get(CAMPO) or []]
    if atuais == [VALOR[n] for n in final]:
        return "SEM_ALTERACAO"
    cliente.patch("/core/items/" + obj["uuid"], operacoes(md, final, metodo))
    depois = cliente.get("/core/items/" + obj["uuid"])
    gravado = [x.get("value", "") for x in (depois.get("metadata") or {}).get(CAMPO) or []]
    return "OK" if gravado == [VALOR[n] for n in final] else "DIVERGENTE"


class Relatorio:
    def __init__(self, rotulo):
        pasta = os.path.join(config.SAIDAS, "ods")
        os.makedirs(pasta, exist_ok=True)
        self.caminho = os.path.join(pasta, "plano_ods_%s_%s.csv" % (rotulo, datetime.now().strftime("%Y%m%d_%H%M%S")))
        self.f = open(self.caminho, "w", newline="", encoding="utf-8-sig")
        self.w = csv.DictWriter(self.f, fieldnames=CAMPOS_PLANO, delimiter=";", extrasaction="ignore")
        self.w.writeheader()
        self.contagem = Counter()

    def escrever(self, linhas):
        for l in linhas:
            self.w.writerow(l)
            self.contagem[l["acao"]] += 1

    def fechar(self):
        self.f.close()
        return self.caminho
