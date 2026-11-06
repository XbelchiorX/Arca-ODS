# -*- coding: utf-8 -*-
"""ODSBahia sozinho como indexador de ODS, na mesma regua dos professores (v4 + v5 + v6; pedido do responsavel, 28/10).

Do jeito dos autores (Santos & Moraes 2024, RGSA, p. 13-15): multirrotulo treinado com BCEWithLogitsLoss, entao cada
ODS tem a sua probabilidade (sigmoide, independente) e entra com p >= 0,5. 20 rotulos (ODS 1-18, 19 arte/cultura,
20 povos tradicionais); 19 e 20 nao sao ODS e nao contam. Treinado em trechos de ~70 palavras (cartao: 128 tokens):
o documento e lido em janelas de 128 tokens (como no treino) ou de 510; um ODS vale para o documento se aparece em
alguma janela (max) ou na media das janelas. Duas entradas: o texto do professor (o mesmo que os professores recebem)
e so a parte em portugues (o idioma do treino). O melhor limiar escolhido olhando o gabarito sai a parte, so como teto
otimista (nao e um resultado valido).
A 1a medicao (28/10) usou softmax, como arca/ods_sinais.py: forca as 20 probabilidades a somar 1 e subestima o modelo.

Saida: publicacoes/artigo_ods/resultados/professor/notas_odsbahia.json e .md (probabilidades em odsbahia_prob.json)
Uso: python ferramentas/ods/avaliacao/notas_odsbahia.py
"""
import json
import os
import sys

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from comparar_professores_v3 import PASTA, _metricas  # noqa: E402

JANELAS = [128, 510]


def golds():
    g = {}
    for v, nome in (("v4", "v4 (150 sorteados)"), ("v5", "v5 (regua, 680)"), ("v6", "v6 (ODS raros)")):
        g[nome] = json.load(open(os.path.join(RAIZ, "dados", "gabarito_claude_" + v, "gabarito_%s.json" % v),
                                 encoding="utf-8"))["itens"]
    return g


def probabilidades(textos, tam, lote=32):
    """Sigmoide por rotulo em cada janela; devolve (max, media) por documento (n x 20)."""
    import torch
    from arca import ods_sinais as S, ods_texto as T
    tok, md, dev, ordem = S._bahia()
    janelas, dono = [], []
    for i, t in enumerate(textos):
        for w in T.janelas(tok, t or " ", tam=tam, passo=tam * 3 // 4):
            janelas.append(w)
            dono.append(i)
    mx = np.zeros((len(textos), 20), dtype=np.float32)
    out = np.zeros((len(textos), 20), dtype=np.float32)
    cont = np.zeros(len(textos))
    for a in range(0, len(janelas), lote):
        enc = tok(janelas[a:a + lote], padding=True, truncation=True, max_length=tam + 2, return_tensors="pt").to(dev)
        with torch.no_grad():
            pr = torch.sigmoid(md(**enc).logits.float()).cpu().numpy()
        for k, p in enumerate(pr):
            i = dono[a + k]
            for j, n in enumerate(ordem):
                out[i, n - 1] += p[j]
                mx[i, n - 1] = max(mx[i, n - 1], p[j])
            cont[i] += 1
    return mx, out / np.maximum(cont, 1)[:, None]


def decidir(p, limiar=0.5):
    return [n + 1 for n in range(18) if p[n] >= limiar]


def main():
    from arca import ods_texto as T
    from arca.decs_acervo import carregar_acervo
    gs = golds()
    ac = carregar_acervo()
    hs = sorted(h for h in set().union(*gs.values()) if h in ac)
    entradas = {"texto do professor": [T.texto_professor(ac[h]) for h in hs],
                "so portugues": [T.texto(ac[h], "pt") for h in hs]}
    prob = {}
    for nome, textos in entradas.items():
        for tam in JANELAS:
            print("ODSBahia, %s, janelas de %d: %d itens" % (nome, tam, len(hs)), flush=True)
            mx, md = probabilidades(textos, tam)
            prob["%s, janelas %d, alguma janela" % (nome, tam)] = mx
            prob["%s, janelas %d, media" % (nome, tam)] = md
    json.dump({e: {h: [round(float(x), 4) for x in prob[e][i]] for i, h in enumerate(hs)} for e in prob},
              open(os.path.join(PASTA, "odsbahia_prob.json"), "w", encoding="utf-8"))
    res, L = {}, ["# ODSBahia sozinho na regua (28/10), do jeito dos autores (sigmoide, p >= 0,5)", "",
                  "Mesma regua e mesma nota dos professores (notas_regua.md). P / R / F1 sem ODS 3; P / R / F1 com ODS 3",
                  "(micro, como a Tabela 2 do artigo: P 0,89 / R 0,70 / F1 0,79 em trechos do proprio corpus).", ""]
    for gnome, gold in gs.items():
        L += ["## %s" % gnome, "", "| Entrada | P / R / F1 com ODS 3 | P / R / F1 sem ODS 3 |", "|---|---|---|"]
        res[gnome] = {}
        for e in prob:
            idx = {h: i for i, h in enumerate(hs)}
            g = {h: v for h, v in gold.items() if h in idx}
            pred = {h: decidir(prob[e][idx[h]]) for h in g}
            c, s = _metricas(g, pred), _metricas(g, pred, sem3=True)
            res[gnome][e] = {"com_ods3": c, "sem_ods3": s}
            L.append("| %s | %.3f / %.3f / %.3f | %.3f / %.3f / %.3f |" % (e, c["precisao"], c["recall"], c["f1"],
                                                                         s["precisao"], s["recall"], s["f1"]))
            melhor = max((_metricas(g, {h: decidir(prob[e][idx[h]], t) for h in g}, sem3=True)["f1"], t)
                         for t in np.arange(0.05, 0.96, 0.05))
            res[gnome]["%s | teto otimista" % e] = {"limiar": round(float(melhor[1]), 2), "f1_sem_ods3": melhor[0]}
            L.append("| *%s: teto com o melhor limiar olhando o gabarito (%.2f)* | - | F1 %.3f |" % (e, melhor[1], melhor[0]))
        L.append("")
    json.dump(res, open(os.path.join(PASTA, "notas_odsbahia.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(PASTA, "notas_odsbahia.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
