# Relatório da versão 0.11.0 — Ferramentas Terra

**Data de geração:** 2026-10-24.

## Confirmação recebida sobre a versão anterior (0.10.0)

O usuário confirmou validação manual real no QGIS 3.44.15 para a 0.10.0, com as fases
anteriores aprovadas, antes de iniciar esta fase.

## Auditoria prévia (preparação obrigatória)

- **Armazenamento:** confirmado que cada lugar é uma tabela própria no GeoPackage,
  geometria sempre em EPSG:4326 — o MESMO CRS que o KML usa por especificação, então a
  importação não precisa de nenhuma transformação de coordenadas.
- **Pastas:** confirmado que a Fase B já tem uma hierarquia canônica própria
  (`places_model.py`, guardada no GeoPackage, não na árvore de camadas) — a importação
  KML liga diretamente nela (`places_model.create_folder`/`set_place_folder`) em vez de
  inventar um mecanismo de pasta paralelo.
- **Exportação existente:** só havia "Salvar lugar como..."/"Enviar por e-mail...", uma
  feição por vez, via driver genérico do GDAL (`QgsVectorFileWriter`). Não preservava
  estilo/descrição de forma garantida em KML. Não havia nenhuma importação.
- **Decisão de arquitetura:** implementar um leitor/escritor KML/KMZ próprio
  (`kml_io.py`, sem nenhuma dependência de QGIS) em vez de usar o driver OGR "KML"/
  "LIBKML" do GDAL — motivo: precisão sobre hierarquia de pastas (o driver OGR trata cada
  `Folder` como camada separada) e sobre estilo (cor KML em formato `aabbggrr`; suporte
  do LIBKML depende de como o GDAL foi compilado, não verificável nesta máquina). Essa
  decisão também tornou a maior parte da lógica desta fase testável sem QGIS.

## Resumo das funcionalidades implementadas

**Importação** (`dlg_import_kml.py` + `kml_bridge.py`)
- Lê `.kml` e `.kmz` (detecção pela assinatura do arquivo, não só pela extensão).
- Marcador, linha, polígono (com anéis internos/buracos), nome, descrição, cor, largura
  e referência de ícone (quando presentes).
- Pastas e subpastas do KML recriadas como pastas canônicas (Fase B) dentro da pasta de
  destino escolhida — só as realmente necessárias para os itens selecionados.
- Lista de seleção com tudo marcado por padrão, exceto itens já importados antes (por
  impressão digital de geometria+nome, não pelo nome do arquivo) — evita duplicar ao
  reimportar o mesmo arquivo, sem bloquear se o usuário quiser forçar.
- Elementos não suportados (`NetworkLink`, sobreposições, etc.) são listados, não travam
  a importação do resto do arquivo.
- `MultiGeometry` gera vários lugares separados (um por parte), nomeados com sufixo
  "(1)", "(2)" — a arquitetura de "uma geometria simples por lugar" não foi alterada.
- Cada item importado é uma chamada independente a `storage.create_place`; uma falha num
  item não afeta os demais nem deixa o GeoPackage num estado parcial.

**Exportação** (`dlg_export_kml.py` + `kml_bridge.py`)
- Uma pasta com subpastas, ou tudo ("propriedade completa"), para `.kml` ou `.kmz`.
- "Salvar lugar como..."/"Enviar por e-mail..." (uma feição) passaram a usar o MESMO
  escritor (`kml_io.build_kml`/`build_kmz`), e "Salvar lugar como..." agora também aceita
  KMZ — preservação de nome/descrição/estilo mais fiel do que o driver genérico GDAL.
- Aviso explícito na janela: não promete equivalência visual completa (ícones
  personalizados e recursos exclusivos do Google Earth não têm garantia).

## Arquivos modificados/criados

Novos: `kml_io.py`, `kml_bridge.py`, `dlg_import_kml.py`, `dlg_export_kml.py`,
`icons/import_kml.svg`, `icons/export_kml.svg`, `tests/test_kml_io.py`.
Modificados: `earth_tools.py` (botões), `layeractions.py` (`_save_as`/`_email` via
escritor próprio), `LEIAME.md`, `metadata.txt`.

## Testes automatizados executados e resultados

`python -m unittest discover -s tests` → **74/74 testes passaram**: os 41 das fases
anteriores (regressão confirmada) + 33 novos em `tests/test_kml_io.py`, cobrindo:
- Conversão de cor KML (`aabbggrr`) nos dois sentidos, incluindo valor inválido/ausente.
- Marcador, linha, polígono com buraco, `MultiGeometry`.
- Coordenada fora do intervalo válido descartada sem travar o parse.
- Placemark sem geometria ignorado.
- Pastas aninhadas, `iter_placemarks`, `count_placemarks`.
- Estilo por `styleUrl`, estilo inline com prioridade, `StyleMap` (par "normal"),
  `icon_href`.
- Elemento não suportado reportado sem travar; XML malformado, KMZ que não é ZIP, KMZ
  sem `.kml` dentro — todos levantando `KmlError` com mensagem específica.
