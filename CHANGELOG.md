# Registro de alterações — GeoSketch

O GeoSketch foi conhecido anteriormente como **Ferramentas Terra**. As entradas
anteriores à versão 0.18.0 descrevem o mesmo complemento, sob esse nome anterior.

## [0.18.0] — 2026-10-30

### Melhorias
- Nome exibido ao usuário atualizado de "Ferramentas Terra" para "GeoSketch" em todos
  os títulos de janela, caixas de mensagem, barra de ferramentas, menu Vetor e menu de
  contexto.
- Novo ícone oficial do complemento.
- Calculadora de área e distância e Gerenciador de Estilos deixam de ter ícone na
  barra de ferramentas e entrada no menu Vetor; passam a ser acessados pelo submenu de
  contexto da camada ("Calcular medidas...", "Estilo..."), sem alteração na lógica ou
  nos parâmetros.
- Descrição do complemento revisada.

### Correções
- Corrigido um erro de formatação no registro de alterações de uma versão anterior
  que podia impedir a exibição completa do histórico no Gerenciador de Complementos
  do QGIS.

### Compatibilidade
- Requisito mínimo do QGIS atualizado para a versão 3.44 (antes 3.22), refletindo a
  versão efetivamente testada até o momento.
- Lugares e presets de estilo criados em versões anteriores (sob o nome "Ferramentas
  Terra") continuam sendo reconhecidos normalmente após a atualização para o GeoSketch.

## [0.17.1] — 2026-10-30

### Correções
- Corrigido o submenu "Adicionar" do menu de contexto da camada, que aparecia
  duplicado em até seis entradas separadas em vez de um único submenu com as seis
  opções (Pasta, Modelo de propriedade rural, Marcador de local, Caminho, Polígono,
  Sobreposição de imagem).

## [0.17.0] — 2026-10-30

### Novidades
- Painel lateral de propriedades, mostrando em tempo real nome, tipo, área,
  perímetro/comprimento, SRC e situação da validação do lugar selecionado.
- Novas ações no menu de contexto da camada: "Calcular medidas...", "Validar
  geometria..." e "Exportar mapa...", já com o lugar clicado pré-selecionado.
- Novos botões na barra de ferramentas: Selecionar, Desenhar círculo, Calculadora,
  Gerenciar estilos e Exportar mapa.

### Melhorias
- Menu de contexto da camada reorganizado: as ações de lugar passam a ficar
  agrupadas em um único submenu, organizado por categoria (Geoprocessamento,
  Medições, Validação, Exportação). A ação "Excluir" permanece na raiz do menu, por
  ser destrutiva.
- Calculadora de área e distância e Exportar mapa passam a ter também botão na barra
  de ferramentas, além da entrada no menu Vetor.

## [0.16.0] — 2026-10-30

### Novidades
- Calculadora de área e distância, para consultar a área, o perímetro ou o
  comprimento de um lugar já salvo, com troca de unidade e botão para copiar o
  resultado. Também foi adicionado o cálculo de diâmetro na aba Círculo da Régua.
- Gerenciador de Estilos, para aplicar o mesmo estilo a um ou mais lugares
  selecionados de uma vez, com biblioteca de presets nomeados reutilizáveis entre
  projetos.
- Validador de geometrias, que identifica geometria vazia ou inválida, vértices
  duplicados, anel não fechado, geometria fora de uma área de referência e
  sobreposição entre polígonos. A correção automática sempre gera uma cópia nova,
  nunca sobrescrevendo o lugar original.
- Exportação de mapas em PDF e PNG, com título, SRC, área/perímetro, legenda, barra
  de escala e seta de norte, com pré-visualização no Layout Designer do QGIS antes de
  exportar.

### Correções
- Corrigido um problema em que o estilo aplicado a um lugar só era realmente salvo se
  o projeto do QGIS fosse salvo e reaberto. O estilo agora é gravado diretamente no
  GeoPackage e permanece mesmo ao reabrir a camada em um projeto novo.

## [0.15.0] — 2026-10-30

### Novidades
- Gerar Buffer, com distância (incluindo valores negativos, para encolher
  polígonos), unidade, número de segmentos, SRC de processamento e de saída
  independentes, opção de unir dois ou mais resultados em uma única geometria,
  estilo do resultado e pasta de destino.
- Unir polígonos, combinando dois ou mais polígonos em uma única geometria.
- Dividir polígono, cortando um polígono com uma linha desenhada no mapa, com
  pré-visualização do resultado antes de confirmar.
- Recortar com, mantendo apenas a parte de uma geometria que está dentro de uma
  máscara.
- Diferença, mantendo apenas a parte de uma geometria que está fora de outra.

### Compatibilidade
- As operações de geoprocessamento usam sempre algoritmos nativos do QGIS
  Processing e preservam as camadas de origem (exceto a divisão, que remove o
  original somente após as partes novas serem gravadas com sucesso).

## [0.14.1] — 2026-10-30

### Novidades
- Campo "SRC/CRS da camada de saída" na janela Novo Caminho, permitindo escolher
  outro sistema de referência com reprojeção efetiva das coordenadas antes de salvar.

### Correções
- Corrigida definitivamente a causa do problema do Círculo, que em determinados
  sistemas de referência projetados (como SIRGAS 2000/UTM) desenhava apenas a linha
  do raio em vez da circunferência completa, com a área calculada como inválida. A
  correção da versão anterior havia tratado apenas parte do problema.
- Corrigida a mesma causa na ferramenta de entrada por distância e azimute, usada ao
  desenhar Caminho e Polígono, que podia inserir um vértice inválido de forma
  silenciosa sob as mesmas condições.

## [0.14.0] — 2026-10-30

### Novidades
- Seletor de SRC/CRS na aba Caminho da Régua, iniciando no SRC do projeto; o caminho
  salvo passa a ser gravado diretamente nesse sistema de referência.

### Melhorias
- Removidas da Régua as abas "Caminho em 3D" e "Polígono em 3D", que não realizavam
  nenhuma medição real.
- Removidos da barra de ferramentas os botões "Tela cheia" (disponível pelo menu
  nativo Ver > Tela cheia do QGIS) e "Pesquisar lugares" (restrito às camadas criadas
  pelo plugin).

### Correções
- Corrigido o desenho do Círculo, que em alguns casos mostrava apenas a linha
  pontilhada do raio em vez da circunferência completa.

### Compatibilidade
- A busca e o histórico de imagens de satélite (Sentinel-2/Landsat), disponíveis
  desde a versão 0.12.0, foram suspensos nesta versão para priorizar desenho,
  medição e geoprocessamento. O código foi preservado no histórico do projeto para
  uma eventual retomada futura.

## [0.13.1] — 2026-10-25

### Correções
- Corrigida a busca de imagens de satélite, que retornava apenas a primeira página
  de resultados do catálogo (até cerca de 30 cenas), fazendo com que somente o ano
  mais recente aparecesse disponível na linha do tempo. A busca agora percorre
  automaticamente até 1000 cenas.
- Corrigida a verificação do sensor/coleção de cada cena antes de ser exibida e
  antes de ser carregada, evitando que uma cena de radar (sem bandas RGB) fosse
  apresentada e selecionada como se fosse uma cena óptica Landsat.
- O cache de metadados de busca passou a ser versionado, descartando
  automaticamente qualquer cache salvo por uma versão anterior.

## [0.13.0] — 2026-10-25

### Novidades
- Linha do tempo anual na janela de imagens de satélite, indicando claramente quais
  anos do período pesquisado têm aquisição real disponível, com navegação direta
  entre anos e aquisições.
- Atalho pelo botão direito em uma pasta no painel Camadas: "Importar KML/KMZ para
  esta pasta...", "Exportar esta pasta..." e "Exportar propriedade completa...".

### Melhorias
- Importar/Exportar KML/KMZ deixam de ter botão na barra principal; continuam
  disponíveis pelo menu Vetor e pelo novo atalho do botão direito.

### Correções
- Corrigida a exibição de imagens de satélite que levava a interpretar como "imagem
  cinza" ou "imagem ausente": a lista agora mostra a cobertura real da área
  pesquisada para cada cena, em vez de tratar qualquer intersecção com a área como
  resultado encontrado.
- Corrigida a composição de bandas (Landsat e, quando necessário, Sentinel-2), que
  não declarava valores sem dado nem aplicava realce de contraste, resultando em
  imagens esmaecidas.
- Corrigido o cálculo da extensão do mapa usado na busca, agora obtido por um
  retângulo envolvente real, mais preciso em sistemas de referência projetados (como
  SIRGAS/UTM).
- A imagem exibida no mapa só é substituída depois de a nova camada ser validada; uma
  busca anterior não sobrescreve mais o resultado de uma busca mais recente.

## [0.12.0] — 2026-10-24

### Novidades
- Busca de imagens de satélite Sentinel-2 e Landsat via Earth Search
  (Element84/AWS Open Data), por extensão do mapa ou feição selecionada e intervalo
  de datas, com data de aquisição, satélite, resolução e cobertura de nuvens.
- Carregamento das cenas em cores naturais (RGB) diretamente do arquivo remoto, sem
  necessidade de baixar o arquivo inteiro.
- Comparação simples entre duas datas (Anterior/Posterior).

### Compatibilidade
- A busca de imagens depende de um serviço gratuito de terceiros, sem garantia
  contratual de disponibilidade. Sem conexão, apenas essa janela é afetada —
  desenho, edição, régua e lugares salvos continuam funcionando normalmente.

## [0.11.1] — 2026-10-24

### Correções
- Corrigida a exportação de pasta ou de propriedade completa para KML/KMZ, que
  gerava um arquivo vazio (ou a mensagem "nada para exportar") quando os lugares
  nunca haviam sido movidos explicitamente pelo menu "Mover para pasta..." ou o
  projeto nunca havia sido salvo. A exportação passou a ler diretamente a árvore de
  camadas visível.
- As mensagens de erro na exportação agora diferenciam pasta inválida, pasta
  realmente vazia e falha ao ler um item específico.

## [0.11.0] — 2026-10-24

### Novidades
- Importação e exportação de arquivos KML/KMZ: marcador, linha, polígono (com anéis
  internos) e pastas aninhadas, com seleção dos elementos a importar, escolha da
  pasta de destino e detecção de arquivos já importados.
- "Salvar lugar como..." e "Enviar por e-mail..." passam a aceitar também o formato
  KMZ.

### Compatibilidade
- Um elemento do tipo MultiGeometry no KML é importado como vários lugares
  separados, já que cada lugar do GeoSketch corresponde a uma única geometria.
- Ícones personalizados do KML não são aplicados como imagem real do marcador nesta
  versão; apenas a referência é preservada.

## [0.10.0] — 2026-10-24

### Novidades
- Aderência (snapping) a vértices e segmentos de qualquer camada ao desenhar, com
  opção de ativar/desativar e ajustar a tolerância em pixels. Não se aplica ao
  Círculo nem à Régua.
- Entrada numérica de vértice por distância e azimute, ou por coordenadas, durante a
  criação e a edição de lugares.
- Destaque visual do vértice durante o arraste também na edição de um lugar já
  existente (antes disponível apenas na criação).

### Compatibilidade
- Desfazer/Refazer (Ctrl+Z/Ctrl+Y) continua limitado à edição de vértices dentro de
  uma sessão aberta; não desfaz a criação ou a exclusão de uma feição inteira.

## [0.9.0] — 2026-10-24

### Novidades
- Pastas e subpastas persistentes para organizar os lugares, guardadas dentro do
  próprio GeoPackage (sobrevivem mesmo sem salvar o projeto do QGIS).
- Criar, renomear e excluir pastas; mover lugares entre pastas pelo menu "Mover para
  pasta..." ou por arrastar-e-soltar.
- Modelo reutilizável de propriedade rural (Sede, Área do Imóvel, APP, Reserva
  Legal, Nascentes, Outros).
- Mostrar/ocultar uma pasta inteira.
- Pesquisa de lugares por nome, com navegação direta até a feição encontrada.

### Compatibilidade
- O arrastar-e-soltar entre pastas é registrado no GeoPackage ao salvar o projeto,
  não em tempo real a cada movimento; por isso a ação "Mover para pasta..." garante
  o registro imediato.

## [0.8.0] — 2026-10-24

### Novidades
- Desfazer/Refazer (Ctrl+Z/Ctrl+Y) para operações de vértice, na criação e na edição
  de lugares existentes.
- Botão "Ir para coordenadas" e ação "Ir para" no menu de lugares, levando o mapa
  diretamente até a feição selecionada.
- Botão de tela cheia na barra de ferramentas.

### Melhorias
- Falhas ao salvar ou excluir um lugar passam a ser registradas no painel nativo de
  Mensagens de registro do QGIS.

## [0.7.0] — 2026-10-24

### Novidades
- Seleção, arraste e exclusão de um vértice individual durante a criação de linhas e
  polígonos.
- Extensão de uma linha ou polígono já existente a partir do último vértice, na
  janela Editar.

### Correções
- Corrigidas falhas silenciosas ao renomear, salvar descrição ou mover um vértice de
  um lugar, que não avisavam o usuário quando a gravação no GeoPackage falhava.
- Corrigida a exclusão de lugares para avisar quando a tabela correspondente não
  pôde ser removida do GeoPackage.

## [0.6.0] e versões anteriores

Estado herdado do projeto, anterior ao início do processo formal de versionamento
registrado a partir da 0.7.0. Não há registros suficientes para reconstruir o
conteúdo detalhado dessa fase, portanto nenhuma descrição foi adicionada aqui.
