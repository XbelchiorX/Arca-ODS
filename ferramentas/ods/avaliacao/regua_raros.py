# -*- coding: utf-8 -*-
"""Candidatos aos ODS raros para completar a regua (D29; decisao do responsavel em 2026-10-27).

Os estratos de 04/10 (sinais de embedding/ODSBahia) quase nao trouxeram os ODS raros (estrato do ODS 7: 0 de 40
confirmados). Aqui a busca e por TERMOS tirados do texto das metas, no texto EXATO que o professor recebe e o aluno
recebera (texto_professor: titulo, resumo inteiro, todas as palavras-chave do autor e, se o resumo e curto, o resumo
gerado do PDF; D9/D10). O DeCS NAO entra: parte dele foi gravada pelo nosso
indexador automatico e nao e fonte humana independente (responsavel, 27/10).
Pontuacao: termos distintos achados (titulo ou palavra-chave vale 2; resumo vale 1). Entram os itens com 2+ pontos;
sorteio (semente 20261028) de N por ODS entre eles. Fora: v4, regua v5 e os 1.000 da planilha de revisao.
Limitacao (para o artigo): itens achados por termo explicito tendem a ser casos mais claros; vale igual para todos
os professores, entao a comparacao entre eles continua justa.

Uso: python ferramentas/ods/avaliacao/regua_raros.py [--contar] [--n 50]
Saida: dados/gabarito_claude_v6/ (amostra.json, lote_NN.txt, metas_completas.txt, PROTOCOLO.md) e
       dados/gabarito_claude_v6_estratos.json (fora da pasta dos rotuladores)
"""
import json
import os
import random
import re
import shutil
import sys
import unicodedata
from collections import Counter

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, RAIZ)
from arca import config, decs_acervo  # noqa: E402
from arca.ods_texto import texto_professor  # noqa: E402

SEMENTE = 20261028
SAIDA = os.path.join(RAIZ, "dados", "gabarito_claude_v6")