- KMZ com `doc.kml` e assets; detecção de KMZ mesmo com extensão `.kml` errada; arquivo
  vazio.
- Fingerprint: mesma entrada → mesmo hash; nome diferente → hash diferente; ruído de
  ponto flutuante não muda o hash.
- Ciclo completo exportar→reimportar: nome/descrição/coordenada preservados, polígono com
  buraco preservado, pastas aninhadas preservadas, nomes de `MultiGeometry` desambiguados.

`python -m py_compile` em todos os 24 módulos `.py` → sem erro de sintaxe.

**O que não pôde ser automatizado:** tudo que depende de criar uma camada real no
GeoPackage (`kml_bridge.py` importa `qgis.core`), de `QgsVectorFileWriter`, ou de abrir
as janelas `dlg_import_kml.py`/`dlg_export_kml.py` com um arquivo real. A separação entre
`kml_io.py` (puro) e `kml_bridge.py` (QGIS) foi desenhada exatamente para que a maior
parte dos cenários pedidos nesta fase caísse do lado testável — o que restou sem teste
automatizado é mínimo e está listado no roteiro manual abaixo.

## Testes manuais pendentes no QGIS (nenhum executado até agora)

1. Importar um `.kml` real com marcadores (do Google Earth, se disponível) e confirmar
   que aparecem corretamente no painel Camadas.
2. Importar um `.kml`/`.kmz` com linhas e polígonos, incluindo um polígono com buraco.
3. Importar um arquivo com pastas aninhadas e confirmar que a hierarquia aparece correta
   na árvore (via `places_model`/Fase B).
4. Importar um `.kmz` de verdade (gerado pelo Google Earth ou por "Exportar" desta
   própria versão).
5. Reimportar o MESMO arquivo e confirmar que os itens já importados aparecem
   desmarcados por padrão, sem duplicar se você não forçar.
6. Importar um arquivo com nomes duplicados entre si e confirmar que
   `unique_display_name` desambigua (já é código existente, reaproveitado).
7. Tentar importar um arquivo inválido (texto qualquer renomeado para `.kml`) e
   confirmar a mensagem de erro específica.
8. Exportar uma feição individual, uma pasta com subpastas, e "tudo", depois reimportar
   o resultado e comparar nome/descrição/geometria/estilo com o original.
9. Forçar uma falha durante a importação (ex.: GeoPackage aberto por outro programa) e
   confirmar que os demais itens selecionados ainda são importados, com o erro
   registrado em Ver → Painéis → Mensagens de registro.
10. Reexecutar o roteiro de validação das fases anteriores (A, B, C) para confirmar que
    nada regrediu.

## Problemas conhecidos / limitações deliberadas

- Ícones personalizados do KML/KMZ são **reconhecidos e guardados como referência**
  (`icon_href`), mas **não** são aplicados como imagem real do marcador no QGIS nesta
  versão — o marcador continua usando o círculo colorido padrão do plugin. Documentado
  no `LEIAME.md`; não implementado por decisão de escopo (exigiria extrair e gerenciar
  arquivos de imagem do KMZ como camada de símbolo separada).
- `MultiGeometry` sempre é dividido em lugares separados — não existe "um lugar com
  várias partes" na arquitetura atual, e esta fase não a alterou.
- A ordem exata dos lugares dentro de uma pasta, e metadados avançados do KML (tours,
  animações, `gx:Track`) não são preservados — fora do que o plugin representa hoje.
- Mesma limitação já registrada nos relatórios anteriores: não foi possível validar
  carregamento/comportamento real no QGIS nesta máquina (sem PyQGIS no shell).

## Commit Git de referência

`0412f53` — "Versao 0.11.0: changelog da Fase D" — HEAD no momento da geração deste
pacote, árvore de trabalho limpa.

## Caminho completo do ZIP

`C:\Users\Usuário\Desktop\ferramentas_terra\releases\v0.11.0\earth_tools_v0.11.0.zip`

## Confirmação de estrutura do pacote

Validado programaticamente nesta tarefa, com o ZIP gerado primeiro em arquivo temporário
e só movido para `releases/v0.11.0/` depois de passar todas as checagens:
- Integridade do ZIP (`zipfile.testzip()`): OK.
- Raiz única `earth_tools/`, sem pasta duplicada `earth_tools/earth_tools/`.
- 36 entradas, incluindo `kml_io.py`, `kml_bridge.py`, `dlg_import_kml.py`,
  `dlg_export_kml.py` e os dois ícones novos.
- Sem `.git`, `.gitignore`, `__pycache__`, `.pyc`, `tests/` ou qualquer `.gpkg`.
- `earth_tools/__init__.py` contém `def classFactory(iface)`.
- `earth_tools/metadata.txt` contém todos os campos obrigatórios, `version=0.11.0`.
- `releases/v0.7.0/` a `v0.10.0/` confirmados intactos.
