# Relatório da versão 0.12.0 — Ferramentas Terra

**Data de geração:** 2026-10-24.

## Confirmação recebida sobre a versão anterior (0.11.1)

O usuário validou manualmente a 0.11.1 no QGIS 3.44.15, incluindo a correção da
exportação KML/KMZ, antes de iniciar esta fase.

## Auditoria e proposta técnica (antes de implementar)

Confirmado HEAD `aff90e7` (0.11.1), árvore limpa, releases `v0.7.0` a `v0.11.1`
preservados.

**Verificação de rede real, não presumida:** este ambiente de desenvolvimento tinha
acesso à internet, então testei de fato (não só pela documentação) a API STAC pública
Earth Search (`https://earth-search.aws.element84.com/v1`), da Element84, hospedada no
Programa de Dados Abertos da AWS:
- Busca anônima funciona sem chave de API (`POST /search`).
- Coleções confirmadas: `sentinel-2-l2a` (Sentinel-2 Nível 2A) e `landsat-c2-l2`
  (Landsat Coleção 2 Nível 2).
- Resultado vazio devolve HTTP 200 com `"features": []` - não é um erro.
- `bbox` inválido devolve HTTP 400 com corpo JSON de erro.
- O asset `visual` do Sentinel-2 é um COG (GeoTIFF otimizado para nuvem) RGB pronto,
  hospedado publicamente em S3, acessível via `/vsicurl/` sem baixar o arquivo inteiro.
- Landsat não tem um asset RGB único - só bandas separadas (`red`, `green`, `blue`).
- `datetime` (aquisição) e `created` (processamento/publicação) são campos distintos e
  realmente diferentes entre si nos dados reais.
- O campo `license` do catálogo diz `"proprietary"` - confirmei que é um valor-padrão do
  catálogo do Element84, **não** a licença real dos dados (Sentinel-2 é Copernicus/ESA
  aberto; Landsat Coleção 2 é domínio público USGS/NASA) - documentado para não repassar
  essa imprecisão ao usuário.

**Alternativas avaliadas e descartadas** (por exigirem autenticação/credenciais, contra
"solução mais simples" e contra "não armazenar credenciais em texto aberto"): Copernicus
Data Space Ecosystem (OAuth2), Microsoft Planetary Computer (assinatura de URL por
asset), USGS EarthExplorer/M2M (conta registrada), Google Earth Engine (conta de
serviço). Earth Search foi o único testado que funciona sem nenhuma credencial.

## Resumo das funcionalidades implementadas

**E1 — Fontes de imagens**
- Busca por área (extensão atual do mapa ou feição selecionada, convertida para WGS84)
  e intervalo de datas, em Sentinel-2 ou Landsat.
- Lista mostra data de aquisição, data de publicação do produto, satélite, resolução
  espacial e cobertura de nuvens - "Não informado" quando a fonte não traz o dado.
- "Carregar no mapa": Sentinel-2 usa o COG `visual` direto; Landsat compõe as 3 bandas
  via `gdal.BuildVRT` (não XML escrito à mão - precisa do georreferenciamento real de
  cada banda, lido do cabeçalho remoto via `/vsicurl/`, sem baixar o arquivo completo).
- Trata resultado vazio, resposta inválida e falha de conexão com mensagens distintas.
- Nunca toca no GeoPackage de lugares nem em geometrias - só cria camadas raster novas.

**E2 — Histórico temporal**
- Dois "slots" (Anterior/Posterior): carregar uma aquisição em cada, alternar qual fica
  visível sem perder o enquadramento do mapa, com rótulo mostrando a data de cada slot.
- Aviso explícito de que datas diferentes podem ter resolução/nuvens/sensor diferentes -
  não é uma comparação perfeitamente equivalente.
- Comparação lado a lado/slider **não foi implementada**: a janela indica a ferramenta
  nativa de mapa comparativo do próprio QGIS, por decisão explícita de não arriscar a
  estabilidade do mapa principal com uma reimplementação.

