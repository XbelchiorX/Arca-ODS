# -*- coding: utf-8 -*-
"""OCR invisivel de PDFs SEM texto (opcoes P1-P4). Esta parte so le do ARCA; a troca no ARCA e do ocr_substituir.

Para cada PDF do bundle ORIGINAL (lido com o login do responsavel):
1. so entra o PDF com menos de LIMITE_PALAVRAS_SEM_TEXTO palavras (PDF com texto nao passa por OCR);
2. OCRmyPDF (Tesseract; por+eng+spa e os idiomas do registro) acrescenta o texto INVISIVEL por tras da imagem
   (--skip-text), em PDF/A-2b, com --pdfa-image-compression lossless e --optimize 0: nenhuma imagem perde
   qualidade (o padrao trocava PNG/Flate por JPEG; medido em 2026-10-19);
3. confere: mesmo numero de paginas, os mesmos pixels em todas as imagens e texto novo presente.
   Se qualquer conferencia falhar, o arquivo e descartado.
Original e versao com OCR ficam em DADOS_LOCAIS/ocr/<handle>/; temporarios no NAS (TEMP_NAS).
"""
import hashlib
import json
import os
import shutil
import subprocess
import time

from . import config

PASTA = os.path.join(config.DADOS_LOCAIS, "ocr")
IDIOMAS = "por+eng+spa"       # base: sempre incluida (portugues, ingles, espanhol)
# idioma do registro (dc.language.iso, 2 ou 3 letras) -> pacote do Tesseract; o pedido do responsavel (19/10/2026)
# cobre frances, alemao, mandarim e linguas classicas da ciencia (latim, grego antigo e moderno, hebraico, arabe)
IDIOMAS_POR_REGISTRO = {
    "fr": "fra", "fra": "fra", "fre": "fra", "de": "deu", "deu": "deu", "ger": "deu", "it": "ita", "ita": "ita",
    "zh": "chi_sim", "zh-cn": "chi_sim", "chi": "chi_sim", "zho": "chi_sim", "la": "lat", "lat": "lat",
    "grc": "grc", "el": "ell", "ell": "ell", "gre": "ell", "he": "heb", "heb": "heb", "ar": "ara", "ara": "ara",
}
TODOS_IDIOMAS = sorted(set(IDIOMAS_POR_REGISTRO.values()) | {"por", "eng", "spa"})
LIMITE_PALAVRAS_SEM_TEXTO = 20   # PDF com menos palavras que isso no total e "sem texto" (so esse recebe OCR)
CACHE_TEXTO = os.path.join(config.CACHE, "ocr_texto_por_checksum.json")
MIN_PALAVRAS_PAG = 5            # pagina com menos que isso de texto conta como "sem texto"
_CAMINHOS = [r"C:\Program Files\Tesseract-OCR"] + [
    os.path.join(r"C:\Program Files\gs", d, "bin") for d in (os.listdir(r"C:\Program Files\gs")
                                                              if os.path.isdir(r"C:\Program Files\gs") else [])]


# pasta temporaria do OCR no NAS (pedido do responsavel em 2026-10-19: poupar o SSD). Se o NAS nao estiver
# acessivel, o OCR usa a pasta temporaria padrao do Windows.
TEMP_NAS = "//SEU_NAS/compartilhamento/tmp"
if os.path.isdir(TEMP_NAS):
    import tempfile
    tempfile.tempdir = TEMP_NAS


def _ambiente():
    amb = dict(os.environ)
    amb["PATH"] = os.pathsep.join(_CAMINHOS + [amb.get("PATH", "")])
    if os.path.isdir(TEMP_NAS):
        amb["TMP"] = amb["TEMP"] = amb["TMPDIR"] = TEMP_NAS
    return amb


def paginas_sem_texto(caminho):
    import fitz
    doc = fitz.open(caminho)
    return sum(1 for p in doc if len(p.get_text().split()) < MIN_PALAVRAS_PAG), len(doc)


def palavras_do_pdf(dados):
    """(palavras, paginas) de um PDF em bytes ou em caminho. Nada e gravado."""
    import fitz
    doc = fitz.open(stream=dados, filetype="pdf") if isinstance(dados, bytes) else fitz.open(dados)
    return sum(len(p.get_text().split()) for p in doc), len(doc)


