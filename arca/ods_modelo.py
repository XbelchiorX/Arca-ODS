# -*- coding: utf-8 -*-
"""Classificador final de ODS (aluno) treinado com os rotulos do professor.

Atributos por documento (ods_sinais.matriz): probabilidades do ODSBahia (20),
maior similaridade com as metas de cada ODS (18) e o vetor do
documento (4096, Qwen3-Embedding-8B). Um classificador logistico por ODS (1-18), com limiar por ODS
escolhido em validacao cruzada nos rotulos do professor (regra 8: nenhum
limiar no chute). A avaliacao final usa o gabarito independente
(dados/ods_gabarito.json), que nunca entra no treino.
"""
import json
import os
import pickle
from datetime import datetime

import numpy as np

from . import config
from . import ods_sinais as S

MODELO_PKL = os.path.join(config.MODELOS, "ods_modelo.pkl")
GABARITO_JSON = os.path.join(config.DADOS, "ods_gabarito.json")
N = 18


def _y(handles, rotulos):
    return np.array([[o + 1 in rotulos[h] for o in range(N)] for h in handles], dtype=np.int8)


def _ajustar(X, Y, C=1.0):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    esc = StandardScaler().fit(X)
    Xs = esc.transform(X)
    clfs = []
    for o in range(N):
        if Y[:, o].sum() < 3:
            clfs.append(None)
            continue
        if Y[:, o].sum() == len(Y):          # todo documento do treino tem este ODS: probabilidade constante 1
            clfs.append(1.0)
            continue
        clfs.append(LogisticRegression(C=C, max_iter=3000, class_weight="balanced").fit(Xs, Y[:, o]))
    return esc, clfs


def _prever(esc, clfs, X):
    Xs = esc.transform(X)
    P = np.zeros((X.shape[0], N), dtype=np.float32)
    for o, c in enumerate(clfs):
        if isinstance(c, float):
            P[:, o] = c
        elif c is not None:
            P[:, o] = c.predict_proba(Xs)[:, 1]
    return P


def decidir(P, limiares, max_ods=5):
    """Lista de ODS (ordem de probabilidade) acima do limiar de cada ODS; ao menos o mais provavel
    quando ele passa de metade do seu limiar (todo documento do ARCA tende a ter algum ODS)."""
    out = []
    for p in P:
        sel = [o + 1 for o in np.argsort(-p) if p[o] >= limiares[o]][:max_ods]
        if not sel:
            o = int(np.argmax(p))
            if p[o] >= limiares[o] / 2:
                sel = [o + 1]
        out.append(sel)
    return out


def metricas(pred, ouro, handles, excluir=()):
    tp = fp = fn = 0
    for h in handles:
        g = set(ouro[h]) - set(excluir)
        p = set(pred[h]) - set(excluir)
        tp += len(g & p)
        fp += len(p - g)
        fn += len(g - p)
    P = tp / max(tp + fp, 1)
    R = tp / max(tp + fn, 1)
    return {"precisao": round(P, 3), "recall": round(R, 3), "f1": round(2 * P * R / max(P + R, 1e-9), 3)}


def treinar(rotulos, cache, C=0.5, folds=5, semente=0, aviso=print):
    """rotulos: {handle: [ods do professor]}. Devolve o pacote do modelo (com limiares)."""
    hs = [h for h in rotulos if h in cache]
    X = S.matriz(hs, cache)
    Y = _y(hs, rotulos)
    # limiares por validacao cruzada
    rng = np.random.RandomState(semente)
    dobra = rng.permutation(len(hs)) % folds
    Pcv = np.zeros(Y.shape, dtype=np.float32)
    for k in range(folds):
        tr, te = dobra != k, dobra == k
        esc, clfs = _ajustar(X[tr], Y[tr], C)
        Pcv[te] = _prever(esc, clfs, X[te])
    limiares = []
    for o in range(N):
        melhor, lim = -1, 0.5
        for t in np.arange(0.2, 0.96, 0.025):
            p = Pcv[:, o] >= t
            tp = (p & (Y[:, o] == 1)).sum()
            f1 = 2 * tp / max(p.sum() + Y[:, o].sum(), 1)
            if f1 > melhor:
                melhor, lim = f1, float(t)
        limiares.append(lim)
    esc, clfs = _ajustar(X, Y, C)
    pred_cv = dict(zip(hs, decidir(Pcv, limiares)))
    pacote = {"esc": esc, "clfs": clfs, "limiares": limiares, "C": C, "n_treino": len(hs),
              "data": datetime.now().isoformat(timespec="minutes"),
              "cv_vs_professor": metricas(pred_cv, {h: rotulos[h] for h in hs}, hs)}
    aviso("Treino: %d documentos; validacao cruzada vs professor: %s" % (len(hs), pacote["cv_vs_professor"]))
    return pacote


def salvar(pacote):
    with open(MODELO_PKL, "wb") as f:
        pickle.dump(pacote, f)


def carregar():
    if not os.path.exists(MODELO_PKL):
        return None
    with open(MODELO_PKL, "rb") as f:
        return pickle.load(f)


def prever(pacote, handles, cache):
    X = S.matriz(handles, cache)
    P = _prever(pacote["esc"], pacote["clfs"], X)
    return P, dict(zip(handles, decidir(P, pacote["limiares"])))


def gabarito():
    with open(GABARITO_JSON, encoding="utf-8") as f:
        d = json.load(f)
    return {h: v["ods"] for h, v in d["itens"].items()}
