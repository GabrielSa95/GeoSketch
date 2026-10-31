# GeoSketch — plugin QGIS

Barra de ferramentas que reproduz o fluxo de trabalho do Google Earth Pro dentro
do QGIS: marcador, polígono, caminho e régua, sem o usuário precisar criar
camada, escolher SRC, definir campos ou alternar o modo de edição.

## Instalação

1. No QGIS: **Complementos > Gerenciar e Instalar Complementos > Instalar a partir do ZIP**
2. Escolha o arquivo `earth_tools_vX.Y.Z.zip` baixado
3. Clique em **Instalar Complemento**
4. A barra aparece na parte de cima. Se não aparecer: **Ver > Barras de Ferramentas > GeoSketch**

Instalação manual (para distribuir na rede da empresa): copie a pasta
`earth_tools` para dentro de

- Windows: `C:\Users\SEU_USUARIO\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
- Linux: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
- macOS: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`

Depois reinicie o QGIS e ative em Complementos > Gerenciar.

## Os botões

| Ícone | O que faz |
|---|---|
| Seta (nativo do QGIS) | "Selecionar feições" - a mesma ferramenta nativa do QGIS, só também disponível nesta barra. |
| Marcador | Abre a janela Novo Marcador. Clique no mapa **ou** digite latitude/longitude. |
| Polígono | Abre a janela Novo Polígono. Clique os cantos; a aba Medidas mostra área e perímetro ao vivo. |
| Caminho | Igual ao polígono, mas em linha aberta, com comprimento ao vivo. |
| Círculo | Abre a Régua já na aba Círculo (mesma ferramenta - não existe um "círculo salvo" separado da medição). |
| Régua | Abas Linha, Caminho, Polígono e Círculo, com troca de unidade e botão Salvar. |
| Calculadora | Abre a Calculadora de área e distância (ver seção própria abaixo). |
| Paleta | Abre o Gerenciador de Estilos para o(s) lugar(es) selecionado(s) no painel Camadas. |
| Pasta | Cria uma pasta nova para organizar lugares (ver "Organizando em pastas"). |
| Globo | Abre o Google Maps no navegador, na mesma vista e coordenada do mapa. |
| Alvo | "Ir para coordenadas": digita latitude/longitude e centraliza o mapa. |
| Mapa com seta | Abre a Exportação de mapas (ver seção própria abaixo). |

## Menu de contexto da camada (botão direito num lugar, no painel Camadas)

Desde esta versão, as ações do plugin ficam organizadas num único submenu
**"GeoSketch"**, por categoria (em vez de soltas, todas juntas, na raiz do menu):

- **Editar..., Ir para, Mover para pasta..., Estilo...** - no topo, sem categoria própria.
- **GEOPROCESSAMENTO**: Gerar Buffer..., Unir polígonos..., Dividir polígono..., Recortar
  com..., Diferença... (ver seção "Geoprocessamento" abaixo).
- **MEDIÇÕES**: Calcular medidas... (abre a Calculadora já com este lugar escolhido).
- **VALIDAÇÃO**: Validar geometria... (abre o Validador já com este lugar marcado).
- **EXPORTAÇÃO**: Salvar lugar como..., Enviar por e-mail..., Exportar mapa... (abre a
  Exportação de mapas já com a extensão ajustada a este lugar).

**Excluir** continua **fora** do submenu, direto na raiz do menu de contexto - por ser uma
ação destrutiva, não fica misturada com as demais.

## Painel "GeoSketch - Propriedades"

Painel lateral (ancorável; mostrar/ocultar em **Vetor > GeoSketch > GeoSketch -
Propriedades**) que mostra, para o lugar selecionado no painel Camadas: nome,
tipo, área, perímetro/comprimento, SRC e situação da validação - sempre lidos da
geometria real no momento da exibição, atualizados automaticamente ao trocar a seleção ou
ao editar/estilizar o próprio lugar. Os botões **Calcular medidas**, **Alterar estilo...**,
**Validar geometria...** e **Exportar geometria...** abrem as mesmas janelas já descritas
nas seções abaixo, pré-selecionadas no lugar mostrado no painel.

