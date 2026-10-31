# Relatório da versão 0.13.1 — Ferramentas Terra

**Data de geração:** 2026-10-25.

## Confirmação recebida sobre a versão anterior (0.13.0)

O usuário testou a 0.13.0 no QGIS 3.44.15 e relatou: a linha do tempo mostra vários anos,
mas só 2026 tem aquisição na consulta testada; ao tentar carregar, aparece "Esta cena não
tem bandas RGB suficientes para carregar"; e a lista de resultados, configurada para
Landsat, traz um produto Sentinel-1. O resumo automatizado da 0.13.0 (testes unitários e
`py_compile`) não detectou nenhum desses três problemas — ver por quê na seção de testes
abaixo. **Esta correção não está declarada aprovada** até o usuário confirmar no QGIS que
consegue consultar e carregar imagens ópticas reais de anos diferentes.

## Diagnóstico (Etapa 1) — causa raiz confirmada contra o serviço real

Confirmado HEAD `f802a5c` (0.13.0), árvore limpa, releases `v0.7.0` a `v0.13.0`
preservados; ZIP e relatório da 0.13.0 intactos.

Em vez de presumir a causa pela leitura do código, reproduzi a consulta real feita pelo
plugin direto contra `https://earth-search.aws.element84.com/v1/search` (`curl`, mesmo
corpo JSON que `stac_client.build_search_body` monta):

**Causa raiz 1 — "só 2026 tem aquisição" é falta de paginação, não um problema na linha
do tempo.** Consulta de teste: `collections=["landsat-c2-l2"]`, bbox rural real, período
de 5 anos, `limit=30` (o valor usado pelo código da 0.13.0). A resposta real devolveu
exatamente 30 cenas — **todas de 2026** — porque o catálogo ordena por data decrescente e
o código nunca pedia a página seguinte. Aumentando o `limit`, a resposta real confirmou
`"context": {"matched": 327...}` só para essa área (uma propriedade rural típica tem
dezenas de cenas Landsat por ano, com 2 satélites e revisita de 16 dias cada) — e seguindo
o token de paginação (`links[rel=next].body.next`) a consulta real continuou trazendo
páginas cheias de 100 itens, confirmando que o catálogo tinha muito mais do que uma
página de resultados no período pedido. `imagery_bridge.SearchRequest` (0.13.0) buscava
só a primeira página — daí "só o ano atual aparece disponível".

**Causa raiz 2 — Sentinel-1 rotulado como Landsat.** Fiz a mesma consulta real **sem** o
filtro `collections` (simulando uma resposta "contaminada", para testar a hipótese) e
confirmei que o catálogo devolve, sem esse filtro, uma mistura real de
`sentinel-2-l2a`/`sentinel-2-c1-l2a`/`sentinel-2-l1c`/**`sentinel-1-grd`**/`landsat-c2-l2`
ordenada só por data. Isso mostrou que o servidor real inclui Sentinel-1 nos resultados
quando a filtragem por coleção não é aplicada com sucesso. Auditando
`stac_client._parse_feature` (0.13.0), confirmei o defeito: a função **nunca lia**
`feature["collection"]` da resposta — rotulava toda cena encontrada com o provedor e a
coleção **pedidos na consulta**, cegamente. Ou seja: se, por qualquer motivo de
transporte (o suspeito mais provável é um arquivo de cache em disco gravado antes desta
auditoria, já que o `cache_imagens` persiste indefinidamente entre sessões e versões,
com TTL de 6h só na leitura — não há como reconstruir com certeza absoluta qual consulta
específica gerou esse arquivo), uma resposta contaminada chegasse ao parser, ela seria
apresentada como se fosse Landsat de verdade. Sentinel-1 é radar (bandas `vv`/`vh`, sem
RGB óptico) — daí "esta cena não tem bandas RGB suficientes para carregar" ao tentar
carregá-la.

**Por que os testes automatizados da 0.13.0 não pegaram isso:** os testes de paginação e
de validação de coleção simplesmente não existiam — a 0.13.0 corrigiu cobertura/NoData/
contraste/extensão geográfica (problemas genuínos, mantidos corrigidos), mas não cobriu
"a busca só traz uma página" nem "a resposta pode vir com uma coleção diferente da
pedida", porque nenhuma dessas hipóteses tinha sido considerada até o teste manual do
usuário revelar o sintoma. `python -m unittest`/`py_compile` confirmam que o código
compila e que a lógica testada funciona como escrita — não que a busca de verdade reflita
o catálogo real inteiro nem que a resposta nunca venha de outra coleção; só o teste
manual (ou, como fiz aqui, uma chamada real ao serviço) expõe isso.

