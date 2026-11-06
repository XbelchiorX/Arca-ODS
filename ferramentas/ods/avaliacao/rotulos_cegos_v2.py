# -*- coding: utf-8 -*-
# Revisao (2026-10-02) dos rotulos cegos apos ler ONU Brasil, IPEA (metas nacionais 2018) e glossarios ONU.
# Criterios decididos com o responsavel:
#  ODS 9 (opcao 1a): documento desenvolve/valida/avalia tecnologia, produto, processo ou inovacao
#     (software, app, plataforma, teste diagnostico, farmaco/vacina/adjuvante candidato, dispositivo, metodo,
#     sistema de qualidade de laboratorio) ou trata de politica industrial/inovacao. Base: 9.5 e 9.b; 3.b Brasil
#     (P&D de tecnologias e inovacoes em saude) correlata a 9.5. Pesquisa basica de mecanismo: so a ODS do tema.
#  ODS 4: formacao profissional/superior (4.3, 4.4), inclusive de trabalhadores da saude (junto com 3.c);
#     educacao em museus, professores (4.7, 4.c). Nao: o documento ser tese/dissertacao.
#  ODS 5: 5.1/5.2 Brasil incluem identidade de genero e orientacao sexual; 5.6 quando a saude sexual e
#     reprodutiva e tratada como direito/acesso/autonomia/servico (contracepcao, aborto, pre-natal e parto como
#     cuidado, aleitamento, violencia sexual/obstetrica, prevencao de IST). Estudo clinico/molecular de gestacao,
#     cancer de mama ou HIV fica so na 3.
#  ODS 11.4: patrimonio cultural inclui acervos museologicos/documentais.
#  ODS 18: metas e sub-metas do glossario ONU (2026).
g = {}; exec(open("rotulos_cegos.py", encoding="utf-8").read(), g); C = {k: list(v) for k, v in g["C"].items()}
MUDA = {
2: ([2, 3, 6, 8], "+8: economia solidaria/trabalho 8.3"),
7: ([3, 9], "+9: derivados de farmaco desenhados por IA (3.b/9.5)"),
9: ([3, 9], "+9: metodo bioanalitico para candidato a antiasmatico"),
15: ([3, 5, 10], "+5: identidade de genero (5.1 Brasil) e prevencao de IST/PrEP (5.6)"),
16: ([3, 9], "+9: desenvolvimento/validacao de teste diagnostico de TB"),
17: ([3, 9], "+9: comparacao/validacao de protocolos moleculares de diagnostico"),
23: ([3, 4, 8], "+4: preceptoria e formacao de residentes (4.4/3.c)"),
26: ([3, 9], "+9: protocolo computacional para alvos terapeuticos"),
27: ([3, 4, 9], "+9: aplicativo educativo MedPICS"),
29: ([2, 3, 5], "+5: protecao ao aleitamento materno (5.6)"),
30: ([3, 4], "+4: formacao em especializacao (4.4/3.c)"),
51: ([3, 9], "+9: candidato a farmaco (complexo de rutenio)"),
61: ([4, 11], "+11: museus de ciencia, patrimonio (11.4)"),
62: ([3, 9], "+9: ensaio molecular consenso multicentrico"),
65: ([3, 9], "+9: insumos para teste diagnostico de Mayaro"),
67: ([3, 9], "+9: candidato a inseticida"),
70: ([3, 9], "+9: avaliacao pre-clinica de farmaco"),
71: ([3, 9], "+9: estabelecimento de colonia/metodo para monitorar resistencia"),
73: ([3, 9], "+9: terapia genica CRISPR in vivo"),
74: ([3, 9], "+9: validacao de sistema targeted NGS (Deeplex)"),
81: ([3, 9], "+9: sistema de gestao da qualidade em pesquisa (indicador 9.b)"),
82: ([3, 9], "+9: peptideos candidatos a antimicrobiano"),
84: ([3, 4], "+4: oficina e manual de capacitacao de profissionais"),
93: ([4, 11], "+11: patrimonio cultural e cientifico do museu"),
95: ([3, 9], "+9: lectina com potencial de adjuvante vacinal"),
99: ([3, 5], "+5: campanha de diagnostico de HIV, prevencao de IST (5.6)"),
103: ([3, 4, 10], "+4: curriculo de capacitacao de profissionais"),
109: ([3, 9], "+9: proteina recombinante terapeutica"),
115: ([3, 9], "+9: modelo de dispositivo organ-on-a-chip"),
116: ([4, 11], "+11: museu (11.4)"),
118: ([3, 5, 10, 16], "+5: violencia contra LGBTIQ+ (5.1/5.2 Brasil)"),
121: ([3, 9], "+9: candidato a farmaco antitumoral"),
123: ([3, 9], "+9: avaliacao de teste diagnostico"),
124: ([2, 3, 5], "+5: pre-natal e aleitamento (5.6)"),
128: ([3, 9], "+9: flavonoides candidatos a antiviral"),
131: ([3, 9], "+9: avaliacao de bioinseticida e concentracao discriminante nova"),
134: ([3, 4], "+4: programa de formacao de agentes (AgPopSUS)"),
135: ([3, 4, 18], "+4: formacao de agentes de educacao popular"),
137: ([3, 4], "+4: educacao permanente/especializacao (4.4/3.c)"),
139: ([3, 9], "+9: chatbot avaliado (3.b/9.5)"),
141: ([3, 4, 10, 18], "+4: formacao antirracista na graduacao"),
144: ([3, 9], "+9: derivados candidatos contra T. cruzi"),
149: ([3, 9], "+9: plataforma web de triagem virtual"),
}
for i, (o, j) in MUDA.items():
    C[i] = (o, j)
C = {i: (v[0], v[1]) if isinstance(v, tuple) else (v[0], v[1]) for i, v in C.items()}