def _imagens(caminho):
    """md5 dos PIXELS decodificados de cada imagem (como conjunto). O PDF/A regrava o fluxo JPEG (bytes diferentes, mesmos
    pixels); comparar os bytes comprados dava falso 'imagens mudaram' (caso icict/77820, 2026-10-19)."""
    import fitz
    doc = fitz.open(caminho)
    # ordenado: o PDF/A pode reordenar os objetos de imagem sem mudar nenhum pixel
    return sorted(hashlib.md5(fitz.Pixmap(doc, i[0]).samples).hexdigest() for p in doc for i in p.get_images(full=True))


def idiomas_do_item(item):
    """IDIOMAS + os idiomas do registro (dc.language) que o Tesseract conhece, sem repetir."""
    meta = item.get("metadata") or {}
    valores = []
    for chave, lista in meta.items():
        if chave.startswith("dc.language"):
            valores += [str(v.get("value") or "").strip().lower() for v in (lista or []) if isinstance(v, dict)]
    pacotes = ["por", "eng", "spa"]
    for v in valores:
        pacote = IDIOMAS_POR_REGISTRO.get(v)
        if pacote and pacote not in pacotes:
            pacotes.append(pacote)
    return "+".join(pacotes)


def versao_ocr():
    """Versoes das ferramentas usadas (vai para a descricao do item, para reproducao)."""
    def versao(cmd):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, env=_ambiente(), timeout=60)
            return (r.stdout or r.stderr).strip().splitlines()[0]
        except Exception:
            return "?"
    gs = shutil.which("gswin64c") or shutil.which("gs") or "gs"
    return {"ocrmypdf": versao(["ocrmypdf", "--version"]), "tesseract": versao([os.path.join(_CAMINHOS[0], "tesseract.exe"), "--version"]),
            "ghostscript": versao([gs, "--version"])}


def fazer_ocr(entrada, saida, jobs=None, idiomas=None):
    """Gera `saida` (PDF/A, com camada de texto invisivel) e confere. Devolve dict (ok True/False e motivo)."""
    t0 = time.time()
    idiomas = idiomas or IDIOMAS
    sem, total = paginas_sem_texto(entrada)
    if sem == 0:
        return {"ok": False, "motivo": "ja tem texto em todas as paginas", "paginas": total}
    cmd = ["ocrmypdf", "-l", idiomas, "--skip-text", "--output-type", "pdfa", "--optimize", "0",
           "--pdfa-image-compression", "lossless",   # o padrao (auto) troca PNG/Flate por JPEG: perda
           "--jobs", str(jobs or max(1, (os.cpu_count() or 2) - 2)), entrada, saida]
    r = subprocess.run(cmd, capture_output=True, text=True, env=_ambiente())
    formato = "PDF/A"
    if (r.returncode != 0 or not os.path.exists(saida)) and "invalid jpeg data" in (r.stderr or ""):
        # o original tem imagem JPEG com defeito (os leitores abrem, a conversao PDF/A nao aceita): PDF comum com OCR,
        # sem recomprimir nada (decisao do responsavel, 2026-10-20: so se nao perder qualidade; a conferencia de
        # pixels abaixo garante isso)
        cmd2 = [c for c in cmd if c not in ("--pdfa-image-compression", "lossless")]
        cmd2[cmd2.index("pdfa")] = "pdf"
        r = subprocess.run(cmd2, capture_output=True, text=True, env=_ambiente())
        formato = "PDF (não PDF/A: o original tem imagem JPEG com defeito)"
    if r.returncode != 0 or not os.path.exists(saida):
        return {"ok": False, "motivo": "ocrmypdf falhou: " + (r.stderr or "")[-300:], "paginas": total}
    import fitz
    a, b = fitz.open(entrada), fitz.open(saida)
    if len(a) != len(b):
        return {"ok": False, "motivo": "numero de paginas mudou", "paginas": total}
    if _imagens(entrada) != _imagens(saida):
        return {"ok": False, "motivo": "imagens das paginas mudaram", "paginas": total}
    palavras = sum(len(p.get_text().split()) for p in b)
    sem_depois, _ = paginas_sem_texto(saida)
    if palavras < 20:
        return {"ok": False, "motivo": "OCR nao encontrou texto", "paginas": total}
    return {"ok": True, "paginas": total, "paginas_sem_texto_antes": sem, "paginas_sem_texto_depois": sem_depois,
            "palavras": palavras, "bytes_antes": os.path.getsize(entrada), "bytes_depois": os.path.getsize(saida),
            "segundos": round(time.time() - t0, 1), "idiomas": idiomas, "formato": formato}