## Correções implementadas

**Paginação real (Etapas 1, 3, 4)**
- `stac_client.build_search_body(..., next_token=None)`: inclui `"next"` no corpo quando
  informado — mesmo formato confirmado contra o serviço real.
- `stac_client.extract_next_token(data)`: lê o link `rel == "next"` da resposta.
- `stac_client.should_fetch_next_page(data, page_limit, pages_fetched, max_pages)`: só
  continua se a página atual veio **cheia**, houver token, e o teto de páginas não tiver
  sido atingido — nunca pagina sem limite.
- `imagery_bridge.SearchRequest` agora encadeia páginas (100 itens/página, até 10
  páginas = 1000 cenas/busca) dentro da mesma consulta assíncrona/cancelável de antes;
  acumula e deduplica o resultado final antes de emitir `finished` e gravar o cache.

**Validação de coleção/sensor (Etapas 1, 2, 5)**
- `stac_client._parse_feature` agora lê `feature["collection"]` de verdade e **descarta**
  (devolve `None`, mesmo tratamento de "item malformado" já existente) qualquer cena cuja
  coleção real não bata com a esperada para o provedor pedido — nunca mais rotula um
  produto de outro sensor como se fosse da fonte certa.
- `imagery_bridge.load_scene` repete a mesma conferência (defesa em profundidade) antes
  de montar qualquer composição RGB, para o caso de um objeto `scene` chegar até o
  carregamento por outro caminho que não a busca normal.
- Catálogos que não preenchem `collection` no item (campo opcional no STAC — não é o caso
  do Earth Search, mas o código não assume isso) continuam aceitos sem essa validação,
  já que não há o que contradizer.

**Cache versionado (Etapas 1, 3, 4, 6)**
- `imagery_cache.CACHE_SCHEMA_VERSION = 2`: muda a chave de cache. Qualquer arquivo em
  disco gravado por uma versão anterior (0.13.0 ou antes — potencialmente incompleto por
  não paginar, e no limite contaminado) deixa de ser encontrado e uma busca nova e
  correta é sempre feita, sem precisar o usuário apagar nada manualmente.

## Arquivos modificados

`stac_client.py`, `imagery_bridge.py`, `imagery_cache.py`, `LEIAME.md`,
`tests/test_stac_client.py`, `tests/test_imagery_cache.py`, `tests/test_imagery_timeline.py`,
`metadata.txt`. Nenhum arquivo das fases A–E (desenho, pastas, KML, régua) foi alterado.

## Testes automatizados executados e resultados

`python -m unittest discover -s tests` → **174/174 testes passaram** (161 da 0.13.0 + 13
novos):

- `build_search_body` inclui/omite `next` corretamente conforme o token.
- `extract_next_token`: presente, ausente, resposta sem `links`/não-dict não quebra.
- `should_fetch_next_page`: página cheia + token → continua; página incompleta → para
  mesmo com token (a resposta real do catálogo às vezes mantém o link "next" além do fim,
  então o tamanho da página é o sinal definitivo, não só a presença do link); sem token →
  para; teto de páginas atingido → para.
- **Reprodução exata do bug relatado:** uma cena com `collection="sentinel-1-grd"`
  misturada a uma cena Landsat genuína, buscadas com `provider_key="landsat"` → só a
  Landsat sobrevive ao parse.
- Cena sem campo `collection` não é descartada por falta de informação (só por
  contradição).
- Cache: a chave agora começa com `v{CACHE_SCHEMA_VERSION}|` (sentinela: se uma correção
  futura mudar o formato do resultado cacheado sem lembrar de subir essa versão, este
  teste continua passando com a versão atual, mas serve de lembrete explícito no código).
- `imagery_timeline.build_year_track` com várias aquisições reais em anos diferentes
  (2021, 2023, 2026) — todos aparecem disponíveis, com a contagem certa; os anos sem
  nenhuma aquisição no meio continuam marcados como indisponíveis.

`python -m py_compile` nos 29 módulos `.py` do plugin → sem erro de sintaxe.

**Verificação contra o serviço real feita nesta auditoria (não presumida):** diferente
das fases anteriores, esta rodada incluiu chamadas HTTP reais ao Earth Search
(`earth-search.aws.element84.com`) durante o diagnóstico, para confirmar a causa raiz
antes de escrever qualquer linha de código — não só para validar o formato de resposta,
mas para reproduzir o comportamento exato relatado (resposta sem filtro de coleção
realmente mistura Sentinel-1; a página 1 de uma busca de 5 anos realmente só traz o ano
atual). Isso não substitui a validação manual no QGIS listada abaixo: confirma a causa,
não que a interface se comporte corretamente de ponta a ponta.

