# Relatório da versão 0.17.1 — Ferramentas Terra

**Data de geração:** 2026-10-30.

## Contexto

Ajuste pontual pedido pelo usuário, com instrução explícita de **não modificar nada que
já estava pronto**: na interface real do QGIS, o menu de contexto de uma camada
apresentava cinco (na prática, até seis) entradas de topo separadas, todas rotuladas
"Adicionar", em vez de um único submenu "Adicionar" contendo todas as opções. Pedido:
unificar essas entradas num só submenu, preservando texto, ícone, callback, parâmetros e
ordem de cada opção, sem tocar em mais nada.

## Auditoria — origem dos menus "Adicionar"

Busca por `"Adicionar"` em todo o código-fonte (`grep -rn '"Adicionar"' earth_tools/`)
encontrou uma única origem: `earth_tools/layeractions.py`, dentro de `LayerActions.install()`
(antigas linhas 160–173). O submenu era alimentado por **6 chamadas independentes** à
mesma API do QGIS, cada uma passando a string literal `"Adicionar"` como parâmetro
`menu`:

```python
make("Pasta", "folder.svg", self._new_group, "Adicionar", True)
make("Modelo de propriedade rural", "folder.svg", self._new_property_template, "Adicionar", True)
make("Marcador de local", "placemark.svg", lambda: ..., "Adicionar", True)
make("Caminho", "path.svg", lambda: ..., "Adicionar", True)
make("Poligono", "polygon.svg", lambda: ..., "Adicionar", True)
make("Sobreposicao de imagem", None, self._image_overlay, "Adicionar", True)
```

Cada `make(...)` chama `self.iface.addCustomActionForLayerType(action, "Adicionar", vector, True)`
- ou seja, **6 registros separados na API nativa do QGIS**, todos com o mesmo texto de
submenu. A API não garante (e, pela interface real observada pelo usuário, não cumpriu)
mesclar automaticamente múltiplos registros com o mesmo nome de `menu` num único
submenu - cada chamada passou a gerar sua própria entrada de topo "Adicionar". Esta é a
única origem de todas as entradas "Adicionar" na interface; nenhum outro arquivo registra
algo com esse nome (confirmado por busca em todo o projeto).

## Ações agrupadas (nenhuma criada, nenhuma removida)

| Ordem | Texto | Ícone | Callback |
|---|---|---|---|
| 1 | Pasta | `folder.svg` | `self._new_group` |
| 2 | Modelo de propriedade rural | `folder.svg` | `self._new_property_template` |
| 3 | Marcador de local | `placemark.svg` | `lambda: self.plugin.open_feature("point", self._current_group())` |
| 4 | Caminho | `path.svg` | `lambda: self.plugin.open_feature("line", self._current_group())` |
| 5 | Poligono | `polygon.svg` | `lambda: self.plugin.open_feature("polygon", self._current_group())` |
| 6 | Sobreposicao de imagem | (nenhum) | `self._image_overlay` |

Exatamente as mesmas 6 opções, mesma ordem, mesmo ícone, mesmo callback, mesmos
parâmetros (ex.: `self._current_group()` continua sendo lido no momento do clique, não
mudou de comportamento).

## Correção aplicada

Um único `QMenu("Adicionar", window)` é criado; as 6 ações são adicionadas a ele
diretamente via `QMenu.addAction()` (API nativa do Qt, não a de agrupamento por nome do
QGIS). Só o `QAction` do próprio menu (`QMenu.menuAction()`) é registrado no QGIS, com
`menu=""` (raiz do menu de contexto) - o Qt desenha a seta de submenu automaticamente
porque esse `QAction` tem um `QMenu` associado. Isso elimina a dependência do
comportamento (não garantido) de agrupamento por nome de string da API do QGIS: agora há
estruturalmente **um único objeto de menu**, não 6 registros que precisam ser mesclados
por terceiros.

`all_layers=True` foi preservado (continua aparecendo em qualquer camada vetorial do
projeto, como antes).

## Arquivos modificados