## Geoprocessamento (Fase F)

As ações abaixo ficam dentro de **GeoSketch > GEOPROCESSAMENTO** no menu de
contexto (ver seção anterior) - o caminho de clique mudou de lugar, a lógica de cada uma
não mudou.

Botão direito num ou mais lugares, no painel Camadas, > **Gerar Buffer...**: cria um
polígono de Buffer usando o algoritmo nativo do QGIS Processing (`native:buffer`).

- Funciona em marcador, caminho ou polígono - qualquer combinação, inclusive vários tipos
  ao mesmo tempo (selecione várias camadas antes de clicar).
- **Distância** e sua unidade; **Número de segmentos** (suaviza curvas); **SRC de
  processamento** (precisa ser projetado em metros - um SRC geográfico é rejeitado com
  aviso claro, nunca calcula em graus); **SRC de saída** (pode diferir do de
  processamento; a geometria é transformada de verdade, não só reclassificada);
  **Dissolver resultados** (só habilitado com 2+ lugares selecionados - combina tudo num
  único polígono); estilo do resultado; pasta de destino.
- O(s) lugar(es) de origem nunca são alterados - o Buffer sempre cria uma camada nova no
  `Meus Lugares.gpkg`, exatamente como qualquer outro lugar do plugin.
- **Buffer negativo**: uma distância negativa encolhe o polígono para dentro, em vez de
  expandir - só faz sentido geometricamente em polígonos.

Botão direito em 2+ polígonos selecionados > **Unir polígonos...**: combina numa única
geometria (`QgsGeometry.unaryUnion`). Nome, SRC de saída, estilo e pasta de destino;
origens preservadas.

Botão direito num único polígono > **Dividir polígono...**: desenhe no mapa a linha de
corte, clique em **Pré-visualizar divisão** para ver quantas partes resultariam (sem
gravar nada), depois **Confirmar divisão**. O polígono original só é removido depois de
as partes novas terem sido gravadas com sucesso. Se a linha não atravessar o polígono de
um lado ao outro, a janela avisa e não altera nada.

Botão direito em qualquer lugar > **Recortar com...**: escolha a camada a recortar e um
polígono para servir de máscara (dois seletores na própria janela) - mantém só a parte da
primeira que está **dentro** da máscara. Funciona com marcador, caminho ou polígono como
entrada.

Botão direito em qualquer lugar > **Diferença...**: escolha a camada base e a que será
subtraída - mantém a parte da base que está **fora** da outra (o oposto do Recortar).

Em todos os casos de Recorte/Diferença/União/Divisão, as camadas de origem nunca são
apagadas ou alteradas (exceto a divisão, que remove o polígono original só depois de
confirmar e gravar as partes com sucesso) - o resultado é sempre um lugar novo.