**O que não pôde ser automatizado:** o encadeamento real de páginas via
`QNetworkAccessManager` (`imagery_bridge.SearchRequest`), a leitura remota do raster e a
interface (`dlg_imagery.py`) dependem do PyQGIS, indisponível neste shell — mesma
limitação de todas as fases anteriores.

## Teste de regressão

Reexecutados, todos passando: `test_geometry_rules.py`, `test_measure_rules.py`,
`test_folder_rules.py`, `test_kml_io.py`, `test_export_rules.py`,
`test_imagery_timeline.py` (módulo da correção anterior, comportamento preservado).
Nenhuma regressão.

## Roteiro de validação manual no QGIS 3.44.15 (nenhum executado até agora)

Esta correção **não está aprovada** até os passos abaixo serem confirmados.

1. Abrir uma área rural conhecida no mapa.
2. Abrir "Imagens de satélite", escolher **Landsat**, período de alguns anos, buscar.
3. Confirmar que a lista/linha do tempo mostra **só** produtos Landsat (checar o rótulo
   "Fonte" no painel de metadados de cada aquisição) — nenhum Sentinel-1/Sentinel-2.
4. Repetir com **Sentinel-2** e confirmar que só aparecem produtos Sentinel-2 ópticos.
5. Confirmar que a linha do tempo agora mostra **mais de um ano** com aquisição
   disponível (não só o ano atual) — testar com um período de pelo menos 3-5 anos.
6. Selecionar um ano antigo (não o mais recente) e confirmar que aparecem aquisições
   reais daquele ano, não uma lista vazia nem um erro.
7. Carregar uma imagem de pelo menos **dois anos diferentes** e confirmar que ambas
   aparecem na área correta, sem o erro "não tem bandas RGB suficientes".
8. Verificar data, fonte, sensor e cobertura de cada uma na janela.
9. Se algum ano específico não tiver aquisição real disponível na área testada, registrar
   isso explicitamente no retorno ao usuário — não é um defeito, é a cobertura real do
   catálogo para aquela área/sensor/período.
10. Simular falha de conexão (desligar a internet) durante uma busca e confirmar que a
    última imagem válida carregada continua visível, com aviso claro do erro.
11. Repetir os testes essenciais das fases A-D (desenho, pastas, KML) para confirmar
    ausência de regressão.

## Problemas conhecidos / limitações deliberadas

- Teto de 1000 cenas por busca (10 páginas de 100): se o período pesquisado tiver mais do
  que isso numa única área, as aquisições mais antigas ficam de fora dessa busca
  específica (registrado no painel de mensagens do QGIS); o usuário pode restringir o
  período para cobrir trechos mais antigos especificamente.
- A causa exata de como uma cena de outra coleção chegou a ser rotulada incorretamente
  numa sessão real do usuário (qual cache específico, de qual teste anterior) não pôde
  ser reconstruída com certeza; a correção (validação de coleção + cache versionado)
  elimina o sintoma de forma robusta independentemente da causa de transporte exata.
- Mesma limitação de todas as fases anteriores: validação de comportamento real no QGIS
  não foi possível nesta máquina (sem PyQGIS neste shell) — ver roteiro manual acima.

## Commit Git de referência

`b749c48` — "Versao 0.13.1: changelog da correcao de paginacao e colecao" — HEAD no
momento da geração deste pacote, árvore de trabalho limpa. Commits desta correção:
`684e0c7` (paginação + validação de coleção + cache versionado), `b749c48` (versão).

## Caminho completo do ZIP

`C:\Users\Usuário\Desktop\ferramentas_terra\releases\v0.13.1\earth_tools_v0.13.1.zip`

## Confirmação de estrutura do pacote

- Integridade do ZIP (`zipfile.testzip()`): OK.
- Raiz única `earth_tools/`, sem pasta duplicada. 43 entradas (mesmo conjunto da 0.13.0).
- Sem `.git`, `.gitignore`, `__pycache__`, `.pyc`, `tests/` ou `.gpkg`.
- `earth_tools/metadata.txt`: `version=0.13.1`.
- `releases/v0.7.0/` a `v0.13.0/` confirmados intactos, nenhum arquivo sobrescrito.
