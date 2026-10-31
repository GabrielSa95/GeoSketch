# Relatório da versão 0.13.0 — Ferramentas Terra

**Data de geração:** 2026-10-25.

## Confirmação recebida sobre a versão anterior (0.12.0)

O usuário testou a 0.12.0 no QGIS 3.44.15 e relatou três problemas: imagens históricas
que não aparecem corretamente na área visualizada, imagens inteiramente cinzas, e
navegação pouco prática entre anos/aquisições — além de pedir uma linha do tempo anual
obrigatória e a simplificação da barra (import/export KML/KMZ para o menu de contexto
das pastas). Esta fase corrige esses problemas; **não foi declarada aprovada** até o
usuário confirmar no QGIS que a linha do tempo funciona com aquisições reais e que as
imagens aparecem corretamente (ver roteiro de validação manual no final deste relatório).

## Etapa 1 — Auditoria e causa raiz (antes de implementar)

Confirmado HEAD `e5473f6` (0.12.0), árvore limpa, releases `v0.7.0` a `v0.12.0`
preservados; ZIP e relatório da 0.12.0 intactos.

**Causa raiz 1 — "imagem não aparece na área atual" e "imagem cinza" têm a mesma
origem:** `stac_client.build_search_body`/`parse_search_response` e
`imagery_bridge.load_scene` nunca verificavam se a cena encontrada **cobre de fato** a
área pesquisada. A consulta STAC filtra por *intersecção* de bbox, não por contenção —
uma cena cujo retângulo apenas toca um canto da área visível já era "encontrada" e podia
ser carregada. O usuário via, na maior parte da tela, a área **fora da extensão real do
raster** (fundo do canvas, cinza-claro por padrão no QGIS) e confundia isso com "a imagem
é cinza" ou "a imagem não apareceu". Confirmado lendo `dlg_imagery.py` (0.12.0) linha a
linha: não existia nenhum cálculo de cobertura antes de popular a lista ou carregar a
cena escolhida.

**Causa raiz 2 — pixel cinza de verdade (Landsat, e Sentinel-2 sem asset `visual`):**
`imagery_bridge.build_landsat_vrt` (0.12.0) montava o VRT com `gdal.BuildVRT(...,
separate=True)` a partir das bandas brutas remotas (DN de reflectância de superfície,
uint16, preenchimento/nodata=0) **sem declarar NoData** e sem nenhum realce de contraste
explícito. `load_scene` criava a `QgsRasterLayer` e adicionava ao projeto sem chamar
nenhum método de contraste. Sem isso, o realce dependia do `QSettings` global do QGIS e
de estatísticas aproximadas que, ao amostrar pixels de preenchimento (valor 0), produzem
um alongamento de contraste ruim — a composição acaba quase monocromática/cinza, mesmo
com dados válidos. O asset Sentinel-2 `visual` (COG 8 bits já pronto) não sofre disso
quando existe — mas nada cobria o caso de não existir.

**Causa raiz 3 — imprecisão na área pesquisada:** `_current_bbox` (0.12.0) convertia só
os dois cantos opostos da extensão do canvas ponto a ponto (`utils.to_wgs84`), em vez de
um retângulo envolvente de verdade — impreciso para CRS projetado (SIRGAS/UTM, o caso
comum deste plugin).

**Causa raiz 4 — navegação:** a janela 0.12.0 era uma lista cronológica única, sem
agrupar por ano, sem avançar/voltar entre aquisições do mesmo ano, e cada "Carregar no
mapa" empilhava uma camada raster nova em vez de substituir a anterior.

**Causa raiz 5 — menu de contexto de pastas:** o próprio código (`dlg_export_kml.py`,
`layeractions.py`, fase D) documentava que `QgsLayerTreeView.setMenuProvider()` havia
sido evitado por derrubar o QGIS. Confirmado agora, contra a documentação oficial PyQGIS
3.44 (`qgis.org/pyqgis/3.44/gui/QgsLayerTreeView.html`) e um relato real de uso em
plugins (`github.com/Mirjan-Ali-Sha/export2kml`), que existe desde o QGIS 3.32 o sinal
`QgsLayerTreeView.contextMenuAboutToShow(menu)`, que só **acrescenta** itens ao menu que
o QGIS continua controlando — sem o risco documentado. Como `qgisMinimumVersion` deste
plugin é 3.22, a conexão é best-effort (try/except).

**Verificação de API feita durante a implementação, não presumida:** o nome do método
usado para aplicar o realce de contraste foi confirmado por busca na documentação oficial
(`api.qgis.org`) **antes** de finalizar o código — a primeira tentativa
(`setDefaultContrastEnhancement`) não existe; o método real é
`QgsRasterLayer.setContrastEnhancement(algorithm, limits, extent, sampleSize,
generateLookupTableFlag)`. Corrigido antes de empacotar esta versão.

