# -*- coding: utf-8 -*-
"""Texto completo de um item para o resumo do D10, de todas as fontes (D23). So LE o ARCA.

- PDFs do bundle ORIGINAL baixados com o login do responsavel (inclui os restritos/embargados);
- PDF sem camada de texto -> OCR (arca/ocr_pdf.py; o PDF com OCR fica guardado para a opcao P de envio);
- sem PDF: video/audio -> transcricao da fala (faster-whisper large-v3-turbo, GPU).
Nada e cortado. Resultado: (texto, fontes, origem) com origem em {"pdf", "pdf+ocr", "transcricao", ""}.
"""
import glob
import os
import site
import tempfile

from . import config

MIDIA = (".mp4", ".avi", ".mov", ".wmv", ".mkv", ".webm", ".flv", ".mpg", ".mpeg", ".m4v",
         ".mp3", ".wav", ".m4a", ".ogg", ".wma")
MIN_PALAVRAS = 50
_W = {}
_C = {}


def cliente():
    if "c" not in _C:
        from . import dspace
        _C["c"] = dspace.conectar()
    return _C["c"]


def _bitstreams(item):
    cli = cliente()
    out = []
    for bd in cli.get("/core/items/%s/bundles" % item["uuid"])["_embedded"]["bundles"]:
        if bd["name"] == "ORIGINAL":
            out += [(bd, x) for x in cli.get("/core/bundles/%s/bitstreams" % bd["uuid"],
                                             params={"size": 100})["_embedded"]["bitstreams"]]
    return out


def _texto_pdf(caminho):
    import fitz
    try:
        return "\n".join(p.get_text() for p in fitz.open(caminho))
    except Exception:
        return ""


def _whisper():
    if "m" not in _W:
        for d in glob.glob(os.path.join(site.getsitepackages()[-1], "nvidia", "*", "bin")):
            os.add_dll_directory(d)
            os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
        from faster_whisper import WhisperModel
        _W["m"] = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")
    return _W["m"]


def liberar_whisper():
    """Solta a GPU antes de subir o resumidor."""
    if _W.pop("m", None) is not None:
        import gc
        gc.collect()


def transcrever(caminho):
    segs, info = _whisper().transcribe(caminho, vad_filter=True, beam_size=5)
    return " ".join(s.text.strip() for s in segs), info.language, info.duration


def texto_completo(item, aviso=print):
    from . import ocr_pdf as O
    cli = cliente()
    arqs = _bitstreams(item)
    pdfs = [(bd, x) for bd, x in arqs if (x.get("name") or "").lower().endswith(".pdf")]
    textos, fontes, ocr = [], [], False
    if pdfs:
        pasta = os.path.join(O.PASTA, item["handle"].replace("/", "_"))
        os.makedirs(pasta, exist_ok=True)
        for bd, x in pdfs:
            orig = os.path.join(pasta, "original_" + x["uuid"] + ".pdf")
            novo = os.path.join(pasta, "ocr_" + x["uuid"] + ".pdf")
            if not os.path.exists(orig):
                r = cli._pedir("GET", config.BASE_URL + "/core/bitstreams/%s/content" % x["uuid"], timeout=900)
                if r.status_code != 200 or not r.content.startswith(b"%PDF"):
                    continue
                with open(orig + ".tmp", "wb") as f:
                    f.write(r.content)
                os.replace(orig + ".tmp", orig)
            t = _texto_pdf(orig)
            if len(t.split()) < MIN_PALAVRAS and O.disponivel():
                if not os.path.exists(novo):
                    d = O.fazer_ocr(orig, novo + ".tmp.pdf")
                    if d["ok"]:
                        os.replace(novo + ".tmp.pdf", novo)
                    elif os.path.exists(novo + ".tmp.pdf"):
                        os.remove(novo + ".tmp.pdf")
                if os.path.exists(novo):
                    t = _texto_pdf(novo)
                    ocr = True
            if t.strip():
                textos.append(t)
                fontes.append(x["name"])
        if textos:
            return "\n\n".join(textos), fontes, "pdf+ocr" if ocr else "pdf"
    for bd, x in arqs:
        if not (x.get("name") or "").lower().endswith(MIDIA):
            continue
        r = cli._pedir("GET", config.BASE_URL + "/core/bitstreams/%s/content" % x["uuid"], timeout=3600, stream=True)
        if r.status_code != 200:
            continue
        ext = os.path.splitext(x["name"])[1]
        fd, tmp = tempfile.mkstemp(suffix=ext, dir=config.DADOS_LOCAIS)
        try:
            with os.fdopen(fd, "wb") as f:
                for bloco in r.iter_content(1 << 20):
                    f.write(bloco)
            t, lang, dur = transcrever(tmp)
        except Exception as e:
            aviso("  %s: falha na transcricao de %s (%s)" % (item["handle"], x["name"], str(e)[:150]))
            continue
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        if t.strip():
            textos.append(t)
            fontes.append("%s (fala, %s, %.0f min)" % (x["name"], lang, dur / 60))
    if textos:
        return "\n\n".join(textos), fontes, "transcricao"
    return "", [], ""
