# -*- coding: utf-8 -*-
"""Texto do documento para os modelos de ODS.

Regra do projeto (memoria "resumo completo"): titulo, resumo INTEIRO e todas
as palavras-chave. Cada modelo recebe o texto no idioma em que foi treinado
(pt para ODSBahia/BERTimbau, en para LUKE/sdgBERT) e textos longos sao lidos em
janelas sobrepostas (nada e cortado em 512 tokens).
"""


def _escolher(lista, idioma):
    """Valor no idioma pedido; senao pt; senao en; senao o primeiro."""
    for alvo in (idioma, "pt", "en"):
        for x in lista or []:
            if (x.get("l") or "").lower().startswith(alvo) and (x.get("v") or "").strip():
                return x["v"].strip()
    for x in lista or []:
        if (x.get("v") or "").strip():
            return x["v"].strip()
    return ""


def palavras_chave(item, idioma=None):
    kws = [k for k in item.get("keywords") or [] if (k.get("v") or "").strip()]
    if idioma:
        sel = [k["v"].strip() for k in kws if not k.get("l") or (k.get("l") or "").lower().startswith(idioma)]
        if sel:
            return sel
    return [k["v"].strip() for k in kws]


def texto(item, idioma="pt"):
    """Titulo + resumo completo + palavras-chave no idioma pedido (para os classificadores)."""
    partes = [_escolher(item.get("titulos"), idioma), _escolher(item.get("resumos"), idioma),
              "; ".join(palavras_chave(item, idioma))]
    if idioma == "pt":   # decisao D10: o resumo gerado do PDF e em portugues
        from .ods_textocompleto import RESUMO_CURTO, resumo_gerado
        if len(_escolher(item.get("resumos"), "pt")) < RESUMO_CURTO:
            partes.append(resumo_gerado(item.get("handle")))
    return "\n".join(p for p in partes if p)


def texto_professor(item):
    """Texto para o LLM professor: titulo e resumo INTEIROS em pt (ou o que houver) + TODAS as
    palavras-chave. Nada e cortado (regra do responsavel)."""
    t = _escolher(item.get("titulos"), "pt")
    r = _escolher(item.get("resumos"), "pt")
    k = "; ".join(dict.fromkeys(palavras_chave(item)))
    s = "TITULO: %s\nRESUMO: %s\nPALAVRAS-CHAVE: %s" % (t, r or "(sem resumo)", k or "(nenhuma)")
    from .ods_textocompleto import RESUMO_CURTO, resumo_gerado
    g = resumo_gerado(item.get("handle")) if len(r) < RESUMO_CURTO else ""
    if g:   # decisao D10: resumo que o professor gerou do PDF inteiro
        s += "\nRESUMO GERADO DO TEXTO COMPLETO (PDF): %s" % g
    return s


def janelas(tokenizer, txt, tam=510, passo=384):
    """Janelas de ate `tam` tokens com sobreposicao (texto decodificado de cada janela)."""
    ids = tokenizer(txt, add_special_tokens=False)["input_ids"]
    if len(ids) <= tam:
        return [txt]
    return [tokenizer.decode(ids[i:i + tam]) for i in range(0, max(len(ids) - tam, 0) + passo, passo)
            if ids[i:i + tam]]
