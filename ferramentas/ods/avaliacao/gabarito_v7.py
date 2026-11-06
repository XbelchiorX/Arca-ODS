# -*- coding: utf-8 -*-
"""Gabarito v7 de ODS (D32/D33, 28/10): os 1.192 itens da regua rotulados de novo, so pelo texto das metas.

Os gabaritos v4-v6 foram descartados (rotulados com criterios fora das metas; arquivados no NAS).
Itens e texto exato entregue: dados/gabarito_v7/amostra.json. Metas: dados/ods_referencia/metas_2026.json
(Ipea 2026, inteiras: texto ONU, texto Brasil e conceitos). A instrucao abaixo e a aprovada pela responsavel;
mudar uma palavra dela e mudar o metodo (registrar em DECISOES_METODOLOGICAS.md).

Instrucao versao 5 (28/10). Dois rotuladores independentes (A e B), lotes de 10 documentos, cada rotulador com
uma ordem sorteada propria (sementes 1 e 2), para que os lotes de A e B nao tenham a mesma composicao.

  --exemplo       grava saidas/ods/exemplo_prompt_rotulador_v7.txt (prompt real de um item sorteado)
  --preparar      grava dados/gabarito_v7/instrucao_e_metas.txt e lotes_A/, lotes_B/ (lote_NNN.txt, 10 documentos)
  --conferir A|B  confere rotulos_A|B/lote_NNN.jsonl: JSON, um registro por handle do lote, ODS 1-18, meta existente
                  e do ODS indicado, trecho literal no texto (sem diferenca de maiusculas e espacos)
Uso: python ferramentas/ods/avaliacao/gabarito_v7.py --exemplo | --preparar | --conferir A
"""
import json
import os
import random
import re
import sys
import textwrap

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, RAIZ)
from arca.ods_metas import OBJETIVOS  # noqa: E402

AMOSTRA = os.path.join(RAIZ, "dados", "gabarito_v7", "amostra.json")
METAS = os.path.join(RAIZ, "dados", "ods_referencia", "metas_2026.json")

INSTRUCAO = """Você vai atribuir Objetivos de Desenvolvimento Sustentável (ODS) a documentos de um repositório. São os 17 ODS da Agenda 2030 da ONU e o ODS 18 do Brasil (igualdade étnico-racial).

Os documentos são de muitos tipos e podem estar em qualquer idioma. O texto de cada um pode ter título, resumo, palavras-chave e um resumo gerado do texto completo, ou só parte disso.

O único critério é o texto das metas dos ODS, anexadas abaixo: os títulos dos 18 ODS e as metas de cada um, cada meta com o texto da ONU, o texto do Brasil e os conceitos do Ipea (2026).

Para cada documento:
- Julgue cada documento separadamente, baseando-se só no que está escrito nele.
- Atribua todos os ODS que se aplicam a ele: um, vários ou nenhum. Um ODS se aplica quando o documento trata do que uma das metas desse ODS descreve, no texto da ONU ou no do Brasil.
- Para cada ODS atribuído, indique a meta que melhor se aplica e copie do documento, sem alterar nenhuma palavra e no idioma original, um trecho de até 20 palavras que mostre isso.
- Antes de responder, confira cada ODS atribuído contra o texto da meta indicada.
- Se nenhum ODS se aplica, devolva a lista vazia.

Não use nenhum critério que não esteja escrito nas metas dos ODS: nem o tipo, o formato ou a área do documento, nem o que você sabe sobre os ODS fora desse texto.

Responda só com JSON, uma linha para cada documento, inclusive os sem ODS, sem texto fora dele:
{"handle": "<handle>", "ods": [{"n": <número do ODS>, "meta": "<código da meta>", "trecho": "<trecho copiado>"}]}"""


def texto_metas():
    ms = json.load(open(METAS, encoding="utf-8"))
    linhas = []
    for c, m in ms.items():
        partes = ["[%s]" % c]
        if m.get("onu"):
            partes.append("ONU: " + m["onu"])
        partes.append("BRASIL: " + (m.get("brasil") or m.get("onu") or ""))
        if m.get("conceitos"):
            partes.append("CONCEITOS: " + m["conceitos"])
        linhas.append(partes[0] + " " + "\n  ".join(partes[1:]))
    return "\n".join(linhas), len(ms)


PASTA = os.path.dirname(AMOSTRA)
TAM_LOTE = 10


def cabecalho():
    metas, n = texto_metas()
    return (INSTRUCAO + "\n\nOS 18 ODS (títulos oficiais):\n" +
            "\n".join("%d: %s" % (k, t) for k, t in OBJETIVOS.items()) +
            "\n\nMETAS DOS ODS (%d; texto da ONU, texto do Brasil e conceitos do Ipea 2026):\n" % n + metas + "\n")


def prompt(itens):
    return (cabecalho() + "\nDOCUMENTOS:\n\n" + "\n\n".join("[handle: %s]\n%s" % (h, t) for h, t in itens) + "\n")