## Resumo das correções e funcionalidades implementadas

**Cobertura real da cena (Etapa 2)**
- `stac_client.coverage_fraction(query_bbox, scene_bbox)`: fração (0.0–1.0) da área
  pesquisada coberta pela cena; `None` (nunca 0.0) quando a informação está ausente.
- Mostrada na lista de aquisições e no painel de metadados sempre que < 100% — nunca
  escondida, e a cena nunca é removida da lista por cobertura baixa (decisão do usuário).

**Correção da imagem cinza (Etapa 4)**
- `imagery_bridge.build_band_vrt` (renomeada de `build_landsat_vrt`, agora usada também
  pelo fallback do Sentinel-2) declara `VRTNodata="0"` no `gdal.BuildVRTOptions`.
- `load_scene` aplica `QgsRasterLayer.setContrastEnhancement(StretchToMinimumMaximum,
  CumulativeCut)` nas composições de banda (não no asset `visual`, que já vem em 8 bits
  pronto) — o mesmo corte 2%–98% que o usuário faria manualmente em Propriedades > Estilo.
- `stac_client.PROVIDERS["sentinel2"]["rgb_bands"]` acrescentado: quando a cena não tiver
  o asset `visual`, cai no mesmo caminho de composição de 3 bandas do Landsat, em vez de
  simplesmente não oferecer nada para carregar.

**Precisão da área pesquisada (Etapa 2)**
- `dlg_imagery._current_bbox` passa a usar
  `QgsCoordinateTransform.transformBoundingBox(extent)` em vez de converter só os dois
  cantos opostos — correto para CRS projetado.

**Linha do tempo anual (Etapa 3, obrigatória)**
- Módulo novo `imagery_timeline.py` (puro, sem PyQGIS): `years_in_range`,
  `years_with_scenes`, `build_year_track`, `scenes_for_year`, `nearest_year_with_scenes`,
  `adjacent_scene`.
- `dlg_imagery.py` reorganizado (mesma janela, não uma nova): trilha horizontal de anos
  do período pesquisado — anos **sem** aquisição ficam visíveis e desabilitados (nunca
  escondidos, para não sugerir um período menor do que o pesquisado); setas "◀ ano"/
  "ano ▶" pulam direto para o próximo ano *com* dado, mesmo com vários anos vazios entre
  um e outro; dentro do ano, lista cronológica com setas "◀ aquisição"/"aquisição ▶" que
  avançam sem voltar à busca, inclusive cruzando para o ano vizinho na ponta da lista.
- Selecionar um ano carrega automaticamente a aquisição mais recente dele no mapa.

**Atualização segura da imagem no mapa (Etapa 3.3)**
- `self.current_layer` rastreia a imagem "principal" (fora dos slots de comparação A/B);
  a camada antiga só é removida **depois** de a nova (`layer.isValid()`) ser confirmada —
  antes, cada clique empilhava uma camada nova sem nunca remover a anterior.
- Enquadramento do canvas salvo antes e restaurado depois de carregar, para nunca saltar.
- Rótulo em negrito mostra a data **efetivamente carregada**, não só a selecionada.
- Falha ao carregar preserva a última imagem válida e avisa o erro, sem apagar nada.

**Descarte de resposta antiga (Etapa 3.3/3.4)**
- `dlg_imagery._do_search` desconecta e cancela a `SearchRequest` anterior antes de
  criar uma nova, e confere um token de geração no callback — uma resposta atrasada de
  uma busca já substituída nunca sobrescreve a lista de uma busca mais nova.
- Busca só roda ao clicar em "Buscar / atualizar nesta área" — mover o mapa não refaz a
  consulta por conta própria (preserva a política de cache de `imagery_cache.py`).

**Menu de contexto de pastas e barra mais curta (Etapa 5)**
- `layeractions.py`: `QgsLayerTreeView.contextMenuAboutToShow` (best-effort) acrescenta,
  quando o item clicado é uma pasta rastreada pelo plugin: "Importar KML/KMZ para esta
  pasta...", "Exportar esta pasta para KML/KMZ..." e, se a pasta pertencer a um Modelo de
  propriedade rural, "Exportar propriedade completa..." (via
  `folder_rules.find_property_root`, novo, sobe a cadeia de `pai_id` até achar a
  pasta-mãe `modelo == "propriedade_rural"`).
- `earth_tools.py`: os botões "Importar KML/KMZ..." e "Exportar pasta para KML/KMZ..."
  saem da barra (`_add_menu_only`), continuam só no menu Vetor > Ferramentas Terra.
