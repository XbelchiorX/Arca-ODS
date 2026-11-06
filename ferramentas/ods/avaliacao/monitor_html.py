# -*- coding: utf-8 -*-
"""Monitor da fila do professor de ODS em HTML (02/11, pedido da responsavel): a pagina se atualiza sozinha a cada
15 s no navegador. Mostra o teste atual (barra, ritmo, tempo restante, hora prevista), a GPU, a fila inteira e a
tabela de resultados contra os registros revisados por ela. So le arquivos; nao mexe na fila.
Uso: python ferramentas/ods/avaliacao/monitor_html.py   (abre saidas/ods/monitor_professor.html)
"""
import glob
import html
import json
import os
import subprocess
import sys
import time
import webbrowser

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fila_revisados as F  # noqa: E402

SAIDA = os.path.join(RAIZ, "saidas", "ods", "monitor_professor.html")
NOME_FORMA = {"tema_trecho": "v8 tema + trecho", "tema_livre": "v8 resumo livre", "nota": "v8 nota 0-100",
              "": "v3 (referência)", "duas_etapas": "v8 duas etapas (descrição antes)",
              "descricao_trecho": "v8 descrição + trecho"}
NOME_MODELO = {"qwen3.5-35b": "Qwen 3.5-35B", "gemma4-26b": "Gemma 4 26B", "gemma4-e4b": "Gemma 4 E4B",
               "gemma4-e2b": "Gemma 4 E2B", "qwen3.8-27b": "Qwen 3.8-27B", "llama3.1-8b": "Llama 3.1 8B"}
S_PADRAO = {"qwen3.5-35b": 16, "gemma4-26b": 20, "gemma4-e4b": 8, "gemma4-e2b": 6}   # s/registro, ate medir
CORTE_NOTA = 70


def ler(caminho, padrao=""):
    try:
        return open(caminho, encoding="utf-8").read().strip()
    except OSError:
        return padrao


def gpu():
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu",
                            "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10)
        usada, total, uso = [int(x) for x in r.stdout.strip().split(",")]
        return usada, total, uso
    except Exception:
        return None


def metricas(arq, gold):
    d = json.load(open(arq, encoding="utf-8"))
    itens, nota = d["itens"], "nota" in os.path.basename(arq)
    c = a = m = n = 0
    for h, g in gold.items():
        if h not in itens:
            continue
        p = {o["n"] for o in (itens[h]["modelo"] or []) if not nota or o.get("nota", 0) >= CORTE_NOTA}
        g = set(g)
        c, a, m, n = c + len(g & p), a + len(p - g), m + len(g - p), n + len(p)
    f1 = 2 * c / (2 * c + a + m) if c else 0.0
    return dict(certos=c, mais=a, faltando=m, f1=f1, ods=n / max(len(gold), 1), s=d["resumo"]["s_por_item"],
                falhas=d["resumo"].get("falhas_json", 0))