**Não implementado nesta fase, por já estar coberto por outra ferramenta (evitar
duplicação):** "Interseção" como ferramenta separada (o Recorte já cobre o caso prático de
sobrepor dois polígonos para este plugin); "Eliminar sobreposições" (ferramenta pensada
para editar uma camada com muitas feições vizinhas - não se aplica à arquitetura de "um
lugar = uma camada" deste plugin).

## Calculadora de área e distância

Botão **Calculadora** da barra, menu **Vetor > GeoSketch > Calculadora de área e
distância...**, ou botão direito num lugar > **GeoSketch > Calcular medidas...**
(já abre com este lugar escolhido): escolha qualquer
lugar já salvo num combo (sem precisar abrir "Editar...") e veja Área+Perímetro
(polígono) ou Comprimento (caminho), com troca de unidade e botão **Copiar resultado**
(vai para a área de transferência). O valor é recalculado a cada vez que você escolhe o
lugar na lista ou clica em "Atualizar lista" — não é uma medição "ao vivo" vinculada à
geometria: se a geometria mudar enquanto esta janela estiver aberta, reselecione o lugar
para reler o valor atual.

## Gerenciador de Estilos

Botão **Paleta** da barra (lugares selecionados no painel Camadas), ou botão direito em um
ou mais lugares > **GeoSketch > Estilo...**: cor/espessura/opacidade de linha e
preenchimento (mesma aba usada em Novo/Editar), aplicada em todos os lugares selecionados
de uma vez. **Salvar como...** guarda um preset nomeado reutilizável em **qualquer
projeto** (fica salvo nas configurações do QGIS, não neste projeto específico); **Carregar**
e **Excluir** completam a biblioteca de presets. Nunca altera a geometria.

## Validador de geometrias

Menu **Vetor > GeoSketch > Validar geometrias...**, ou botão direito num lugar >
**GeoSketch > Validar geometria...** (já marca este lugar): verifica os lugares
selecionados ou todos os do projeto — geometria vazia/inválida (com a mensagem e a
localização exatas do QGIS), vértices duplicados consecutivos, anel não fechado,
fora de uma extensão de referência (opcional, usa a extensão atual do mapa) e
sobreposição entre polígonos (opcional, pode ser lento com muitos lugares). Mostra quantas
geometrias foram verificadas/válidas/com problema, numa tabela; duplo clique leva até a
geometria no mapa. **Corrigir (criar cópia)...** só está disponível para geometria
inválida (usa `QgsGeometry.makeValid()`) — sempre pede confirmação, sempre cria uma cópia
nova com "(corrigido)" no nome, **nunca apaga nem altera o lugar original**.

## Exportação de mapas

Botão **Mapa com seta** da barra, menu **Vetor > GeoSketch > Exportar mapa...**,
ou botão direito num lugar > **GeoSketch > Exportar mapa...** (já ajusta a
extensão a este lugar): título, nome da propriedade,
formato (A4/A3), orientação, extensão (a atual do mapa, ou ajustada a um lugar
específico — nesse caso, a área/perímetro ou comprimento dele entra automaticamente no
rodapé), SRC utilizado, data de geração, e as opções Legenda/Barra de escala/Seta de
norte. **Pré-visualizar** abre o **Layout Designer nativo do QGIS** (o mesmo de Projeto >
Layouts), onde dá para ajustar qualquer detalhe antes de exportar. **Exportar PDF...** e
**Exportar PNG...** geram o arquivo de verdade, com todos os elementos escolhidos — não é
uma captura crua da tela do mapa.

Desde esta versão, os botões **Tela cheia** e **Pesquisar lugares** saíram da barra (e o
histórico de imagens de satélite, da versão) para priorizar desenho, medição e
geoprocessamento. Tela cheia continua disponível pelo menu nativo **Ver > Tela cheia** do
próprio QGIS - não foi um recurso exclusivo deste plugin.

## Como desenhar e corrigir

- **Clique simples** adiciona um vértice.
- **Botão direito** ou **duplo clique** encerra o desenho.
- **Clique e arraste um vértice já colocado** move ele; soltar confirma a posição.
- **Botão direito sobre um vértice** apaga só aquele vértice, sem encerrar o desenho.
- **Backspace** apaga o último vértice.
- **Esc** cancela e começa de novo.
- **Ctrl+Z** desfaz e **Ctrl+Y** (ou Ctrl+Shift+Z) refaz a última mudança de vértice —
  tanto durante o desenho quanto editando um lugar já salvo (nesse caso, desfazer também
  regrava o arquivo, não é só visual).
- Clicar fora de qualquer vértice, na janela **Editar**, estende o desenho com um
  vértice novo no final.
- A janela fica aberta o tempo todo e pode ser arrastada para o lado, igual à do
  Google Earth. O botão OK só habilita quando há vértices suficientes.

## Aderência e entrada numérica

- Caixa **Aderência a vértices/segmentos**, no topo das janelas de criação e edição:
  ativada por padrão, adere o clique/arraste a um vértice ou trecho de qualquer camada
  do projeto. Um **X** magenta mostra onde aderirira antes de você clicar. Desative a
  caixa para desligar na hora. A tolerância é em **pixels de tela** (não em metros/graus),
  então o comportamento não muda com o SRC do projeto nem com o zoom. Não se aplica ao
  círculo nem à Régua, que mantêm o comportamento de sempre.
- Aba **Adicionar por medida**, em linhas e polígonos: acrescenta um vértice no final do
  desenho por **distância e azimute** (azimute em graus, a partir do Norte, sentido
  horário — a mesma convenção do rumo mostrado na aba Linha da Régua) ou por
  **coordenadas** (latitude/longitude). As medidas e a prévia no mapa atualizam na hora,
  igual a um clique manual, e entram na mesma pilha de desfazer/refazer (Ctrl+Z).

## Novo Caminho — SRC/CRS da camada de saída

A janela **Novo Caminho** tem o campo **"SRC/CRS da camada de saída:"**, logo abaixo da
caixa de aderência — o mesmo seletor nativo do QGIS usado nos parâmetros de SRC do
Processamento (ex.: Buffer, em Vetor Geral). Mostra o código EPSG e o nome do sistema
escolhido, e abre o diálogo nativo de escolha de SRC ao clicar.

- Começa no **SRC do projeto**. Se você não tocar nele, o caminho é salvo nesse SRC.
- Ao trocar para outro SRC, as coordenadas dos vértices são **de fato transformadas**
  (não é só a etiqueta do SRC que muda) antes de a feição ser gravada no
  `Meus Lugares.gpkg` — a camada salva já nasce no SRC escolhido.
- Para usar o resultado no **Buffer** do QGIS, escolha aqui um SRC **projetado em
  metros** (ex.: SIRGAS 2000/UTM da sua região) antes de concluir o desenho — um SRC
  geográfico (graus) faz o Buffer pedir a distância em graus, quase nunca o que se quer.
- Marcador e Polígono não têm este campo — continuam gravando em WGS84, sem mudança.
- A Régua também tem este seletor, só na aba **Caminho** (ver seção própria abaixo) —
  são duas janelas independentes, cada uma com seu próprio seletor e seu próprio
  resultado salvo.

### Os quatro CRS envolvidos (para não confundir)

Numa mesma criação de caminho, até quatro conceitos de "SRC" entram em jogo — são
independentes entre si:

1. **CRS do canvas/mapa**: o sistema em que o QGIS mostra o mapa agora (normalmente o
   mesmo do projeto). É nele que os cliques do mouse chegam como coordenadas.
2. **CRS de cálculo**: as medições de distância/área (comprimento mostrado na tela,
   raio/circunferência/área do Círculo) são sempre calculadas sobre o **elipsoide
   WGS84** internamente, não importa qual SRC o canvas ou a camada de saída usam —
   por isso o número de comprimento mostrado **não muda** se você só trocar o SRC de
   saída sem mover nenhum vértice.
3. **Unidade de exibição**: metros, pés, hectares etc. — só a formatação do número
   mostrado na tela. Trocar a unidade não muda nenhum dos outros três itens.
4. **CRS de armazenamento/saída**: o SRC escolhido no seletor "SRC/CRS da camada de
   saída" (Novo Caminho) ou "SRC do caminho" (Régua) — o único que afeta o que fica
   gravado no arquivo.

## Régua - SRC do caminho e uso no Buffer

Na aba **Caminho** da Régua, abaixo da medida de comprimento, há um seletor de **SRC do
caminho** — o mesmo seletor nativo do QGIS usado nos parâmetros de SRC das ferramentas de
Processamento (ex.: o SRC de saída do **Buffer**, em **Vetor Geral**). Mostra o código
EPSG e o nome do sistema escolhido, e abre o diálogo nativo de escolha de SRC ao clicar.

- Começa sempre no **SRC do projeto** (padrão inicial). Se você não tocar nele, o
  comportamento é esse: o Caminho é salvo nesse SRC, não em WGS84.
- A **unidade mostrada no campo Comprimento** (metros, pés, etc.) é só de exibição — não
  é o SRC de gravação. Trocar a unidade não muda o SRC do caminho, e trocar o SRC não
  muda a unidade mostrada.
- A medição em si (o valor de Comprimento) sempre usa o elipsoide WGS84 por baixo dos
  panos (nunca distância plana em graus), então o número mostrado não muda ao trocar o
  SRC do seletor — só muda o sistema de coordenadas em que a geometria final é gravada.
- Ao clicar em **Salvar**, a camada do caminho é criada no GeoPackage **já com o SRC
  escolhido declarado** (não reprojetada para WGS84 por baixo). Para usar no Buffer:
  1. Escolha no seletor um SRC **projetado em metros** (ex.: SIRGAS 2000 / UTM da sua
     região) — um SRC geográfico (graus) faz o Buffer pedir a distância em graus, o que
     quase nunca é o que se quer.
  2. Clique em **Salvar** e dê um nome ao caminho.
  3. No painel Camadas, clique com o botão direito na camada salva > **Propriedades** (ou
     passe o mouse) para confirmar o SRC — deve ser o mesmo escolhido no seletor.
  4. Abra **Processar > Caixa de ferramentas > Vetor Geral > Buffer**, escolha essa
     camada como entrada e digite a distância **na mesma unidade linear do SRC escolhido**
     (metros, na maioria dos SRC projetados do Brasil).

## Importar e exportar KML/KMZ

Desde a versão 0.13.0, **Importar KML/KMZ...** e **Exportar pasta para KML/KMZ...** não
têm mais botão na barra principal (para deixá-la mais curta) — continuam disponíveis em
dois lugares, sem duplicar a lógica entre eles:

- Menu **Vetor > GeoSketch**: igual a antes, pede o arquivo (importar) ou a
  pasta/escopo (exportar) na própria janela.
- **Botão direito numa pasta**, no painel Camadas: **Importar KML/KMZ para esta
  pasta...** e **Exportar esta pasta para KML/KMZ...** abrem a mesma janela já com
  aquela pasta escolhida e travada (clicou, já era). Se a pasta fizer parte de um
  **Modelo de propriedade rural**, aparece também **Exportar propriedade completa...**,
  que exporta a pasta-mãe inteira (Sede, APP, Reserva Legal...) mesmo clicando numa
  subpasta.

Em qualquer um dos caminhos: escolha o arquivo, confira a lista de marcadores/caminhos/
polígonos encontrados (tudo marcado por padrão, exceto o que já foi importado antes nesta
mesma pasta de trabalho — identificado pela geometria e nome, não só pelo nome do
arquivo) e clique em Importar. Pastas e subpastas do KML são recriadas dentro da pasta
escolhida. Elementos que o plugin não sabe representar (como `NetworkLink` ou
sobreposições de imagem) aparecem listados, mas não travam a importação do resto do
arquivo. Exportar uma pasta inclui as subpastas; para exportar **um único lugar**, use
botão direito na camada > **Salvar lugar como...** (ou **Enviar por e-mail...**), que
também aceita KMZ.
- Nomes, descrições e as cores/largura de linha e preenchimento suportadas são
  preservados nos dois sentidos. **Ícones personalizados do Google Earth e alguns
  recursos visuais específicos dele não têm equivalente garantido** neste formato —
  não é uma reprodução pixel a pixel.
- Um polígono do KML com `MultiGeometry` (várias partes numa única feição) vira vários
  lugares separados na importação (ex.: "Nome (1)", "Nome (2)"), já que cada lugar do
  plugin é sempre uma única geometria simples.

## Onde os dados ficam

Tudo vai para um único arquivo `Meus Lugares.gpkg`, com três camadas dentro
(Marcadores, Caminhos, Polígonos). O arquivo fica na pasta do projeto salvo; se
o projeto ainda não foi salvo, vai para `Meus Lugares QGIS` na pasta do usuário.
Não é camada temporária — não se perde ao fechar o QGIS.

O campo **Pasta** faz o papel das pastas de Meus Lugares (ex.: "Chácara Recanto
Vitória"). Ele sugere as pastas já usadas conforme você digita.

Para mandar para quem usa Google Earth: botão direito na camada >
**Exportar > Salvar feições como** > formato **KML**.

## Unidades disponíveis

Comprimento: metros, quilômetros, centímetros, pés, jardas, milhas, milhas náuticas.
Área: metros quadrados, hectares, quilômetros quadrados, **alqueire paulista**,
**alqueire mineiro**, acres, pés quadrados.

Todas as medições são feitas sobre o elipsoide WGS84, não em projeção plana, então
a área não muda conforme o SRC do projeto.

## Organizando em pastas

- Botão **Pasta** (ou botão direito no painel Camadas > **Adicionar > Pasta**) cria uma
  pasta. Clicar com uma pasta já selecionada cria uma subpasta dentro dela.
- **Modelo de propriedade rural** (botão direito > Adicionar): cria de uma vez a pasta do
  imóvel com as subpastas padrão **Sede, Área do Imóvel, APP, Reserva Legal, Nascentes e
  Outros**.
- Para mover um lugar entre pastas: **arraste e solte** no painel Camadas (recurso nativo
  do QGIS) **ou** botão direito no lugar > **Mover para pasta...** — essa segunda opção
  grava a mudança imediatamente; o arrastar-e-soltar fica gravado no arquivo quando o
  projeto é salvo.
- Mostrar/ocultar uma pasta inteira: desmarque a caixinha da pasta na árvore, como em
  qualquer grupo do QGIS — esconde todos os lugares dentro dela no mapa.
- Renomear uma pasta: duplo clique no nome, como em qualquer grupo do QGIS.
- Excluir uma pasta (botão direito > Excluir, ou tecla Delete) pede confirmação e apaga
  os lugares que estiverem dentro dela do arquivo `Meus Lugares.gpkg` — leia o aviso
  antes de confirmar.
- A organização em pastas fica guardada dentro do próprio `Meus Lugares.gpkg` (não só no
  arquivo de projeto do QGIS), então sobrevive mesmo se você fechar o QGIS sem salvar o
  projeto.

## Limitações conhecidas

- O campo Descrição aceita HTML (link e imagem), mas o QGIS só mostra formatado
  se você configurar um mapa de identificação HTML na camada.
- Pastas criadas pelo plugin só reconhecem como "pasta-mãe" outra pasta também criada
  pelo plugin. Se você selecionar um grupo de camadas qualquer do QGIS (não criado pelo
  botão Pasta) ao criar uma pasta nova, ela nasce na raiz, não dentro desse grupo.
- A ordem dentro de uma mesma pasta (qual lugar vem antes de qual) não é garantida após
  reabrir o projeto — só a relação de "está dentro de qual pasta" é preservada.
- **Histórico de imagens de satélite (Sentinel-2/Landsat) suspenso nesta versão:** a busca
  e o carregamento de imagens de satélite, disponíveis nas versões 0.12.0 a 0.13.1, foram
  retirados para priorizar desenho, medição e geoprocessamento. O código permanece
  preservado no histórico do Git (branch `feature/historico-imagens-suspenso`, a partir da
  marca `pre-fase2-historico-imagens`) para retomada futura, se decidido.

## Requisitos

QGIS 3.44 ou superior (`qgisMinimumVersion` em `metadata.txt`) - é a única versão com
testes empíricos confirmados no histórico deste projeto (ver `CHANGELOG.md`, a partir da
0.14.1). Uma versão mínima menor (3.22) foi declarada em versões anteriores sem
comprovação equivalente registrada - corrigido nesta auditoria para não declarar
compatibilidade não testada.

## Desenvolvimento e autoria

O GeoSketch é desenvolvido e mantido por Gabriel Alberto.

Durante o desenvolvimento do projeto foram utilizadas ferramentas de inteligência
artificial como apoio à programação, revisão de código, identificação de erros,
documentação e aprimoramento das funcionalidades.

A responsabilidade pelo projeto, suas decisões técnicas, manutenção e evolução é de seu
desenvolvedor.
