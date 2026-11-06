# -*- coding: utf-8 -*-
"""Notas de todos os professores contra o gabarito Sol + GPT-6 (D44, 04/11/2026).

Le cada resultado salvo (comparacao_*.json) e as respostas dos modelos web, sem rodar nenhum modelo, e pontua nos
registros que existem nos dois lados. Grava resultados/professor/notas_gabarito_sol_gpt6.md.
Notas de grupos diferentes nao se comparam: mudam os registros e, em parte, as metas candidatas (ver a coluna do arquivo).
"""
import glob
import json
import os
import random
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
P = os.path.join(RAIZ, "publicacoes", "artigo_ods", "resultados", "professor")
SAIDA = os.path.join(P, "notas_gabarito_sol_gpt6.md")
GRUPOS = [("Régua de 500 registros", 400, 10 ** 9), ("Régua de 300 registros", 250, 400),
          ("Revisados pela especialista e testes pequenos (de 11 a 249 registros em comum)", 11, 250)]


def ods(lista):
    out = set()
    for x in lista or []:
        if isinstance(x, dict):
            out.add(int(x["n"]))
        elif isinstance(x, int):
            out.add(x)
        else:
            out.add(int(str(x).split(".")[0]))
    return out


def medir(G, Q, hs, sem3=False):
    c = m = f = 0
    for h in hs:
        g, q = G[h], Q[h]
        if sem3:
            g, q = g - {3}, q - {3}
        c, m, f = c + len(g & q), m + len(q - g), f + len(g - q)
    return c, m, f, (2 * c / (2 * c + m + f) if c else 0.0)


def ic(G, Q, hs):
    r = random.Random(1)
    a = sorted(medir(G, Q, r.choices(hs, k=len(hs)))[3] for _ in range(2000))
    return a[50], a[1949]


def carregar():
    g = json.load(open(os.path.join(RAIZ, "dados", "gabarito_sol", "gabarito_500.json"), encoding="utf-8"))
    G = {h: {int(m.split(".")[0]) for m in v} for h, v in g["metas"].items()}
    R = {h: set(v) for h, v in json.load(open(os.path.join(RAIZ, "dados", "gabarito_revisado_500.json"), encoding="utf-8"))["itens"].items()}
    res = []
    for f in sorted(glob.glob(os.path.join(P, "comparacao_*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        it = d.get("itens") if isinstance(d, dict) else None
        if not isinstance(it, dict):
            continue
        Q = {h: ods(x.get("modelo")) for h, x in it.items() if isinstance(x, dict) and "modelo" in x and x.get("modelo") is not None}
        if not Q:
            continue
        nome = re.sub(r"^comparacao_|\.json$", "", os.path.basename(f))
        res.append((nome, Q, (d.get("resumo") or {}).get("s_por_item")))
    w = json.load(open(os.path.join(RAIZ, "dados", "gabarito_v8", "respostas_copilot.json"), encoding="utf-8"))
    for mod, prompts in w.items():
        if not isinstance(prompts, dict):      # chaves de descricao do arquivo
            continue
        for pr, r in prompts.items():
            if not isinstance(r, dict):
                continue
            res.append(("web: %s, %s" % (mod, pr), {h: ods(v) for h, v in r.items()}, None))
    return G, R, res


def main():
    G, R, res = carregar()
    L = ["# Notas dos professores contra o gabarito Sol + GPT-6", "",
         "Gabarito: 165 registros do GPT-6.1 Sol + 335 do GPT-6 (Copilot, sem Work IQ, só o texto das 180 metas); substitui A2 e B2 "
         "por decisão da responsável (D44, 04/11/2026). Nenhum modelo foi rodado de novo: as respostas salvas foram pontuadas contra o novo gabarito.",
         "", "Certos / a mais / faltando e F1 com ODS 3, salvo indicação. O intervalo é de 95% (reamostragem de registros). "
         "\"Revisão\" é a nota contra as decisões da especialista, nos registros em comum.",
         "Notas de grupos diferentes não se comparam: mudam os registros e, em parte, o número de metas candidatas (está no nome do arquivo).",
         "Limites: os resultados `v8nota` guardam todas as metas, sem o corte de nota, então a nota deles aqui não vale como desempenho; "
         "`v3`/`v4` `_regua` são de rodadas antigas, antes da correção das metas de 28/10; os modelos `web` têm só 11 registros e 20 candidatas nos prompts v8 e v9.", ""]
    sobra = 0
    for tit, a, b in GRUPOS:
        linhas = []
        for nome, Q, seg in res:
            hs = sorted(set(G) & set(Q))
            if not a <= len(hs) < b:
                continue
            c, m, f, f1 = medir(G, Q, hs)
            lo, hi = ic(G, Q, hs)
            f13 = medir(G, Q, hs, True)[3]
            rv = sorted(set(R) & set(Q))
            nr = "%.2f (%d)" % (medir(R, Q, rv)[3], len(rv)) if rv else "—"
            od = sum(len(Q[h]) for h in hs) / len(hs)
            linhas.append((f1, "| %s | %d | %d / %d / %d | **%.2f** | %.2f–%.2f | %.2f | %s | %.2f | %s |"
                           % (nome, len(hs), c, m, f, f1, lo, hi, f13, nr, od, seg if seg else "—")))
        linhas.sort(key=lambda x: -x[0])
        L += ["## %s" % tit, "", "| Resultado | Registros | Certos / a mais / faltando | F1 | Intervalo | F1 sem ODS 3 | Revisão (registros) | ODS por registro | s/registro |",
              "|---|---:|---|---:|---|---:|---:|---:|---:|"] + [x[1] for x in linhas] + [""]
        sobra += len(linhas)
    fora = [nome for nome, Q, _s in res if len(set(G) & set(Q)) < 11]
    L += ["Fora das tabelas, com menos de 11 registros em comum com o gabarito: %d resultados." % len(fora), ""]
    open(SAIDA, "w", encoding="utf-8").write("\n".join(L))
    print(sobra, "linhas;", len(fora), "fora;", SAIDA)


if __name__ == "__main__":
    main()