def hhmm(seg):
    seg = int(max(seg, 0))
    return "%dh%02d" % (seg // 3600, seg % 3600 // 60) if seg >= 3600 else "%d min" % max(seg // 60, 1)


def pagina():
    gold = json.load(open(F.GAB, encoding="utf-8"))["itens"]
    status = ler(F.STATUS, "sem status")
    feitos, total = (ler(F.PROGRESSO, "0 11").split() + ["11"])[:2]
    feitos, total = int(feitos), int(total)
    try:
        inicio = time.mktime(time.strptime(status[:19], "%Y-%m-%d %H:%M:%S"))
    except ValueError:
        inicio = time.time()
    rodando = "FIM" not in status
    decorrido = time.time() - inicio
    ritmo = decorrido / feitos if feitos else None
    # fila: testes feitos x pendentes, tempo estimado pelo s/registro medido de cada modelo
    medido = {}
    linhas_fila, pend_s = [], 0
    for t in F.TESTES:
        if os.path.exists(F.arquivo(*t)):
            medido.setdefault(t[0], []).append(json.load(open(F.arquivo(*t), encoding="utf-8"))["resumo"]["s_por_item"])
    atual_txt = status[20:] if len(status) > 20 else status
    for i, t in enumerate(F.TESTES, 1):
        m, p, f, _ = t
        feito = os.path.exists(F.arquivo(*t))
        atual = rodando and not feito and status.endswith("%s, prompt v%d %s" % (m, p, f))
        s_item = sum(medido.get(m, [])) / len(medido[m]) if medido.get(m) else S_PADRAO.get(m, 20)
        if f in ("duas_etapas", "descricao_trecho"):
            s_item *= 1.5
        if not feito:
            pend_s += (max(total - feitos, 0) if atual else 11) * (ritmo if atual and ritmo else s_item)
        estado = "feito" if feito else ("rodando" if atual else "na fila")
        linhas_fila.append((i, NOME_MODELO.get(m, m), NOME_FORMA.get(f, f), estado))
    fim_prev = time.strftime("%H:%M", time.localtime(time.time() + pend_s)) if rodando and pend_s else "-"
    g = gpu()
    # resultados: todos os arquivos dos revisados com as metas corrigidas (inclusive modelos descartados)
    res = []
    for arq in glob.glob(os.path.join(F.PROF, "comparacao_v*_revisados_metas2026_*.json")):
        b = os.path.basename(arq)
        forma = b.split("metas2026_")[1][:-5]
        forma = "" if forma == "v3" else forma[2:]
        modelo = next((k for k, v in F.NOMES.items() if v in b), b)
        try:
            res.append((NOME_MODELO.get(modelo, modelo), NOME_FORMA.get(forma, forma), metricas(arq, gold),
                        modelo in ("qwen3.8-27b", "llama3.1-8b")))
        except Exception:
            pass
    res.sort(key=lambda r: -r[2]["f1"])
    pct = 100 * feitos / total if total else 0
    e = html.escape
    tr_res = "".join(
        "<tr class='%s'><td>%s</td><td>%s</td><td class='n'><b>%.2f</b></td><td class='n'>%d</td><td class='n'>%d</td>"
        "<td class='n'>%d</td><td class='n'>%.2f</td><td class='n'>%.0f</td><td class='n'>%s</td></tr>" % (
            "desc" if desc else "", e(mo), e(fo) + (" (corte %d)" % CORTE_NOTA if "nota" in fo else ""), r["f1"],
            r["certos"], r["mais"], r["faltando"], r["ods"], r["s"], r["falhas"] or "")
        for mo, fo, r, desc in res)
    tr_fila = "".join("<tr class='%s'><td class='n'>%d</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
        est.replace(" ", ""), i, e(mo), e(fo), est) for i, mo, fo, est in linhas_fila)
    return """<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="15"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Professor de ODS — monitor</title>
<style>
:root{--bg:#f7f6f2;--card:#fff;--tx:#1f2328;--mut:#6b7078;--lin:#e4e2dc;--ac:#2f6f4f;--warn:#9a6700}
@media (prefers-color-scheme:dark){:root{--bg:#16181c;--card:#1f2228;--tx:#e6e6e6;--mut:#9aa0a8;--lin:#30343b;--ac:#5fbf8c;--warn:#d8a43a}}
body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.45 system-ui,Segoe UI,sans-serif}
main{max-width:980px;margin:0 auto;padding:20px 16px}
h1{font-size:20px;margin:0 0 4px}.mut{color:var(--mut);font-size:13px}
.card{background:var(--card);border:1px solid var(--lin);border-radius:12px;padding:16px;margin:14px 0}
.bar{height:14px;background:var(--lin);border-radius:7px;overflow:hidden;margin:10px 0}
.bar>div{height:100%%;background:var(--ac)}
.kpis{display:flex;gap:14px;flex-wrap:wrap}.kpi{flex:1;min-width:130px}.kpi b{display:block;font-size:20px}
table{width:100%%;border-collapse:collapse;font-size:14px}th,td{padding:6px 8px;border-bottom:1px solid var(--lin);text-align:left}
th{color:var(--mut);font-weight:600}td.n{text-align:right;font-variant-numeric:tabular-nums}
tr.desc td{color:var(--mut)}tr.feito td{color:var(--mut)}tr.rodando td{font-weight:700;color:var(--ac)}
.wrap{overflow-x:auto}
</style></head><body><main>
<h1>Professor de ODS — fila dos registros revisados</h1>
<div class="mut">Atualiza sozinho a cada 15 s · última leitura %s</div>
<div class="card"><div><b>%s</b></div>
<div class="bar"><div style="width:%.0f%%"></div></div>
<div class="kpis">
<div class="kpi"><span class="mut">Registros neste teste</span><b>%d de %d</b></div>
<div class="kpi"><span class="mut">Ritmo</span><b>%s</b></div>
<div class="kpi"><span class="mut">Falta na fila</span><b>%s</b></div>
<div class="kpi"><span class="mut">Fim previsto</span><b>%s</b></div>
<div class="kpi"><span class="mut">GPU</span><b>%s</b></div>
</div></div>
<div class="card"><b>Resultados contra a sua revisão (%d registros)</b>
<div class="mut">F1 com ODS 3. Cinza: modelos descartados. Nota com corte fixo %d. São poucos registros: diferenças pequenas podem ser acaso.</div>
<div class="wrap"><table><tr><th>Modelo</th><th>Prompt</th><th>F1</th><th>certos</th><th>a mais</th><th>faltando</th><th>ODS/reg.</th><th>s/reg.</th><th>falhas</th></tr>%s</table></div></div>
<div class="card"><b>Fila</b><div class="wrap"><table><tr><th>#</th><th>Modelo</th><th>Prompt</th><th>Situação</th></tr>%s</table></div></div>
</main></body></html>""" % (
        time.strftime("%d/%m %H:%M:%S"), e(atual_txt if rodando else "Fila terminada (%s)" % status[:16]), pct,
        feitos, total, ("%.0f s por registro" % ritmo) if ritmo else "-", hhmm(pend_s) if rodando else "-", fim_prev,
        ("%d%% · %.1f de %.0f GB" % (g[2], g[0] / 1024, g[1] / 1024)) if g else "-",
        len(gold), CORTE_NOTA, tr_res, tr_fila)


def main():
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    aberto = False
    while True:
        try:
            tmp = SAIDA + ".tmp"
            open(tmp, "w", encoding="utf-8").write(pagina())
            os.replace(tmp, SAIDA)
        except Exception as ex:     # o monitor nunca derruba nada; tenta de novo na proxima volta
            print("monitor:", ex, flush=True)
        if not aberto:
            webbrowser.open("file:///" + SAIDA.replace("\\", "/"))
            aberto = True
        if "FIM" in ler(F.STATUS) and "--sempre" not in sys.argv:
            time.sleep(30)
            open(SAIDA, "w", encoding="utf-8").write(pagina())
            break
        time.sleep(15)


if __name__ == "__main__":
    main()