# termos das metas (pt / en / es), sem acento e em minusculas; "*" = qualquer final
TERMOS = {
    1: ["pobreza", "pobre*", "poverty", "poor", "pobreza extrema", "extrema pobreza", "extreme poverty",
        "protecao social", "social protection", "transferencia de renda", "cash transfer*", "bolsa familia",
        "renda basica", "basic income", "vulnerabilidade social", "assistencia social", "social assistance",
        "seguridade social", "social security", "beneficio de prestacao continuada", "programa social"],
    7: ["energia renovave*", "renewable energ*", "energias renovaveis", "energia limpa", "clean energy",
        "eficiencia energetica", "energy efficiency", "biocombustive*", "biofuel*", "biodiesel", "bioetanol",
        "bioethanol", "etanol combustivel", "energia solar", "solar energy", "energia eolica", "wind energy",
        "matriz energetica", "energy matrix", "acesso a energia", "energy access", "eletrificacao",
        "electrification", "biogas", "biomassa energetica", "fotovolta*", "photovolta*", "hidrogenio verde",
        "green hydrogen", "combustivel limpo", "clean fuel*", "cozimento limpo", "clean cooking"],
    9: ["infraestrutura", "infrastructure", "industrializacao", "industrialization", "inovacao tecnologica",
        "technological innovation", "pesquisa e desenvolvimento", "research and development", "p&d",
        "desenvolvimento tecnologico", "technological development", "transferencia de tecnologia",
        "technology transfer", "complexo industrial da saude", "health industrial complex",
        "complexo economico-industrial da saude", "producao nacional", "industria farmaceutica",
        "pharmaceutical industry", "patente*", "patent*", "propriedade intelectual", "intellectual property",
        "internet", "inclusao digital", "digital inclusion", "conectividade", "connectivity",
        "incubadora", "startup*", "empresa de base tecnologica"],
    12: ["residuo*", "waste", "lixo", "reciclagem", "recycling", "reuso", "reuse", "consumo sustentavel",
         "sustainable consumption", "producao sustentavel", "sustainable production", "desperdicio de alimentos",
         "food waste", "perda de alimentos", "food loss", "agrotoxico*", "pesticide*", "produtos quimicos",
         "chemical products", "residuos de servicos de saude", "health care waste", "medical waste",
         "compras publicas sustentaveis", "sustainable procurement", "economia circular", "circular economy",
         "turismo sustentavel", "sustainable tourism", "relatorio de sustentabilidade", "sustainability report*",
         "logistica reversa", "reverse logistics", "descarte"],
    13: ["mudanca* do clima", "mudanca* climatica*", "climate change", "aquecimento global", "global warming",
         "cambio climatico", "adaptacao climatica", "climate adaptation", "mitigacao", "mitigation",
         "gases de efeito estufa", "greenhouse gas*", "emissoes de carbono", "carbon emission*",
         "eventos extremos", "extreme event*", "extreme weather", "desastre* natura*", "natural disaster*",
         "alerta precoce", "early warning", "resiliencia climatica", "climate resilience", "onda* de calor",
         "heat wave*", "heatwave*", "seca*", "drought*", "enchente*", "inundac*", "flood*"],
    14: ["oceano*", "ocean*", "marinh*", "marine", "mar ", "sea ", "costeir*", "coastal", "pesca", "fishing",
         "fisheries", "pescador*", "fisher*", "manguezal", "manguezais", "mangrove*", "recife* de coral",
         "coral reef*", "acidificacao", "acidification", "poluicao marinha", "marine pollution", "estuario*",
         "estuar*", "maricultura", "aquicultura", "aquaculture", "zona costeira", "coastal zone", "praia*",
         "beach*", "microplastico*", "microplastic*", "biologia marinha", "marine biology"],
    15: ["biodiversidade", "biodiversity", "floresta*", "forest*", "desmatamento", "deforestation",
         "reflorestamento", "reforestation", "desertificacao", "desertification", "degradacao do solo",
         "land degradation", "especies ameacadas", "endangered species", "threatened species",
         "especies invasoras", "invasive species", "especie exotica", "trafico de animais", "wildlife trafficking",
         "caca ilegal", "poaching", "conservacao", "conservation", "unidade* de conservacao", "protected area*",
         "area* protegida*", "ecossistema* terrestre*", "terrestrial ecosystem*", "recursos geneticos",
         "genetic resources", "repartic* de beneficios", "benefit sharing", "mata atlantica", "atlantic forest",
         "cerrado", "caatinga", "pantanal", "amazonia", "amazon rainforest", "fauna silvestre", "wildlife"],
    17: ["cooperacao internacional", "international cooperation", "cooperacao sul-sul", "south-south cooperation",
         "cooperacao norte-sul", "cooperacao triangular", "triangular cooperation", "parceria*", "partnership*",
         "parceria publico-privada", "public-private partnership*", "ajuda humanitaria", "assistencia oficial",
         "official development assistance", "financiamento do desenvolvimento", "development finance",
         "mobilizacao de recursos", "resource mobilization", "comercio internacional", "international trade",
         "organizacao mundial do comercio", "world trade organization", "divida externa", "external debt",
         "diplomacia da saude", "health diplomacy", "saude global", "global health", "agenda 2030",
         "objetivos de desenvolvimento sustentavel", "sustainable development goals", "multilateral*"],
}


def norm(s):
    s = "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c))
    return " " + re.sub(r"[^a-z0-9&\- ]+", " ", s.lower()).replace("-", " ") + " "


def padrao(t):
    t = norm(t).strip().replace("-", " ")
    p = re.escape(t).replace(r"\*", r"\w*")
    return re.compile(r"(?<![a-z0-9])" + p + r"(?![a-z0-9])")


PADROES = {n: [(t, padrao(t)) for t in ts] for n, ts in TERMOS.items()}


