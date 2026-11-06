# -*- coding: utf-8 -*-
"""So leitura: escreve o prompt EXATO que o professor recebe para um item (prompt v3, as 20 metas candidatas do item,
o texto do documento como vai no fluxo), para conferencia humana. Nao chama o modelo.
Uso: python ferramentas/ods/avaliacao/mostrar_prompt.py icict/43244 [--sem-trecho]"""
import os
import sys

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, RAIZ)
from arca import ods_metabusca as MB, ods_professor as P, ods_sinais as S, ods_texto as T  # noqa: E402
from arca.decs_acervo import carregar_acervo  # noqa: E402

h = sys.argv[1]
ac = carregar_acervo()
cache = S.carregar_cache()
metas = MB.metas()
cand = MB.candidatas(list(metas), cache[h]["sim"].astype(np.float32))
p = P._prompt(T.texto_professor(ac[h]), cand, metas, com_trecho="--sem-trecho" not in sys.argv)
saida = os.path.join(RAIZ, "publicacoes", "artigo_ods", "resultados", "professor",
                     "prompt_v3_exato_%s.md" % h.replace("/", "_"))
with open(saida, "w", encoding="utf-8") as f:
    f.write("# Prompt v3 exato enviado ao professor (%s)\n\nGerado por ferramentas/ods/avaliacao/mostrar_prompt.py a "
            "partir do codigo em uso (arca/ods_professor.py). %d caracteres.\n\n```text\n%s\n```\n" % (h, len(p), p))
print(saida)