def _quebrar(s, largura=300):
    """Linhas de no maximo ~300 caracteres, quebradas so entre palavras (nada muda no texto): o leitor de arquivos
    do rotulador pode cortar linhas muito longas, e conceitos e resumos passam de 3 mil caracteres numa linha."""
    return "\n".join(textwrap.fill(ln, largura, break_long_words=False, break_on_hyphens=False,
                                   replace_whitespace=False, drop_whitespace=True) if len(ln) > largura else ln
                     for ln in s.split("\n"))


def preparar():
    itens = json.load(open(AMOSTRA, encoding="utf-8"))["itens"]
    open(os.path.join(PASTA, "instrucao_e_metas.txt"), "w", encoding="utf-8").write(_quebrar(cabecalho()))
    for rot, semente in (("A", 1), ("B", 2)):
        pasta = os.path.join(PASTA, "lotes_" + rot)
        if os.path.exists(pasta):
            sys.exit("ja existe %s; nada foi sobrescrito" % pasta)
        os.makedirs(pasta)
        os.makedirs(os.path.join(PASTA, "rotulos_" + rot), exist_ok=True)
        hs = sorted(itens)
        random.Random(semente).shuffle(hs)
        for k in range(0, len(hs), TAM_LOTE):
            lote = hs[k:k + TAM_LOTE]
            open(os.path.join(pasta, "lote_%03d.txt" % (k // TAM_LOTE + 1)), "w", encoding="utf-8").write(
                _quebrar("DOCUMENTOS:\n\n" + "\n\n".join("[handle: %s]\n%s" % (h, itens[h]["texto"]) for h in lote) + "\n"))
        print(rot, len(hs), "itens,", (len(hs) + TAM_LOTE - 1) // TAM_LOTE, "lotes")


def _norm(s):
    s = str(s or "").translate(str.maketrans("‘’“”", "''\"\""))   # aspas curvas = retas
    return re.sub(r"\s+", " ", s).strip().lower()


def conferir(rot):
    itens = json.load(open(AMOSTRA, encoding="utf-8"))["itens"]
    ms = json.load(open(METAS, encoding="utf-8"))
    pasta_l, pasta_r = os.path.join(PASTA, "lotes_" + rot), os.path.join(PASTA, "rotulos_" + rot)
    ok, falhas, faltam = 0, [], []
    for arq in sorted(os.listdir(pasta_l)):
        esperados = re.findall(r"^\[handle: (\S+)\]$", open(os.path.join(pasta_l, arq), encoding="utf-8").read(), re.M)
        saida = os.path.join(pasta_r, arq.replace(".txt", ".jsonl"))
        if not os.path.exists(saida):
            faltam.append(arq)
            continue
        vistos = {}
        for ln in open(saida, encoding="utf-8"):
            if not ln.strip():
                continue
            try:
                r = json.loads(ln)
                vistos[r["handle"]] = r["ods"]
            except (ValueError, KeyError, TypeError):
                falhas.append((arq, "?", "linha nao e JSON valido: " + ln[:80]))
        for h in esperados:
            if h not in vistos:
                falhas.append((arq, h, "sem resposta"))
                continue
            erro = None
            for o in vistos[h]:
                n, meta, tr = o.get("n"), str(o.get("meta", "")), o.get("trecho", "")
                if not isinstance(n, int) or not 1 <= n <= 18:
                    erro = "ODS invalido: %r" % n
                elif meta not in ms or ms[meta]["ods"] != n:
                    erro = "meta %s nao existe ou nao e do ODS %s" % (meta, n)
                elif not _norm(tr) or _norm(tr) not in _norm(itens[h]["texto"]):
                    erro = "trecho nao e literal: %s" % str(tr)[:80]
                if erro:
                    break
            if erro:
                falhas.append((arq, h, erro))
            else:
                ok += 1
        for h in set(vistos) - set(esperados):
            falhas.append((arq, h, "handle fora do lote"))
    print("rotulador %s: %d itens aprovados; %d falhas; %d lotes sem resposta" % (rot, ok, len(falhas), len(faltam)))
    for f in falhas:
        print("  %s %s: %s" % f)
    return falhas, faltam


def exemplo():
    itens = json.load(open(AMOSTRA, encoding="utf-8"))["itens"]
    h = random.Random(20261028).choice(sorted(itens))
    p = prompt([(h, itens[h]["texto"])])
    saida = os.path.join(RAIZ, "saidas", "ods", "exemplo_prompt_rotulador_v7.txt")
    open(saida, "w", encoding="utf-8").write(p)
    print(h, len(p), "caracteres;", saida)


if __name__ == "__main__":
    if "--preparar" in sys.argv:
        preparar()
    elif "--conferir" in sys.argv:
        conferir(sys.argv[sys.argv.index("--conferir") + 1])
    else:
        exemplo()