- `dlg_import_kml.py`/`dlg_export_kml.py`: `preselect_folder_id` reaproveita 100% da
  lógica existente (inclusive a correção de exportação da 0.11.1) para os dois caminhos
  de entrada, sem duplicar código.

## Arquivos modificados/criados

Novos: `imagery_timeline.py`, `tests/test_imagery_timeline.py`.
Modificados: `stac_client.py`, `imagery_bridge.py`, `dlg_imagery.py`, `folder_rules.py`,
`places_model.py`, `layeractions.py`, `earth_tools.py`, `dlg_import_kml.py`,
`dlg_export_kml.py`, `tests/test_stac_client.py`, `tests/test_folder_rules.py`,
`LEIAME.md`, `metadata.txt`.

## Testes automatizados executados e resultados

`python -m unittest discover -s tests` → **161/161 testes passaram**: os 130 das fases
anteriores (regressão confirmada) + 31 novos:

- `coverage_fraction`: cobertura total, parcial (fração exata calculada), zero (sem
  intersecção), bbox ausente (devolve `None`, nunca `0.0`), bbox degenerado.
- `true_color_source`: Sentinel-2 sem asset `visual` cai para bandas separadas; sem
  `visual` e sem bandas devolve "sem fonte" (não finge uma composição).
- `imagery_timeline`: todo ano do período aparece na trilha mesmo sem aquisição (sem
  fingir disponibilidade); cena sem data é ignorada; ordenação cronológica crescente
  dentro do ano; navegação entre anos pulando lacunas longas (e `None` quando não há
  mais nenhum nessa direção); aquisição adjacente nas duas pontas da lista e com id
  desconhecido; direção inválida levanta erro em vez de silenciar.
- `folder_rules.find_property_root`: acha a raiz a partir de subpasta rasa e profunda,
  pasta já é a raiz, pasta fora de qualquer propriedade, id desconhecido, ciclo (não
  trava, devolve `None`).

`python -m py_compile` nos 29 módulos `.py` do plugin (raiz de `earth_tools/`) → sem
erro de sintaxe, incluindo depois da correção do nome real do método de contraste.

**O que foi testado com mocks, e por que isso não prova que o serviço/QGIS real
funciona:** os testes de `stac_client.py`/`imagery_timeline.py`/`folder_rules.py` usam
dados fixos em código (ainda que no formato confirmado contra o serviço real nas fases
anteriores) — não chamam a rede nem o QGIS. Nenhum teste automatizado comprova que:
- o serviço Earth Search continua respondendo no formato esperado agora;
- uma cena remota real é lida corretamente pelo GDAL via `/vsicurl/`;
- `setContrastEnhancement`/`VRTNodata` de fato eliminam a imagem cinza visualmente;
- a linha do tempo, os botões de navegação e o menu de contexto da pasta funcionam de
  verdade na interface do QGIS.

**O que não pôde ser automatizado (mesma limitação de todas as fases anteriores):**
`dlg_imagery.py`, `imagery_bridge.py`, `layeractions.py`, `earth_tools.py` dependem do
PyQGIS, indisponível neste shell — só o roteiro manual abaixo confirma o comportamento
real.

## Teste de regressão

Reexecutados nesta fase, todos passando: regras geométricas e desfazer/refazer
(`test_geometry_rules.py`), régua/unidades (`test_measure_rules.py`), hierarquia de
pastas (`test_folder_rules.py`, agora com `find_property_root`), KML/KMZ (`test_kml_io.py`,
`test_export_rules.py`), cache de metadados de imagem (`test_imagery_cache.py`, sem
mudança de regra). Nenhuma regressão.

## Roteiro de validação manual no QGIS 3.44.15 (nenhum executado até agora)

Esta fase **não está aprovada** até os passos abaixo serem confirmados pelo usuário.

1. Abrir uma propriedade rural já salva (ou criar um Modelo de propriedade rural) e
   centralizar o mapa sobre ela.
2. Abrir "Imagens de satélite", escolher Sentinel-2, período de alguns anos, e clicar em
   "Buscar / atualizar nesta área".
3. Confirmar que a trilha de anos aparece, com os anos sem aquisição visíveis mas
   desabilitados (não escondidos).
4. Clicar num ano antigo (ex.: 2017 ou 2018) e confirmar que a lista de aquisições
   daquele ano aparece, ordenada por data, e que uma imagem carrega automaticamente.
5. Escolher uma aquisição específica na lista e clicar em "Carregar no mapa"; confirmar
   que a imagem aparece **na localização correta** (sobre a propriedade, não deslocada)
   e que o rótulo "Mostrando: ..." tem a data certa.
6. Confirmar que a imagem **não aparece cinza** — nem a do asset `visual` do Sentinel-2,
   nem uma composição de bandas (testar também com Landsat).