**E3 — Qualidade e metadados**
- Metadados mostrados tal como o provedor informa, sem inventar valores ausentes.
- Nenhum filtro ou correção radiométrica aplicado - visualização RGB direta do produto.

**E4 — Cache e robustez**
- Cache só de metadados de busca (JSON pequeno, TTL de 6 horas), nunca das imagens -
  decisão documentada em `imagery_cache.py`. Botão para limpar.
- Consulta assíncrona via `QNetworkAccessManager` (não bloqueia o canvas), cancelável.
- Nenhuma credencial é necessária, então não há nada para guardar com segurança.
- Falha de rede afeta só esta janela - demonstrável pela ausência de qualquer import de
  rede em `maptools.py`/`vertexedit.py`/`storage.py`/`places_model.py`/`kml_io.py`.

## Arquivos modificados/criados

Novos: `stac_client.py`, `imagery_cache.py`, `imagery_bridge.py`, `dlg_imagery.py`,
`icons/imagery.svg`, `tests/test_stac_client.py`, `tests/test_imagery_cache.py`.
Modificados: `earth_tools.py` (botão novo), `LEIAME.md`, `metadata.txt`.

## Testes automatizados executados e resultados

`python -m unittest discover -s tests` → **130/130 testes passaram**: os 88 das fases
anteriores (regressão confirmada) + 42 novos (`test_stac_client.py` e
`test_imagery_cache.py`), usando formatos de resposta confirmados contra o serviço real
durante o desenvolvimento (não inventados):

- Validação de intervalo de datas (início depois do fim, início no futuro, data ausente).
- Validação de `bbox` (fora do intervalo, invertido, número errado de valores).
- Resultado vazio → lista vazia, sem erro.
- Resposta malformada (`features` ausente, não é lista, não é dict) → erro distinto.
- Item individual malformado não derruba a lista inteira.
- Metadado ausente → "Não informado"; nuvem `0.0%` não é tratada como ausente (é um
  valor válido, céu limpo).
- Deduplicação de produtos por id, preservando a primeira ocorrência.
- Classificação de erro HTTP (400 com descrição, 5xx, sem resposta/sem conexão).
- Fonte de cores naturais: Sentinel-2 usa o asset `visual`; Landsat exige as 3 bandas
  (e devolve "sem fonte" se faltar uma).
- Política de cache: mesma chave para pequena variação de enquadramento, chave diferente
  por fonte/período, expiração exata no limite do TTL.

`python -m py_compile` em todos os 30 módulos `.py` → sem erro de sintaxe.

**O que foi testado com mocks, e por que isso não prova que o serviço real funciona:**
os testes de `stac_client.py` usam corpos de resposta fixos, no formato que CONFIRMEI
contra o serviço real durante esta auditoria - mas são, ainda assim, dados fixos em
código, não uma chamada de rede de verdade a cada execução de teste. O próprio Earth
Search pode mudar de formato, ficar indisponível, ou ter seu endereço alterado sem
aviso; nada nos testes automatizados detectaria isso. Só uma consulta real no QGIS (ver
roteiro manual) confirma que o serviço está funcionando agora.

**O que não pôde ser automatizado:** a consulta assíncrona real (`QNetworkAccessManager`,
`QNetworkReply`), o carregamento de camada raster (`QgsRasterLayer`,
`gdal.BuildVRT`), e toda a interface (`dlg_imagery.py`) dependem do PyQGIS, indisponível
neste shell - mesma limitação de todas as fases anteriores.

## Teste de regressão

Reexecutados nesta fase, todos passando: regras geométricas, desfazer/refazer, entrada
numérica, aderência (`test_geometry_rules.py`, `test_measure_rules.py`), pastas e
hierarquia (`test_folder_rules.py`), importação/exportação KML/KMZ
(`test_kml_io.py`, `test_export_rules.py`). Nenhuma regressão.

