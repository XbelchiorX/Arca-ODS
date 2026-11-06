# -*- coding: utf-8 -*-
"""Extrai as metas do Ipea (2026), "Nacionalizacao da Agenda 2030", para dados/ods_referencia/metas_2026.json.

Para cada meta: texto global (ONU), texto Brasil (com as sub-metas brasileiras X.Y.Nbr quando houver),
justificativa e conceitos importantes. Nada e cortado; so se limpa cabecalho/rodape de pagina e
hifenizacao do PDF.
"""
import json
import os
import re

import fitz

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
REF = os.path.join(RAIZ, "dados", "ods_referencia")
PDF = os.path.join(REF, "ipea_nacionalizacao_agenda2030_2026.pdf")


def texto_limpo():
    linhas = []
    for p in fitz.open(PDF):
        for ln in p.get_text().replace("\xa0", " ").split("\n"):
            s = ln.strip()
            if re.fullmatch(r"\d{1,3}", s):                       # numero de pagina
                continue
            if (re.match(r"^ODS \d+: .{10,}$", s) and len(s) < 160
                    and (not s.endswith(".") or s.endswith("..."))):      # cabecalho corrente (titulo cortado com "...")
                continue
            if s.startswith("NACIONALIZAÇÃO DA AGENDA 2030"):
                continue
            linhas.append(ln.rstrip())
    t = "\n".join(linhas)
    t = re.sub(r"\xad\s*\n\s*", "", t).replace("\xad", "")     # hifen de quebra
    return t


def junta(s):
    return " ".join(s.split())


H_META = re.compile(r"\n[ \t]*META[ \t]*(\d{1,2}\.[0-9a-z]{1,2})\b[^\n]*\n")
H_SECAO = re.compile(r"\n[ \t]*([1-9])\.[ \t]*([^\n]*)\n")
H_SUB = re.compile(r"\n[ \t]*Meta[ \t]*(\d+\.[0-9a-z]+\.\d+)[ \t]*\(Brasil\)[ \t]*\n")


def extrair():
    """Blocos "META X.Y"; dentro, secoes numeradas: 1 meta global, 2 meta Brasil, 3 justificativa,
    4 conceitos, 5 indicadores... (no ODS 18: 1 meta, 2 indicadores)."""
    t = texto_limpo()
    cab = list(H_META.finditer(t))
    metas = {}
    for k, m in enumerate(cab):
        cod = m.group(1)
        bloco = "\n" + t[m.end():cab[k + 1].start() if k + 1 < len(cab) else len(t)]
        if cod.startswith("18.") and k + 1 == len(cab):
            bloco = bloco[:bloco.find("\nREFER")] if "\nREFER" in bloco else bloco
        secs = list(H_SECAO.finditer(bloco))
        sec = {}
        for i, x in enumerate(secs):
            corpo = bloco[x.end():secs[i + 1].start() if i + 1 < len(secs) else len(bloco)]
            sec.setdefault(x.group(1), (x.group(2), corpo))
        tit = lambda n: (sec.get(n) or ("", ""))[0].lower()
        corpo = lambda n: (sec.get(n) or ("", ""))[1]
        if cod.startswith("18."):
            m18 = junta(corpo("1"))
            d = {"onu": "", "brasil": m18, "justificativa": "", "conceitos": ""}
        else:
            glob = junta(corpo("1"))
            br = H_SUB.sub(lambda y: "\n%sbr " % y.group(1), corpo("2"))
            br = junta(br)
            mantida = bool(re.search(r"mantida sem altera", br, re.I))
            if "nova proposi" in glob.lower():
                glob = ""
            d = {"onu": glob, "brasil": glob if mantida else br, "mantida": mantida,
                 "justificativa": junta(corpo("3")) if "justific" in tit("3") else "",
                 "conceitos": junta(corpo("4")) if "conceito" in tit("4") else ""}
            if re.match(r"n[aã]o h[aá] conceitos", d["conceitos"], re.I):
                d["conceitos"] = ""
        d["ods"] = int(cod.split(".")[0])
        if cod not in metas:
            metas[cod] = d
    return metas


if __name__ == "__main__":
    ms = extrair()
    from collections import Counter
    print(len(ms), "metas", sorted(Counter(m["ods"] for m in ms.values()).items()))
    vazios = {c: [k for k in ("onu", "brasil") if not v[k]] for c, v in ms.items()}
    print("campos vazios:", {c: v for c, v in vazios.items() if v})
    with open(os.path.join(REF, "metas_2026.json"), "w", encoding="utf-8") as f:
        json.dump(ms, f, ensure_ascii=False, indent=1)
