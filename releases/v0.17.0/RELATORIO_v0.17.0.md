# Relatório da versão 0.17.0 — Ferramentas Terra

**Data de geração:** 2026-10-30.

## Contexto

Pedido do usuário: melhoria de interface e experiência de uso ("MELHORIA DE INTERFACE E
EXPERIÊNCIA DE USO — FERRAMENTAS TERRA"), com auditoria prévia obrigatória, reorganização
do menu de contexto em categorias, barra de ferramentas própria, painel lateral de
propriedades e identidade visual consistente. **Nenhuma captura de tela foi recebida
junto com o pedido** (o texto menciona uma, mas nenhuma imagem chegou nesta conversa) - a
auditoria foi feita por exame do código-fonte real, não por inspeção visual.

Marca de segurança: topo do histórico de `0.16.0` (`6d3f0f5`).

## Etapa 1 — Auditoria (resumo)

| Item auditado | Situação encontrada |
|---|---|
| Construção do menu de contexto | `addCustomActionForLayerType`/`addCustomActionForLayer` (API nativa, nunca `setMenuProvider()` - documentado em `layeractions.py` como decisão deliberada, por segurança). |
| Ações próprias no menu de contexto | 12 ações soltas na raiz, sem agrupamento nem separador: Editar, Ir para, Mover para pasta, Estilo, Buffer, União, Divisão, Recortar, Diferença, Excluir, Salvar como, Enviar por e-mail. |
| Submenu existente | "Adicionar" (6 itens), disponível em qualquer camada vetorial do projeto (`all_layers=True`), não só lugares do plugin - comportamento intencional, preservado. |
| Barra de ferramentas | Uma ("Ferramentas Terra"), 7 botões com ícone próprio; Calculadora, Exportar mapa, Validar geometrias, Importar/Exportar KML/KMZ existiam só no menu Vetor (decisão documentada de "reduzir botões"). |
| Painel lateral de propriedades | **Não existia.** Zero ocorrências de `QDockWidget`/`addDockWidget` no projeto inteiro antes desta versão. |
| Ações duplicadas | Nenhuma encontrada entre as ações próprias do plugin. |
| Funcionalidades realmente operacionais | Todas as lidas (`dlg_validate.py`, `dlg_calculator.py`, `dlg_style_manager.py`, `dlg_export_map.py`, `geometry_validator.py`) tinham lógica real, nenhum placeholder - confirmado por leitura de código e pela suíte de 161 testes já existente (136+ validados contra QGIS 3.44.15 real, por auditorias anteriores). |

Decisões de design levantadas durante a auditoria e confirmadas com o usuário antes de
codar:
1. Categorias dentro do submenu "Ferramentas Terra": rótulos de seção desabilitados (não
   há API documentada de submenu aninhado em `addCustomActionForLayerType` para validar
   sem uma instalação QGIS local - não disponível neste ambiente).
2. Validação e Calculadora passam a aparecer também no menu de contexto por-camada
   (antes só no menu Vetor).
3. Painel lateral de propriedades entra nesta mesma entrega.

## Etapa 2 — Implementação

### Menu de contexto (`layeractions.py`)
`install()` reescrito: todas as ações de lugar (exceto `Excluir`) passam a usar
`menu="Ferramentas Terra"` em vez de `menu=""`, com rótulos de seção desabilitados
(`header()`, um `QAction.setEnabled(False)` sem callback) separando GEOPROCESSAMENTO,
MEDIÇÕES, VALIDAÇÃO e EXPORTAÇÃO. `Excluir` continua fora do submenu, na raiz - ação
destrutiva não deve ficar escondida junto das demais. Nenhuma das 12 ações antigas foi
removida (coberto por teste de regressão). Três ações novas: `_on_calculate`,
`_on_validate`, `_on_export_map` - todas delegam para os métodos já existentes de
`EarthTools` (`open_calculator_for`, `_open_validate`, `open_export_map_for`), sem
duplicar lógica.

### Barra de ferramentas e menu Vetor (`earth_tools.py`)
- Ação nativa `iface.actionSelectFeatures()` passa a também aparecer nesta barra (mesmo
  `QAction`, não uma cópia - zero lógica nova).
- 4 botões novos: Desenhar círculo (abre a Régua na aba Círculo via novo parâmetro
  `initial_tab`), Calculadora, Gerenciar estilos, Exportar mapa.
- Calculadora e Exportar mapa deixam de ser `_add_menu_only` (só menu) e passam a
  `_add()` (menu + barra) - sem duplicar a entrada no menu Vetor (coberto por teste).
- `_open_calculator()`/`_open_export_map()` (ligados a `QAction.triggered`, sem parâmetro
  extra) agora delegam para `open_calculator_for(layer)`/`open_export_map_for(layer)`,
  que aceitam a camada explicitamente. Essa separação existe porque
  `QAction.triggered` emite um `bool` (`checked`); se o callback ligado por `.connect()`
  aceitasse um parâmetro opcional de camada, o PyQt passaria esse `bool` para dentro
  dele, corrompendo silenciosamente a seleção. Mesmo cuidado aplicado a
  `_save_as`/`_save_as_layer` em `layeractions.py`.

### Painel lateral (`dlg_properties_panel.py`, novo arquivo)
`PropertiesPanel(QDockWidget)`: nome, tipo, área, perímetro/comprimento, SRC e situação
da validação do lugar selecionado no painel Camadas. Os valores usam **as mesmas funções
de medição** de `dlg_calculator.py`/`dlg_export_map.py`
(`utils.measure_area_geometry`/`measure_perimeter_geometry`/`measure_length_geometry`) e
a mesma rotina de validação de `dlg_validate.py`
(`geometry_validator.validate_layers`) - nenhum cálculo novo, nenhum valor fictício.
Atualiza ao trocar a seleção (`currentLayerChanged`) e ao editar/estilizar a própria
camada (`committedGeometriesChanges`, `editingStopped`, `styleChanged`, `nameChanged`),
sem polling. Os 4 botões (Calcular medidas, Alterar estilo, Validar geometria, Exportar
geometria) delegam para o código já existente em `EarthTools`/`LayerActions` - nenhuma
lógica de cálculo/estilo/validação/exportação foi duplicada.

### Pré-seleção opcional (`dlg_calculator.py`, `dlg_export_map.py`, `dlg_ruler.py`)
`CalculatorDialog`/`ExportMapDialog` ganham `initial_layer=None`; `RulerDialog` ganha
`initial_tab=0`. Todos com default que preserva o comportamento exato de antes quando
abertos sem esse argumento (menu Vetor/barra, sem lugar específico).

### Ícones novos
`circle.svg`, `calculator.svg`, `style.svg`, `export_map.svg` - mesmo estilo visual
(paleta de cores, `viewBox 24x24`) dos ícones já existentes.

## Etapa 3 — Testes

Executados (sem PyQGIS, como já era o padrão de `test_regression_static.py` neste
ambiente - **não há instalação local do QGIS/módulo `qgis` disponível aqui**, diferente
de quando a 0.14.1/0.15.0/0.16.0 foram auditadas; `test_qgis_integration.py` continua
pulado/skipped por esse motivo, igual a antes desta versão):

```
python -m unittest discover -s tests -p "test_*.py"
Ran 182 tests in 0.041s
OK (skipped=1)
```

161 testes pré-existentes continuam passando (nenhuma regressão). 21 testes novos
cobrindo especificamente esta versão: submenu categorizado (`SubmenuFerramentasTerraTests`),
painel lateral (`PropertiesPanelTests`), barra de ferramentas
(`ToolbarNaoRemoveNadaExistenteTests`) e parâmetros de pré-seleção
(`PreSelecaoOpcionalTests`). Dois testes pré-existentes precisaram de ajuste de string
(não de comportamento) porque o texto literal mudou: `test_acao_estilo_esta_cadastrada`
(ícone `None` → `"style.svg"`) e a formatação de uma linha de `earth_tools.py`.

Também verificado: `python -m py_compile` em todos os arquivos `.py` modificados/novos, e
validação XML dos 4 SVGs novos - sem erro.

**Limitação explícita desta entrega:** sem QGIS 3.44.15 real disponível neste ambiente
para a validação funcional de verdade (abrir o painel, clicar nos botões, confirmar a
pré-seleção do lugar nas três janelas, abrir o menu de contexto categorizado) - só a
auditoria estática (testes de string/import/compilação) pôde ser executada aqui. Ver
`ROTEIRO_VALIDACAO_MANUAL_v0.17.0.md`, na raiz do projeto, para os passos manuais
pendentes antes de considerar esta versão validada, seguindo a mesma disciplina das
versões anteriores (nunca confiar sem rodar contra o QGIS real).

## Arquivos alterados

- `earth_tools/layeractions.py` - submenu categorizado, 3 ações novas, `_save_as`/`_save_as_layer`.
- `earth_tools/earth_tools.py` - barra (5 itens novos), painel lateral, `open_calculator_for`/`open_export_map_for`.
- `earth_tools/dlg_properties_panel.py` - **novo**.
- `earth_tools/dlg_calculator.py` - parâmetro `initial_layer`.
- `earth_tools/dlg_export_map.py` - parâmetro `initial_layer`.
- `earth_tools/dlg_ruler.py` - parâmetro `initial_tab`.
- `earth_tools/icons/circle.svg`, `calculator.svg`, `style.svg`, `export_map.svg` - **novos**.
- `earth_tools/metadata.txt` - versão 0.17.0 + changelog.
- `earth_tools/LEIAME.md` - documentação do novo menu/barra/painel.
- `earth_tools/tests/test_regression_static.py` - 21 testes novos, 2 ajustados.
- `CHANGELOG.md` - entrada 0.17.0.

## Funcionalidades preservadas (não alteradas)

Todo o geoprocessamento (Buffer/União/Divisão/Recorte/Diferença), cálculo de
área/perímetro/distância, validação de geometrias, gerenciador de estilos, exportação de
mapas/KML/KMZ, organização em pastas, desenho/edição/régua/snapping/desfazer-refazer -
nenhum desses teve a lógica interna tocada; só mudou de onde cada ação é acionada.

## Problemas encontrados

Nenhum defeito funcional pré-existente foi encontrado durante esta auditoria (diferente
da 0.14.1/0.16.0, que encontraram bugs reais de cálculo/persistência). O único ponto de
atenção é a limitação de ambiente descrita acima (sem QGIS real para validação funcional
nesta sessão).
