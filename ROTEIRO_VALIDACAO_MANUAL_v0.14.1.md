# Roteiro de validação manual — v0.14.1 (QGIS 3.44.15)

Substitui `ROTEIRO_VALIDACAO_MANUAL_v0.14.0.md` para os itens de Círculo e SRC do
Caminho — os outros itens daquele roteiro (abas 3D, barra simplificada, histórico de
imagens suspenso, regressão geral) continuam válidos e não precisam ser repetidos se já
foram confirmados na 0.14.0.

Pré-requisito: instalar o ZIP de `releases/v0.14.1/earth_tools_v0.14.1.zip` (não o da
0.14.0) num QGIS 3.44.15 limpo.

**Importante — o motivo do bug anterior ter passado sem ser detectado:** a causa raiz só
aparece quando o **projeto está num SRC projetado** (ex.: SIRGAS 2000/UTM — o caso comum
de uso real deste plugin no Brasil). Testar só com um projeto em WGS84 (graus) não
reproduz o defeito. Por isso os passos abaixo pedem explicitamente para configurar um SRC
projetado antes de testar.

Marque cada item como OK / FALHOU ao executar de fato. Se algo falhar, pare e registre o
comportamento observado (prints de tela ajudam) antes de continuar.

## 0. Preparação

- [ ] Abrir o QGIS 3.44.15, criar um projeto novo.
- [ ] **Propriedades do Projeto > SRC**: definir um SRC **projetado em metros** (ex.:
  `EPSG:31983` — SIRGAS 2000 / UTM zona 23S, ou o SRC/UTM correto da sua região).
  Confirmar no rodapé da tela que o SRC do projeto é esse.
- [ ] Navegar o mapa até uma área conhecida (não precisa ter imagem de fundo).

## 1. Círculo — sem NaN, circunferência completa

- [ ] Abrir a **Régua**, ir para a aba **Círculo**.
- [ ] Clicar para definir o **centro**.
- [ ] Mover o mouse: a prévia deve mostrar uma **circunferência inteira** (contorno +
  preenchimento leve), não só uma linha reta do centro até o cursor.
- [ ] Clicar de novo para fixar a **borda** (raio).
- [ ] Confirmar que o círculo completo permanece desenhado no mapa.
- [ ] Conferir os três valores no painel:
  - **Raio**: um número plausível, não vazio.
  - **Circunferência**: ≈ 2π × raio.
  - **Área**: **um número, não "NaN"** — este é o ponto central desta correção. Confirmar
    visualmente que o campo mostra um valor numérico de verdade.
  - Confirmar que Área ≈ π × raio².
- [ ] Zoom in/out algumas vezes: o círculo continua completo, sem deformar.
- [ ] Desenhar um círculo bem maior (vários km de raio) e repetir as checagens acima.
- [ ] Clicar em **Salvar**, confirmar que a feição salva no painel Camadas também é um
  círculo completo (abrir a camada e olhar a geometria no mapa).
- [ ] Clicar em **Limpar**: o círculo e a linha do raio desaparecem do mapa.
- [ ] **Repetir o teste do círculo com o projeto em EPSG:4326 (WGS84/graus)** para
  confirmar que o caso que já funcionava antes continua funcionando.

## 2. Novo Caminho — campo de SRC/CRS

- [ ] Com o projeto ainda no SRC projetado (passo 0), clicar no botão **Caminho** da
  barra principal (não a Régua — a janela "Novo Caminho").
- [ ] Confirmar que existe o campo **"SRC/CRS da camada de saída:"**, logo abaixo da
  caixa de aderência, mostrando o código EPSG do SRC do projeto.
- [ ] Clicar no seletor e escolher um **SRC diferente** (outro projetado em metros, ou
  WGS84 para contraste) — confirmar que o diálogo nativo do QGIS abre normalmente.
- [ ] Desenhar um caminho de 3–4 vértices no mapa.
- [ ] Concluir o desenho (botão direito, duplo clique, ou "Concluir desenho") e clicar
  **OK**.
- [ ] No painel Camadas, selecionar a camada criada e confirmar o SRC dela (barra de
  status inferior, ou Propriedades > Informações): deve ser **exatamente o SRC escolhido
  no seletor**, não o do projeto original (a menos que tenham coincidido de propósito).
- [ ] Abrir a tabela de atributos / usar a ferramenta de identificação para olhar as
  coordenadas de um vértice e confirmar que fazem sentido no SRC escolhido (números em
  metros se escolheu um SRC projetado; em graus se escolheu um geográfico) — não os
  mesmos números do SRC original com uma etiqueta trocada.
- [ ] Repetir sem tocar no seletor (deixando o SRC do projeto): o caminho deve salvar
  normalmente nesse SRC, sem erro.

## 3. Caminho + Buffer (confirma a utilidade do SRC escolhido)

- [ ] Usando a camada de caminho salva num SRC projetado (passo 2), abrir **Processar >
  Caixa de ferramentas > Vetor Geral > Buffer**.
- [ ] Selecionar essa camada como entrada, digitar uma distância em metros (ex.: `10`).
- [ ] Confirmar que o resultado é uma faixa de ~10 m ao redor do caminho, visualmente
  coerente (não um buffer absurdamente grande/pequeno por confusão de unidade/grau).

## 4. Adicionar por medida (distância/azimute) — mesma causa raiz

- [ ] Com o projeto no SRC projetado, abrir **Novo Caminho** novamente e começar a
  desenhar (pelo menos 1 vértice no mapa).
- [ ] Ir para a aba **"Adicionar por medida"**, escolher o modo distância/azimute,
  digitar uma distância (ex.: `100` metros) e um azimute (ex.: `45`), clicar em
  adicionar.
- [ ] Confirmar que o novo vértice aparece no mapa, numa posição plausível (a ~100 m do
  último vértice, na direção nordeste) — **não em branco, não fora da área visível, não
  travando a janela**.
- [ ] Repetir o mesmo na janela **Novo Polígono**.

## 5. Regressão rápida

- [ ] Criar um marcador e um polígono normalmente (sem usar SRC diferente) e confirmar
  que salvam sem erro.
- [ ] Confirmar que as abas **Linha**, **Caminho** (sem trocar SRC) e **Polígono** da
  Régua continuam funcionando como antes.
- [ ] Reabrir o projeto salvo e confirmar que todas as camadas criadas neste roteiro
  (inclusive as com SRC diferente) continuam aparecendo corretamente, no SRC certo.

## Registro do resultado

Preencher o resultado real (não o esperado) de volta para quem conduziu esta correção.
Só depois da confirmação dos itens 1 e 2 (os dois problemas relatados) esta versão pode
ser considerada aprovada.
