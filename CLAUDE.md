# CLAUDE.md — regras para quem (pessoa ou IA) mexer neste projeto

Arca ODS: indexação de ODS no Arca, repositório institucional da Fiocruz (DSpace 9.3). Guia: [README.md](README.md).

1. **O programa grava só com confirmação.** Uma IA não grava no Arca por conta própria: para testar, use `ARCA_SOMENTE_LEITURA=sim`.
2. **`dc.description.provenance` é intocável.**
3. **Toda escrita passa pelo `ClienteDSpace`** (`arca/dspace.py`), que aplica as travas. Não criar outro caminho de escrita.
4. **ODS se julga só pelo texto das metas** (lista dos 18 ODS + metas ONU e Ipea 2026). Nenhuma regra por ODS.
5. **O resumo vai inteiro** para o modelo, nunca truncado.
6. **Mudou o método? Meça antes**, em registros reservados, e crie uma nova versão de prompt.
7. **Dados, saídas e sessão de login não entram no git.**