- `earth_tools/layeractions.py` — único arquivo de código alterado: import de `QMenu`,
  atributo `self._add_menu` (inicializado em `__init__`, limpo em `uninstall()`), bloco
  de registro do submenu "Adicionar" reescrito.
- `earth_tools/metadata.txt` — versão 0.17.1 + changelog.
- `earth_tools/tests/test_regression_static.py` — 4 testes novos (`SubmenuAdicionarUnificadoTests`).
- `CHANGELOG.md` — entrada 0.17.1.

**Nenhum outro arquivo foi tocado.** Em particular: nenhuma mudança em geoprocessamento,
medições, validação, estilos, exportação, armazenamento/GeoPackage, ícones existentes,
barra de ferramentas, ou no submenu "Ferramentas Terra" categorizado introduzido na
0.17.0.

## Testes executados

```
python -m unittest discover -s tests -p "test_*.py"
Ran 186 tests in 0.032s
OK (skipped=1)
```

182 testes pré-existentes (161 anteriores à 0.17.0 + 21 da 0.17.0) continuam passando sem
nenhuma alteração - confirma que nada além do bloco "Adicionar" foi afetado. 4 testes
novos cobrindo especificamente esta correção:

1. `test_addcustomactionforlayertype_chamado_uma_unica_vez_para_adicionar` - trava que a
   string `"Adicionar", True)` (assinatura das 6 chamadas antigas) não existe mais, e que
   o novo registro único existe.
2. `test_as_6_acoes_sao_filhas_diretas_do_qmenu_nao_da_api_do_qgis` - trava que há
   exatamente 1 `QMenu.addAction()` chamado 6 vezes (uma por ação).
3. `test_nenhuma_das_6_acoes_antigas_foi_removida_mesmo_texto_icone_callback` - trava
   texto/ícone/callback de cada uma das 6 ações, idênticos aos de antes.
4. `test_restante_do_menu_de_contexto_nao_foi_tocado` - garantia negativa de que o
   submenu "Ferramentas Terra" categorizado e o "Excluir" na raiz continuam intactos.

Também executado `python -m py_compile earth_tools/layeractions.py` - sem erro.

**Limitação de ambiente, igual às versões anteriores:** não há QGIS 3.44.15 instalado
nesta máquina de desenvolvimento, então a confirmação visual de que o menu de contexto
real mostra agora **um único** "Adicionar" com seta de submenu é uma auditoria estática
(leitura do código e testes de string), não uma execução real contra o QGIS. Ver
`ROTEIRO_VALIDACAO_MANUAL_v0.17.1.md` para os passos manuais pendentes.

## Confirmação de que nenhuma outra funcionalidade foi alterada

- Ferramentas de desenho/edição/régua/snapping/desfazer-refazer: não tocadas.
- Geoprocessamento (Buffer/União/Divisão/Recorte/Diferença): não tocado.
- Medições/Calculadora: não tocadas.
- Estilos/Gerenciador de Estilos: não tocados.
- Validação de geometrias: não tocada.
- Exportação (mapas/KML/KMZ/lugar individual): não tocada.
- Estrutura de armazenamento e banco GeoPackage (`storage.py`): não tocados.
- Ícones existentes: nenhum alterado (nenhum ícone novo nesta versão).
- Barra de ferramentas: não tocada.
- Integração com o QGIS (`addCustomActionForLayerType`/`addCustomActionForLayer`,
  `contextMenuAboutToShow`): o padrão de uso continua o mesmo descrito no cabeçalho de
  `layeractions.py` - só a forma de registrar o submenu "Adicionar" mudou.
- Menu "Ferramentas Terra" categorizado (0.17.0), "Excluir" na raiz, e todos os menus
  nativos do QGIS (Duplicar Camada, Remover Camada, Abrir tabela de atributos, Alternar
  Edição, Filtrar, SRC da camada, Exportar, Estilos, Propriedades etc.): não tocados -
  esta correção só adiciona/edita código dentro do bloco "Submenu 'Adicionar'" de
  `layeractions.py`, documentado linha a linha acima.