def processar_item(cliente, item, aviso=print):
    """OCR de todos os PDFs escaneados do item (so leitura no ARCA). Devolve lista de resultados por arquivo."""
    h = item["handle"]
    pasta = os.path.join(PASTA, h.replace("/", "_"))
    os.makedirs(pasta, exist_ok=True)
    res = []
    for bd in cliente.get("/core/items/%s/bundles" % item["uuid"])["_embedded"]["bundles"]:
        if bd["name"] != "ORIGINAL":
            continue
        for x in cliente.get("/core/bundles/%s/bitstreams" % bd["uuid"], params={"size": 100})["_embedded"]["bitstreams"]:
            if not (x.get("name") or "").lower().endswith(".pdf"):
                continue
            orig = os.path.join(pasta, "original_" + x["uuid"] + ".pdf")
            novo = os.path.join(pasta, "ocr_" + x["uuid"] + ".pdf")
            if not os.path.exists(orig):
                r = cliente._pedir("GET", config.BASE_URL + "/core/bitstreams/%s/content" % x["uuid"], timeout=900)
                if r.status_code != 200 or not r.content.startswith(b"%PDF"):
                    res.append({"arquivo": x["name"], "ok": False, "motivo": "nao baixou (HTTP %d)" % r.status_code})
                    continue
                with open(orig + ".tmp", "wb") as f:
                    f.write(r.content)
                os.replace(orig + ".tmp", orig)
            palavras, _ = palavras_do_pdf(orig)
            if palavras >= LIMITE_PALAVRAS_SEM_TEXTO:
                res.append({"arquivo": x["name"], "ok": False, "palavras": palavras, "bitstream": x["uuid"],
                            "bundle": bd["uuid"], "motivo": "ja tem texto (%d palavras): nao passa por OCR" % palavras})
                continue
            try:
                d = fazer_ocr(orig, novo + ".tmp.pdf", idiomas=idiomas_do_item(item))
            except Exception as e:
                d = {"ok": False, "motivo": "%s: %s" % (type(e).__name__, str(e)[:200])}
            if d["ok"]:
                os.replace(novo + ".tmp.pdf", novo)
            elif os.path.exists(novo + ".tmp.pdf"):
                os.remove(novo + ".tmp.pdf")
            d.update({"arquivo": x["name"], "bitstream": x["uuid"], "bundle": bd["uuid"],
                      "original_local": orig, "ocr_local": novo if d["ok"] else None})
            res.append(d)
            aviso("  %s | %s: %s" % (h, x["name"], "OK (%d pag, %d palavras, %.0f s)" % (d["paginas"], d["palavras"], d["segundos"])
                                     if d["ok"] else d["motivo"]))
    with open(os.path.join(pasta, "resultado.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    return res


def disponivel():
    return bool(shutil.which("ocrmypdf")) and os.path.exists(os.path.join(_CAMINHOS[0], "tesseract.exe"))


def _baixar(cliente, uuid, tentativas=4):
    """Baixa o conteudo de um arquivo; repete em queda de conexao. None se nao foi possivel."""
    import time
    for n in range(tentativas):
        try:
            return cliente._pedir("GET", config.BASE_URL + "/core/bitstreams/%s/content" % uuid, timeout=900)
        except Exception:
            time.sleep(5 * (n + 1))
    return None


def varrer_sem_texto(cliente, itens, aviso=print, workers=8):
    """Varre o ARCA AGORA (so leitura) e devolve uma linha por PDF: handle, arquivo, palavras, situacao.

    A lista vem do servidor no momento da consulta. O que se reaproveita e so o texto medido de um arquivo
    cuja soma md5 (checkSum do proprio ARCA) ja foi medida: a soma diz que o arquivo e o mesmo, entao o
    numero de palavras tambem e o mesmo. Arquivo novo ou trocado tem soma nova e e medido de novo.
    """
    import json as _json
    import threading
    from concurrent.futures import ThreadPoolExecutor
    cache = {}
    if os.path.exists(CACHE_TEXTO):
        with open(CACHE_TEXTO, encoding="utf-8") as f:
            cache = _json.load(f)
    trava = threading.Lock()
    linhas = []
    cont = {"itens": 0, "pdfs": 0, "do_cache": 0, "ilegiveis": 0}

    def um_item(item):
        out = []
        for bd in (cliente.get("/core/items/%s/bundles" % item["uuid"], obrigatorio=False) or {}).get("_embedded", {}).get("bundles", []):
            if bd["name"] != "ORIGINAL":
                continue
            bitst = (cliente.get("/core/bundles/%s/bitstreams" % bd["uuid"], params={"size": 100},
                                 obrigatorio=False) or {}).get("_embedded", {}).get("bitstreams", [])
            for x in bitst:
                if not (x.get("name") or "").lower().endswith(".pdf"):
                    continue
                soma = ((x.get("checkSum") or {}).get("value") or "")
                with trava:
                    hit = cache.get(soma) if soma else None
                if hit is None:
                    r = _baixar(cliente, x["uuid"])
                    if r is None:
                        out.append({"handle": item.get("handle") or item.get("uuid"), "arquivo": x["name"],
                                    "palavras": None, "situacao": "nao_verificado", "bitstream": x["uuid"],
                                    "bundle": bd["uuid"]})
                        with trava:
                            cont["ilegiveis"] += 1
                        continue
                    if r.status_code != 200 or not r.content.startswith(b"%PDF"):
                        out.append({"handle": item.get("handle"), "arquivo": x["name"], "palavras": None,
                                    "situacao": "ilegivel", "bitstream": x["uuid"], "bundle": bd["uuid"]})
                        with trava:
                            cont["ilegiveis"] += 1
                        continue
                    try:
                        pal, pag = palavras_do_pdf(r.content)
                    except Exception:
                        out.append({"handle": item.get("handle"), "arquivo": x["name"], "palavras": None,
                                    "situacao": "ilegivel", "bitstream": x["uuid"], "bundle": bd["uuid"]})
                        with trava:
                            cont["ilegiveis"] += 1
                        continue
                    hit = {"palavras": pal, "paginas": pag}
                    if soma:
                        with trava:
                            cache[soma] = hit
                else:
                    with trava:
                        cont["do_cache"] += 1
                situacao = "sem_texto" if hit["palavras"] < LIMITE_PALAVRAS_SEM_TEXTO else "com_texto"
                out.append({"handle": item.get("handle") or item.get("uuid"), "arquivo": x["name"],
                            "palavras": hit["palavras"], "paginas": hit["paginas"], "situacao": situacao,
                            "bitstream": x["uuid"], "bundle": bd["uuid"]})
        with trava:
            cont["itens"] += 1
            cont["pdfs"] += len(out)
            if cont["itens"] % 2000 == 0:
                aviso("  %d itens lidos, %d PDFs" % (cont["itens"], cont["pdfs"]))
        return out

    with ThreadPoolExecutor(workers) as ex:
        for lote in ex.map(um_item, itens):
            linhas += lote
    os.makedirs(os.path.dirname(CACHE_TEXTO), exist_ok=True)
    with open(CACHE_TEXTO + ".tmp", "w", encoding="utf-8") as f:
        _json.dump(cache, f)
    os.replace(CACHE_TEXTO + ".tmp", CACHE_TEXTO)
    aviso("Itens lidos: %d; PDFs: %d (%d com medida reaproveitada pela soma md5; %d ilegiveis)"
          % (cont["itens"], cont["pdfs"], cont["do_cache"], cont["ilegiveis"]))
    return linhas