7. Usar "◀ aquisição anterior"/"aquisição seguinte ▶" para avançar e retroceder sem
   voltar à tela de busca; confirmar que a imagem no mapa muda a cada clique.
8. Trocar de ano pelas setas "◀ ano"/"ano ▶" e confirmar que a imagem no mapa é
   efetivamente atualizada (não só o texto do rótulo).
9. Deslocar o mapa para outra área e clicar em "Buscar / atualizar nesta área"
   novamente; confirmar que a trilha de anos e a lista são recalculadas para a nova área
   (não reaproveitam o resultado da área anterior).
10. Carregar uma aquisição em "Anterior" e outra em "Posterior" (Comparar duas datas);
    alternar as caixas de marcar e confirmar que o enquadramento não muda.
11. Testar a ferramenta nativa "Mapa comparativo" do QGIS com as duas camadas carregadas.
12. Desligar a internet e clicar em "Buscar / atualizar nesta área": confirmar a
    mensagem de falha de conexão.
13. Com uma imagem já carregada, simular uma falha (ex.: desligar a internet e tentar
    carregar outra aquisição): confirmar que a imagem anterior continua visível e que
    aparece um aviso claro, em vez de uma tela vazia ou travada.
14. Botão direito numa pasta no painel Camadas: confirmar "Importar KML/KMZ para esta
    pasta..." e "Exportar esta pasta para KML/KMZ..." (e "Exportar propriedade
    completa..." se a pasta for parte de um Modelo de propriedade rural); confirmar que
    a pasta já vem selecionada/travada na janela que abre.
15. Confirmar que os botões de Importar/Exportar KML/KMZ não aparecem mais na barra
    principal, mas continuam em Vetor > Ferramentas Terra.
16. Reexecutar os roteiros essenciais das fases A, B, C e D (desenho, edição com
    Ctrl+Z/Ctrl+Y, régua, pastas, importar/exportar um lugar individual) para confirmar
    ausência de regressão.

## Problemas conhecidos / limitações deliberadas

- A cobertura da cena é calculada sobre o *bbox* da cena informado pelo catálogo STAC,
  não sobre a máscara de pixels válidos de verdade — uma cena pode ter bbox cobrindo
  100% da área e ainda ter nuvens/nodata reais dentro dela; o aviso de nuvens (já
  existente desde a Fase E) continua sendo o indicador para isso, não a cobertura.
- `setContrastEnhancement` com `CumulativeCut` é uma aproximação geral de bom senso (o
  mesmo que o QGIS sugere por padrão); não é uma calibração radiométrica cientificamente
  precisa cena a cena.
- Comparação lado a lado com slider continua não implementada (mesma decisão da Fase E):
  a janela aponta para a ferramenta nativa do QGIS.
- `QgsLayerTreeView.contextMenuAboutToShow` exige QGIS ≥ 3.32; em instalações entre 3.22
  e 3.31, o menu de contexto da pasta não ganha os itens novos (conexão best-effort,
  documentado) — o menu Vetor > Ferramentas Terra continua funcionando em qualquer
  versão suportada.
- Mesma limitação de todas as fases anteriores: validação de comportamento real no QGIS
  não foi possível nesta máquina (sem PyQGIS neste shell) — ver roteiro manual acima.

## Commit Git de referência

`f802a5c` — "Versao 0.13.0: changelog da Fase F" — HEAD no momento da geração deste
pacote, árvore de trabalho limpa. Commits desta fase, em ordem:
`929d562` (causa raiz/correções de núcleo), `d703a23` (linha do tempo na interface),
`4bbe297` (menu de contexto de pastas + barra), `b013e3c` (LEIAME.md), `f802a5c` (versão).

## Caminho completo do ZIP

`C:\Users\Usuário\Desktop\ferramentas_terra\releases\v0.13.0\earth_tools_v0.13.0.zip`

## Confirmação de estrutura do pacote

- Integridade do ZIP (`zipfile.testzip()`): OK.
- Raiz única `earth_tools/`, sem pasta duplicada.
- 43 entradas, incluindo `imagery_timeline.py` (novo) e os módulos corrigidos
  (`stac_client.py`, `imagery_bridge.py`, `dlg_imagery.py`, `folder_rules.py`,
  `places_model.py`, `layeractions.py`, `earth_tools.py`).
- Sem `.git`, `.gitignore`, `__pycache__`, `.pyc`, `tests/` ou `.gpkg`.
- `earth_tools/__init__.py` contém `def classFactory(iface)`.
- `earth_tools/metadata.txt`: todos os campos obrigatórios, `version=0.13.0`.
- `releases/v0.7.0/` a `v0.12.0/` confirmados intactos, nenhum arquivo sobrescrito.
