# -*- coding: utf-8 -*-
"""Etiquetas de ODS do OpenAlex (classificador de outubro de 2026) nos registros da regua de 500, para comparar com o
gabarito Sol + GPT-6 e com o professor. Tudo so leitura. Procura por DOI (metadado do Arca) e, sem DOI, por titulo identico.
  python ferramentas/ods/avaliacao/openalex_500.py          baixa e grava dados/gabarito_sol/openalex_500.json (retoma)
  python ferramentas/ods/avaliacao/openalex_500.py --notas  so calcula as notas
O OpenAlex tem 17 ODS: as notas saem com o ODS 18 fora do gabarito e do professor, para a comparacao ser justa.
"""
import json
import os
import random
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, RAIZ)
from arca.decs_acervo import carregar_acervo  # noqa: E402

SAIDA = os.path.join(RAIZ, "dados", "gabarito_sol", "openalex_500.json")
GAB = os.path.join(RAIZ, "dados", "gabarito_sol", "gabarito_500.json")
PROF = os.path.join(RAIZ, "publicacoes", "artigo_ods", "resultados", "professor")
V8SC = "comparacao_v8_Qwen3.5-35B-A3B-Q4_K_M_regua500_v8tema_trecho_50metas_semconceitos.json"
API_ARCA = "https://api.arca.fiocruz.br/api/core/items/"
API_OA = "https://api.openalex.org/works"
CAMPOS = "id,doi,title,language,sustainable_development_goals"
UA = {"User-Agent": "suite-curadoria-arca/1.0"}


def _get(url, tentativas=3):
    for t in range(tentativas):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if t == tentativas - 1:
                raise
        except OSError:
            if t == tentativas - 1:
                raise
        time.sleep(3 * (t + 1))


def _norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in s if not unicodedata.combining(c))).strip()


def _doi(item):
    for campo, vals in (item.get("metadata") or {}).items():
        if "identifier" not in campo and "doi" not in campo:
            continue
        for v in vals:
            m = re.search(r"10\.\d{4,9}/\S+", v.get("value", ""))
            if m:
                return m.group(0).rstrip(".,;)").lower()
    return None


def _por_titulo(titulo):
    q = urllib.parse.urlencode({"filter": "title.search:" + _norm(titulo), "select": CAMPOS, "per-page": 10})
    d = _get(API_OA + "?" + q) or {}
    return [w for w in d.get("results", []) if _norm(w.get("title")) == _norm(titulo)]


def baixar():
    ac = carregar_acervo()
    hs = sorted(json.load(open(GAB, encoding="utf-8"))["itens"])
    res = json.load(open(SAIDA, encoding="utf-8")) if os.path.exists(SAIDA) else {}
    t0 = time.time()
    feitos = 0
    for i, h in enumerate(hs):
        if h in res:
            continue
        if h not in ac:
            res[h] = {"como": "fora_do_acervo"}
            continue
        doi = None
        item = _get(API_ARCA + ac[h]["uuid"])
        if item:
            doi = _doi(item)
        w, como = None, "nao_achado"
        if doi:
            w = _get(API_OA + "/doi:" + urllib.parse.quote(doi, safe="/") + "?select=" + CAMPOS)
            como = "doi" if w else como
        if not w:
            for tit in ac[h].get("titulos") or []:
                tit = tit.get("v", "") if isinstance(tit, dict) else str(tit)
                if len(_norm(tit)) < 25:   # titulo curto demais para garantir que e o mesmo trabalho
                    continue
                ach = _por_titulo(tit)
                if len(ach) == 1:
                    w, como = ach[0], "titulo"
                    break
        res[h] = {"como": como, "doi": doi}
        if w:
            res[h].update(id=w.get("id"), idioma=w.get("language"), titulo=w.get("title"),
                          ods=[{"n": int(str(s["id"]).rstrip("/").split("/")[-1]), "score": s.get("score")}
                               for s in w.get("sustainable_development_goals") or []])
        feitos += 1
        if feitos % 10 == 0:
            json.dump(res, open(SAIDA, "w", encoding="utf-8"), ensure_ascii=False)
            s = (time.time() - t0) / feitos
            print("%d/%d  %.1f s/registro  faltam %.0f min" % (i + 1, len(hs), s, (len(hs) - i - 1) * s / 60), flush=True)
        time.sleep(0.2)
    json.dump(res, open(SAIDA, "w", encoding="utf-8"), ensure_ascii=False)


def _prf(pares):
    c = sum(len(m & g) for m, g in pares)
    a = sum(len(m - g) for m, g in pares)
    f = sum(len(g - m) for m, g in pares)
    p = c / (c + a) if c + a else 0
    r = c / (c + f) if c + f else 0
    return c, a, f, p, r, (2 * p * r / (p + r) if p + r else 0)


def _linha(nome, pares):
    c, a, f, p, r, f1 = _prf(pares)
    rnd = random.Random(1)
    bs = sorted(_prf([pares[rnd.randrange(len(pares))] for _ in pares])[5] for _ in range(2000))
    print("| %s | %d | %d | %d | %d | %.2f | %.2f | %.2f (%.2f-%.2f) | %.2f |" % (
        nome, len(pares), c, a, f, p, r, f1, bs[50], bs[1949], sum(len(m) for m, _g in pares) / len(pares)))


def notas():
    res = json.load(open(SAIDA, encoding="utf-8"))
    gab = {h: set(v) - {18} for h, v in json.load(open(GAB, encoding="utf-8"))["itens"].items()}
    v8 = json.load(open(os.path.join(PROF, V8SC), encoding="utf-8"))["itens"]
    from collections import Counter
    print(Counter(x["como"] for x in res.values()), "com DOI no Arca:", sum(bool(x.get("doi")) for x in res.values()))
    ach = [h for h, x in res.items() if "ods" in x and h in gab and h in v8]
    print("achados e pontuaveis:", len(ach), "| sem nenhum ODS no OpenAlex:", sum(not res[h]["ods"] for h in ach),
          "| sem ODS no gabarito:", sum(not gab[h] for h in ach))
    print("| Quem | Registros | Certos | A mais | Faltando | Precisao | Recall | F1 (IC 95%) | ODS/registro |\n|---|---|---|---|---|---|---|---|---|")
    oa = {h: {o["n"] for o in res[h]["ods"]} - {18} for h in ach}
    pr = {h: {o["n"] for o in v8[h]["modelo"]} - {18} for h in ach}
    _linha("OpenAlex", [(oa[h], gab[h]) for h in ach])
    _linha("v8 sem conceitos, mesmos itens", [(pr[h], gab[h]) for h in ach])
    _linha("OpenAlex x v8 (v8 como referencia)", [(oa[h], pr[h]) for h in ach])
    sem3 = {3}
    _linha("OpenAlex, sem ODS 3", [(oa[h] - sem3, gab[h] - sem3) for h in ach])
    _linha("v8 sem conceitos, sem ODS 3", [(pr[h] - sem3, gab[h] - sem3) for h in ach])


if __name__ == "__main__":
    if "--notas" not in sys.argv:
        baixar()
    notas()
