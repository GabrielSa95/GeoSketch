# Relatório da versão 0.18.0 — GeoSketch (identidade visual + preparação para publicação)

**Data de geração:** 2026-10-30. **Atualizado em:** 2026-10-30, duas vezes (adendo
"Ícone oficial e descrição em português" e, mais abaixo, "Finalização da identidade e
preparação para publicação") - ainda dentro da mesma versão 0.18.0, a pedido explícito do
usuário em ambas (sem bump de versão), já que esta versão nunca chegou a ser publicada.

## Adendo 2 — Finalização da identidade e preparação para publicação (mesma versão 0.18.0)

Pedido de acompanhamento: fixar autor (Gabriel Alberto), revisar `qgisMinimumVersion`
conforme compatibilidade **comprovada**, adicionar a seção "Desenvolvimento e autoria"
(deixando claro que IA foi usada como apoio, nunca como autora), auditar
licenciamento/direitos de terceiros, e revisar `metadata.txt`/documentação contra a
documentação oficial do QGIS (`plugins.qgis.org/docs/publish` e `/docs/approval`).

### Identificação oficial (`metadata.txt`)
- `author=Gabriel Alberto` (era `[PENDENTE]`).
- `qgisMinimumVersion`: **3.22 → 3.44**. Motivo: o pedido explicitamente pede "a versão
  realmente suportada e testada" / "conforme compatibilidade comprovada". A única versão
  com teste empírico real **confirmado** no histórico deste projeto (`CHANGELOG.md`,
  0.14.1+) é o QGIS 3.44.15 - a declaração anterior de `3.22` vinha de uma afirmação no
  README antigo ("testado em 3.34 LTR, 3.40 e 3.44") sem registro equivalente no
  changelog. Corrigido para não declarar compatibilidade não comprovada, conforme
  instrução explícita e conforme a própria documentação oficial do QGIS (fetchada nesta
  etapa - ver abaixo). Isso **estreita** a compatibilidade declarada; se o usuário testar
  com sucesso numa instalação 3.22-3.40, é evidência válida para baixar o valor de novo.
- `tags=` normalizadas para minúsculas/hifenizadas (`google earth` → `google-earth`),
  conforme o formato exigido pela documentação oficial (ver abaixo).
- `email=`/`homepage=`/`repository=`/`tracker=` continuam `[PENDENTE]` - **não
  inventados**. Mantive assim mesmo esses serem campos obrigatórios (ver auditoria da
  documentação oficial abaixo) porque exigem dado real do usuário que não me foi
  fornecido nesta etapa.
- Versão (`0.18.0`), categoria (`Vector`) e `deprecated=False`: inalterados, como pedido.
- `experimental=True`: **mantido**. Só viraria `False` com evidência de estabilidade
  validada em QGIS real, que não existe neste ambiente de desenvolvimento (sem QGIS
  instalado) nem foi reportada pelo usuário.

### Consulta à documentação oficial do QGIS (`plugins.qgis.org/docs/publish` e `/docs/approval`)
Buscadas nesta etapa (não só citadas de memória). Confirmações relevantes:
- **`homepage=`, `repository=` e `tracker=` são campos OBRIGATÓRIOS**, não apenas
  recomendados - a documentação explicita que `repository=` precisa ser um repositório de
  código **publicamente acessível, nunca um arquivo zipado**. Isso **bloqueia a submissão
  por completo** até existir um repositório público - não é um "nice to have" como eu
  vinha registrando antes; atualizei a linguagem em `README.md`/`CHANGELOG.md` para
  deixar isso inequívoco.
- Versionamento semântico (`0.18.0` já está correto).
- Tags devem ser minúsculas e hifenizadas (corrigido acima).
- O pacote ZIP deve excluir `__MACOSX`, `.git`, `__pycache__`, arquivos gerados
  (`ui_*.py`/`resources_rc.py` - não existem neste projeto) e **deve incluir README e
  LICENSE dentro do próprio pacote** - por isso copiei `README.md` e `LICENSE` da raiz
  para dentro de `earth_tools/` (ver abaixo), além de já existirem na raiz do repositório.
- Revisão de aprovação testa instalação real cross-platform (Windows/Linux/macOS) e
  espera conformidade com PEP8 - não executei lint de PEP8 nesta etapa (fora do escopo
  pedido, que é identidade/documentação/licenciamento, não revisão de estilo de código) e
  sinalizo isso como item em aberto, não resolvido.

### Bug real encontrado e corrigido: `metadata.txt` não carregava o changelog inteiro
Ao validar `metadata.txt` com `configparser` (o mesmo tipo de parser que o QGIS usa para
ler `metadata.txt`), a leitura do campo `changelog=` **falhava com
`InterpolationSyntaxError`** por causa de um `%` solto no texto histórico da versão
0.13.0 ("corte cumulativo 2%-98%") - `ConfigParser` usa `%` para interpolação de
variáveis, e um `%` sozinho (não seguido de `%` ou `(`) é erro de sintaxe. Esse defeito
já existia **antes** desta auditoria (não foi introduzido por nenhuma mudança minha) e
podia impedir o QGIS de mostrar o changelog completo do plugin no Gerenciador de
Complementos. Corrigido escaneando `metadata.txt` inteiro por `%` (só essa ocorrência
encontrada) e duplicando para `%%` (sintaxe de escape do `ConfigParser` - confirmado
empiricamente que isso volta a ler como um `%` único, sem alterar o texto exibido ao
usuário). Revalidei **todos** os campos de `metadata.txt` (não só os obrigatórios) depois
da correção - todos leem sem erro agora.

### Auditoria de licenciamento e direitos de terceiros
- **Origem do código**: busca por `Copyright`/`SPDX`/`adapted from`/`based on`/`source:`
  em todo o projeto não encontrou nenhum trecho de código de terceiros nem aviso de
  copyright preexistente a preservar - o código é original deste projeto.
- **Licenças de bibliotecas**: zero dependências Python de terceiros (confirmado por
  inspeção de todo `import`/`from` do projeto, repetida nesta etapa) - só biblioteca
  padrão do Python e `qgis.*`/`qgis.PyQt.*`, fornecidas pelo próprio QGIS (GPL-2.0-or-later
  no núcleo). GPL-2.0-or-later é a licença convencional e compatível para plugins QGIS
  justamente por essa razão - nenhum impedimento de licenciamento encontrado.
- **Ícones**: os SVGs em `earth_tools/icons/` não têm nenhum marcador de autoria/licença
  de terceiros (busca específica, sem resultado) - são geometria simples, de autoria
  própria deste projeto. O PNG oficial (`geosketch.png`) foi fornecido pelo usuário como
  "a identidade visual oficial do GeoSketch"; não há metadado EXIF/PNG embutido no
  arquivo indicando origem - a titularidade dos direitos sobre essa imagem é uma
  declaração do usuário, que não tenho meios técnicos de verificar de forma independente.
- **LICENSE**: `Copyright (C) 2026 Gabriel Alberto` - atribuído só ao autor do projeto
  (código próprio), não a nenhum código de terceiros (não havia nenhum a atribuir
  erradamente). Nenhum aviso de copyright preexistente foi removido (não havia nenhum).

### Declaração de auxílio de IA
Seção "Desenvolvimento e autoria" adicionada, com o texto exato fornecido, a:
- `README.md` (raiz, inglês - seção em português, como pedido literalmente).
- `earth_tools/LEIAME.md` (guia em português).
`metadata.txt` `author=` continua só "Gabriel Alberto" - nenhuma ferramenta de IA foi
adicionada a esse campo.

### Documentação revisada
- `README.md`: seção de requisitos/compatibilidade reescrita (3.44, não mais 3.22;
  ressalva de Windows-only testado; nota sobre `sys.platform` em "Enviar por e-mail");
  pendências atualizadas com a exigência **obrigatória** de repositório público; nova
  seção "Version history" apontando para `CHANGELOG.md`; nova seção "Desenvolvimento e
  autoria"; nota sobre direitos dos ícones na seção de licença.
- `earth_tools/LEIAME.md`: seção "Requisitos" corrigida (3.44, com a mesma justificativa);
  nova seção "Desenvolvimento e autoria".
- `DEVELOPMENT.md`: seção de requisitos atualizada (decisão tomada, não mais pendência
  em aberto); passo 1 do processo de release lembra de sincronizar `README.md`/`LICENSE`
  para dentro de `earth_tools/`.
- `earth_tools/README.md` e `earth_tools/LICENSE` (**novos** - cópias de
  `README.md`/`LICENSE` da raiz, para acompanhar o pacote instalável, exigência da
  documentação oficial de publicação).

### Testes desta etapa
```
python -m unittest discover -s tests -p "test_*.py"
Ran 193 tests in 0.043s - OK (skipped=1)
```
Nenhum arquivo `.py` de código foi alterado nesta etapa (confirmado por
`git status --short` antes de começar) - só `metadata.txt`, `LICENSE`, `README.md`,
`LEIAME.md`, `DEVELOPMENT.md`, `CHANGELOG.md`. `metadata.txt` revalidado como INI
completo (todos os 15 campos, incluindo `changelog`, sem erro de interpolação). ZIP
reconstruído (194 KB) e reauditado: pasta única, `metadata.txt` no lugar certo,
`README.md`/`LICENSE`/ícone presentes dentro do pacote, sem `__pycache__`/`.git`/`tests`/
`__MACOSX`, sem binário além do PNG legítimo, 55 arquivos. Não há QGIS instalado neste
ambiente para a confirmação visual real (Gerenciador de Complementos) - ver roteiro de
validação manual.

### Itens fora do escopo desta etapa, sinalizados mas não executados
- Lint de PEP8 (mencionado pela documentação de aprovação do QGIS, mas fora do pedido
  desta etapa, que é identidade/documentação/licenciamento).
- Teste de instalação real em cópia limpa do QGIS (sem QGIS neste ambiente).
- Qualquer contato com o repositório oficial/conta OSGeo (explicitamente não autorizado).

## Adendo — Ícone oficial e descrição em português (mesma versão 0.18.0)

Pedido de acompanhamento: resolver a pendência #1 (ícone oficial) e traduzir
`description=`/`about=` de `metadata.txt` para português, sem alterar nome, versão,
autor/dados pendentes, menus, botões, barras ou qualquer código de ferramenta.

**Ícone**: PNG localizado em `Blob azul-turquesa translúcido e brilhante.png`, na raiz do
projeto (colocado pelo usuário). Verificado: PNG válido, 1313×1198 px, RGBA com canal
alfa nativo (não é truque de paleta/tRNS), fundo 100% transparente nos 4 cantos
(alfa=0), símbolo opaco no centro (alfa≈253) - transparência de verdade, confirmada
pixel a pixel, não só pela extensão do arquivo. 1,1 MB no tamanho original.

Como 1,1 MB/1313×1198 é desproporcional para um ícone de listagem (o resto do pacote
inteiro, antes disso, tinha 136 KB), criei uma cópia otimizada - redimensionada
*proporcionalmente* (sem distorcer, sem cortar, sem redesenhar o símbolo) para 256×234 px
(a maior dimensão em 256 px, a outra escalada na mesma proporção), reamostragem LANCZOS,
RGBA/transparência preservada (confirmado: alfa ainda varia de 0 a 255 depois do
redimensionamento) e compressão PNG otimizada - 48 KB. Salva em
`earth_tools/icons/geosketch.png` (caminho relativo à pasta principal do plugin, dentro
de `icons/`, mesma convenção dos demais ícones do projeto).

**O arquivo original (1,1 MB) foi mantido intacto**, exatamente onde o usuário o colocou
(raiz do projeto, fora de `earth_tools/`) - não foi movido, renomeado nem sobrescrito
(timestamp e tamanho em bytes conferidos antes/depois, idênticos). Fica fora do ZIP
instalável de propósito (deliberado, não um esquecimento): é um arquivo-fonte de 1,1 MB
sem função em tempo de execução - incluí-lo inflaria o pacote ~8× sem benefício para
quem instala o plugin. Caso o usuário queira o arquivo-fonte versionado dentro do
repositório Git do plugin também (não só na raiz do projeto), é só pedir.

`metadata.txt`: `icon=icons/geosketch.png` (era `icons/placemark.svg` - nunca foi o
ícone amarelo padrão do QGIS, mas também não era o ícone oficial da marca; não usei o
ícone padrão do QGIS como substituto, como pedido). Não toquei em nenhum ícone de
botão/menu/barra de ferramentas (`placemark.svg`, `polygon.svg` etc. continuam intactos e
em uso pelas ferramentas, como sempre) - a "identificação do complemento" com o novo
ícone se aplica só ao campo `icon=` do `metadata.txt` (Gerenciador de Complementos,
página do repositório oficial), que é o único local do QGIS onde esse ícone de
identidade realmente aparece; não há um segundo local de "identificação do complemento"
na arquitetura deste plugin para aplicar o mesmo ícone.

**Descrição**: `description=` e `about=` traduzidos para o português exato fornecido pelo
usuário, só depois de verificar cada afirmação contra a funcionalidade real:

| Afirmação do texto | Verificado contra |
|---|---|
| "pontos, polígonos, caminhos e círculos" | `dlg_feature.py` (ponto/caminho/polígono) + `dlg_ruler.py._save()` (aba Círculo salva de verdade via `storage.create_place("polygon", ...)`, com o anel do círculo) - círculo é salvável, confirmado no código |
| "medição de áreas e distâncias" | `dlg_calculator.py`, `dlg_ruler.py` |
| "gerenciamento de estilos" | `dlg_style_manager.py` |
| "operações de geoprocessamento" | `geoprocessing.py` (Buffer/União/Divisão/Recorte/Diferença, algoritmos nativos do QGIS) |
| "validação de geometrias" | `geometry_validator.py`, `dlg_validate.py` |
| "exportação de mapas em PDF e PNG" | `reports.py`/`dlg_export_map.py` (`QgsPrintLayout`/`QgsLayoutExporter` reais) |
| "importação e exportação de KML e KMZ" | `kml_io.py`, `kml_bridge.py`, `dlg_import_kml.py`, `dlg_export_kml.py` |
| "salvos automaticamente em GeoPackage, pastas e subpastas" | `storage.py` (GeoPackage "Meus Lugares") + `places_model.py` (hierarquia de pastas persistida) |

Nenhuma afirmação encontrada sem funcionalidade real correspondente - texto do usuário
usado literalmente, sem edição.

**Testes desta etapa**: `python -m unittest discover` (193 testes, sem alteração - nenhum
código `.py` foi tocado); `metadata.txt` revalidado via `configparser` (13/13 campos
obrigatórios, sem erro de sintaxe); caminho do ícone resolvido e conferido como existente
a partir da pasta do plugin; ZIP reconstruído e reauditado (ver tabela abaixo,
atualizada). Não há QGIS instalado neste ambiente para abrir o Gerenciador de
Complementos de verdade - essa confirmação visual fica pendente, registrada no roteiro de
validação manual.

**Arquivos desta etapa**: `earth_tools/metadata.txt` (icon=, description=, about=),
`earth_tools/icons/geosketch.png` (novo). Nenhum outro arquivo alterado.

## Contexto

Pedido do usuário: renomear o complemento (até então "Ferramentas Terra") para
**GeoSketch**, remover os ícones de Calculadora e Gerenciador de Estilos da barra
(mantendo as funcionalidades no menu de contexto) e preparar o projeto para submissão ao
repositório oficial de plugins do QGIS (https://plugins.qgis.org/docs/publish e
/docs/approval). Instrução explícita: preservar toda funcionalidade existente; não é uma
reescrita.

**Bloqueios identificados no início desta tarefa e decisões tomadas com o usuário:**

1. **Nenhum ícone PNG foi recebido** nesta conversa (nem anexado, nem presente no disco -
   confirmado por busca). Decisão do usuário: seguir com todo o resto agora, mantendo
   `icons/placemark.svg` como `icon=` temporário em `metadata.txt`, claramente marcado
   como pendência.
2. **`author=`/`email=`/`tracker=`/`repository=` em `metadata.txt` eram placeholders
   fictícios** (`Equipe interna`, `suporte@exemplo.com.br`, `example.com`) - não há
   repositório git remoto configurado. Decisão do usuário: ele tem/vai providenciar uma
   conta GitHub/GitLab e informar a URL - até lá, estes campos ficam marcados como
   `[PENDENTE - ...]`, não preenchidos com dados inventados.
3. **Identificador interno do pacote**: decisão do usuário foi manter `earth_tools`/
   `EarthTools` (recomendado por mim) - zero risco de regressão, compatível com qualquer
   instalação local já existente.

## Auditoria de dependências antes de renomear

Antes de qualquer alteração de texto, busquei todas as ocorrências de
`Ferramentas Terra`/`FerramentasTerra`/`ferramentas_terra`/`earth_tools`/`EarthTools` no
código-fonte (239 ocorrências em 27 arquivos) e separei em duas categorias:

| Categoria | Exemplos | Decisão |
|---|---|---|
| **Texto exibido ao usuário** (cosmético) | Títulos de janela (`setWindowTitle`), títulos de `QMessageBox`, títulos da `messageBar()`, nome da barra de ferramentas (`addToolBar("...")`), nome do submenu de contexto (`SUBMENU = "..."`), nome do menu Vetor (`"&Ferramentas Terra"`), título do painel lateral | **Renomeado para "GeoSketch"** (156 ocorrências em 27 arquivos, via substituição literal auditada) |
| **Identificador interno/persistido** (estrutural) | `storage.CUSTOM_KEY = "ferramentas_terra"` (gravado em toda camada do GeoPackage - é como o plugin reconhece "isto é um lugar meu"), `SETTINGS_GROUP = "FerramentasTerra/EstilosSalvos"` (QSettings dos presets de estilo), `setObjectName("FerramentasTerra"/"FerramentasTerraPropriedades")` (posição salva da barra/painel), pasta `earth_tools`, classe `EarthTools`, `classFactory` | **Mantido sem alteração** - mudar qualquer um destes faria todo lugar/preset já criado por qualquer versão anterior parar de ser reconhecido |

Esta separação foi confirmada com testes de regressão automatizados (ver seção de
testes) que travam especificamente que os identificadores estruturais **não** mudaram.

## Alterações aplicadas

### 1. Ícone oficial — **bloqueado, não aplicado**
Nenhum PNG foi recebido. `icon=icons/placemark.svg` permanece como estava, claramente
documentado como pendência em `metadata.txt`, `README.md` e aqui.

### 2. Remoção dos ícones de Calculadora e Gerenciador de Estilos da barra
`earth_tools.py`: removidas as duas linhas `self._add("calculator.svg", ...)` e
`self._add("style.svg", ...)` de `initGui()` (cada uma registrava simultaneamente um
ícone na barra **e** uma entrada no menu Vetor - remover a chamada removeu as duas
exposições de uma vez, deixando as funcionalidades acessíveis **exclusivamente** pelo
menu de contexto, como pedido). As funções `_open_calculator()` e `_open_style_manager()`
continuam definidas (não foram excluídas, por instrução explícita), agora sem nenhum
callback ligado a elas na barra - código morto preservado intencionalmente. As entradas
já existentes no menu de contexto (`layeractions.py`, submenu GeoSketch: "Calcular
medidas...", "Estilo...") não foram tocadas - continuam chamando a mesma lógica
(`open_calculator_for()`, `LayerActions._on_style()`) de sempre.

Separador redundante da barra ajustado (dois separadores ficariam adjacentes sem as duas
linhas removidas no meio).

### 3. Renomeação para GeoSketch
Substituição literal de `"Ferramentas Terra"` (com espaço) por `"GeoSketch"` em 27
arquivos (`.py` em `earth_tools/` e `earth_tools/tests/`, mais `LEIAME.md`), feita por
script Python (não editor manual, para garantir cobertura completa e nenhuma ocorrência
perdida por engano). Um caso de quebra de linha no meio do texto (markdown) em
`LEIAME.md` não foi pego pelo replace literal e foi corrigido manualmente. Resultado
verificado por nova busca: zero ocorrências de `"Ferramentas Terra"` restantes em código
ou documentação do plugin, fora do histórico (`CHANGELOG.md`/`RELATORIO_*`/`ROTEIRO_*`
anteriores a esta versão, que descrevem o estado passado e não foram reescritos).

`metadata.txt`: `name=GeoSketch`; `description=`/`about=` traduzidos para inglês (texto
novo, derivado da funcionalidade real documentada em `LEIAME.md`/`CHANGELOG.md`, não
inventado); `tags=` revisadas (inglês + português); `version=0.18.0`.

### 4. Preparação para o repositório oficial do QGIS
- **`metadata.txt`**: todos os campos obrigatórios presentes e válidos como INI
  (`configparser`, sem erro). `author=`/`email=`/`homepage=`/`tracker=`/`repository=`
  marcados como `[PENDENTE - ...]` - **não preenchidos com dados inventados**, conforme
  instrução explícita. `qgisMinimumVersion=3.22` **mantido** (ver discrepância abaixo).
  `experimental=True` mantido (ver justificativa abaixo). `category=Vector` (já era
  válido). `icon=icons/placemark.svg` (pendência #1).
- **Discrepância encontrada e não resolvida silenciosamente**: `README.md` (antes desta
  versão) afirmava "testado em 3.34 LTR, 3.40 e 3.44", mas `CHANGELOG.md` só registra
  testes empíricos **confirmados** contra uma instalação real a partir da 0.14.1,
  especificamente contra o QGIS 3.44.15 (não 3.34/3.40 citados). Não tenho evidência para
  contradizer a afirmação original do README, então mantive `qgisMinimumVersion=3.22`
  (valor original) em vez de estreitar unilateralmente - mas documentei a discrepância em
  `DEVELOPMENT.md` e `README.md` como item pendente de reverificação manual, por ser
  exigência explícita do processo oficial de publicação ("não declarar compatibilidade
  não testada").
- **`experimental=True` mantido**: não há QGIS instalado neste ambiente para validar de
  verdade a interface renomeada (abrir o menu, clicar nos botões) - rodei só a auditoria
  estática (testes de string/compilação). Virar para `False` antes da validação manual
  real seria uma afirmação não verificada.
- **Documentação**:
  - `README.md` (raiz, **inglês**, novo): descrição, funcionalidades, requisitos/
    compatibilidade (com a ressalva da discrepância acima), instalação, uso (referencia
    `earth_tools/LEIAME.md` para o guia detalhado em português), suporte/issues (pendente
    de URL), licença, e uma seção explícita "Project status & pending items" listando
    tudo que falta antes de publicar.
  - `earth_tools/LEIAME.md` (guia de uso em **português**, já existia): preservado e
    atualizado para o novo nome; satisfaz o pedido de "README ou guia de utilização em
    português".
  - `DEVELOPMENT.md` (raiz, **novo nome** do antigo `README.md` de desenvolvimento em
    português): conteúdo 100% preservado, só o nome do arquivo e as referências ao nome
    do plugin foram atualizados - nada deletado.
  - `LICENSE` (raiz, **novo**): texto oficial e completo da GNU GPL v2, com o cabeçalho
    padrão "version 2, or (at your option) any later version" (GPL-2.0-or-later). Nome
    do titular do copyright e ano marcados como `[PENDENTE - ...]` - não inventados.

## Auditoria de empacotamento (item 5 do pedido)

Executada sobre o ZIP gerado (`releases/v0.18.0/earth_tools_v0.18.0.zip`):

| Verificação | Resultado |
|---|---|
| `metadata.txt` válido (parseável, campos obrigatórios presentes) | OK - `configparser` leu sem erro, 13/13 campos obrigatórios presentes |
| Ícone existe no caminho indicado em `icon=` | OK - `icons/geosketch.png` existe, 256×234 px, RGBA com transparência (ver adendo acima) - **resolvido** |
| Uma única pasta principal no ZIP | OK - só `earth_tools/` |
| `metadata.txt` diretamente dentro dessa pasta | OK - `earth_tools/metadata.txt` |
| Sem `__pycache__`/`.git`/arquivos temporários | OK - nenhum encontrado |
| Sem pasta `tests/` (não faz parte do pacote instalável) | OK - excluída do empacotamento |
| Sem credenciais/tokens/senhas/dados pessoais | OK - busca por padrões (`api_key`, `secret`, `password`, `senha`, `token =`, `-----BEGIN` etc.) no código-fonte não encontrou nenhuma ocorrência real (únicos "hits" foram falsos-positivos de palavras como "desenha" contendo a substring "senha") |
| Sem binários proibidos | OK - únicas extensões no pacote: `.py` (36), `.svg` (14), `.md` (1 - `LEIAME.md`), `.txt` (1 - `metadata.txt`) |
| Tamanho ≤ 25 MB | OK - 136 KB |
| Dependências externas documentadas | OK - **nenhuma dependência Python de terceiros** (confirmado lendo todo `import`/`from` do código: só biblioteca padrão do Python e `qgis.*`/`qgis.PyQt.*`, fornecidas pelo próprio QGIS) - documentado em `README.md` |
| Código-fonte público corresponde ao enviado | **Não aplicável ainda** - não existe repositório público (pendência) |

## Testes executados

```
python -m unittest discover -s tests -p "test_*.py"
Ran 193 tests in 0.044s
OK (skipped=1)
```

187 testes pré-existentes continuam passando sem alteração. 6 testes novos
(`RebrandingGeoSketchTests`) travando especificamente: `CUSTOM_KEY` inalterado,
`SETTINGS_GROUP` inalterado, `objectName`s inalterados, classe/`classFactory`
inalterados, texto exibido correto ("GeoSketch" nos pontos-chave), e ausência de
qualquer "Ferramentas Terra" residual em `earth_tools.py`/`layeractions.py`/
`dlg_properties_panel.py`. Também ajustados 2 testes pré-existentes
(`test_acao_calculadora_esta_cadastrada`, `test_botoes_novos_pedidos_na_auditoria`/
`test_calculadora_e_estilos_nao_tem_mais_icone_na_barra`) para refletir a mudança
intencional de comportamento (ícones saem da barra).

Também executado `python -m py_compile` em todos os `.py` do plugin (sem erro) e
validação do `metadata.txt` como INI via `configparser` (sem erro).

**Limitação de ambiente, igual às versões anteriores**: não há QGIS instalado nesta
máquina de desenvolvimento - toda a validação acima é estática (código/testes de
string/compilação), não uma execução real. Ver `ROTEIRO_VALIDACAO_MANUAL_v0.18.0.md`.

## Confirmação de que nenhuma outra funcionalidade foi alterada

Ferramentas de desenho, caminhos/polígonos/círculos, cálculos, geoprocessamento,
Gerenciador de Estilos, Validador, Exportação, GeoPackage e persistência dos dados: **não
tocados** - único código funcional alterado foi a remoção de 2 linhas de registro na
barra (`earth_tools.py`) e a troca de texto de exibição (não de lógica) em todos os
outros arquivos. Confirmado pela suíte de 187 testes pré-existentes continuando 100%
verde sem nenhuma modificação neles.

## Pendências para publicação (lista consolidada, atualizada após o Adendo 2)

1. ~~Ícone oficial PNG~~ - **resolvido** (Adendo 1).
2. ~~Nome do autor~~ - **resolvido** (`author=Gabriel Alberto`, Adendo 2).
3. ~~`qgisMinimumVersion`~~ - **decidido**: `3.44`, única versão com teste empírico
   comprovado (Adendo 2). Pode ser revisado para baixo com evidência de teste real numa
   versão mais antiga.
4. **`email=` real do autor** - obrigatório para o repositório oficial, não preenchido
   (não inventado).
5. **Repositório de código público** (GitHub/GitLab/OSGeo) e as URLs de
   `homepage=`/`repository=`/`tracker=` - **bloqueia a submissão por completo**, conforme
   confirmado na documentação oficial consultada no Adendo 2 (não é opcional).
6. Validação manual completa (`ROTEIRO_VALIDACAO_MANUAL_v0.18.0.md`) numa instalação QGIS
   real antes de virar `experimental=False` - não executada neste ambiente (sem QGIS
   instalado).
7. Verificação cross-platform (Linux/macOS) - só testado/auditado em Windows até agora.
8. (Opcional, fora do pedido desta etapa) Lint de PEP8, mencionado pela documentação de
   aprovação do QGIS.
9. Só depois de 1-8: seguir o processo oficial (conta OSGeo, envio do ZIP ao
   repositório, acompanhar validação de segurança e aprovação) - **não realizado nesta
   tarefa**, nem autorizado a ser realizado sem confirmação explícita do usuário.

## Adendo 3 — Publicação no GitHub, origem do ícone e validação manual (mesma versão 0.18.0)

Atualização registrada em 2026-10-31, cobrindo três pedidos de acompanhamento distintos
do autor, ainda sem bump de versão (0.18.0 continua sendo a versão em preparação).

**Repositório público criado.** `https://github.com/GabrielSa95/GeoSketch` existe,
inicialmente privado. `email=`, `homepage=`, `repository=` e `tracker=` em
`metadata.txt` foram preenchidos com dados reais do autor - resolve a pendência #4 e a
parte de URLs da pendência #5 (falta só tornar o repositório público antes da submissão
oficial, que exige um repositório **público**).

**Origem do ícone oficial esclarecida.** O autor declarou que `geosketch.png` foi
**gerado pelo ChatGPT, a seu pedido** - não é um recurso de terceiros obtido pronto na
internet. Isso resolve a incerteza registrada no Adendo 1 ("a titularidade dos direitos
sobre essa imagem é uma declaração do usuário, que não tenho meios técnicos de verificar
de forma independente"): a origem agora está documentada (`DEVELOPMENT.md`, seção "Origem
dos recursos visuais"), e o autor assume a responsabilidade pelos direitos de uso sobre
conteúdo gerado por IA a seu pedido, como já constava na seção "Desenvolvimento e
autoria" do `README.md`/`LEIAME.md` para o restante do projeto. O arquivo PNG e sua
transparência RGBA não foram reprocessados nesta atualização.

**Validação manual no QGIS 3.44.15: relatada e aprovada pelo autor.** Diferente das
versões anteriores, esta etapa não contou com uma instalação real do QGIS neste
ambiente de desenvolvimento - a validação foi executada pelo próprio autor,
independentemente, e reportada como concluída e aprovada em 2026-10-31. Este relatório
registra essa aprovação como informada pelo responsável do projeto, não como algo
verificado diretamente por esta auditoria. `experimental=True` foi **mantido**
(não alterado para `False`), por instrução explícita do autor, até que todos os demais
requisitos de estabilidade - notadamente a verificação cross-platform (pendência #7,
ainda em aberto) - sejam confirmados.

### Pendências remanescentes após o Adendo 3
- Tornar o repositório GitHub **público** (hoje privado) antes de qualquer submissão ao
  repositório oficial do QGIS.
- Verificação cross-platform (Linux/macOS) - segue não testada.
- Decisão final sobre `experimental=False` - intencionalmente adiada pelo autor.
- Itens 8 e 9 da lista consolidada acima continuam em aberto, sem alteração.