def partes(texto):
    """O texto EXATO que o professor recebe (e o aluno recebera: texto_professor, D9/D10), em 3 partes normalizadas:
    titulo, palavras-chave e resumo (+ resumo gerado do PDF quando o resumo e curto)."""
    def sec(rotulo):
        m = re.search(r"^%s: (.*?)(?=^[A-Z][A-Z ()-]*: |\Z)" % re.escape(rotulo), texto, re.M | re.S)
        return m.group(1) if m else ""
    return (norm(sec("TITULO")), norm(sec("PALAVRAS-CHAVE")),
            norm(sec("RESUMO") + " " + sec("RESUMO GERADO DO TEXTO COMPLETO (PDF)")))


def pontos(secoes, n):
    tit, kw, res = secoes
    p, achados = 0, []
    for t, rx in PADROES[n]:
        if rx.search(tit) or rx.search(kw):
            p += 2
            achados.append(t)
        elif rx.search(res):
            p += 1
            achados.append(t)
    return p, achados


def main():
    contar = "--contar" in sys.argv
    n_por = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 50
    fora = set(json.load(open(os.path.join(RAIZ, "dados", "gabarito_claude_v4", "amostra.json"),
                              encoding="utf-8"))["itens"])
    fora |= set(json.load(open(os.path.join(RAIZ, "dados", "gabarito_claude_v5", "amostra.json"),
                               encoding="utf-8"))["itens"])
    fora |= set(json.load(open(os.path.join(config.SAIDAS, "ods", "revisao_professor_1000_rotulos.json"),
                               encoding="utf-8")))
    acervo = decs_acervo.carregar_acervo()
    textos = {h: texto_professor(acervo[h]) for h in sorted(acervo) if h not in fora}
    secoes = {h: partes(t) for h, t in textos.items()}
    print("%d textos do professor montados" % len(textos), flush=True)
    rnd = random.Random(SEMENTE)
    escolhidos, estrato, achados = [], {}, {}
    for n in TERMOS:
        pool = []
        for h in secoes:
            if h in estrato:
                continue
            p, a = pontos(secoes[h], n)
            if p >= 2:
                pool.append(h)
                achados.setdefault(h, {})[n] = a
        termos = Counter(t for h in pool for t in achados[h][n])
        print("ODS %2d: %5d candidatos; termos mais achados: %s" % (n, len(pool), termos.most_common(6)), flush=True)
        if contar:
            continue
        rnd.shuffle(pool)
        for h in pool[:n_por]:
            estrato[h] = n
            escolhidos.append(h)
    if contar:
        return
    rnd.shuffle(escolhidos)
    os.makedirs(SAIDA, exist_ok=True)
    json.dump({"semente": SEMENTE, "estrato": estrato, "termos_achados": {h: achados[h][estrato[h]] for h in estrato}},
              open(SAIDA + "_estratos.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"semente": SEMENTE, "descricao": __doc__.split("\n\n")[0], "itens": escolhidos, "textos": textos},
              open(os.path.join(SAIDA, "amostra.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    v5 = os.path.join(RAIZ, "dados", "gabarito_claude_v5")
    shutil.copy(os.path.join(v5, "metas_completas.txt"), os.path.join(SAIDA, "metas_completas.txt"))
    shutil.copy(os.path.join(v5, "PROTOCOLO.md"), os.path.join(SAIDA, "PROTOCOLO.md"))
    for k in range(0, len(escolhidos), 25):
        with open(os.path.join(SAIDA, "lote_%02d.txt" % (k // 25 + 1)), "w", encoding="utf-8") as f:
            for i, h in enumerate(escolhidos[k:k + 25], 1):
                f.write("=== [%d] %s ===\n%s\n\n" % (i, h, textos[h]))
    print("%d itens em %d lotes: %s" % (len(escolhidos), -(-len(escolhidos) // 25), SAIDA))


if __name__ == "__main__":
    main()