## Roteiro de validação manual no QGIS 3.44.15 (nenhum executado até agora)

1. Abrir "Imagens de satélite", buscar Sentinel-2 para a extensão atual do mapa num
   período recente (ex.: últimos 90 dias) e confirmar que a lista aparece com datas e
   percentual de nuvens plausíveis.
2. Repetir a busca para Landsat na mesma área/período.
3. Carregar uma cena Sentinel-2 no mapa e confirmar que a imagem aparece corretamente
   georreferenciada, sobre as camadas de lugares já existentes.
4. Carregar uma cena Landsat e confirmar que a composição das 3 bandas aparece em cores
   naturais, não invertida ou deslocada.
5. Buscar um período sem cobertura (ex.: antes de 2015 para Sentinel-2) e confirmar a
   mensagem de "nenhuma aquisição encontrada", distinta de um erro.
6. Desligar a internet e tentar buscar - confirmar a mensagem de falha de conexão, e que
   desenhar/editar/usar a régua/abrir um lugar salvo continua funcionando normalmente.
7. Iniciar uma busca e clicar em "Cancelar consulta" antes de terminar - confirmar que
   não fica nenhuma operação pendente nem mensagem de erro falsa.
8. Carregar uma cena em "Anterior" e outra em "Posterior", alternar as caixas de marcar,
   e confirmar que o enquadramento do mapa não muda.
9. Testar a ferramenta nativa "Mapa comparativo" do QGIS com as duas camadas carregadas,
   para confirmar que a sugestão no `LEIAME.md` funciona na prática.
10. Clicar "Limpar cache de busca" e confirmar que só os arquivos de metadados somem
    (verificar a pasta `cache_imagens` ao lado do `Meus Lugares.gpkg`), sem afetar lugares
    ou camadas carregadas.
11. Reexecutar o roteiro de validação das fases A, B, C e D para confirmar ausência de
    regressão.

## Problemas conhecidos / limitações deliberadas

- Comparação lado a lado com slider não foi implementada; a janela aponta para a
  ferramenta nativa do QGIS.
- O cache cobre só metadados de busca; cada "Carregar no mapa" busca a imagem de novo via
  rede (o GDAL faz seu próprio cache de blocos durante a sessão, fora do controle deste
  plugin).
- Dependência de um serviço gratuito de terceiros sem SLA contratual - documentado,
  não escondido.
- O VRT temporário gerado para composições Landsat fica na pasta temporária do sistema;
  não há limpeza automática ao fechar o plugin (arquivo de texto pequeno, poucos KB).
- Mesma limitação de todas as fases anteriores: validação de comportamento real no QGIS
  não foi possível nesta máquina (sem PyQGIS neste shell).

## Commit Git de referência

`e5473f6` — "Versao 0.12.0: changelog da Fase E" — HEAD no momento da geração deste
pacote, árvore de trabalho limpa.

## Caminho completo do ZIP

`C:\Users\Usuário\Desktop\ferramentas_terra\releases\v0.12.0\earth_tools_v0.12.0.zip`

## Confirmação de estrutura do pacote

- Integridade do ZIP (`zipfile.testzip()`): OK.
- Raiz única `earth_tools/`, sem pasta duplicada.
- 42 entradas, incluindo `stac_client.py`, `imagery_bridge.py`, `imagery_cache.py`,
  `dlg_imagery.py` e `icons/imagery.svg`.
- Sem `.git`, `.gitignore`, `__pycache__`, `.pyc`, `tests/` ou `.gpkg`.
- `earth_tools/__init__.py` contém `def classFactory(iface)`.
- `earth_tools/metadata.txt`: todos os campos obrigatórios, `version=0.12.0`.
- `releases/v0.7.0/` a `v0.11.1/` confirmados intactos, nenhum arquivo sobrescrito.
