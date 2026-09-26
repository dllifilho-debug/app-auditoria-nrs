# Contexto do projeto para sessões futuras

App Streamlit que analisa fotos de inspeção de segurança do trabalho e emite laudo
de não conformidades enquadrado nas Normas Regulamentadoras brasileiras.

Usuário: engenheiro de segurança do trabalho. Auditorias reais chegam a **100 fotos**.
Conta Groq no **plano gratuito**. Publicado em `auditoria-nrs-08.streamlit.app`, a partir
do `main` do repositório GitHub `dllifilho-debug/app-auditoria-nrs`.

Fluxo de trabalho agora passa por PR: branch `claude/...`, testes, navegador, PR contra
`main`, e só mergear — nesse ponto ou quando o usuário pedir — depois disso o Streamlit
Cloud redeploya sozinho em ~1-2 min (confirme pelo hash em "Versão em execução" na
barra lateral). O repositório tem **"Automatically delete head branches" ligado** desde
01/09: a branch some sozinha no merge, não precisa limpar depois. **Antes desta sessão, `main` estava travado num protótipo antigo e a
reescrita inteira vivia numa branch nunca mergeada** — se `git diff main...HEAD` um dia
mostrar milhares de linhas de novo, desconfie do `main` local antes de concluir que o
`main` remoto está desatualizado (ver armadilha do `git fetch` abaixo).

**Sem acesso de rede à Groq a partir desta sessão remota.** O domínio `groq.com`
**inteiro** é bloqueado pela política de egress do container, não só a API — medido em
10/09 tentando ler os termos de uso: `EGRESS_BLOCKED`, e não 403 da API. A frase anterior
daqui dizia `api.groq.com`, o que fez supor que a documentação e os termos fossem
alcançáveis. Não são: **nada em groq.com se lê daqui**, nem doc, nem termos, nem console.
Isso significa: nada de `ClienteGroq` real aqui, só `ClienteDemonstracao` e testes da
camada determinística (roteador, dossiê, aferição). Testar com o modelo de visão de
verdade é sempre com o usuário, em produção, com fotos e laudos que ele manda de volta.

---

## COMECE POR AQUI — decisão em 16/09/2026: PAROU de iterar no parágrafo de pessoa/EPI

**Decisão do usuário, depois da quarta rodada (0 de 3, abaixo): parar de escrever mais
trava de prompt no parágrafo de pessoa do `PROMPT_OLHO`, e registrar o limite em vez de
persegui-lo.** `main` em `612824d` (PR #60, merge desta validação). 250 testes passam.

**Por quê.** Quatro rodadas seguidas nas MESMAS três fotos — 15/09 (sem vocabulário de
EPI), 16/09 pós-PR #57 (0/3), pós-PR #58 (1/3), pós-PR #59 (0/3) —, todas custando cota do
dia, sem lote de 5 novo desenhado na fila. A quarta não só não melhorou: **a regra 1 (mão
que segura aparece), que tinha segurado na rodada anterior, e a regra 4 (achado próprio
por pessoa), que não tinha sido nem confirmada nem contrariada antes, falharam agora —
as duas com o MESMO texto** desde o PR #58 — o que é variação de execução do modelo sobre
o prompt fixo, não regressão de código, e mais uma trava textual não tem como endereçar
isso sozinha. Escrever uma quinta trava cega, sem medir por que a regra 1 parou de
segurar, arrisca repetir o padrão já visto: regra nova resolve o caso que a motivou (foi
o que a trava do vão fez), regra antiga intocada falha na mesma rodada.

**O que isso significa na prática, a partir de agora:**
- **Nenhuma rodada nova agendada para o parágrafo de pessoa/EPI.** O `PROMPT_OLHO` fica
  como está no PR #59/#60: dentro do parágrafo de pessoa, o pedido do atributo (PR #57),
  as quatro regras contra as três alucinações (PR #58) e o reforço da regra do
  boné/capacete com critério checável (PR #59); fora dele, a trava do vão inexistente
  (também PR #59, no parágrafo de barreira/abertura). Sem trava adicional daqui em diante.
- **O limite fica registrado, não escondido.** Neste domínio estreito — parágrafo de
  pessoa, achado esparso —, o Olho variou rodada a rodada com o prompt fixo: a regra 1
  segurou na 3ª rodada e falhou na 4ª com o texto idêntico; a regra 4, sem confirmação nem
  contradição na 3ª, falhou na 4ª. Isso contradiz, aqui, o que a medição de 10/09
  estabeleceu para canteiro rico em achados ("o Olho não varia") — não generalize aquele
  achado para este parágrafo. Não medido: se a causa é o parágrafo ter ficado longo
  (4 regras + 1 reforço) ou limite do modelo em achado esparso.
- **O único ganho que sobrevive das quatro rodadas é a trava do vão inexistente** (n=1,
  segurou no único caso em que foi exercida). Fica, sem nova medição agendada — só o
  próximo lote de qualquer natureza que passe por uma foto com vão real ou fabricado dirá
  se ela generaliza.
- **Não há métrica de "quando retomar"** — isso ficaria sujeito à mesma armadilha do
  número que envelhece em silêncio se eu inventasse um gatilho agora. Retomar é decisão do
  usuário, não deste arquivo.
- **Próxima frente, quando o usuário quiser seguir**: qualquer item de "Em aberto" que não
  dependa de nova rodada nesta pergunta específica — por exemplo "área de corte sem
  barreira de acesso" (item inalcançável, não depende do Olho), ou remedir se o modelo
  ainda é o melhor disponível. **A hipótese do bigrama foi atacada em 18/09** — ver a
  seção logo abaixo — e cobre a família do `sem` e a da relação invertida; o particípio da
  negação ("sem trechos abertos") continua fora do que ela resolve, registrado lá.

O histórico completo da quarta rodada — o que regrediu, foto a foto, com a tabela e a
leitura da imagem real — está na seção de validação logo abaixo; este bloco só registra a
decisão de parar.

**A quarta rodada, nas MESMAS três fotos, saiu PIOR que a terceira: gabarito caiu de 1
para 0 de 3.** O achado mais importante não é sobre as travas novas — é que **as regras
1 e 4, cujo texto não foi tocado entre a terceira e a quarta rodada, regrediram**: a
regra 1 (mão que segura aparece) voltou a produzir a MESMA contradição interna que ela
existe para impedir ("segurando... com a mão direita" + "...as mãos não aparecem no
recorte", foto 2), e a foto 1 reproduziu a frase da invenção do boné **palavra por
palavra idêntica à da SEGUNDA rodada** (antes do PR #58), pior que a terceira rodada
(que já tinha corrigido a luva). Hash confirmado pelo usuário contra `c95bba3` antes de
rodar — não é versão errada. Ver a seção de validação logo abaixo.

**A única coisa que seguiu funcionando foi a trava do vão inexistente**: a foto 1 não
inventou mais abertura no piso (o pallet/régua de nivelamento não é mais lido como vão),
e a abertura na parede que ela relatou desta vez é REAL — confirmada na ampliação
(buraco com profundidade visível, bordas irregulares). É a primeira medição da trava
nova, e ela segurou no caso que a motivou.

**O que isso muda de leitura**: não dá mais para tratar "a regra X segurou" como fato
estável só porque ela segurou numa rodada. Regra 1 e regra 4 seguraram na terceira
rodada e falharam na quarta, com o MESMO texto — é variação de execução sobre o mesmo
prompt, não regressão de código. Isso contradiz, num domínio estreito (o parágrafo de
pessoa, achado esparso), o que a medição de 10/09 tinha estabelecido para fotos de
canteiro ricas em achados ("o Olho não varia"). Uma hipótese não medida: o parágrafo de
pessoa cresceu de 4 regras para 4 regras + 2 reforços na mesma sessão, e o texto mais
longo pode estar diluindo a atenção às regras que não mudaram — mas isso é hipótese, não
medição.

**Quatro rodadas nas mesmas três fotos, todas custando cota do dia**: 15/09 (sem
vocabulário de EPI, antes do PR #57), 16/09 pós-PR #57 (0 de 3, invenção), 16/09 pós-PR
#58 (1 de 3, primeira NC de EPI real do acervo), 16/09 pós-PR #59 (0 de 3, regras que
seguravam regrediram). **Decisão registrada no bloco acima: parar de iterar aqui.**

**O que mudou de método nestas quatro sessões, e vale mais que os lotes:**

- **A regra 3 caiu para o acervo histórico.** O engenheiro declarou em 13/09 que não tem
  a memória destas fotos — o que ele vê é a imagem, igual a mim. A régua (a)-(d) que a
  substitui está em *Em aberto → AUDITAR A FOTO CONTRA OS FATOS*, e ela é mais estreita de
  propósito: a imagem decide GEOMETRIA e PRESENÇA, não decide MATERIAL, NOME nem ESTADO.
  **Para lote NOVO, fotografado com ele em campo, a regra 3 continua inteira.**
- **O aceite de toda foto que preveja NC tem DUAS metades** — recuperação (o item chegou
  ao Analista) e laudo (a NC tem lastro visual). O `/critico` rejeitou três vezes por
  colapsá-las, e nos dois últimos lotes a diferença entre as duas foi o resultado.

---

## Contraprova visual de 26/09/2026 — o Diretor passa a ter a foto como segunda fonte (À ESPERA DE LOTE)

Pedido do usuário: "ainda está errando coisas bobas — as de leitura, do Diretor". O diagnóstico é
estrutural e está neste arquivo desde 11/09: **o Diretor confere a constatação contra o TEXTO do
Olho, nunca contra a imagem**, e o `fato` é o único ponto do pipeline que ninguém confere. Os erros
mais caros do histórico passaram por aí limpos — VÃO INEXISTENTE (seis ocorrências, inclusive a de
PLANO errado de 24/09), "sem sapatas" sobre placa de base visível (24/09), cancela instalada e
aberta lida como ausente (26/09), boné numa cabeça descoberta (16/09). É a "confirmação fato a
fato" que a seção 7 da validação de 11/09 dizia faltar.

**O conserto**: `agente_contraprova` (`pipeline.py`), uma chamada de VISÃO depois do Gauntlet, só
para as NCs que sobreviveram. Recebe a imagem e as constatações como afirmações a REFUTAR (sem o
item de norma — julga a condição física, não o enquadramento), pede primeiro `visto` (o que há no
lugar, em que plano, se há profundidade, se a peça dada como ausente aparece) e só depois
`veredito`: `confirma|contradiz|nao_decide`. O prompt lista os quatro erros reais acima.
- **`contradiz` derruba**: vira veto, a constatação vai aos pontos de atenção com "verificar no
  local", e o parecer é corrigido (laudo vazio → texto de `_parecer_coerente`; com sobreviventes,
  o parecer é REFEITO pelo código a partir da mais grave que sobrou — o do Diretor foi escrito
  antes e costuma eleger justamente a NC refutada. A primeira versão só acrescentava uma frase, e o
  `/critico` rejeitou por classe de erro 4).
- **`nao_decide` MANTÉM** e fica na trilha. Derrubar por inconclusão trocaria falso positivo por
  achado que evapora (classe 5), e 16/09 mostrou o modelo preferindo não afirmar. O lote diz
  quantas inconclusivas eram NC real antes de endurecer.
- **Resposta ilegível mantém** ("contraprova sem resposta"); erro de cota/rede sobe, como em todo
  agente.
- **A trilha registra os quatro desfechos** — lição da "rede que só registra quando falha".
- Perfil Padrão e Máximo ligam; Rápido desliga (`Configuracao.usar_contraprova`).

**Custo**: uma chamada de visão a mais por foto COM NC. Estimado (não medido) em ~2.500 tokens;
`CUSTO_POR_FOTO` do Padrão foi de 7.100 para 9.600 como teto. No limite de 200.000/dia isso tira
~5 fotos/dia (de ~25 para ~20) se toda foto tiver NC.

**Hipótese não medida, e é a que decide se isto funciona**: é o MESMO modelo de visão sobre a
MESMA imagem. Se perguntado de frente ele repetir a leitura errada, a rede não pega nada. Oito
testes travam o mecanismo (falham no código antigo; 302 no total); nenhum teste alcança o comportamento do
modelo. **O que o lote tem de responder**, lido na linha "Contraprova visual" da trilha: (a) nas
fotos de erro conhecido — `8 PAV. CANCELA CREMALHEIRA SEM SINALIZAÇÃO`, a foto 4 (`5af17330…`, vão de
parede lido como piso) e a 6 (`WhatsApp Image 2026-05-05 at 14.41.18`, "sem sapatas") do lote de andaime, a contraparte `6 PAV. TRABALHADORES
SEM DOCUMENTAÇÃO` —, se sai `contradiz`; (b) nas NCs reais — a âncora `13 PAV. PEÇO ELEVADOR SEM
PROTEÇÃO` e o controle `13 PAV. PEÇO ELEVADOR SEM PROTEÇÃO E SINALIZAÇÃO` de 26/09 —, se sai `confirma` e a NC fica (o risco simétrico:
contraprova severa derrubando NC real); (c) quantas saem `nao_decide`.

**MEDIDO no lote de 26/09 — ver a seção de validação logo abaixo.**

---

## Lote de validação da contraprova de 26/09/2026 — pega o vão inexistente, e um defeito do próprio conserto

`main` em `545788c` (PR #77) pelo comportamento — o `18.11.13` da cancela não saiu —; **hash não
lido na barra lateral**. **6 laudos, 6 NCs, 0 não auditadas, 1 ciclo em todos.** Fotos na ordem
dos laudos: `WhatsApp Image 2026-05-05 at 14.41.18`, `5af17330…`, `8 PAV. CANCELA CREMALHEIRA SEM
SINALIZAÇÃO`, `6 PAV. TRABALHADORES SEM DOCUMENTAÇÃO`, `13 PAV. PEÇO ELEVADOR SEM PROTEÇÃO` e
`13 PAV. PEÇO ELEVADOR SEM PROTEÇÃO E SINALIZAÇÃO`. As fotos 3, 4 e 6 foram abertas no acervo; os
dossiês das fotos 3 e 6 foram reproduzidos sem rede a partir dos fatos dos laudos.

| # | Foto | Laudo | Contraprova | Na imagem |
|---|---|---|---|---|
| 1 | `14.41.18` | `18.9.4.2` crítica + `18.12.13` "sem sapatas" alta | confirma as duas | guarda-corpo: conteúdo certo e **item certo** (a trava do `18.12.15.2` de 24/09 segurou); "sem sapatas": FALSO, placa de base visível (decidido em 24/09, não reaberto) |
| 2 | `5af17330` | `18.9.2` proposto | **contradiz** → 0 NC | ✅ vão de parede lido como piso |
| 3 | `8 PAV. CANCELA` | `NR-08 8.3.3.2` "umidade" média | confirma | ❌ **zero risco curado roteado**, item da busca textual; mancha escura em laje de obra |
| 4 | `6 PAV. TRABALHADORES` | `18.9.2` proposto + `NR-10 10.10.1` + `NR-11 11.3.3` | **contradiz** o vão; confirma os dois | ✅ piso contínuo. Os sacos encostados: real. O "painel elétrico coberto por papelão" é um papelão preso na parede — NOME, fica ABERTO |
| 5 | `13 PAV.` (âncora) | `18.9.2` crítica | confirma | ✅ |
| 6 | `13 PAV. … E SINALIZAÇÃO` | `18.9.2` proposto → **0 NC** | **contradiz**: "vão de porta na parede, não no piso" | ⚠️ certo sobre o PLANO, e o laudo perdeu uma NC crítica real — vão de porta aberto para o poço |

**(a) VÃO INEXISTENTE: 2 de 2 contraditos** (fotos 2 e 4) — a classe mais cara do histórico,
pega pela primeira vez. **(b) NC real: a âncora ficou; o controle da foto 6 caiu** — o risco
simétrico, e pelo mecanismo que ninguém previu: não contraprova severa, mas contraprova CERTA
aplicada por um código que só sabia retirar. **(c) `nao_decide`: 0 em 9.** A hipótese de risco
declarada se confirmou num caso: o "sem sapatas" foi ratificado — mesmo modelo, mesma leitura.
**Medi X, afirmo Y**: são 9 veredictos em 6 fotos; nada disso é taxa.

**Consertos do mesmo dia, sem lote:**
- **`outro_plano`** — quarto veredito da contraprova, com `plano` e `constatacao_corrigida`. A NC
  não cai: passa ao item que cobre o plano visto (`PLANOS_DO_ITEM` + `ITENS_EQUIVALENTES`:
  `18.9.2` só piso → `8.3.2.2` piso e parede), com a constatação corrigida, o rótulo "Abertura no
  piso" apagado, o item de piso fora dos complementos e o parecer refeito. Teto não tem item
  (é o "não tetos" de 14/09) e cai como antes; sem reescrita, cai também. Reproduzido: o
  `8.3.2.2` estava em D2 do dossiê da foto 6. **Mudança de prompt — só o lote diz se o modelo
  separa "contradiz" de "outro_plano".**
- **`ITENS_DE_DESEMPENHO_DA_EDIFICACAO`** (`dossie.py`) — `NR-08 8.3.3.1`/`8.3.3.2` fora da busca
  textual: especificação da edificação acabada (impermeabilização, resistência ao fogo,
  isolamento), que foto de obra não evidencia. Lista explícita porque `impermeabiliz` casa 11
  itens da base e só esses dois são especificação — medido. Reproduzido: a mancha de umidade da
  foto 3 deixa o `8.3.3.2` fora do dossiê.

Seis testes novos, todos falham no código anterior. **313 testes passam.**

---

## Cancela aberta no embarque de 26/09/2026 — o sinal que provava o contrário do item (CONSERTADO, sem lote)

`NR-18 18.11.13` cobra que a cancela seja **instalada** ("deve ser instalada barreira (cancela)
que tenha, no mínimo, 1,8 m"); cancela ABERTA está instalada. O sinal `"cancela aberta"` de
`torre_elevador_sem_cancela` era prova do oposto do que o item exige — e foi ele que levou a foto
`8 PAV. CANCELA CREMALHEIRA SEM SINALIZAÇÃO` a `18.11.13` crítica em 26/09. O perigo real de
cancela aberta é abri-la **sem a cabine no nível**, que é o `18.11.13.1` (intertravamento) e o
`NR-11 11.1.2` — e a foto quase nunca decide o intertravamento.

**Conserto**: o sinal saiu. Reproduzido sem rede com o fato do laudo reconstruído (a frase
transcrita neste arquivo, completada pela descrição da P4 de 13/09 — **não** é o fato literal,
que não está no repositório): antes, `18.11.13`/`18.11.14` em D1/D2; depois, nenhum item de
elevador. As três redações de perigo real — cancela ausente, quebrada, e aberta "sem cabine no
nível … vão da torre exposto" — continuam pondo `18.11.13` no dossiê (a última também
`NR-11 11.1.2`), pelos outros sinais. **Cobertura perdida, declarada**: "cancela aberta" sem o
Olho dizer que o vão está exposto deixa de rotear. Sinal que exija a cabine fora do nível não foi
escrito: `"cancela aberta sem cabine"` tem 4 radicais e passa a 0,75 sem `cabin`, e
`"cancela sem cabine"` casaria cancela FECHADA sem cabine, que é o estado correto.

**Ruído na mesma foto, também consertado**: `tapume_galeria_ausente` disparava por
`"obra aberta para a rua"` — 4 radicais, um de cola (`para`), casando a 0,75 sem `rua`, que é o
único que diz que o risco é do passeio. Virou `"obra aberta rua"` (3 radicais, todos
obrigatórios): o positivo "frente da obra aberta para a rua, sem tapume" continua; a cancela e
"tapume contínuo … com a rua ao fundo" calam.

Sinais: 883 → **882**; de 4+ radicais: 257 → **256**. Cinco casos de teste novos (três funções, uma
parametrizada em três): os dois que medem os consertos falham no código antigo; os três
positivos passam nos dois. O teste antigo `test_o_elevador_de_verdade_continua_chegando_ao_item_certo` usava
"cancela … aberta" como defeito da cena — o mesmo erro escrito como expectativa; trocado por
cancela ausente. **307 testes passam.**

---

## Laudo de andaime de 24/09/2026 — a periferia que ninguém endereçou, e um sinal frágil consertado

`main` em `b18800a` (merge do PR #69). Um laudo real de andaime, com `andaime_sem_guarda_corpo`
e o risco de base instável **marcados pelo inspetor**, voltou com a falta de guarda-corpo/rodapé
da periferia **sem endereçamento nenhum** — nem NC, nem ponto de atenção. Dossiê reproduzido sem
rede com os fatos exatos do laudo.

**1. A marcação funcionou; o Olho não viu.** Os itens dos dois riscos marcados (`NR-18 18.9.1`,
`18.9.4.2`, `18.12.15.2`, `18.12.13`, `18.12.3`) entraram em D1–D5. Mas nenhum fato do Olho fala
da periferia da plataforma nem da base do andaime, e o Analista só enquadra o que um fato
sustenta. É a fronteira de 09/09 (**a marcação dirige o dossiê, não o Olho**) no seu pior caso:
não foi "item certo pendurado no achado errado", foi **silêncio** — o Analista também não
escreveu nada em `sem_enquadramento`, e a seção de pontos de atenção sumiu do laudo. **O
reforço do `PROMPT_OLHO` veio no PR seguinte — ver o item 3 abaixo, à espera de lote.** É também mais um
caso do item em aberto *"Nada pede que todo achado de risco seja endereçado"*, pelo lado do risco
MARCADO: o inspetor apontou o risco e o laudo não diz nada sobre ele, nem que não pôde verificar.

**2. Sinal frágil achado na medição, CONSERTADO.** `andaime_sem_guarda_corpo` também roteava
sozinho, sem precisar da marcação, pelo sinal `"andaime so com o piso"`: `so` e `o` somem no
filtro de duas letras e sobra `andaim`+`com`+`piso` — `com` é cola, e `piso` vem do ambiente de
quase toda foto de canteiro. Medido com ambiente "piso de concreto": disparava um risco
**crítico** em três contrapartes — andaime com guarda-corpo, travessão e rodapé descritos
PRESENTES; andaime neutro; e travessão instalado "sem oxidação". É a armadilha *"sinal cujas
palavras somem no filtro de radicais"* outra vez, agora completada pela do ambiente. Não mudou
este laudo (a marcação já punha os itens lá), mas inflava o risco em foto sem marcação. Trocado
por `"andaime sem travessao"` (3 radicais, a peça que a descrição do risco nomeia, e o `sem`
agora protegido pela proximidade de 18/09): as três contrapartes calam, os dois positivos medidos
continuam roteando. `test_andaime_sem_guarda_corpo_nao_dispara_so_por_andaime_e_piso` trava, e
falha no sinal antigo. **274 testes passam** (272 + 2 — o segundo isola o sinal novo, pedido pelo `/critico`, porque o positivo do primeiro também casa `"andaime sem rodape"`; a contagem "264" deste arquivo estava
defasada desde os PRs #66-#68; o #69 não acrescentou teste). Contagem de sinais inalterada — troca, não acréscimo.

**3. Prompt do Olho reforçado a pedido do usuário (mesmo dia, PR seguinte ao #70) — MEDIDO no
lote seguinte, ver a seção logo abaixo.** Um parágrafo novo no `PROMPT_OLHO`, logo depois da regra "sem <peça> visível": com andaime
na cena, a periferia da plataforma é sempre um achado PRÓPRIO, mesmo quando o achado principal é
outro; para cada borda livre que aparece no recorte, o que há nela (guarda-corpo, travessão
superior, travessão intermediário, rodapé), o que falta, material e fixação; a base dos montantes
(sapata ou base de apoio, sobre o que assenta); borda fora do recorte vira "não dá para ver a borda
<lado>", nunca silêncio. O texto diz "base de apoio" e não "placa de apoio" de propósito: medido,
"sem sapata nem placa de apoio" acionava `sinalizacao_de_seguranca_ausente` pelo sinal `"sem placa"`.
**O vocabulário novo acordou três sinais antigos de 4 radicais, medido ANTES de escrever o prompt**
— é a armadilha "ensinar o Olho a nomear muda o risco de todo sinal que casa aquele nome":
`"guarda corpo de madeira frouxo"` disparava `periferia_laje_sem_guarda_corpo` (crítico) num
guarda-corpo ÍNTEGRO com rodapé de madeira (0,75, faltando `froux`); `"placa apoiada sobre abertura"`
disparava `abertura_piso_desprotegida` (crítico) em "sapatas metálicas sobre placas de madeira" e em
"placa apoiada sobre a bancada" (0,75, faltando `abertur` — o mesmo caso já registrado em 15/09).
Os dois foram encurtados para 3 radicais (`"guarda corpo frouxo"`, `"placa sobre abertura"`), com
os positivos mantidos. O terceiro, `"passarela sem guarda corpo"`, **ficou como está, ressalva
declarada**: ele aciona `rampa_passarela_irregular` junto do andaime SEM guarda-corpo (ruído ao lado
de um positivo, nunca numa cena conforme), e encurtá-lo perdia "passarela ... sem guarda-corpo" de
verdade — medido. Sinais de 4+ radicais: 259 → **257** de 883. Três testes novos (texto do prompt;
roteamento das redações que ele pede, conforme e não conforme; positivo dos sinais encurtados), os
dois de roteamento falham nos sinais antigos. **277 testes passam.** Verificado no navegador em Modo
Demonstração: 3 NCs, sem erro. **O que o lote tem de responder**, lido na LISTA DE FATOS: (a) numa
foto de andaime, o Olho escreve um achado próprio da periferia; (b) não inventa "sem guarda-corpo"
numa borda que não aparece — o risco simétrico, o mesmo que o parágrafo de pessoa/EPI mostrou em
16/09; (c) o parágrafo novo não dilui regras vizinhas (hipótese de 16/09 sobre parágrafo longo).

---

## Lote de andaime de 24/09/2026 — o reforço da periferia medido, e o `18.12.15.2` trancado

`main` em `4a8d54a` (PR #71) no lote. **6 laudos, 8 NCs, 0 não auditadas, 1 ciclo em todos.** Hash
não lido na barra lateral. As seis fotos foram subidas ao acervo pelo usuário depois dos laudos
(`a629dcd4…`, `3c34d1a1…`, `83b1bd33…`, `5af17330…`, `WhatsApp Image 2026-05-07 at 08.44.49`,
`WhatsApp Image 2026-05-05 at 14.41.18` — laudos 1 a 6, nesta ordem), abertas e ampliadas antes de
concluir causa; os seis dossiês foram reproduzidos sem rede a partir dos fatos. Leitura da imagem
pela régua (a)-(d) do acervo: "decide" é geometria ou presença; o resto fica ABERTO.

| # | O que a foto mostra da periferia/base | O que o Olho escreveu | NC entregue |
|---|---|---|---|
| 1 | plataforma no teto, vista de baixo; pés no entulho; placa **"ANDAIME NÃO LIBERADO"** | nada da periferia; a placa sem o texto | `18.12.13` alta — base ABERTA (pés no entulho) |
| 2 | plataforma vista de baixo; o gradil "à altura do peito" está **no nível do chão**, abaixo dela | guarda-corpo atribuído à plataforma (POSIÇÃO); "sem sapatas visíveis" | `18.12.13` crítica + `18.12.5` alta (frestas vistas de baixo: ABERTO) |
| 3 | andaime montado **em primeiro plano**, plataforma a ~2 m, borda frontal sem travessão nem rodapé (decide) | **omitiu**; pôs um andaime do fundo nas conformidades, "aparentando uso adequado" | `18.12.5` alta sobre quadros DESMONTADOS empilhados — classe 1, e o aparo escreveu "não se aplica" e não vetou |
| 4 | plataforma sob a tela laranja, fora de vista; vão retangular **na parede**, cocho de argamassa no piso | nada da periferia; "abertura retangular **no piso** … profundidade visível" | `18.9.2` **crítica — FALSO POSITIVO, VÃO INEXISTENTE** |
| 5 | face frontal só com escoras em X, sem travessão nem rodapé (decide); plataformas de chapa metálica | **certo** — "borda frontal livre … sem guarda-corpo, travessão superior ou rodapé"; mas "plataformas revestidas com tela plástica" (MATERIAL: a tela é um rolo no canto) | `18.12.15.2` crítica — conteúdo certo, **item errado** |
| 6 | frente sem rodapé (decide); estrutura tubular acima do estrado na lateral direita (função ABERTA); **dois montantes sobre placa de base metálica** (decide); um trabalhador ao fundo | "bordas laterais e frontais sem guarda-corpo…"; "**sem sapatas ou bases de apoio visíveis**"; "nenhum" trabalhador | `18.12.15.2` crítica (item errado) + `18.12.13` alta **FALSO POSITIVO** |

**(a) Achado próprio da periferia: 3 de 6** (2, 5, 6), com o vocabulário exato do parágrafo novo;
**pleno só na 5**. Nenhum laudo escreveu "não dá para ver a borda <lado>" — as fotos 1 e 4, com a
plataforma fora de vista, ficaram em silêncio, que é o que a regra existia para impedir. A foto 3 é
a omissão mais cara: borda desprotegida visível e o andaime nas conformidades.
**(b) Ausência inventada: 1 caso, e na BASE** — a foto 6 afirma "sem sapatas" sobre placas de base
que aparecem nítidas, e disso nasceu uma NC. É o risco simétrico que o item (b) mandava vigiar, na
metade do parágrafo novo que pede a base. Nas bordas, os "sem" das fotos 5 e 6 recaem sobre bordas
que aparecem no recorte.
**(c) Regras vizinhas**: o parágrafo de pessoa segurou (fotos 2 e 3); a trava do vão segurou NO
TEXTO e errou o PLANO (foto 4: o vão real é de parede, e ela não pergunta em que plano está a
profundidade) — **sexta ocorrência da classe VÃO INEXISTENTE**, variante nova: um vão real
realocado de plano. Contagem de gente falhou na 6. Diluição por parágrafo longo: compatível com a
omissão da foto 3, não separável com n=6.

**Das 8 NCs, as duas com lastro de conteúdo são as de guarda-corpo das fotos 5 e 6 — e as duas
citavam o item errado.** Três são falso positivo confirmado (4, base da 6, e o `18.12.5` da 3 como
classe 1); as outras três dependem de peça que a foto não decide.

**Decisão sobre o parágrafo de andaime do `PROMPT_OLHO`: congelado, na linha de 16/09.** O lote
mostrou os dois lados que o parágrafo de pessoa mostrou — omissão onde a peça aparece e ausência
inventada onde ela existe — e uma trava a mais, cega, arrisca o mesmo padrão (regra nova resolve um
caso, vizinha falha). Sem rodada nova agendada; retomar é decisão do usuário.

**Conserto de código, sem lote: `NR-18 18.12.15.2` só entra com o tipo nomeado.** O item começa com
"Quando da utilização de andaimes **multidirecionais**", e estava em `andaime_sem_guarda_corpo` para
qualquer andaime: saiu nas fotos 5 e 6, andaime tubular de quadros (quadros-escada, escora em X, sem
roseta nos nós — o NOME fica formalmente ABERTO, mas nenhum fato o sustenta), com o `18.9.4.2` —
que cobra travessão a 1,20 m e rodapé para qualquer andaime — em D2 nos dois dossiês.
`dossie.ITENS_RESTRITOS_A_TIPO` + `tipo_pertinente()` trancam o item nos **dois** caminhos: o risco
curado (`pipeline.montar_dossie`) e a busca textual (`util` em `dossie.montar`). **Trancar só o
curado não bastava, medido: a busca textual o devolvia em D10** — a armadilha "medir o roteamento
não vê o item que a busca textual traz", pelo lado do conserto. Reproduzido nos fatos reais: o item
sai dos dois dossiês e o `18.9.4.2` fica em D2. O termo é `multidirecion` porque `_menciona` tolera
três letras de sufixo e "multidirecional" não casaria o plural. O teste antigo
`test_item_generico_entra_no_dossie_sem_rotulo_de_risco` exigia o `18.12.15.2` numa cena de andaime
**suspenso** — o mesmo defeito escrito como expectativa; corrigido. **280 testes passam** (277 + 3);
os dois que medem o bloqueio falham no código antigo.

**Em aberto, sem conserto**: o aparo que escreve a razão do veto e não veta (foto 3, a mesma classe
da foto 4 de 14/09 — consertado em 26/09 por prompt + schema, à espera de lote; ver a seção logo abaixo); `NR-15 Anexo 6` voltando por "umidade" (foto 3 — consertado em 26/09, ver "Em aberto"); a trava do vão não conferir o
PLANO da abertura (foto 4).

---

## O aparo que escreve a razão do veto e não veta — campo `sobra_descumpre` (26/09/2026, À ESPERA DE LOTE)

Classe de erro 1 pelo caminho do aparo, vista em três laudos: o Diretor escreveu, no próprio aparo,
por que o item não cobria o que sobrou — *"a norma regula aberturas em pisos e paredes, não
tetos, mas a…"* (foto 4, 14/09), *"a norma regula especificamente aberturas no piso"* (laudo 1,
09/09), *"não se aplica"* (foto 3, 24/09) — e manteve o enquadramento. `_exigencia_ancorada` não
pega: o trecho copiado existe no item; o que falha é ele não ter relação com a constatação aparada.

**Trava só no código, medida e RECUSADA.** Uma regex sobre o `retirado` ("não se aplica", "a
norma/o item regula|trata|cobre", "não regula|trata|cobre|abrange"), contra os textos de aparo
transcritos neste arquivo: 3 dos 4 casos que deviam vetar disparam (o B01 de 10/09 cala — a razão
ali fala do FATO); 0 de 11 textos legítimos transcritos (9 retirados de aparo reais, 1 frase de
parecer, 1 exemplo do próprio `PROMPT_DIRETOR`); **2 de 2 aparos legítimos sintéticos disparam**
("a exigência de 1,20 m, que não se aplica à tela; permanece a ausência de rodapé"). O que separa
é se a negação fala do trecho cortado ou do que SOBROU — semântica, a armadilha do sinal escrito
por extenso. E o corpus é fraco: os casos reais só existem aqui como fragmento truncado.

**Conserto**: todo aparo responde `"sobra_descumpre": "sim|nao"` no schema do `PROMPT_DIRETOR`,
com os três casos reais no texto. `"nao"` vira veto mecânico (`MOTIVO_SOBRA_FORA_DO_ITEM`),
**antes** da repescagem (refutação não é silêncio). O ponto de atenção leva a constatação APARADA,
não a original: o corte de lastro foi aceito, só o item foi recusado. **Campo ausente ou ilegível
mantém o aparo** — tratá-lo como veto abriria uma porta nova de omissão, a mesma que o #34 separou
no `exigencia`; o custo é o campo não proteger quando o modelo o omite. A pergunta é sobre o RESTO
e não sobre o motivo do corte ("fato|item", a primeira proposta): cortar uma cláusula que o item
não trata, com o resto ainda descumprindo, é aparo legítimo, e um campo sobre o motivo o vetaria.
Oito testes (os três que medem o conserto falham no código antigo). **290 testes passam.**
Verificado no navegador em Modo Demonstração: 3 NCs, sem erro.

**O que o lote tem de responder**, lido na TRILHA (vetos com o motivo novo) e nos aparos: (a) o
Diretor preenche o campo; (b) numa foto como a 4 de 14/09 ou a 3 de 24/09 ele responde "nao" e o
enquadramento cai; (c) o risco simétrico — "nao" demais, aparos legítimos (a escada no entulho em
NR-35, o `18.9.2` da âncora) virando veto. Mexe em todo laudo com aparo.

---

## Lote de validação do `sobra_descumpre` de 26/09/2026 — o conserto NÃO foi exercido, e um falso positivo novo

`main` em `330fe49` (PR #74), **hash não lido na barra lateral**. Obra "teste", **5 laudos, 4 NCs**,
0 não auditadas, 1 ciclo em todos, `qwen3.8-27b` no campo de visão (lido no print; o de texto não
aparece nele). Fotos, na ordem dos laudos: `8 PAV. CANCELA CREMALHEIRA SEM SINALIZAÇÃO`,
`18 PAV. PROTEÇÃO POÇO DE ELEVADOR`, `13 PAV. PEÇO ELEVADOR SEM PROTEÇÃO` (controle),
`13 PAV. PEÇO ELEVADOR SEM PROTEÇÃO E SINALIZAÇÃO` (controle extra, acrescentado pelo usuário) e
`83b1bd33-6acc-4b22-9322-4e32cd165c5d.jpg` (a foto 3 do lote de andaime de 24/09). Nomes conferidos
na pasta `fotos/` do acervo.

| # | Foto | Resultado | Leitura |
|---|---|---|---|
| 1 | `8 PAV. CANCELA…` | `NR-18 18.11.13` crítica, aparada e mantida | o caso "não tetos" de 14/09 **não se repetiu**; saiu outra NC, falso positivo (abaixo) |
| 2 | `18 PAV. PROTEÇÃO POÇO…` | `NR-08 8.3.2.2` crítica, aparada e mantida; `18.9.3` vetado | o caso de 09/09 **não se repetiu**: o corte foi de lastro ("suposição de vão de elevador") e o item cobre parede. A NC segue falsa pelo erro de MATERIAL do Olho de 10/09 ("painel marrom" é tela metálica) |
| 3 | `13 PAV.` (controle) | `18.9.2` crítica mantida | ✓ |
| 4 | `13 PAV. … E SINALIZAÇÃO` | `18.9.2` crítica mantida | ✓ |
| 5 | `83b1bd33…` | **0 NC**, `18.12.5` vetado | resultado certo, mas pelo **veto direto** do Diretor ("regula a superfície de trabalho de um andaime montado"), não pelo campo |

**As três perguntas da seção do `sobra_descumpre`**: (a) se o Diretor preenche o campo — **não
mensurável**: o campo não aparecia no laudo, e nos aparos mantidos "sim" e ausente davam o mesmo
documento. É a armadilha "rede que só registra quando falha", cometida no próprio conserto.
**Consertado em seguida, sem lote**: todo aparo mantido diz na trilha "a supervisão declarou que o
que sobrou segue coberto pelo item" ou "a supervisão não declarou…" (4 testes, falham no código
antigo). (b) se ele responde "nao" nos casos que motivaram o campo — **não exercido**: nenhum dos
três se repetiu na forma original. (c) "nao" demais — **não**: os dois controles mantiveram o `18.9.2`.

**Achado novo, e o mais caro do lote: `torre_elevador_sem_cancela` disparou pela primeira vez em
produção — como falso positivo.** O Olho escreveu *"Cancela metálica de malha quadrada, pintada de
vermelho, aberta … com um dispositivo de fechamento azul"*, e saiu `NR-18 18.11.13` crítica, prazo de
1 dia: "a cancela … está aberta, não impedindo a exposição de partes do corpo". O critério
pré-registrado em 13/09 (P4) diz que qualquer NC de queda nesta foto é falso positivo: o item cobra
que a barreira seja INSTALADA, e ela está — aberta, com intertravamento, plataforma no nível. É a porta
registrada em "Em aberto" (*"A `cancela` entrega os itens de elevador sem passar por portão nenhum"*):
o sinal `"cancela aberta"` não separa cancela ausente de cancela aberta no embarque. **Medi X, afirmo
Y**: o que está medido é o laudo; o dossiê desta foto não foi reproduzido sem rede nesta sessão.
**CONSERTADO em 26/09, sem lote — ver a seção "Cancela aberta no embarque", mais acima.**

---

## Conserto de roteamento de 18/09/2026 — a hipótese do bigrama, atacada

`main` em `86bb35d` (merge do PR #65) antes desta sessão. **Código determinístico de roteamento,
sem prompt de agente envolvido — mesmo raciocínio dos PR #62/#63: não precisa de lote de
produção, precisa de teste e de `/critico`.** 264 testes passam (259 + 5).

**O que estava quebrado.** `rotear_riscos` (`pipeline.py`) sempre tratou cada achado como
um SACO de radicais sem posição — é o que a tabela de armadilhas chama de "`sem` é
radical-cola" e "a âncora não protege contra a relação invertida". Duas famílias de falso
positivo vinham daí, as duas medidas em produção mais de uma vez: um sinal como `"sem
carenagem"` casava com "Carenagem íntegra... **sem** folgas" (o `sem` do texto nega
"folgas", não "carenagem" — mas o roteador só perguntava "os dois radicais estão em algum
lugar do achado?"); e um sinal como `"abertura no piso"` casava com "**Piso** de concreto
visível na parte inferior da **abertura**" (a foto mostra o PÉ de um vão vertical, não um
buraco no chão — mas de novo, os dois radicais existiam em algum lugar do mesmo achado).
Foi por essa porta que `NR-18 18.9.2` chegou a D1 três vezes em quatro execuções sobre
fotos sem buraco no chão (10/09), e que a ressalva `"tanque sem cerca"` ficou registrada
no código como "resolver de vez exige a hipótese do bigrama" desde 17/09.

**O conserto.** `kb.radicais_posicionados()` é a versão do velho `radicais()` que preserva
ORDEM em vez de devolver um set — só isso já não existia. Em `pipeline.py`, três peças
novas:
- **`_radicais_negados(sinal)`** — os radicais que `"sem"` nega DENTRO do sinal: tudo que
  vem depois da primeira ocorrência dele, na ordem em que aparece. `"tanque sem cerca"`
  nega `cerca`, não `tanque` — em português `"sem X"` nega X, nunca o resto da frase.
- **`_proximidade_da_negacao(alvo, texto)`** — existe um `"sem"` DE VERDADE, no MESMO
  texto, com `alvo` a até `JANELA_PROXIMIDADE` (7) palavras NA FRENTE dele? Direcional de
  propósito: é a direção, não o tamanho da janela, que separa `"sem cerca"` (cerca depois
  do sem, 1 palavra) de `"isolado com cerca... sem manutenção"` (cerca ANTES do sem, que
  nega outra coisa, a 3 palavras) — as duas distâncias são parecidas, só a ordem as
  diferencia. Só a CABEÇA do que foi negado precisa passar nesse teste — o resto do
  substantivo composto (`"guarda-corpo"` tokeniza em `guard`+`corp`; `"placa de
  identificação"` em `plac`+`identificaca`) anda junto sem checagem própria.
- **`_bigrama_proximo(t1, t2, texto)`** — para sinal de EXATAMENTE dois radicais sem
  negador (166 dos 883): os dois precisam estar a até `JANELA_PROXIMIDADE` palavras um do
  outro, sem direção. Não se aplica a sinal mais longo, que já tolera paráfrase solta de
  propósito (ver `test_escada_com_apoio_instavel_roteia_sem_depender_do_fraseado`).

**Três rodadas de calibração, não uma — e a ordem importa para quem for mexer aqui de
novo.** A primeira versão negava só o radical IMEDIATAMENTE seguinte a `"sem"` no sinal.
Contra ela, uma varredura sintética dos 883 sinais (reescrevendo cada um com um enchimento
de 3 palavras entre CADA palavra — o pior caso plausível de um Olho verboso) achou 3
quebrados com `JANELA_PROXIMIDADE=6` (por 1 palavra de distância) e 0 com 7 — foi essa
medição que fixou o valor 7, calibrado para baixo pelo caso real que a hipótese existe
para barrar (`"Piso... visível... da abertura"`, 9 palavras de distância, tem que ficar de
fora). Só depois, testando os quatro sinais problemáticos de `periferia_laje_sem_guarda_corpo`
já registrados na tabela de armadilhas, apareceu o defeito do "vizinho imediato": um achado
que afirma "guarda-corpo... sem folgas" ainda disparava, porque só `guard` era descartado e
`corp` (segundo radical do composto, gerado pelo hífen) continuava contando livre. Negar
TODOS os radicais depois do `"sem"` (não só o imediato), cada um com sua própria checagem
de proximidade a partir do mesmo `"sem"`, consertou os quatro casos — mas reabriu a
varredura sintética: 78 sinais quebrados, porque a distância entre `"sem"` e o ÚLTIMO
radical de um composto de 2-3 palavras cresce com o enchimento entre cada uma delas.
Ancorar só pela CABEÇA (o resto do composto anda junto sem checagem própria) resolveu as
duas coisas ao mesmo tempo: os quatro sinais de `periferia_laje_sem_guarda_corpo` continuam
bloqueados, e a varredura sintética volta a zero quebrados.

**Medido, não hipótese**, contra os três casos documentados:
- `test_tanque_sem_cerca_nao_colide_mais_com_a_ressalva_conhecida` — a ressalva do
  `area_de_risco_nao_delimitada` (`ambiental.py`) fechada; a contraparte positiva (cerca
  genuinamente ausente) continua roteando.
- `test_abertura_no_piso_nao_casa_com_a_relacao_invertida` — o achado real de 10/09 não
  rotea mais `abertura_piso_desprotegida`; as duas contrapartes positivas continuam.
- `test_sem_nega_so_o_vizinho_no_sinal_nao_qualquer_negacao_do_achado` — o mecanismo em
  isolado, contra o par positivo/negativo original de `"sem carenagem"` (04/09).

Além dos três: `test_item_generico_entra_no_dossie_sem_rotulo_de_risco` (a suíte antiga)
usava, sem perceber, um achado que afirmava guarda-corpo PRESENTE para exercer
`andaime_sem_guarda_corpo` — exatamente o bug que o próprio docstring do teste denuncia
("o fato registrado dizia que o andaime TINHA guarda-corpo"). Corrigido para um achado que
nega o guarda-corpo de verdade; é a prova de que o conserto ataca a causa, não só os casos
que motivaram a rodada — um teste ESCRITO CONTRA o bug, sem saber, deixou de passar por
acidente.

**O que ficou de fora, documentado, não escondido**: `"sem trechos abertos"` — onde o
NEGADOR está no TEXTO, não no SINAL (o sinal é afirmativo, `"poço aberto"`, e o texto nega
com `"sem trechos abertos"`) — continua fora do alcance. É outro mecanismo, e o CLAUDE.md
já registrava isso como fora do escopo desta hipótese antes de ela existir em código.

**O `/critico` REJEITOU a primeira versão**, e o gap era real: a varredura sintética contra
os 883 sinais que calibrou `JANELA_PROXIMIDADE` e o desenho "a cabeça ancora o grupo"
existia só como número em prosa neste arquivo — nada no repositório a reproduzia, e um
sinal novo cadastrado depois desta rodada (ou uma mudança na janela) podia voltar a quebrar
em massa sem que nada avisasse. **Consertado**: as duas varreduras viraram teste —
`test_todo_sinal_casa_com_a_propria_frase_literal` (o caso canônico, os 883 sinais) e
`test_varredura_sintetica_com_enchimento_nao_quebra_sinal_de_sem_ou_bigrama` (o enchimento
adversarial que motivou o valor 7). 264 testes passam (259 + 5). **O `/critico` rodou de
novo sobre o range com os dois commits e APROVOU.**

**Verificado no navegador em Modo Demonstração**: pipeline inteiro (Olho → dossiê →
aferição → supervisão) roda sem erro, 3 não conformidades, sem regressão visível.

---

## Validação em produção de 16/09/2026 — quarta rodada (0 de 3): regras que seguravam regrediram, só a trava do vão segurou

Obra "teste 8". **3 laudos, 4 NCs (1 + 1 + 2), 0 não auditadas, 1 ciclo em todos.**
Mesmas três fotos das três rodadas anteriores, sem marcação. Hash confirmado pelo
usuário contra `c95bba3` (PR #59) antes de rodar. As três fotos foram reabertas no
acervo e ampliadas de novo antes de concluir causa.

| # | Foto | O que o Olho escreveu sobre a pessoa | Confronto com a foto real | NC entregue |
|---|---|---|---|---|
| 1 | `TRABALHADOR SEM EPI` | "Usa **boné preto** na cabeça e **luvas** nas mãos" — frase IDÊNTICA à da 2ª rodada | Cabeça descoberta, confirmado de novo | `NR-08 8.3.2.2` alta — abertura na parede, **desta vez real** (ver seção 3) |
| 2 | `TRABALHADOR SEM PROTEÇÃO` | "segurando... com a mão direita... **as mãos não aparecem no recorte**" — a MESMA contradição da 2ª rodada, que a 3ª tinha corrigido | Mão nua, sem luva, visível (já confirmado nas rodadas anteriores) | `NR-17 17.6.3` média — bancada desgastada, **nada a ver com EPI** |
| 3 | `TRABALHADOR SE EPI` | Nenhuma negação de EPI desta vez — só roupa ("camisa azul, calça jeans, bota de trabalho"; "mãos livres" do 2º homem, que é AUSÊNCIA DE OBJETO NA MÃO, não luva) | — | `NR-08 8.3.2.2` crítica (abertura vertical, real) + `NR-18 18.10.2.4` média (cabo, real) |

**Gabarito contra o nome do arquivo: 0 de 3** — pior que a rodada anterior (1 de 3), e
empatado com a pior medição do acervo (a 2ª rodada, logo após o PR #57).

### 1. Foto 1: a mesma invenção, com o mesmo texto — a trava reforçada não mudou nada aqui

"Usa boné preto na cabeça e luvas nas mãos." é, caractere por caractere, a frase que a
2ª rodada escreveu (antes de qualquer trava contra isso existir). A 3ª rodada, já com a
regra 3 original, tinha ao menos corrigido a luva ("não usa luvas"); esta rodada, com o
critério checável novo (borda/aba/viseira), inventou os dois de novo. A trava nova pede
uma descrição de contorno para justificar "boné" — o Olho não descreveu contorno nenhum,
só afirmou a peça, exatamente como antes de a trava existir. **Não é evidência de que a
trava piorou o problema; é evidência de que ela não teve efeito nesta execução.**

### 2. Foto 2: a contradição que a regra 1 existe para proibir, de volta com o texto igual

A regra 1 não foi tocada entre a 3ª e a 4ª rodada. Na 3ª: "segurando... com a mão
direita; cabeça, rosto e pés não aparecem no recorte" — mão corretamente excluída da
lista do que não aparece. Nesta: "segurando... com a mão direita... a cabeça, os pés e
**as mãos** não aparecem no recorte" — a mão está DE VOLTA na lista, na mesma frase em
que a descrição diz que ela seguraria a ferramenta. É a contradição original,
reproduzida com o prompt inalterado nesse trecho. **Consequência prática**: zero achado
sobre a mão, e o Analista foi atrás do único risco que sobrou no dossiê — o desgaste da
bancada, `NR-17 17.6.3` — uma NC de ergonomia sobre o móvel, não sobre a pessoa.

### 3. Foto 1: a trava do vão inexistente segurou, e o achado novo é real

O piso não foi mais descrito como tendo abertura — o pallet e a régua de nivelamento,
que na rodada anterior viraram "vão", desta vez saíram como "Palet de madeira... apoiado
diretamente sobre o piso de concreto, sem carga sobre ele", sem nenhuma palavra de
abertura. No lugar, o Olho relatou uma abertura na PAREDE: "bordas irregulares e
interior escuro, indicando um vão para a estrutura interna". Reaberta a foto e ampliado
o canto superior esquerdo: **existe mesmo um buraco retangular na parede, com
profundidade visível (interior escuro) e bordas irregulares** — geometria real, não
fabricação. É a primeira medição da trava nova, e no único caso em que ela foi
exercida, segurou: nem inventou vão onde não há, nem deixou de registrar um vão que há.

### 4. Foto 3: perdeu o único acerto real do acervo, sem trocar por outro erro

Na 3ª rodada esta foto tinha, pela primeira vez em quatro rodadas do acervo, uma NC de
EPI real e com lastro (`NR-06 6.5.1`, sem óculos/luvas/protetor do 1º homem). Nesta
rodada, o fato sobre a pessoa não menciona nenhuma ausência de EPI — só descreve roupa e
diz que o 2º homem tem "as mãos livres" (não seguram nada, o que é sobre presença de
objeto na mão, não sobre luva). As duas NCs que saíram (abertura na parede + cabo no
piso) têm lastro real — confirmado nas rodadas anteriores — mas nenhuma é sobre EPI. A
regra 4 (achado próprio por pessoa) também não foi seguida de novo: os dois homens
continuam no mesmo achado, sem dano visível desta vez porque nenhum "sem X" apareceu
para colidir.

### 5. O que isso muda no método

**A trava do vão inexistente (n=1) segurou no único caso em que foi testada.** As
regras 1 e 4, que não foram tocadas nesta sessão, regrediram sem mudança de texto — o
que descarta "o texto está errado" como explicação única e aponta para variação de
execução do próprio modelo sobre o mesmo prompt, possivelmente agravada pelo parágrafo
de pessoa ter ficado mais longo (a trava do boné cresceu no meio dele). **Isso muda o
que vale a pena tentar a seguir**: mais uma trava textual no mesmo parágrafo, sem medir
por que regras que já seguravam pararam de segurar, arrisca a mesma coisa — regra nova
resolve um caso e uma regra antiga, intocada, falha na mesma rodada. Perguntar ao
usuário antes de decidir o próximo passo, e antes de rodar de novo, dado que já são
quatro rodadas consumindo cota do dia na mesma pergunta.

---

## Validação em produção de 16/09/2026 — a trava do PR #58 medida (1 de 3), e um defeito novo mais caro que a alucinação

Obra "teste". **3 laudos, 4 NCs (2 + 0 + 2), 0 não auditadas, 1 ciclo em todos.** Mesmas
três fotos do lote anterior, sem marcação. As três fotos foram abertas no acervo
(`auditoria-nrs-fixtures`) e ampliadas ponto a ponto (cabeça, mão, piso) antes de
concluir causa — não é leitura à distância, é pixel contra fato.

| # | Foto | O que o Olho escreveu sobre a pessoa | Confronto com a foto real | NC entregue |
|---|---|---|---|---|
| 1 | `TRABALHADOR SEM EPI` | "Usa **boné preto** na cabeça e óculos de proteção" | Cabeça **nitidamente descoberta**, cabelo curto à mostra — confirmado na ampliação. Óculos: correto, existem de verdade | `NR-18 18.9.2` **crítica** — fabricada (ver seção 3) |
| 2 | `TRABALHADOR SEM PROTEÇÃO` | "segurando... com a mão direita; cabeça, rosto e pés não aparecem" — **luva não é mencionada** | Mão nua, sem luva, perfeitamente visível — confirmado na ampliação | 0 NC |
| 3 | `TRABALHADOR SE EPI` | 1º homem: boné azul, "sem óculos, sem luvas, sem protetor auricular". 2º homem, no MESMO achado do 1º: "apenas tronco e pernas visíveis" | 1º homem: tudo confirmado real. 2º homem: a mão dele **também aparece** (canto superior direito) — sub-relato, não erro grave | `NR-06 6.5.1` alta (1º homem, **com lastro real**) + `NR-18 18.10.2.4` média (cabo, real) |

**Gabarito contra o nome do arquivo: 1 de 3** — contra 0 de 3 na medição anterior, antes
do PR #58. É a primeira vez nas três rodadas deste acervo (15/09, 16/09 conserto, agora)
que uma NC de EPI real e com lastro sai de uma destas três fotos.

### 1. As regras 1 e 2 seguraram contra a contradição que existia para prevenir — com um efeito colateral novo: omissão no lugar de invenção

Nas fotos 2 e 3 sumiu a contradição medida na rodada anterior ("segura com a mão" +
"mão não aparece"; "cabeça descoberta" sobre quem estava fora do recorte). Mas nas
duas fotos o Olho também deixou de **afirmar** o que a foto mostra com clareza: na foto
2 a mão seguindo o disco está nua, sem luva, plenamente visível — e o fato não diz nada
sobre a luva, nem presença nem ausência. Na foto 3 o 2º homem tem a mão erguida também
visível no recorte (canto superior direito), e o fato o limita a "tronco e pernas". As
duas regras foram escritas para impedir a AFIRMAÇÃO contraditória; o preço, não previsto,
é o modelo ficar conservador demais e não afirmar nada onde antes inventava ou
contradizia. **É melhor que o defeito anterior** (nenhuma NC nasce de um fato falso), mas
ainda deixa a NC de EPI fora em duas das três fotos — por um mecanismo diferente do de
15/09 (lá era o prompt não pedir o atributo; hoje é o modelo pedir e preferir não
responder a arriscar).

### 2. A regra 3 falhou no caso exato que a motivou

A foto 1 é a MESMA foto onde a invenção do boné foi medida na rodada anterior. O Olho
escreveu "usa boné preto na cabeça" de novo — quase palavra por palavra —, e a
ampliação confirma o que já estava registrado: cabelo curto à mostra, nenhum boné,
nenhuma borda de objeto sobre a cabeça. A regra 3 (PR #58) proibia deduzir "usa boné"
por contexto; o texto pedia exatamente o oposto do que o modelo escreveu, e ele escreveu
do mesmo jeito. **Isso desloca o diagnóstico**: não é (só) que o modelo estava
deduzindo por contexto e a proibição não bastou — é possível que ele genuinamente
"visse" um objeto ali, um erro de percepção em baixa resolução (a imagem chega em
~674 px de largura, retrato de 1204×1600 reduzida a 896 na maior dimensão), não uma
falha de obediência à instrução. Proibir de novo, do mesmo jeito, teria retorno
decrescente. A trava nova (ver "COMECE POR AQUI") muda de tática: em vez de só proibir,
pede um critério CHECÁVEL (borda/aba/viseira distinta do couro cabeludo) e dá uma saída
de baixa confiança explícita — mais perto de como a regra da moldura já trata
material/nome ambíguos do que de uma proibição a mais.
**Óculos, ao contrário, saiu certo desta vez**: "óculos de proteção" está confirmado na
ampliação (armação visível). Não é a mesma classe de erro se repetindo em todo atributo,
só no boné.

### 3. A regra 4 não foi aplicada estruturalmente, sem dano desta vez

Na foto 3 os dois homens continuam no MESMO achado ("um homem... segura...; ao lado, um
segundo homem... observa"), não em achados separados como o texto pede desde o PR #58.
n=1 sem dano visível: nenhuma palavra como "bota" apareceu para colidir entre os dois
desta vez. A regra continua sem confirmação de que segura sob a condição que a motivou.

### 4. O achado fora do escopo das quatro regras, e o mais caro do lote: VÃO INEXISTENTE pela quinta vez

Na foto 1, o piso **não tem abertura nenhuma**. A ampliação mostra uma régua/guia de
madeira de nivelamento (com marcações numéricas visíveis) deitada sobre um piso de
concreto plano e contínuo, com um pallet pequeno apoiado em cima — nenhuma sombra de
profundidade, nenhuma borda com espessura, nada que sugira vão. O Olho escreveu
"abertura retangular... contendo um palet de madeira apoiado solto no interior do vão",
e isso virou a NC de frente do laudo: `NR-18 18.9.2`, **crítica, prazo de 1 dia**. É a
quinta ocorrência confirmada da classe VÃO INEXISTENTE deste histórico (as anteriores:
foto 3 do lote de máquina em 11/09, foto 3 do lote de elétrica em 12/09, a contraparte
do lote de pessoa na cena em 15/09, a contraparte do lote de escada em 15/09) — e a
primeira em que ela nasce dentro do próprio lote desenhado para medir a alucinação de
EPI, deslocando justamente a NC que a foto pedia. Diferente da alucinação do boné (que
tem duas rodadas de medição e uma trava dedicada), esta classe nunca tinha recebido
conserto de prompt — só era documentada e deixada em aberto. A trava nova (ver "COMECE
POR AQUI") é a primeira tentativa: exigir profundidade real antes de afirmar abertura,
vão ou buraco, e nomear explicitamente que marcação/régua/objeto sobre piso plano não é
abertura — o caso exato medido aqui.

### 5. O que isso muda no método

A regra 3 sozinha não bastou (n=2 rodadas no mesmo defeito); desta vez a trava do boné
reforçada e a trava do vão inexistente vão juntas para a próxima medição, para não gastar
duas rodadas de cota em vez de uma — não é padrão estabelecido (n=1 não sustenta isso),
é só a economia óbvia quando dois defeitos do mesmo agente estão medidos ao mesmo tempo.
E a régua de aceite continua a mesma:
vocabulário aparecer não basta, tem que resistir à foto real, achado por achado, sem
contradição, sem invenção e sem sub-relato do que está claramente visível. **Ainda não
tem lote de produção medindo se as duas travas novas seguram — perguntar ao usuário
antes de rodar, dado que consome cota do dia.**

---

## Validação em produção de 16/09/2026 — o lote de EPI (conserto do prompt), 3 fotos

Obra "teste". **3 laudos, 3 NCs, 0 não auditadas, 1 ciclo em todos.** Hash não lido na
barra lateral nesta sessão — inferido pelo comportamento do Olho: as três listas de
fatos trazem vocabulário de EPI da pessoa (boné, luvas, capacete, cabeça descoberta,
bota) que `PROMPT_OLHO` só passou a pedir no PR #57. Mesmas três fotos do lote de
PESSOA NA CENA de 15/09 — `TRABALHADOR SEM EPI.jpg`, `TRABALHADOR SEM PROTEÇÃO.jpg`,
`TRABALHADOR SE EPI.jpg` —, sem marcação e sem contexto extra. Os três dossiês foram
reproduzidos sem rede a partir dos fatos reais (`rotear_riscos` + `montar_dossie`) e as
três fotos foram abertas no acervo (`auditoria-nrs-fixtures`) antes de concluir causa.

| # | Foto | O que o Olho escreveu sobre a pessoa | NC entregue |
|---|---|---|---|
| 1 | `TRABALHADOR SEM EPI` | "Usa **boné preto** na cabeça e **luvas** nas mãos" | `NR-08 8.3.2.2` alta (aberturas na parede) |
| 2 | `TRABALHADOR SEM PROTEÇÃO` | "mãos, cabeça, olhos, ouvidos e pés **não aparecem no recorte**" | **0 NC** |
| 3 | `TRABALHADOR SE EPI` | 1º homem: boné azul, bota — correto. 2º homem: "**apenas o tronco, braços e pernas** estão no recorte, **sem capacete, cabeça descoberta**" | `NR-08 8.3.2.2` crítica (abertura vertical) + `NR-06 6.5.1` alta (**cabeça do 2º homem**) |

**Gabarito contra o nome do arquivo: 0 de 3.** Pior que o 1 de 5 de 15/09 pelo critério
de sempre — nenhuma das três fecha com o achado do nome e lastro real —, e por um
motivo que aquele lote não tinha: aqui não é mais omissão, é **invenção**.

### 1. A cadeia técnica fechou — `epi_nao_utilizado` disparou pela primeira vez na história do projeto

Reproduzido sem rede sobre os três fatos reais: a foto 3 roteia `epi_nao_utilizado`
(cobertura 1,00 no sinal `"sem capacete"`) e põe `NR-06 6.5.1`/`6.6.1` em **D1/D2
curados** — e o Analista os usou, com `6.5.1`. É a primeira vez, desde 03/09, que esse
risco (25 de 126, nunca medido em produção) sai de um laudo real. O conserto do PR #57
— o parágrafo novo no prompt e `pessoas.descricao` deixando de ser descartada — fez
exatamente o que prometia: o vocabulário de EPI chega ao roteamento.
**Nas fotos 1 e 2 o risco não dispara, e está certo não disparar dado o fato**: o fato
1 afirma que a pessoa USA boné e luvas (presença, não ausência) e o fato 2 diz que a
mão "não aparece no recorte" — nenhum dos dois tem a palavra `sem` que o sinal precisa.
**O defeito não está mais no parse nem no roteamento — está no que o Olho escreveu.**

### 2. Foto 1: o Olho INVENTOU um boné e uma luva que não existem — geometria pura, e ele errou

Aberta a foto real: o trabalhador está agachado aplicando massa na parede, de costas.
**A cabeça dele está nitidamente DESCOBERTA** — cabelo curto à mostra, nenhum boné,
nenhum capacete, nada. É exatamente o achado que o nome do arquivo pede, e é geometria
pura pela régua (a)-(d): presença ou ausência de objeto sobre a cabeça se decide com
confiança, sem ambiguidade de material, nome nem estado. **O Olho escreveu "usa boné
preto na cabeça e luvas nas mãos"** — o oposto do que a foto mostra. Não é omissão (a
causa raiz de 15/09): é **invenção de presença de EPI onde a foto mostra ausência**, e
o resultado é o pior possível — a NC certa (`NR-06`, capacete) nunca teve chance de
sequer ser candidata, porque o fato afirmou o contrário do que está na imagem.
**É o "risco simétrico" que o item em aberto do PR #57 previa vigiar ("inventar 'sem
luva' numa mão que a foto não mostra"), mas na direção oposta e mais grave**: não é
inventar ausência, é inventar PRESENÇA — o que faz uma condição insegura real virar
"conforme" no laudo do cliente. A mão que segura a espátula também não mostra luva
nenhuma com confiança na escala da foto, mas essa parte fica ABERTA pela regra (b)
(pele nua e luva clara podem se confundir); a cabeça não — ali não há dúvida.

### 3. Foto 2: o Olho negou a visibilidade de uma mão que está claramente visível

Aberta a foto real: o trabalhador segura a serra circular amarela com a **mão direita
nua, sem luva, perfeitamente visível** segurando o cabo — é a leitura que a leitura
cega do pré-registro de 16/09 já previa ("mão segurando a serra sem luva visível").
**O Olho escreveu "mãos, cabeça, olhos, ouvidos e pés não aparecem no recorte"** — na
MESMA frase em que diz "segurando uma ferramenta elétrica amarela **com a mão
direita**". A contradição está dentro do próprio fato: se a mão segura algo visível na
foto, ela apareceu; dizer que não apareceu é negar o que a frase anterior, dele mesmo,
acabou de afirmar. Resultado: **0 NC**, na foto que a leitura cega considerava o caso
mais fácil e mais claro do lote inteiro.

### 4. Foto 3: o Olho afirmou o estado de uma cabeça que ele mesmo disse estar fora do recorte

Este é o caso mais grave, porque produziu uma NC real no documento. Aberta a foto: o
segundo trabalhador aparece só pelo braço e mão erguidos no canto superior direito — a
cabeça dele **não está no recorte**, cortada pela borda da foto. **O próprio fato do
Olho registra isso**: "apenas o tronco, braços e pernas estão no recorte" — e na
sequência, na mesma frase, afirma "sem capacete, cabeça descoberta". É uma contradição
interna explícita, não uma inferência duvidosa: o Olho documentou que não vê a cabeça e
declarou o estado dela mesmo assim. **É o efeito colateral que este arquivo já vigiava
desde antes do PR #57** ("o Olho começar a inventar ausência de peça que está fora do
enquadramento… até aqui não tinha aparecido") — agora apareceu, e ele produziu uma NC
(`NR-06 6.5.1`, alta) sobre uma pessoa cuja cabeça ninguém, nem o próprio Olho, pode
confirmar que está ou não coberta.
**E o achado real mais óbvio da foto foi omitido.** O primeiro trabalhador (o que o
Olho descreveu corretamente — boné azul, camisa "FORTLEV", bota de cano alto, todos
confirmados na foto) segura a mesma serra circular com a mesma mão nua e sem luva da
foto 2 — visível na imagem exatamente como na foto 2 — e o Olho não escreveu uma
palavra sobre a mão dele. A NC que saiu é sobre a pessoa ERRADA, pendurada num atributo
que a foto não permite verificar, enquanto o achado com lastro real (mão sem luva do
trabalhador principal) ficou de fora dos fatos.

**E há um segundo defeito técnico, medido, que não mudou o resultado por sorte.** O
Olho descreveu os DOIS trabalhadores dentro do MESMO achado (um único item da lista de
fatos, com os dois homens), o que quebra a premissa de "cada achado é uma condição
verificável" — aqui é uma condição composta. Medido: o sinal `"sem bota"` do próprio
`epi_nao_utilizado` também casa a **cobertura 1,00** neste fato, porque `bota` vem do
PRIMEIRO homem (que a foto confirma vestir bota) e `sem` vem da frase do SEGUNDO — o
mesmo mecanismo do `"sem"` completando um sinal alheio, de novo, mas desta vez os dois
radicais vêm do mesmo fragmento por causa do formato composto, não por vazamento do
ambiente. Não mudou o dossiê aqui porque os dois sinais apontam para o MESMO risco
(`epi_nao_utilizado`, já roteado por `"sem capacete"`), mas noutra combinação — um
homem com luva, o outro sem — o mesmo formato composto casaria um sinal de EPI sobre a
peça errada da pessoa errada. Vale de olho no próximo lote se o Olho volta a agrupar
duas pessoas no mesmo achado.

### 5. O que isso muda no método: a regra da moldura precisa cobrir o corpo da pessoa

A regra da moldura já existe para objeto ("a constatação só afirma que algo NÃO existe
se aquilo apareceria no recorte") e para o parecer/consequência (cláusula d, contra a
hipótese). **Ela nunca foi escrita para o corpo da pessoa**, e o parágrafo novo do
PR #57 tentou cobrir isso com uma frase só ("se a mão ou o rosto não aparecerem claros
o bastante, 'não dá para ver'") — medido agora: **essa frase não impediu nenhuma das
três variantes do defeito**. O Olho não é inconsistente ao acaso: nas três fotos ele
tentou cumprir a instrução nova (descrever cabeça/mãos) e falhou de três jeitos
diferentes — inventando presença, negando visibilidade real, e contradizendo a si
mesmo dentro da mesma frase. **Isso não é mais causa raiz de omissão** (que o PR #57
consertou de verdade, e a foto 3 prova: quando o Olho escreve a negação certa,
`epi_nao_utilizado` dispara e o Analista usa) — **é confiabilidade do próprio dado**,
uma classe de erro nova e mais cara que a omissão original, porque uma NC pode nascer
de uma frase que se contradiz dentro dela mesma.
**CONSERTADO na mesma sessão, à espera de novo lote.** Quatro regras novas no parágrafo
de pessoa do `PROMPT_OLHO`, uma por variante medida: (1) se a mão segura, apoia ou
manuseia algo, ela APARECE — proíbe a contradição da foto 2 ("segura com a mão direita"
+ "mãos... não aparecem"); (2) limitar o que aparece da pessoa ("apenas tronco, braços e
pernas") proíbe afirmar o estado de qualquer parte fora dessa lista na mesma frase —
mata a contradição da foto 3 ("cabeça descoberta" sobre quem não teve a cabeça
descrita); (3) proíbe escrever "usa capacete/boné/luva" por dedução de contexto (é
canteiro de obras, a pessoa trabalha) — a causa direta do boné inventado na foto 1; e
(4) havendo mais de uma pessoa, cada uma vira achado PRÓPRIO, para não deixar o `sem`
de uma colar com a peça da outra (o defeito secundário do `"sem bota"` medido na foto 3).
**Quatro testes novos travam o texto do prompt**, sem rede — 248 testes passam
(244 + 4). Verificado no navegador em Modo Demonstração, sem regressão.
É mudança de prompt de agente sobre um parágrafo que **acabou de ser medido e
reprovado** — vale nova rodada de lote antes de declarar fechado, e a régua de aceite
muda: não basta o vocabulário aparecer, tem que resistir à foto real, achado por
achado. Perguntar ao usuário antes de rodar, dado que consome cota do dia.

---

## Validação em produção de 16/09/2026 — o lote de MARCAÇÃO (o desenho D)

Obra "teste". **1 laudo, 1 NC, 0 não auditadas, 1 ciclo.** Hash não lido na barra
lateral nesta sessão. Foto: `PROTEÇÃO POÇO DE ELEVADOR SOMENTE COM UM PONTO DE
FIXAÇÃO.jpg`, com `abertura_piso_desprotegida` e `vao_caixa_elevador_sem_fechamento`
marcados no painel de marcação por foto — a mesma foto e os mesmos dois riscos que a
"segunda rodada" de 09/09 já tinha testado uma vez. O dossiê foi reproduzido sem rede
(com e sem a marcação) e a foto foi aberta no acervo (`auditoria-nrs-fixtures`) antes
de concluir causa.

### 1. A marcação funcionou exatamente como o código promete — e sem ela o dossiê seria lixo

Reproduzido sem rede: **sem marcação, zero riscos roteiam** e o dossiê inteiro vem da
busca textual, encabeçado por `NR-06 6.9.3` (EPI) e uma fileira de itens de ergonomia da
NR-17 — nada de NR-18, nada sobre abertura ou vão nenhum. **Com a marcação**, os itens
dos dois riscos apontados entram na frente, exatamente na ordem declarada:
`NR-18 18.9.2` (D1), `NR-08 8.3.2.2` (D2) — os dois de `abertura_piso_desprotegida` — e
`NR-18 18.9.3` (D3) — de `vao_caixa_elevador_sem_fechamento`. A trilha do laudo confirma
os dois nomes certos e a trava 1 do desenho segurando: *"Risco(s) apontado(s) pelo
inspetor antes da análise... A leitura da imagem foi feita sem acesso a esta
indicação."* O Analista usou `NR-18 18.9.2` — o item marcado chegou e foi enquadrado.

### 2. Mas de novo pendurado no achado errado — n=2 para a mesma fronteira de 09/09

A constatação: *"A grade metálica instalada sobre o vão vertical apresenta sinais de
corrosão na superfície e na estrutura de suporte."* **Nenhum fato do Olho menciona
quantos pontos de fixação a grade tem** — os cinco achados falam de corrosão, do vão
atrás da grade, de uma estrutura vermelha na borda esquerda e de uma junta com
resíduos. É a *segunda* vez, com a *mesma foto*, que a marcação recupera o item certo
(`18.9.2`) e o Analista o pendura no achado que O OLHO viu (a corrosão), não no achado
que o ENGENHEIRO nomeou no arquivo (o ponto de fixação único) — em 09/09 saiu **alta**
sobre a mesma corrosão, hoje saiu **média**, e as duas descrições do achado são quase
idênticas palavra por palavra, o que bate com o achado de 10/09 de que o Olho não varia
sobre a mesma foto e quem varia é a gravidade do Analista/Diretor.
**Confirma de novo a fronteira medida em 09/09: marcação dirige o dossiê, não o Olho —
ela garante que o item certo esteja disponível, não que o achado certo seja visto.**

### 3. A foto real foi aberta, e a hipótese registrada na fila ("é resolução") fica mais estreita, não confirmada

A fila apostava: *"se os pontos de fixação não forem visíveis na escala em que o Olho
recebe a foto (504 px de largura numa foto retrato), o conserto não é marcação nem
prompt, é resolução."* Aberta a foto ORIGINAL (não a versão reduzida que o Olho recebe):
uma tela metálica expandida cobre o vão, presa por uma cantoneira enferrujada no topo e
por uma barra vertical avermelhada na borda esquerda — mas **nenhum ponto de fixação
individual (parafuso, grampo, amarração) aparece isolado e contável no recorte**, nem em
resolução plena. O enquadramento mostra a face da tela, não a base nem os quatro cantos
onde a fixação de fato aconteceria. **Medi X, afirmo Y com cuidado aqui**: o que está
medido é que EU, olhando a foto em resolução original, não consigo contar pontos de
fixação nela — não que nenhuma resolução resolveria, e não que o Olho tentou e falhou
por causa do tamanho (ele nem chegou a mencionar o atributo). O que isso desloca é a
hipótese: o limite pode não ser (só) o downscale para 896/504 px — pode ser que **esta
foto, neste ângulo, não enquadra o que decidiria a pergunta**, caso em que nem a
correção de resolução nem a de prompt resolveriam sozinhas; precisaria de uma foto que
mostrasse a base da grade.

### 4. Critério de aceite — como saiu

Pelo critério de recuperação-vs-laudo: **recuperação parcial** (o item marcado chegou ao
Analista e foi usado — a metade que o desenho D promete cumpriu), **laudo com lastro
real mas fora do alvo** (a corrosão é visível na foto de verdade — não é falso positivo
—, mas não é o que o nome do arquivo pede). Gabarito contra o nome do arquivo: **não
fecha** (achado do nome — ponto de fixação único — não é o que saiu), mas também não é
falso positivo: é o padrão "item certo, achado errado" que 09/09 já tinha registrado
nesta mesma foto.

---

## Validação em produção de 15/09/2026 — o lote de PESSOA NA CENA

Obra "teste 7". **5 laudos, 6 NCs, 0 não auditadas, 1 ciclo em todos.** Hash não lido na
barra lateral nesta sessão — os cinco HTML chegaram prontos e o `main` de então
(`2cb0eee`/`706424b`, sem diferença de código entre os dois) foi inferido do merge, o
mesmo dado que já faltou em 09/09 e 12/09. Os cinco dossiês foram reproduzidos sem rede a
partir dos fatos reais (`rotear_riscos` + `montar_dossie`, sem tocar a Groq), e as quatro
fotos de pessoa foram abertas no acervo (`auditoria-nrs-fixtures`) antes de concluir
causa — a foto do vão da âncora não precisou, é a oitava execução com o mesmo padrão.

| # | Foto | O Olho escreveu sobre a pessoa/EPI? | NC entregue |
|---|---|---|---|
| 1 | `TRABALHADOR SEM EPI` | **nada** — nenhum achado menciona o trabalhador | `NR-08 8.3.2.2` alta (aberturas na parede) |
| 2 | `TRABALHADOR SEM PROTEÇÃO` | **nada** — só "Operador segurando uma serra circular..." | **0 NC** |
| 3 | `TRABALHADOR SE EPI` | **nada** | `NR-18 18.10.2.4` média (cabo) + `NR-08 8.3.2.1` baixa (piso) |
| 4 | `6 PAV. TRABALHADORES SEM DOCUMENTAÇÃO` (contraparte) | **nada** — "2" na contagem, nenhum fato sobre os dois | `NR-18 18.9.2` **CRÍTICA** (piso) + `NR-11 11.3.3` média (empilhamento) |
| 5 | `13 PAV. PEÇO ELEVADOR SEM PROTEÇÃO` (âncora) | — | `NR-18 18.9.2` **alta** (não crítica — ver seção 4) |

**Gabarito contra o nome do arquivo: 1 de 5** (só a âncora) — **abaixo do piso da
previsão registrada ("3 a 5 de 5")**, e por um mecanismo que o pré-registro não tinha
como medir: nenhuma das quatro fotos de pessoa produziu um único fato sobre o que o
trabalhador veste.

### 1. O achado principal: o portão `exige_pessoa` continua mudo, e agora a causa está no código, não é mais hipótese

O registro "o portão de pessoa continua sem lote" vem se repetindo desde 03/09, inclusive
nas validações de 11/09, 12/09 e 14/09 (cada uma com foto de gente na cena e nenhum dos 25
riscos disparando) — este era o primeiro lote desenhado especificamente para isso, com
três fotos de trabalhador operando ferramenta sem EPI visível. **Aberta cada uma no acervo,
a ausência de capacete (foto 1) e de luva (fotos 2 e 3) está lá, visível, exatamente como
a leitura cega do pré-registro previu.** Mas nenhum dos três laudos registrou o fato, e a
causa não é sorte de amostra: é `PROMPT_OLHO` (`auditoria/pipeline.py:314-383`).

Medido em `PROMPT_OLHO` (grep contra o texto que vai para a Groq, não leitura): **zero**
ocorrências de `epi`, `capacete`, `luva`, `óculos`, `protetor` ou `bota`. Os parágrafos
que instruem o Olho a descrever atributo — linhas 339-346 — cobrem barreira/tela/rede,
máquina/painel elétrico/andaime/escada/cinta/cabo, e não dizem uma palavra sobre a
pessoa. O único lugar em que a pessoa aparece no schema é `pessoas: {presentes,
quantidade, descricao}` (linha 327), com `descricao` documentada como "**o que fazem**,
ou vazio" — nunca "o que veste". E mesmo que o modelo escrevesse ali, não adiantaria:
`agente_olho` (linha 416) lê `dados.get("pessoas")` e só repassa `presentes` e
`quantidade` para a `Visao` (linhas 428-429) — **`descricao` é lida e descartada**, nunca
chega a `achados`, ao roteamento nem ao dossiê. Duas causas, não uma: o prompt não pede
o atributo, e o único campo que poderia carregá-lo é jogado fora antes de sair do Olho.

**É por isso que os três mecanismos do pré-registro nunca tiveram chance.** A seção 3 do
pré-registro apostava que "sem luva"/"sem óculos de proteção"/"sem protetor auricular"
routearia `epi_nao_utilizado` (`auditoria/riscos/ambiental.py:30`) e, pela armadilha dos
4+ radicais, também `serra_bancada_sem_protecao_disco`
(`auditoria/riscos/industria.py:124`, crítica) e mais quatro ou cinco riscos alheios —
medido e reproduzido aqui: **nenhum dos dois disparou em foto nenhuma**, porque a frase que os
sustentava nunca foi escrita. Não é o mecanismo errado; é a matéria-prima que nunca
chegou. `epi_nao_utilizado` continua com **zero disparos em produção desde 02/09**,
agora mesmo nas três fotos que este lote desenhou de propósito para ele.

### 2. A foto 4 é a quarta ocorrência confirmada da classe VÃO INEXISTENTE, e é a mais cara: NC crítica numa foto de controle

A foto real mostra exatamente o que o pré-registro leu às cegas: dois trabalhadores de
costas dentro de um vão de porta em alvenaria de tijolos aparentes, **os dois com
capacete** (um vermelho, um cinza claro), sacos de cimento encostados na parede à
esquerda, mesa metálica ao fundo. **O piso do corredor é contínuo — não há abertura
nenhuma.** O Olho escreveu, mesmo assim: *"Abertura retangular no piso de concreto, sem
tampa ou proteção, localizada no centro do corredor"* e *"Estrutura metálica de cor
escura, com formato de escada ou suporte, posicionada sobre a abertura no piso"* — a
mesa metálica virou uma estrutura sobre um vão que não existe. `abertura_piso_desprotegida`
casou a 1,00 no sinal `"abertura no piso"` (dois radicais, os dois do próprio achado),
pôs `NR-18 18.9.2` em D1 curado, e o Analista o enquadrou como **crítica, prazo de 1
dia** — a foto que o desenho do lote existia para fechar em 0 NC virou a pior NC do lote.

É a mesma classe das três ocorrências anteriores (foto 3 do lote de máquina em 11/09,
confirmada pelo engenheiro; foto 3 do lote de elétrica em 12/09, idem; a contraparte do
lote de escada em 15/09, pela leitura geométrica sem árbitro) — **mas aqui o objeto é
fabricado do zero**, não uma feature real inflada, e ela nasce sobre uma cena que a
imagem mostra sem defeito nenhum. **Nenhuma trava do pipeline pergunta se o vão existe**;
o Diretor confere a constatação contra o fato, e o fato mente.

**A segunda NC da foto, `NR-11 11.3.3` (empilhamento a menos de 0,50 m da estrutura), tem
lastro real** — os sacos de cimento estão de fato encostados na parede branca na foto —,
o que faz deste laudo um caso raro de uma NC real e uma fabricada lado a lado, sem que
nada no documento distinga as duas.

### 3. Fotos 2 e 3: o ruído de NR-12 nunca teve chance, mas o dossiê tem duas armadilhas novas não usadas pelo Analista

**Foto 2 fechou em 0 NC**, e a reprodução mostra por quê: só `abertura_piso_desprotegida`
roteou, e sozinho — nenhum risco de EPI, nenhum de máquina. Mas ele **não devia ter
roteado**: o sinal `"placa apoiada sobre abertura"` (4 radicais — `plac`, `apoiad`,
`abertur`, `sobr`) casou a 0,75 (faltando `abertur`) contra o achado *"Placa metálica
clara... apoiada sobre a bancada"* — uma chapa sobre uma mesa, sem abertura nenhuma
por perto. É a armadilha dos 4+ radicais de sempre, e o Analista não a usou (não haveria
como: o fato não sustenta a constatação), mas ela entrou curada em D1 do dossiê.

**Foto 3 fechou com duas NCs reais** — `NR-18 18.10.2.4` (cabo elétrico estendido pelo
piso, cruzando a circulação) e `NR-08 8.3.2.1` (resíduos no piso) —, as duas com lastro
visual confirmado na foto. Mas o roteamento também trouxe `escavacao_sem_escoramento_ou_talude`
(gravidade **crítica**), numa sala de acabamento sem vala nenhuma: o sinal
`"buraco com parede reta"` (`pared`, `reta`, `com`, `burac`) casou a 0,75 — `reta` e `com`
vêm do achado da bancada ("com tampo plano e pernas **retas**"), `pared` vem do ambiente
("**paredes** brancas"), faltando só `burac`. É uma variante nova da mesma família: `com`
já está em `PALAVRAS_COLA` (`auditoria/riscos/__init__.py:55`), mas continua contando
para a âncora de 2 radicais próprios exigida pelo roteador — ela barra o ambiente
sozinho, não barra a cola do próprio achado. Não chegou ao laudo porque o Analista não a
usou, mas é a primeira vez que essa combinação específica (mobília + parede) é medida.

**E o mecanismo "abertura vertical" que o usuário pediu para vigiar de fato disparou —
na foto 3, não na 4, e sem produzir NC falsa.** O achado *"Abertura vertical sem
fechamento (janela ou vão) ao fundo... com uma tela de malha metálica visível na lateral
esquerda"* casou `"abertura vertical"` a 1,00 e pôs `NR-08 8.3.2.2` em D3 curado. O
Analista não o usou — corretamente: o próprio fato registra a tela de malha presente, e
não há lastro para "sem proteção". É o que a régua (a)-(d) previa: o roteamento oferece,
o Analista lê o fato inteiro antes de enquadrar.

### 4. A âncora manteve o item, mas não a gravidade — primeira queda de crítica para alta em oito execuções

O dossiê reproduz o de sempre: `18.9.2` em D1 e `8.3.2.2` em D2 curados, `NR-18 18.9.3`
continua fora. **Mas o laudo saiu com `NR-18 18.9.2` ALTA, não crítica** — a primeira
vez, nas oito execuções com laudo lido desde 09/09, em que esse item não sai crítico
nesta foto. A trilha mostra o caminho provável: o Diretor aparou a constatação,
retirando *"a afirmação categórica de que não há evidência de travamento, que é uma
limitação da moldura fotográfica e não um fato visível"* — e é plausível que a
gravidade tenha caído junto, no mesmo aparo (o schema do Diretor permite ajustar
`gravidade` dentro do próprio aparo). Não é um veto nem um erro óbvio — é a mesma
regra da moldura de sempre, só que desta vez ela também mexeu na gravidade, e isso
nunca tinha sido registrado. Vale ficar de olho no próximo lote se a âncora volta a
crítica ou se "alta" é o novo normal depois de um aparo assim.

### 5. O que este lote muda no método

**O pré-registro mediu o mecanismo certo sobre uma premissa que nunca foi checada**: que
o Olho, ao ver um trabalhador sem capacete ou sem luva, escreveria isso. As fotos
anteriores deste acervo com pessoa na cena nunca tinham testado essa premissa
especificamente — o gap estava sempre coberto pela explicação "o Olho não viu o achado
certo" (a classe já registrada nas fotos de içamento e elétrica). Aqui ficou claro que
não é falta de sorte de amostra: **é o prompt nunca ter pedido o atributo, e o único
campo que poderia carregá-lo (`pessoas.descricao`) ser descartado no parse.** Isso muda
o próximo passo — não é "tente outra foto de pessoa", é "mude o prompt e o parse, e só
então meça de novo". Ver "Em aberto" para a proposta e o porquê de não ter sido aplicada
nesta sessão sem o usuário decidir primeiro.

---

## Pré-registro do lote de PESSOA NA CENA — 5 fotos (escrito em 16/09/2026, ANTES de rodar)

`main` em `2cb0eee`. **Quarto lote pré-registrado do histórico.** As quatro fotos foram
abertas aqui, os dossiês medidos sobre fatos SINTÉTICOS e a previsão escrita antes de o
lote existir. **Medi X, afirmo Y, e aqui X é estreito**: o que está medido é o DOSSIÊ
sobre fatos que escrevi eu, imitando o Olho; o que o Olho vai escrever é hipótese até os
laudos chegarem.

| # | Foto | Papel | O que ela responde |
|---|---|---|---|
| 1 | `TRABALHADOR SEM EPI` | EPI ausente, sem ruído | trabalhador aplicando massa, sem capacete visível — nenhuma ferramenta de corte na cena |
| 2 | `TRABALHADOR SEM PROTEÇÃO` | EPI ausente + ferramenta de corte | trabalhador operando serra circular manual sobre bancada, sem luva/óculos/protetor auricular |
| 3 | `TRABALHADOR SE EPI` | idem, segunda medição | mesma configuração da foto 2 — nome sem o "M" de "SEM", provável erro de digitação do engenheiro |
| 4 | `6 PAV. TRABALHADORES SEM DOCUMENTAÇÃO` | **CONTRAPARTE / controle** | dois trabalhadores de costas, os dois **com capacete** — o nome pede algo (documentação) que nenhuma foto pode comprovar |
| 5 | `13 PAV. PEÇO ELEVADOR SEM PROTEÇÃO` | âncora | `NR-18 18.9.2` em toda execução com laudo lido desde 09/09 |

**Este é o primeiro lote desenhado para exercer o portão `exige_pessoa`**, que governa 25
dos 126 riscos e nunca disparou em produção em nenhum lote anterior — nenhum routeou
risco de EPI porque nenhum deles tinha o achado certo no vocabulário. (Já estava
registrado assim desde 03/09: "o portão de pessoa continua sem lote".)

### 1. A leitura das quatro imagens, feita antes de qualquer fato

Cega por construção, e **não é gabarito** — regra (a)-(d) do acervo histórico: a imagem
decide GEOMETRIA e PRESENÇA (há ou não capacete no recorte), não decide MATERIAL, NOME
nem ESTADO.

- **Foto 1** — trabalhador ajoelhado no canto de uma sala já pintada, aplicando massa
  corrida na parede com espátula, camisa de manga longa com logotipo de empresa
  ("RPJA"), calça jeans. **Nenhum capacete no recorte.** Óculos e luvas não são
  decidíveis com confiança na escala em que a foto chega. Placa de gesso/drywall
  encostada na parede, vassoura, saco de massa, pallets de madeira no chão — nenhuma
  ferramenta de corte na cena.
- **Foto 2** — trabalhador de manga longa azul operando serra circular manual amarela
  sobre uma bancada de madeira tosca (tábuas apoiadas em cavalete improvisado), cortando
  uma placa clara. **Mão segurando a serra sem luva visível.** Rosto não aparece de
  frente o bastante para decidir óculos/protetor auricular com segurança, mas nenhum dos
  dois é visível na lateral da cabeça.
- **Foto 3** — mesma configuração: trabalhador de manga longa azul ("FORTLEV"), boné (não
  capacete), calça jeans, bota, operando serra circular manual amarela sobre bancada com
  trilho guia, cortando placa clara. **Sem luva visível na mão que segura a serra, sem
  óculos de proteção.**
- **Foto 4** — dois trabalhadores de costas, dentro de um vão de porta em alvenaria de
  tijolos, **os dois com capacete** (um vermelho, um cinza claro). Sacos de cimento
  empilhados ao lado, mesa metálica ao fundo. Nada na cena sugere ausência de
  documentação — documento é papel, não aparece numa foto de dois trabalhadores de
  costas.

### 2. O que está MEDIDO: os cinco dossiês, sem rede

| # | riscos roteados | entradas | curadas | o que encabeça |
|---|---|---|---|---|
| 1 | `epi_nao_utilizado` | 7 | 2 | `NR-06 6.5.1` **D1**, `6.6.1` D2 |
| 2 | `epi_nao_utilizado` + 5 outros (ver seção 3) | 22 | 12 | `NR-06 6.5.1`/`6.6.1` **D1-D2**, `NR-12 12.5.1`/`12.5.10` D3-D4 |
| 3 | `epi_nao_utilizado` + 4 outros | 22 | 10 | idem, sem `area_carpintaria_armacao_irregular` |
| 4 | **nenhum** | 6 | 0 | busca textual só, `NR-01`/`NR-06` genéricos |
| 5 | `abertura_piso_desprotegida` | 7 | 2 | `18.9.2` **D1**, `8.3.2.2` D2 |

A âncora reproduz o que sete execuções anteriores mediram, `18.9.3` continua fora do
dossiê.

**A foto 1 é limpa: 7 entradas, sem ruído de outra NR.** `epi_nao_utilizado` casa com
três sinais a cobertura 1,00 cada (`"sem capacete"`, e o `pontos` acumulado o deixa muito
à frente de tudo mais no ranqueamento), e o dossiê inteiro é NR-01/NR-06. **É a foto mais
segura do lote.**

### 3. O achado principal: o vocabulário do EPI ausente colide com máquina, solda e transporte manual

Nas fotos 2 e 3, junto com `epi_nao_utilizado` (que também dispara limpo, 1,00 em três
sinais: `"sem luva"`, `"sem oculos de protecao"`, `"sem protetor auricular"`), roteiam
**mais quatro ou cinco riscos que não têm nada a ver com a cena**:

| risco | sinal | cobertura | falta | itens | gravidade |
|---|---|---|---|---|---|
| `serra_bancada_sem_protecao_disco` | `"serra de bancada improvisada"` | **1,00** | — | `NR-12 12.5.1`, `12.5.10` | **crítica** |
| `esmeril_sem_protecao_rebolo` | `"esmerilhadeira de bancada sem protecao"` | 0,75 | `esmerilhadeir` | `NR-12 12.5.10`, `12.5.11` | alta |
| `area_carpintaria_armacao_irregular` | `"sobras de madeira embaixo da serra"` | 0,75 | `embaix` | `NR-18 18.7.3.1`, `18.7.3.2` | média |
| `transporte_manual_sem_meio_mecanico` | `"carrinho sem protecao de mao"` | 0,75 | `carrinh` | `NR-17 17.5.3`, `NR-11 11.2.2.1`, `11.1.4` | média |
| `solda_sem_protecao_contra_radiacao` | `"corte com maçarico sem protecao"` | 0,80 | `macaric` | `NR-09 9.5.2`, `NR-06 6.5.1`/`6.5.2` | alta |

**Quatro dos cinco são robustos** — não dependem de nenhuma palavra frágil que eu tenha
escolhido: `serra_bancada` casa porque o achado tem `serr`+`bancad` e o ambiente tem
`improvisada` (a bancada real É tosca, então é provável que o Olho a descreva assim);
`area_carpintaria` casa inteiramente dentro do achado da serra (`serr`+`madeir`+`sobr`,
de "sobre bancada de madeira"); `transporte_manual` casa inteiramente dentro do achado da
mão (`mao`+`sem`+`proteca`); `esmeril` casa com `sem`+`proteca` do achado dos óculos e
`bancad` do ambiente. **O de solda é o mais frágil**: medido de novo sem a palavra
"corte" no ambiente, ele **não dispara** — os outros quatro continuam. Ele depende
especificamente de eu ter escrito "bancada de **corte**" no ambiente sintético, e é a
única linha desta tabela que pode não se realizar.

**É a armadilha dos 4+ radicais em estado puro, mas numa forma nova**: não é o `sem`
completando um sinal alheio — é o vocabulário que o `PROMPT_OLHO` **manda** usar para
reportar EPI ausente ("sem luva", "sem óculos de proteção", "sem protetor auricular")
que, somado a "serra"/"bancada"/"madeira"/"mão" do achado da ferramenta, casa com sinais
de risco de máquina ESTACIONÁRIA, transporte manual e solda — nenhum dos quais tem
qualquer relação com um trabalhador usando uma serra circular **manual e portátil** sobre
um cavalete. **Quanto mais completo o Olho descreve a ausência de EPI, mais sinais de
outras NRs ele alimenta.**

**O `serra_bancada_sem_protecao_disco` é o mais caro dos cinco**: gravidade **crítica**,
mesma classe da âncora, e o item que ele cita (`NR-12 12.5.1`/`12.5.10`, zonas de perigo
e risco de ruptura de máquina) não tem nada a ver com uma serra circular manual — é
vocabulário de serra de bancada **estacionária**, com disco fixo. Não há essa máquina em
nenhuma das duas fotos.

**O que isso NÃO decide**: `epi_nao_utilizado` pontua mais alto que qualquer um dos cinco
(três sinais a 1,00, cada um valendo mais que um sinal só de `serra_bancada`), então ele
deve ficar em D1/D2 do dossiê ranqueado, à frente do ruído. **O risco não é o item certo
sumir — é o Analista enxergar 22 entradas, boa parte delas de "proteção" de máquina, e
acrescentar uma SEGUNDA não conformidade falsa** (a de NR-12, gravidade crítica) ao lado
da certa, ou trocar a certa pela errada. **Previsão: a NC de EPI sai; o risco real é uma
NC extra e falsa de `12.5.1`/`12.5.10` junto dela.**

### 4. A foto 4 é inalcançável por construção, não por mérito da cena

Buscado no catálogo inteiro: o único sinal que menciona documentação/identificação de
trabalhador é `"operador sem cracha"`, em `empilhadeira_operacao_irregular`
(`industria.py`) — específico de **operador de empilhadeira**, e nada na foto (dois
trabalhadores parados num vão de porta) aciona vocabulário de empilhadeira. **Não existe,
hoje, risco genérico para "trabalhador sem documentação" fora do contexto de
empilhadeira.** Reproduzido: zero riscos roteiam, dossiê de seis entradas por busca
textual, nenhuma pertinente.

**Isso é diferente das fotos de "contraparte" anteriores** (a `17 PARA O 18 PAV` do lote
de escada, a `18 PAV. PROTEÇÃO POÇO DE ELEVADOR` do lote de poço): naquelas, a cena
mostrava uma condição de segurança em ordem que um risco curado PODERIA capturar e não
capturava por engano do Olho. Aqui, a cena não tem nada de errado (os dois trabalhadores
usam capacete) **e** o achado que o nome pede não é do tipo que uma foto resolve —
documento é papel, e a foto não mostra papel nenhum.

**O `/critico` rejeitou a primeira redação: a previsão de 0 NC não testava a hipótese
concorrente mais repetida do histórico deste arquivo — o vão da porta sendo descrito como
abertura de parede desprotegida.** Medido: com o achado dizendo "vão de acesso na parede
de alvenaria, sem porta instalada", `abertura_parede_desprotegida` **não dispara** — os
dois sinais do risco (`"abertura vertical"`, `"vao de janela aberto"`) exigem a palavra
`vertical` ou `janela`, e nenhuma delas é vocabulário natural para uma porta interna
comum. **Mas dispara se o Olho escrever "abertura vertical"** para o mesmo vão — medido
também —, trazendo `NR-08 8.3.2.2` numa foto sem vão de queda nenhum. É condicional a uma
palavra específica, a mesma classe da fragilidade do risco de solda na seção 3: **o risco
não é zero, é estreito**, e vale vigiar se o Olho usa "vertical" para descrever o vão.
**Previsão: 0 NC**, mas por um
motivo estrutural que nenhuma foto futura de "documentação" vai resolver sozinha.

### 5. Critério de aceite, e onde cada coisa se lê

1. **Na LISTA DE FATOS do Olho** — se ele escreve "sem capacete" na foto 1 (a imagem
   decide isso, presença); se escreve "sem luva"/"sem óculos de proteção"/"sem protetor
   auricular" nas fotos 2 e 3 (é o vocabulário que o `PROMPT_OLHO` manda usar, e é ele
   que sustenta tanto o acerto quanto o ruído); se menciona "bancada"/"madeira" nas fotos
   2 e 3 (decide se `area_carpintaria` e `esmeril` disparam); se **não** escreve nada
   sobre documentos, crachá ou identificação na foto 4 (não deveria — não há nada disso
   no recorte); e se descreve o vão da porta da foto 4 como **"abertura vertical"** (é o
   único vocabulário que dispararia `abertura_parede_desprotegida` ali, uma NC falsa sem
   relação com documentação — ver a seção 4).
2. **Na CONTAGEM de trabalhadores** — a foto 4 tem dois trabalhadores; se
   `quantidade_pessoas` sair 1 ou 0, é o portão de pessoa contado errado, e vale medir
   separado da questão de documentação.
3. **Nas NÃO CONFORMIDADES**:
   - **Foto 1** — NC de EPI ausente (sem capacete) deve sair, `NR-06 6.5.1` ou `6.6.1`,
     sem concorrência de outra NR. Se sair limpa, fecha o gabarito e o laudo ao mesmo
     tempo — não há a divisão em duas metades que os últimos lotes exigiram, porque
     aqui o achado é geometria pura (há ou não capacete) e a foto decide sozinha.
   - **Fotos 2 e 3** — a NC de EPI (certa) deve sair. **O que vigiar é se uma SEGUNDA NC,
     falsa, de `NR-12 12.5.1`/`12.5.10` (proteção de disco de serra de bancada,
     crítica) aparece ao lado dela** — isso é falso positivo declarado de antemão: não
     há serra de bancada estacionária em nenhuma das duas fotos, só serra circular
     manual. Se a NC de EPI sair sozinha, essas duas fotos fecham limpo.
   - **Foto 4** — 0 NC é o acerto. Qualquer NC nesta foto é falso positivo, porque a cena
     mostra os dois EPIs (capacete) em ordem.
   - A âncora mantendo `18.9.2`.

**O gabarito previsto: 3 a 5 de 5**, a faixa mais larga registrada neste arquivo — porque
a foto 1 e a foto 4 são previsões fortes (uma quase certa de fechar, a outra quase certa
de dar 0 NC certo), e as fotos 2 e 3 dependem inteiramente de uma coisa só: se o Analista
resiste à tentação do `NR-12 12.5.1`/`12.5.10` crítico que o dossiê pobre em vocabulário
de máquina põe ao lado do item certo. **É o primeiro lote em que o risco não é o item
certo ficar de fora — é um item errado e mais grave entrar junto.**

---

## O que travou o lote de 04/09/2026: o OTPM, e não o TPM

O lote de 12 fotos de poço de elevador rodou e **só 1 foto foi auditada**. As outras
levaram 429. Parte disso era regressão do #27 (o `except` largo que fazia erro de cota
virar laudo de foto examinada), fechada pelo #28 e registrada na tabela de armadilhas.
Mas a causa dos 429 não era volume, nem código: é o **OTPM — output tokens per minute —
da organização, que é 1.000**. Mensagem literal, lida nos Logs do console da Groq:

> "Request too large for model qwen/qwen3.8-27b … on output tokens per minute (OTPM):
> Limit 1000, Requested 1113. The request's expected output tokens exceed the enforced
> limit; reduce max_tokens (or the request's expected output) and try again."

O pipeline pedia 1.600 (Olho), 1.800 (Analista) e 3.000 (Diretor): **cada um sozinho
excede a janela inteira do minuto**. A Groq recusa antes de processar (latência
0,006 s), então nem a primeira foto do dia passa. Isso não está na tabela pública do
plano gratuito — lá só há o TPM de 8.000 do `qwen3.8-27b`, que soma entrada e saída;
OTPM e ITPM são limites **por organização**, e a doc da Groq diz que só algumas os têm.
Passou a ser aplicado entre 02 e 04/09: nos dias 01 e 02 rodaram ~20 fotos/dia com a
mesma chave, sem travar.

**Esperar não resolve, e essa é a parte que muda o desenho.** A requisição é rejeitada
pelo TAMANHO que declara, não pela fila: espera-e-retentativa lendo o `retry-after`
falharia 100% das vezes. E a retentativa de `_conversar_sem_cortar`, que DOBRA o teto
(3.200/3.600/6.000), era 429 garantido — a segunda tentativa morria sem nunca chegar ao
modelo, justamente na hora em que a foto já foi lida e cobrada.

O que o lote também mostrou, a favor de cortar: as respostas que passaram nos logs da
Groq tiveram **250, 435, 477 e 501 tokens de saída**. A folga de 1.600 a 3.000 nunca foi
usada. O painel de uso mede a mesma coisa por outro caminho: em 04/09 o dia inteiro deu
**18,9 mil tokens de entrada e 4,8 mil de saída em ~10 solicitações** — ~480 de saída
por chamada, com a saída valendo ~20% do total. É essa proporção que torna o OTPM o
gargalo e não o TPM: a janela de 8.000 por minuto não aperta quando só um quinto do
tráfego é saída, e a de 1.000 aperta sempre.

**Conserto (nesta sessão):** `ClienteGroq.teto_permitido()` corta todo teto de saída
para 90% do `OTPM_ORGANIZACAO` (900 com o limite de 1.000), no único ponto do projeto
em que `max_completion_tokens` é montado — os agentes continuam pedindo o que precisam,
e quando o tier pago subir o limite basta o número na barra lateral. A retentativa
consulta `teto_permitido` antes: quando o dobro não cabe, o que muda entre as duas
tentativas passa a ser o **pedido** (`_com_pedido_de_concisao`, que manda encurtar a
resposta), não o teto. A margem de 10% existe porque a Groq recusou um pedido de 1.600
dizendo "Requested 1113": o número que ela compara com o limite não é o
`max_completion_tokens` que mandamos, e não sabemos a fórmula.

**Onde o OTPM NÃO está**: `settings/limits` mostra só o TPM somado (nenhuma coluna de
saída, e o modal de limites do projeto também não tem), e `dashboard/usage` dá consumo,
não limite — as duas telas foram olhadas em 04/09. A fonte do número é a mensagem de
erro em **Registros**, que diz `Limit 1000` com todas as letras. Se um dia ele mudar, é
de lá que se descobre, e é o campo "Limite de saída por minuto da conta (OTPM)" na
barra lateral que ajusta, sem mexer em código.

**O teto de 900 morde o Olho antes do Diretor, e ninguém tinha olhado para isso.**
Foi o `/critico` que apontou: o corte valia para os três, e o único agente cuja saída
**é** a evidência do laudo é o Olho — um achado que ele não escreve não é enquadrado
por ninguém depois. Medido sem rede, sobre a resposta do dublê (a cena de canteiro
de `FATOS_DEMO`, 5 achados): **~95 tokens por achado**, ~397 no total. Extrapolando,
**10 achados ≈ 872 tokens e 12 ≈ 1.062** — ou seja, uma foto rica de canteiro passa
dos 900. Não há como dar mais espaço a ele (900 é o máximo da conta), então o que se
fez foi impedir que a segunda tentativa PIORE isso: o `PEDIDO_DE_CONCISAO` manda
cortar prosa e proíbe encurtar a lista, com a razão escrita. Para o Diretor a mesma
omissão é pior de outro jeito: enquadramento sem entrada em `conferencia` chega a
`_exigencia_ancorada("")`, que é falso, e vira **veto automático com o motivo
errado** — a NC verdadeira cai e o laudo diz que ela não descumpre o item. **Há teste
travando as duas cláusulas.** O que continua sem resposta é o truncamento na PRIMEIRA
chamada do Olho, numa foto de muitos achados: aí não há mitigação, só o lote dirá.

**Ressalva que ficou de pé:** o Diretor pede 3.000 e é o agente que já morreu por
truncamento no lote de 29/08. Com 900 ele pode truncar de novo, e o remédio antigo
(dobrar o teto) agora é proibido. O que se fez contra isso: o `PROMPT_DIRETOR` passou a
pedir a **oração que basta** nas duas cópias literais da conferência, em vez do
parágrafo inteiro — "nunca menos que ela", porque `_exigencia_ancorada` recusa trecho
com menos de 12 caracteres. Se ainda assim truncar no lote, as saídas são pedir menos
por chamada (fatiar a conferência do Diretor) ou o Dev Tier pago.

---

## Validação em produção de 15/09/2026 — o lote de ESCADA, 5 fotos

Obra "teste". **5 laudos, 6 NCs, 0 não auditadas, 1 ciclo em todos.** Rodado no `f7449a2`,
hash **lido** na barra lateral (print do usuário), com `qwen/qwen3.8-27b` nos dois campos —
confirmado pelo consumo do dia mostrando um único balde ("qwen/qwen3.8-27b — 41.143 de
200.000 tokens", 5 imagens, 8.228 tokens/imagem). Ciclos Padrão, resolução 896, OTPM 1000:
tudo no padrão, nada a descartar por configuração fora do comparável. Os cinco HTML foram
lidos e os cinco dossiês reproduzidos sem rede a partir dos fatos reais, e as cinco fotos
foram abertas no acervo (`auditoria-nrs-fixtures`) antes de concluir causa.

| # | Foto | O que o Olho escreveu do objeto do nome | NC entregue |
|---|---|---|---|
| 1 | `ESCADA EM LOCAL INADEQUADO` | "Escada de extensão metálica com cor azul, apoiada em ângulo contra a parede... com os pés sobre o piso de concreto" — **nenhuma menção a corredor/porta/circulação no achado da escada** | `NR-18 18.8.6.12` (sapata) alta |
| 2 | `20 PROTEÇÃO DE ESCADA DANIFICADA` | "Tela plástica flexível... presa por fitas de tecido... apoiada em ripas de madeira" — **nenhuma menção a `guarda-corpo`/`corrimão`** | `NR-08 8.3.2.2` alta + `NR-18 18.8.6.1` crítica |
| 3 | `18 PAV. PROTEÇÃO DE ESCADA QUEBRADA 18 PARA O 19` | "bordas esgarçadas e fios soltos visíveis na extremidade direita" — idem, sem `guarda-corpo` | `NR-08 8.3.2.2` crítica |
| 4 | `PROTEÇÃO DE ESCADA 17 PARA O 18 PAV` (contraparte) | "Abertura vertical no piso, com bordas de concreto, localizada ao lado da grade metálica" | `NR-18 18.9.2` **crítica** |
| 5 | `13 PAV. PEÇO ELEVADOR SEM PROTEÇÃO` (âncora) | — | `NR-18 18.9.2` crítica |

**Gabarito contra o nome do arquivo: 3 de 5** (fotos 2, 3 e a âncora), pelo critério de
10/09. **No teto da previsão registrada ("2 a 3 de 5")** — mas o número bateu por um
mecanismo quase todo diferente do que a previsão apostava, e é isso que este lote ensina.

### 1. O falso positivo central da previsão não se realizou — porque o Olho não escreveu a palavra que o sustentava

A seção 3 do pré-registro apostava que `andaime_sem_guarda_corpo` dispararia nas fotos 2
e 3 sobre a palavra "guarda-corpo" negada no mesmo fato ("sem corrimão nem guarda-corpo
rígido"), trazendo `NR-18 18.9.1`/`18.9.4.2` "pela porta errada" — item certo, com o
risco de o rótulo sair "Andaime sem guarda-corpo" numa foto de escada. **Medido na LISTA
DE FATOS do Olho: `guarda-corpo`/`corrimão` não aparece em nenhum achado nem no ambiente
das duas fotos** — a palavra só entra depois, na ação corretiva e no parecer (que citam
"guarda-corpo" quatro vezes ao todo, mas nunca antes disso). O Olho descreveu a tela
(rasgada, esgarçada, com fios soltos) e nada mais sobre o que falta na lateral do lance,
e é só o que ele escreve que `rotear_riscos` enxerga. `andaime_sem_guarda_corpo` **não rotou em nenhuma das duas** — reproduzido sem
rede: riscos roteados na foto 2 são `abertura_parede_desprotegida`, `escada_mao_irregular`
e `escada_provisoria_coletiva_irregular`; na foto 3, só `abertura_parede_desprotegida` e
`canteiro_desorganizado_circulacao_obstruida`.

**E o item certo chegou mesmo assim, por um caminho mais limpo.** Na foto 2,
`escada_provisoria_coletiva_irregular` disparou direto e pôs `NR-18 18.8.6.1` em D6
curado — item que no próprio texto (alínea b) remete a "sistema de proteção contra
quedas, de acordo com o subitem 18.9.4.1 ou 18.9.4.2". O Analista o enquadrou, com a
constatação "não está dotada de sistema de proteção contra quedas rígido e contínuo,
utilizando apenas uma tela plástica flexível" — **sem citar o travessão de 1,20 m nem os
90 kgf/m** que a previsão temia como enquadramento sem lastro. Na foto 3,
`abertura_parede_desprotegida` pôs `NR-08 8.3.2.2` em D1, e a constatação cita
literalmente "bordas esgarçadas e fios soltos" — geometria que a imagem confirma (ver
seção 3). **A trava de `itens_compartilhados()` sobre o rótulo "Andaime sem guarda-corpo"
nunca foi exercida**, porque o risco de andaime nunca rotou: n=0, não n=1 aprovado.

O bloco de `escada_mao_irregular` rotou como ruído latente na foto 2 (D2-D5, os quatro
itens de sempre) e **o Analista não o usou** — o falso positivo ficou no dossiê e não
vazou pro laudo, o que os dois lotes anteriores (elétrica, içamento) nem sempre
conseguiram.

**A lição é a mesma de `chão`/`piso`, `abertura`/`aberto` e `quadro`/`quadrada`: o
discriminante medido sobre fato sintético é sempre um grau mais estreito do que a
frase que o Olho de fato escreve.** A previsão mediu o mecanismo certo (o `sem` completa
um sinal negando outra peça no mesmo fato) sobre um fato que continha a palavra; o Olho
real nunca a escreveu, e o mecanismo nunca teve chance de disparar.

### 2. A contraparte (foto 4) confirmou o pior medo do pré-registro — mas por um mecanismo diferente do previsto, e a foto real mostra falso positivo

A seção 5 do pré-registro previa o risco assim: *"o risco de o número ser pior está todo
na foto 4: a redação mais natural dela abre o bloco de escada de mão"* — e listava quatro
redações possíveis, a pior delas pondo `18.8.6.12`/`18.8.6.14` no dossiê de uma escada de
concreto. **Isso não aconteceu**: `escada_mao_irregular` não rotou na foto 4. O que rotou,
sem estar em nenhuma das quatro redações previstas, foi `abertura_piso_desprotegida`,
sobre o fato "Abertura vertical no piso, com bordas de concreto, localizada ao lado da
grade metálica" — dossiê reproduzido sem rede: `NR-18 18.9.2` em **D1 curado** e
`NR-08 8.3.2.2` em D2.

**Aberta a foto real, a leitura é geométrica e decide sozinha: não há vão de queda ali.**
O que existe, ao lado da grade metálica (que está aparentemente apoiada/deitada sobre o
piso, coberta de poeira — não instalada verticalmente cobrindo um vão, como o fato 4 do
Olho afirma), é uma **junta de dilatação fina entre duas placas de concreto**, de largura
milimétrica — visível na ampliação. Não é um vão pelo qual pessoa ou objeto caiam, e não
é o que `18.9.2` ("as aberturas no piso devem ter fechamento provisório...") regula. O
laudo entregou: *"Abertura vertical no piso com bordas de concreto, sem fechamento
provisório fixado na estrutura nem sistema de proteção contra quedas visível"* — **crítica,
prazo de 1 dia**, na foto que o desenho do lote existia para testar como controle
negativo.

**É a terceira ocorrência da classe VÃO INEXISTENTE** (depois da foto 3 do lote de máquina
em 11/09 e da foto 3 do lote de elétrica em 12/09) — **mas com uma proveniência diferente
das outras duas, e vale marcar a diferença.** Naquelas, quem confirmou foi o ENGENHEIRO,
segunda fonte humana independente ("o engenheiro respondeu que não há abertura ali",
12/09). Aqui não há engenheiro a perguntar — é o acervo histórico, sem memória — e quem
decide é a leitura geométrica de quem escreve este registro, pela régua (a)-(d): existe um
vão de queda no recorte? Não. A régua autoriza tratar isso como decidido mesmo sem árbitro
humano ("errar aqui é errar diante de um recorte que fica no repositório"), mas é uma
fonte mais fraca que as duas anteriores, e chamá-la de "confirmação" no mesmo grau seria
misturar duas proveniências de evidência diferentes. Nas duas primeiras o vão era
**inteiramente fabricado** (nada ali); aqui há uma feature real — a junta —, só que
**inflada** para "abertura sem proteção contra quedas".

**O aparo tentou reconciliar uma contradição interna do próprio Olho e não resolveu o
problema de fundo.** O fato 4 diz que a grade está "instalada em uma abertura no piso"
(implicando proteção presente ali) e o fato 5 descreve uma abertura diferente "ao lado da
grade" (implicando uma segunda abertura, desprotegida). O Diretor aparou duas vezes —
retirando "a menção à grade metálica adjacente como parte da falha de proteção, pois a
foto não confirma que a grade cubra a abertura ou que esteja ineficaz" e "a referência à
grade metálica adjacente como elemento ausente ou ineficaz" — o que é uma leitura correta
da contradição textual, mas **manteve a constatação central** (abertura sem fechamento)
que a imagem desmente por inteiro. O aparo corta o que não tem lastro textual; não
pergunta se o que sobrou corresponde a um vão real.

### 3. Fotos 2 e 3, abertas: as duas NCs têm lastro visual real

Diferente da foto 4, aqui a abertura da foto para conferir jogou a favor do laudo. A foto
2 mostra a escada fixa de concreto com o lance lateral aberto, sem qualquer barreira
rígida, fechado só pela tela laranja — que tem um **rasgo grande e óbvio no centro do
pano**, com luz passando através dele. A foto 3 mostra a mesma configuração noutro lance,
com a tela **rompida ao meio**, os dois panos separados e o vazio visível entre eles,
bordas esgarçadas com fios soltos pendendo. As duas constatações citam exatamente esses
achados (rasgo/rompimento, ausência de barreira rígida) e não extrapolam para o que a
foto não mostra. **As duas NCs têm lastro.**

### 4. A foto 1: recuperação confirmada, laudo sem lastro pleno — de novo pela cláusula (e)

**Recuperação: como previsto, `NR-18 18.8.6.8` (o item do nome do arquivo) ficou
inalcançável.** O achado da escada não menciona corredor, porta nem circulação — as
palavras aparecem só nos achados 4 e 5 (o vão vertical e o pilar), fragmentos diferentes
do achado da escada, e o ambiente ("alvenaria de tijolos aparentes e piso de concreto")
também não os contém. Pelo próprio desenho do roteamento (cada achado é seu fragmento
isolado; ambiente/contexto só completam, não emprestam de outro achado), o sinal nunca
teve como casar. Reproduzido: só `escada_mao_irregular` roteou, trazendo o bloco de
sempre (`18.8.6.13`, `18.8.6.14`, `18.8.6.12`, `NR-35 Anexo III 5.2.2.5`) em D1-D4.

**O Analista evitou o falso positivo mais provável.** Das quatro medições sintéticas que
previam `18.8.6.14` (montante único) em 8 de 8 redações, o laudo real **não o usou** —
saiu só `18.8.6.12` (sapata).

**Mas o laudo não tem lastro pleno, e a foto confirma.** O fato do Olho diz apenas "com os
pés sobre o piso de concreto" — não descreve o que há na ponta do pé, nem afirma nem nega
sapata. Ampliado o recorte do pé na foto real: a ponta é ambígua, sem definição suficiente
para decidir. A constatação impressa, mesmo depois do aparo (que retirou "a afirmação
categórica de que o dispositivo não existe"), ainda diz *"não apresenta evidência visual
de sapatas antiderrapantes"* — uma NC de gravidade **alta, prazo de 1 dia**, sobre uma
peça que o próprio Olho não descreveu. O "verificar no local" só entrou na ação corretiva,
não na constatação. **É a cláusula (e) contornada de novo, pela variante de linguagem
mais branda** ("não apresenta evidência visual" em vez de "não é possível verificar") —
mesma classe de erro do laudo 1 de elétrica (12/09), onde o engenheiro respondeu "não
consigo ver se a escada tem sapata" para uma NC idêntica.

### 5. A âncora manteve, e o parecer carregou hipótese pela quinta vez

`NR-18 18.9.2` crítica, sétima execução com laudo lido. Dossiê reproduzido: 7 entradas,
`18.9.2` em D1 e `8.3.2.2` em D2 curados, **`NR-18 18.9.3` continua fora**, como em toda
execução desde 09/09 — confirmado de novo na foto real (o vão de acesso ao poço segue sem
fechamento nenhum, ao lado da grade metálica não instalada). O aparo desta vez foi bom:
retirou "a afirmação categórica de que não há fixação", substituída por "o estado de
apoio simples visível na imagem" — a foto mostra exatamente isso, placas apoiadas sobre a
estrutura.

**O parecer voltou a carregar hipótese** — *"pode ceder ou deslocar-se sob carga"* —, no
campo que a cláusula (d) não governa. Quinta aparição da mesma armadilha (as anteriores:
laudo 5 de elétrica em 12/09, e a âncora do lote de içamento e cancela em 14/09, marcada
"quarta aparição" — esta é a quinta).

### 6. O que este lote ensina sobre medir com fatos sintéticos

**Medi X, afirmo Y, no nível do lote inteiro.** O gabarito previsto (2 a 3 de 5) bateu no
teto — mas quase todo mecanismo específico que sustentava a previsão errou: o falso
positivo do andaime (seção 3 do pré-registro) não rotou porque o Olho não escreveu
"guarda-corpo"; o item certo das fotos 2/3 chegou por um risco diferente do previsto, e
sem o problema de lastro nos números (1,20 m, 90 kgf/m) que a previsão temia; o risco de
a foto 4 abrir foi confirmado — mas pelo mecanismo errado (`abertura_piso_desprotegida`,
não `escada_mao_irregular`), e o resultado (NC crítica falsa na contraparte) é pior do
que qualquer uma das quatro redações que a seção 5 do pré-registro chegou a medir. **O
número certo por caminho errado já apareceu antes** (12/09, 14/09); a novidade aqui é que
o número bateu mesmo com o caminho errado em *ambos* os sentidos — a favor (fotos 2/3,
melhor que o previsto) e contra (foto 4, pior que qualquer cenário medido).

---

## Pré-registro do lote de ESCADA — 5 fotos (escrito em 15/09/2026, ANTES de rodar)

**RODADO em 15/09 — o resultado está na seção de validação acima.** O que esta seção
previu e o que ela errou se lê lá, previsão por previsão; ela fica intacta porque é o
artefato contra o qual o lote foi medido.

`main` em `0212227`. **Terceiro lote pré-registrado do histórico.** As quatro fotos foram abertas
aqui, os dossiês medidos sobre fatos SINTÉTICOS e a previsão escrita antes de o lote existir. O
que isso compra está medido duas vezes: em 12/09 a previsão acertou o item inalcançável e errou o
par de palavras; em 14/09 acertou a cláusula literal da foto 4 e errou o alcance do mecanismo da
seção 4.

**Medi X, afirmo Y, e aqui X é estreito.** O que está medido é o DOSSIÊ sobre fatos que escrevi
eu, imitando o Olho; o que o Olho vai escrever é hipótese até os laudos chegarem.

| # | Foto | Papel | O que ela responde |
|---|---|---|---|
| 1 | `ESCADA EM LOCAL INADEQUADO` | escada de mão real | a única do lote com escada portátil. `NR-18 18.8.6.8` — o item que o nome pede — é **alcançável**, e é a primeira vez em quatro lotes que isso acontece |
| 2 | `20 PROTEÇÃO DE ESCADA DANIFICADA` | proteção rasgada | escada FIXA de concreto com tela plástica no lugar do guarda-corpo. O item certo chega **pelo risco errado** |
| 3 | `18 PAV. PROTEÇÃO DE ESCADA QUEBRADA 18 PARA O 19` | proteção rompida | a mesma coisa, com o rasgo no meio do pano |
| 4 | `PROTEÇÃO DE ESCADA 17 PARA O 18 PAV` | **CONTRAPARTE** | o nome **não aponta defeito** e a tela está íntegra. É a contraparte natural do lote, e o desenho da fila não a tinha reconhecido como tal |
| 5 | `13 PAV. PEÇO ELEVADOR SEM PROTEÇÃO` | âncora | `NR-18 18.9.2` em toda execução com laudo lido desde 09/09, mais 14/09 |

**Correção ao desenho da fila, e ela muda o lote.** A linha da fila diz *"nas três de proteção de
escada o defeito está na proteção, não na escada"*. **São duas, não três**: a foto 4 mostra a tela
instalada, esticada, em várias camadas sobrepostas e **sem rasgo no recorte**, e o nome dela não
traz adjetivo de defeito — é o mesmo padrão de `18 PAV. PROTEÇÃO POÇO DE ELEVADOR` no lote de
poço, cujo aceite é 0 NC. O lote ganhou de graça a contraparte que os dois anteriores não tinham.

### 1. A leitura das quatro imagens, feita antes de qualquer fato

Cega por construção. **Não é gabarito** — regra (a)-(d) do acervo histórico, e ela tem número: a
leitura feita nesta casa errou 2 das 7 respostas do lote de máquina, e uma delas INVENTOU um
achado. Lidas no original e na escala em que o Olho as recebe (a foto 1 é retrato e chega com
**504 px de largura**; as outras três são paisagem e chegam com 896).

- **Foto 1** (retrato) — **escada de mão de alumínio apoiada contra parede de blocos cerâmicos**,
  dentro de um vão de passagem estreito entre duas paredes, num ambiente escuro sem iluminação.
  Um montante é pintado de **azul** e o outro é alumínio natural; ampliado o topo, aparece uma
  peça metálica de encaixe — compatível com escada extensível de duas seções, mas isso é NOME e
  fica **ABERTO**. **Os DOIS PÉS aparecem no recorte**, apoiados sobre o piso, e cada um termina
  numa ponta escura. Ripa de madeira solta no chão à esquerda. Piso claro com linhas paralelas
  regulares. Nenhuma pessoa.
- **Foto 2** (paisagem) — **lance de escada FIXA de concreto**, degraus moldados, sem guarda-corpo
  rígido nem corrimão. O vão lateral do lance é fechado por **tela plástica flexível laranja**,
  com uma tábua de madeira acima. Ampliada a borda direita: **a malha está rasgada e esgarçada
  junto ao pilar**, com fios soltos pendendo ao longo de toda a aresta, e a tela não está fixada
  continuamente ali. Detritos e uma embalagem de papel nos degraus.
- **Foto 3** (paisagem) — a mesma configuração noutro lance. **A tela está ROMPIDA no trecho
  central**: os dois panos aparecem separados e pendurados soltos, com o vazio visível entre eles,
  e a borda junto ao pilar esgarçada como na foto 2.
- **Foto 4** (paisagem) — a tela laranja **instalada, esticada e contínua**, em camadas
  sobrepostas, cobrindo o vão lateral do lance; ampliada, **não há rasgo nem fio solto**, e a
  borda inferior está acabada. Ao fundo, patamar de concreto com **cabos elétricos pretos
  enrolados no piso**, sacos plásticos e entulho fino, e **tela metálica de malha romboidal em
  moldura de madeira** — proteção rígida — instalada num vão ao fundo.

**O que a imagem DECIDE e o que fica ABERTO**, pela régua do acervo histórico:

| | decide? |
|---|---|
| os pés da escada da foto 1 aparecem no recorte | **SIM** — é presença, e é o que separa esta foto da escada de 12/09, cuja base sumia atrás de uma pilha de blocos |
| se aquela ponta escura no pé é sapata ou sujeira | **ABERTO** — material, regra (b) |
| a tela das fotos 2 e 3 está rasgada / rompida | **SIM** — é geometria: descontinuidade e fios soltos se ampliam e se mostram |
| a tela da foto 4 está íntegra no recorte | **SIM**, com a ressalva de que "no recorte" é o que se afirma |
| se a escada da foto 1 é extensível, e de que material é o piso | **ABERTO** — nome e material, regra (b) |

### 2. O que está MEDIDO: os cinco dossiês, sem rede

| # | riscos roteados | entradas | curadas | o que encabeça |
|---|---|---|---|---|
| 1 | `escada_mao_irregular`, `area_circulacao_maquinas_obstruida` | 19 | 8 | `18.8.6.13`, `18.8.6.14`, `18.8.6.12`, `NR-35 Anexo III 5.2.2.5` |
| 2 | `andaime_sem_guarda_corpo`, `escada_mao_irregular`, `escada_provisoria_coletiva_irregular`, `rampa_passarela_irregular` | 18 | 12 | `18.9.1` **D1**, `18.9.4.2` **D2**, `18.12.15.2` D3 |
| 3 | os mesmos quatro | 18 | 12 | idem |
| 4 | `escada_provisoria_coletiva_irregular`, `escada_mao_irregular`, `cabo_eletrico_danificado` | 13 | 8 | `18.8.6.1` D1, `18.8.1` D2, e **`18.8.6.12`/`18.8.6.14` em D5/D4** |
| 5 | `abertura_piso_desprotegida` | 7 | 2 | `18.9.2` **D1**, `8.3.2.2` D2 |

A âncora reproduz o que 11, 12 e 14/09 mediram, e o `NR-18 18.9.3` **continua fora do dossiê**.

### 3. O achado principal: o item CERTO das fotos 2 e 3 chega pelo risco de ANDAIME

Medido: `NR-18 18.9.1` ("proteção coletiva onde houver risco de queda") em **D1** e
**`NR-18 18.9.4.2`** em **D2**, os dois curados — e o `18.9.4.2` é o item que diz que a proteção,
*"quando constituída de anteparos **rígidos** em sistema de guarda-corpo e rodapé"*, deve ter
travessão a 1,20 m e resistir a 90 kgf/m. **É o item de frente do achado**: é por ele que tela
plástica não substitui guarda-corpo.

**Os dois chegam inteiramente por `andaime_sem_guarda_corpo`**, que é falso positivo — não há
andaime nenhum nas duas cenas. O sinal `andaime sem guarda corpo` casa a **0,75 faltando
`andaim`**, sobre *"Lance de escada fixa de concreto … sem corrimão nem guarda-corpo rígido"*:
quatro radicais, e o que falta é justo o substantivo que nomeia o objeto do risco. É a armadilha
dos 4+ radicais, já registrada, num par novo.

**E tirar o falso positivo TIRA o item certo — medido.** Reescrito o fato sem a palavra
"guarda-corpo" (*"…fechado lateralmente apenas por tela plástica"*), o risco de andaime cala e o
dossiê inteiro vira **quatro itens de escada de mão** — sapata antiderrapante, montante único,
comprimento máximo e piso estável — sobre um lance de concreto moldado. O `18.9.1` e o `18.9.4.2`
**somem**. É a lição de 07/09 pelo avesso: lá, destrancar o roteamento não tirava o item que o
BM25 trazia; aqui, trancar o risco errado tira o único item certo que existia.
**Previsão: NC de `18.9.1` ou `18.9.4.2` nas fotos 2 e 3, pelo motivo errado** — que é a classe
"laudo certo pelo motivo errado" que o controle da auditoria de imagem existe para pegar, e que
até hoje só apareceu uma vez (passada A na foto 1 de 10/09).

**O rótulo da NC é o que vigiar, e a trava está medida.** `itens_compartilhados()` marca os itens
que mais de um risco reivindica, e para eles o rótulo do risco cai. Medido: o `18.9.1` e o
`18.9.4.2` vêm com **rótulo vazio** (são compartilhados, então a NC será nomeada pela
constatação), e o `18.12.15.2` de D3 vem com o rótulo **"Andaime sem guarda-corpo e rodapé no
perímetro da plataforma"**. **Se o Analista escolher o D3, a NC sai intitulada com andaime numa
foto de escada** — que é, palavra por palavra, o defeito que motivou `itens_compartilhados()` em
01/09. A trava cobre D1 e D2 e não cobre D3.

### 4. O falso positivo latente, e este não precisa de palavra nenhuma do Olho

`escada_mao_irregular` tem **quatro itens** e eles entram em **BLOCO**: `18.8.6.13` (comprimento
máximo de 7 m), `18.8.6.14` (**proibido montante único**), `18.8.6.12` (**sapata antiderrapante**)
e `NR-35 Anexo III 5.2.2.5` (piso estável). Disparado por **qualquer** dos doze sinais, o risco
entrega os quatro — e os quatro afirmam defeitos DIFERENTES e independentes entre si.

**Medido nas oito redações da foto 1**: o `18.8.6.14` entra em **8 de 8**, inclusive na que diz
*"escada de mão de alumínio com **dois montantes laterais**"*. Duas causas somadas:

1. basta um sinal qualquer casar — `escada apoiada solta na parede` fica em 0,75 faltando `solt`,
   sobre "apoiada contra a parede" — e o bloco inteiro entra;
2. o sinal `escada de um montante so` reduz a **DOIS radicais, `escad` e `montant`**: `de`, `um` e
   `so` têm duas letras e somem no filtro. Medido, ele casa a **1,00 com âncora 2** sobre a frase
   que diz o oposto. **O numeral é que discriminava, e é ele que o filtro apaga** — o sinal não
   consegue expressar "um só", apenas "escada" e "montante".

É parente da armadilha `"t em cima de t"`, e mais difícil de ver: lá o sinal inteiro virava cola e
o validador quebra no import; aqui sobram dois radicais **discriminantes**, e os dois são o
vocabulário que o `PROMPT_OLHO` manda usar para descrever uma escada direito. **Quanto melhor o
Olho descreve, mais garantido o falso positivo.**

**A consequência prática é a classe de erro 2 registrada e nunca remediada**: `18.8.6.12` em D3
curado põe "sem sapata antiderrapante" à mão do Analista em toda foto que mencione escada. Foi ele
que saiu no laudo 1 do lote de elétrica, em 12/09, sobre uma escada cuja base não aparecia. **Nesta
foto a base APARECE**, o que muda o caso: se a NC de sapata sair aqui, ela terá lastro visual — e
se o Olho registrar o que há no pé, o Diretor tem fato para conferir.

### 5. A contraparte dispara os MESMOS riscos das fotos de defeito

Medido na foto 4, com a tela íntegra: `escada_provisoria_coletiva_irregular` dispara por
**`escada de concreto sem protecao lateral` a 0,80**, faltando `proteca`, sobre o fato *"Tela
plástica flexível laranja **instalada e contínua** cobrindo o vão lateral do lance"*. O `sem` do
sinal é cola, o `proteca` que discriminaria é o que falta, e a frase afirma o contrário do risco.
`escada de obra sem patamar` casa a 0,75 no mesmo fato.

**E o dossiê dela oscila entre 0 e 4 entradas por uma palavra**, medido em quatro redações:

| o que o Olho escrever | riscos | dossiê |
|---|---|---|
| "tela … instalada e contínua cobrindo o vão **lateral**" | `escada_provisoria_coletiva_irregular` | 3 entradas |
| a mesma frase **sem** "lateral" | nenhum | **vazio** |
| "guarda-corpo metálico rígido instalado no lance" | nenhum | 1 entrada |
| só "**lance de escada** de concreto com degraus moldados e patamar" | `escada_mao_irregular` | 4 entradas, com **`18.8.6.12` e `18.8.6.14`** |

A última linha é a mais provável das quatro, e é a pior: a redação mais natural e mais correta que
o Olho pode escrever para esta foto põe item de **sapata antiderrapante** e de **montante único**
no dossiê de uma escada de concreto moldada in loco. **Previsão para a foto 4: 0 NC é o acerto, e
o risco é uma NC de escada de mão sobre uma escada que não é de mão.**

**Ela também traz NR-10.** `cabo_eletrico_danificado` casa a **0,80** (falta `estendid`) sobre os
cabos enrolados no patamar, e põe `NR-10 10.2.8.2` e `10.2.8.2.1` em **D7 e D8 curados**. É
exatamente o par que o lote de elétrica mediu em 12/09 e que o Analista **recusou nas três fotos**,
porque o item trata de partes vivas e o cabo está íntegro. **Previsão: ele recusa de novo** — e se
enquadrar, é regressão sobre um caso já medido.

### 6. A foto 1 é a primeira em quatro lotes cujo item de frente é ALCANÇÁVEL

`NR-18 18.8.6.8` — *"É proibido utilizar escada portátil: a) nas proximidades de portas ou áreas
de circulação, de aberturas e vãos e em locais onde haja risco de queda de objetos…"* — é o item
que o nome do arquivo pede, e o risco que o cita é `escada_mao_local_perigoso`. Medido nas oito
redações:

- **3 de 8 alcançam** e põem o `18.8.6.8` em **D1 curado**, com o `18.8.6.9` em D2: as que contêm
  `corredor`, `porta` ou `area de circulacao`;
- **5 não alcançam**, entre elas *"apoiada dentro do **vão de passagem**, sem isolamento"* — que é
  a redação mais provável, porque é o que o recorte mostra: um vão de porta sem porta instalada.

**Isso quebra a série dos três últimos lotes**, em que o item de frente era inalcançável por
construção (barreira da área de corte 11/09, `18.10.2.4` 12/09, `18.13.1` 14/09). Aqui ele existe,
passa pelos três filtros e **está a uma palavra de distância**. O gatilho é estreito e conhecido:
`circulaca`, `corredor` ou `port` no achado.
**Previsão: NC de `18.8.6.13`/`18.8.6.12` (escada de mão genérica), não de `18.8.6.8`** — porque a
palavra que destrava é do vocabulário do inspetor, não do descritor de imagem.

**E há ruído de NR-12 nesta foto.** `area_circulacao_maquinas_obstruida` dispara por `passagem
estreita entre maquinas` a 0,75, **faltando `maquin`**, e traz `NR-12 12.2.1`, `12.2.1.2`, `12.2.2`
e `12.2.3` a **D5-D8 curados**, numa foto sem máquina nenhuma. O risco tem
`itens_so_com_maquina=()` **vazio**, então nem o portão que existe para isso o alcança — é a
armadilha já registrada de o item curado não passar por `setor_pertinente`, agora com um risco que
poderia declarar a dependência e não declara.

### 7. Critério de aceite, e onde cada coisa se lê

1. **Na LISTA DE FATOS do Olho** — se ele escreve `guarda-corpo` (fotos 2 e 3, que é o que traz o
   item certo pelo caminho errado), se escreve `corredor`/`porta`/`circulação` (foto 1) e se
   escreve `lateral` (foto 4). As três decidem o dossiê antes de qualquer agente de texto, e as
   três estão medidas acima.
2. **No RÓTULO da não conformidade das fotos 2 e 3** — se sair "Andaime sem guarda-corpo e rodapé"
   numa foto de escada, o Analista escolheu o D3 e a trava de `itens_compartilhados()` não alcança
   o item que ele usou. Se sair nomeada pela constatação, ela alcançou.
3. **Nas NÃO CONFORMIDADES**, e **o aceite tem duas metades em TODAS as fotos que preveem NC**,
   pela razão que o lote de 14/09 obrigou a separar duas vezes:
   - **Fotos 2 e 3 — e são elas que sustentam o número previsto, então esta é a metade que mais
     importa.** Que o `18.9.1` ou o `18.9.4.2` seja enquadrado mede a RECUPERAÇÃO, e só ela: é o
     que responde se o item de frente chega ao Analista, ainda que pela porta do andaime.
     **Não mede o laudo.** O `18.9.4.2` cobra **travessão superior a 1,20 m de altura e
     resistência à carga horizontal de 90 kgf/m** — dois números que a foto **não mostra**. Então
     a NC **tem lastro** para "a proteção do vão lateral é tela plástica flexível, rasgada, e não
     anteparo rígido" — que é geometria, e a régua deixa decidir — e **não tem lastro** para
     qualquer afirmação sobre altura ou resistência, que é enquadramento sem lastro visual e o
     caso que a cláusula (e) manda a ponto de atenção. **É o aparo de 10/09 nominalmente**: lá o
     Diretor retirou *"a exigência específica de altura mínima de 1,10 m … que não é verificável
     pela imagem"*, e este é o mesmo item pedindo a mesma coisa. Se a constatação citar o
     travessão ou os 90 kgf/m e sobreviver, o acerto de recuperação virou classe de erro 3.
   - **A foto 1**, pela mesma razão:
   - **RECUPERAÇÃO**: que `escada_mao_local_perigoso` dispare e ponha o `18.8.6.8` em D1. É o que
     responde se o item do nome é alcançável na prática, e só isso.
   - **LAUDO**: uma NC de `18.8.6.14` (montante único) nesta foto é **falso positivo**, porque a
     imagem mostra dois montantes — isso é geometria e a régua deixa decidir. Uma NC de
     `18.8.6.12` (sapata) **tem lastro** se o Olho descrever o que há no pé, porque os pés
     aparecem no recorte; não tem lastro se ele afirmar a ausência sem descrever o pé, e aí é a
     cláusula (e) outra vez.
   - **A foto 4 é 0 NC**, e qualquer NC de escada de MÃO nela é falso positivo declarado de
     antemão: não há escada portátil na cena.
   - A âncora mantendo `18.9.2`.

**O gabarito previsto: 2 a 3 de 5, pelo critério de 10/09** — o achado do nome do arquivo num
item que se aplica. Melhor que os dois lotes anteriores por uma razão estrutural: duas das cinco
fotos (2 e 3) têm o item certo no dossiê, ainda que pela porta errada, e a contraparte (4) fecha
se o app calar. **Mas esse número é do gabarito, não do laudo**, e os dois podem divergir aqui
mais do que em qualquer lote anterior: as fotos 2 e 3 podem fechar o gabarito e falhar a metade
do laudo pela cláusula (e), exatamente como a foto 1 do lote de 14/09 fechou a recuperação e
falhou o laudo. **Quem for ler este lote leia as duas metades separadas**, e não anuncie "melhorou
para 3 de 5" sem dizer quantas das NCs tinham lastro. **O risco de o número ser pior está todo na
foto 4**: a redação mais natural dela abre o bloco de escada de mão.

---

## Validação em produção de 14/09/2026 — o lote de IÇAMENTO E CANCELA, 5 fotos

Obra "teste". **5 laudos, 5 NCs (uma por foto), 0 não auditadas, 1 ciclo em todos.** É o
**segundo lote pré-registrado** do histórico, e o primeiro em que a previsão foi escrita foto a
foto com o dossiê medido antes. Os cinco HTML foram lidos e os cinco dossiês reproduzidos sem
rede a partir dos fatos reais. **Rodado no `6f735e0`, hash LIDO na barra lateral** — print de
14/09, "Versão em execução: 6f735e0", que é o `main` de 13/09. **É a primeira vez no histórico
que o hash é lido em vez de inferido do merge**: 09/09 e 12/09 o inferiram, e 11/09 dependeu de o
usuário informá-lo. Os laudos não o carregam, então a fonte é a barra lateral, e a instrução de
lê-la está neste arquivo desde 09/09.

| # | Foto | O que o Olho escreveu do objeto do nome | NC entregue |
|---|---|---|---|
| 1 | `19 PAV. CINTAS DE ELEVAÇÃO…` | "**Cinta** de içamento de tecido laranja, com marcas de **desgaste** e sujeira, amarrada em nó simples" | `NR-18 18.10.1.27` alta |
| 2 | `9 PAV. CANCELA CREMALHEIRA SEM SINALIZAÇÃO` | "Painéis rígidos … parcialmente cobrindo a **abertura** para a torre" — **nenhuma** `cancela` | `NR-08 8.3.2.2` alta |
| 3 | `17 PAV AUSENCIA DE SINALIZAÇÃO NAS CANCELAS` | "Painéis rígidos de cor preta instalados na **abertura** frontal" — **nenhuma** `cancela` | `NR-08 8.3.2.2` alta |
| 4 | `8 PAV. CANCELA CREMALHEIRA SEM SINALIZAÇÃO` | "**Grade metálica de malha quadrada, pintada de vermelho, aberta**" — **nenhuma** `cancela` | `NR-08 8.3.2.2` **crítica** |
| 5 | `13 PAV. PEÇO ELEVADOR SEM PROTEÇÃO` (âncora) | — | `NR-18 18.9.2` crítica |

**Gabarito contra o nome do arquivo: 1 de 5**, e o único acerto é a âncora. **A previsão
registrada era "1 a 2 de 5" e ela se sustentou.** As três fotos de cancela deram **zero
enquadramento de cancela e zero de sinalização**; `torre_elevador_sem_cancela` continua **sem
nunca ter disparado em produção**, agora em três fotos escolhidas para exercê-lo.

### 1. O achado principal: `abertura` e `aberta` são radicais DIFERENTES

É o que decidiu três das cinco fotos, e nenhuma medição anterior deste arquivo o registrava.
Medido: `radical("abertura")` devolve **`abertur`** e `radical("aberta")`/`("aberto")` devolve
**`abert`**. São radicais distintos e **não casam entre si** — a regra do `s` simples reduz o
plural, e nada reduz o substantivo ao particípio.

**Isso desarmou o falso positivo da seção 4 do pré-registro, e por um triz.** A previsão dizia
que o sinal `torre do elevador aberta` casaria a 1,00 com âncora 2 numa cena de cancela
instalada, com `torr` e `elevador` do achado e o `abert` vindo do AMBIENTE. Na foto 2 real o
achado traz `torr` e o ambiente traz `elevador`, **e o `abert` nunca aparece**: o Olho escreveu
`abertura` sete vezes e `aberto` nenhuma. Cobertura medida: **0,67 em todos os sete fragmentos**,
faltando sempre `abert`. O risco calou, e o `18.11.13` ficou fora do dossiê.
**O mecanismo continua armado, e é uma palavra.** Acrescentado ao ambiente REAL da foto 2 o
trecho *"vão de fachada **aberto** para o exterior"* — que é a redação que o pré-registro
escreveu e que qualquer pavimento de obra pode receber —, `torre_elevador_sem_cancela` **dispara**
sobre a cena com a cancela instalada. **Medi X, afirmo Y**: o que está medido é o roteamento
sobre o ambiente alterado; que o Olho venha a escrever `aberto` numa foto assim é hipótese, e
esta é a segunda vez que ela não se realiza.
**A previsão errou o alcance, não o mecanismo** — é o par `chão`/`piso` de 12/09 outra vez: o
discriminante existia, e era um grau mais estreito do que eu tinha escrito.

**A mesma régua matou a colisão do `quadro`.** A seção 3 previa que "cancela metálica de
**quadro** tubular" acionaria `quadro_eletrico_aberto_ou_sem_sinalizacao` e traria `NR-10 10.10.1`
a D3. O Olho escreveu "malha **quadrada**", e `radical("quadrada")` é **`quadrad`**, não `quadr`:
o risco calou e nenhuma NR-10 entrou em dossiê nenhum. A colisão prevista era com a palavra
`quadro`, e a palavra não veio.

### 2. A foto 4 confirmou a previsão pela cláusula literal, e ela era a mais específica do lote

O pré-registro dizia, com todas as letras: *"se o Olho escrever 'grade metálica de malha quadrada
pintada de vermelho, aberta' — literalmente o que ele escreveu no lote de içamento de 02/09 —, o
risco cala e `18.11.13` e `18.11.14` saem do dossiê inteiro"*. **Foi exatamente essa a frase que
ele escreveu**, palavra por palavra, e o dossiê medido tem **3 entradas, todas de NR-08**, sem um
item de NR-18. Dos cinco riscos previstos para esta foto, **nenhum** disparou: só
`abertura_parede_desprotegida`, por um sinal que a previsão não listava.
**É a medição mais limpa do lote**, porque a condição foi escrita antes e o modelo a cumpriu
sozinho: o vocabulário do Olho decide o dossiê inteiro, e ele não aprendeu `cancela`.

**E a NC desta foto é o falso positivo que o critério de aceite declarou de antemão.** O aceite
dizia que *"qualquer NC de queda nesta foto é falso positivo"* — a plataforma está no nível, o
piso é contínuo, a barreira está instalada (aberta) e com intertravamento aparafusado. O laudo
entregou `NR-08 8.3.2.2` **crítica**, prazo de 1 dia, sobre *"vão vertical na estrutura de
concreto **no teto**"*. **A previsão acertou a classe do erro e errou a porta**: ela vigiava
`18.11.13` e `NR-11 11.1.2`, e o falso positivo veio de um item de abertura, por um achado de
teto que nenhuma das duas previa.

**O Diretor NOMEOU o defeito e manteve o enquadramento.** O aparo diz, literalmente: *"a norma
regula aberturas em pisos e paredes, **não tetos**, mas a…"*. Ele releu o item, viu que ele não
cobre teto, cortou a conclusão e deixou a citação de pé. **É a classe de erro 1 pelo caminho do
aparo, pela terceira vez** — as duas anteriores são o laudo 1 de 09/09 e a passada B de 10/09 —,
e esta é a primeira em que o texto do aparo **contém a razão do veto que ele não deu**. O aparo
corta o que não tem lastro e não pergunta se o que sobrou ainda descumpre AQUELE item; aqui ele
chegou a escrever que não descumpre.

**O intertravamento foi registrado** — *"Dispositivo eletrônico azul e caixa vermelha fixados na
estrutura da grade metálica"* —, que era o achado que a seção 5 do pré-registro mandou vigiar. Ele
**não** virou "quadro elétrico" nem "caixa de comando", então o segundo caminho do falso positivo
elétrico não se abriu. **O trabalhador da cena não routeou nada**: nenhum risco com
`exige_pessoa` disparou, e o portão de pessoa segue sem lote.

### 3. A foto 1 acertou a RECUPERAÇÃO e falhou o LAUDO — as duas metades, como o aceite pedia

**A recuperação fechou.** `dispositivo_icamento_deteriorado` disparou com cobertura **1,00 e
âncora 3**, e o dossiê tem `NR-18 18.10.1.27` em **D1** e `NR-11 11.1.3.1` em **D2**, os dois
curados, com **zero item de NR-06**. A taxonomia do #22, escrita em 03/09 e nunca validada, está
validada: **a cinta deixou de virar EPI**, que é o defeito do lote de 02/09.
**Mas o sinal que casou não é o que a previsão apostou.** Ela media `tecido da cinta desfiado`
(`tecid`+`cint`+`desfiad`); o Olho escreveu *"marcas de desgaste"* e quem casou foi
`desgaste na cinta de icamento` — a **outra** das duas redações que o pré-registro mediu como
alcançando o item (`desgast`+`cint`+`icament`). A lista de oito é o que tornou isso legível: sem
ela, o acerto pareceria o mesmo acerto.
**E o desfiamento não foi escrito.** O Olho registrou desgaste, sujeira e o nó; as **bordas
desfiadas**, que a leitura da imagem de 13/09 nomeou e que são o defeito estrutural, não estão em
fato nenhum. É a classe OMISSÃO, e sobre o achado mais grave da foto.

**O laudo falhou na palavra que o aceite separou.** A NC saiu pela alínea (a) — identificação —,
como previsto, e o título diz *"sem identificação **legível**"*, que é a redação com lastro. **A
constatação diz outra coisa**: *"**não é possível verificar** a presença de identificação
indelével"*. Isso não é afirmação, é verificação — e verificação é ponto de atenção, não não
conformidade de gravidade alta com prazo de 1 dia. **É a cláusula (e) contornada pela segunda
vez**, depois da passada B de 10/09 — o laudo 7 de 09/09 é o caso que a motivou, não uma falha
dela —, e aqui pela variante que ela não alcança: ela proíbe a constatação na FORMA `"Verificar no local se…"`, e esta vem na forma
`"não é possível verificar"`, que é a mesma coisa escrita ao contrário. A cláusula mata a forma
que ela nomeia; a reformulação passa.
**E o aparo piorou**: ele retirou *"nem certificado de conformidade"* — a alínea (b) —, deixando
de pé justamente a metade que a foto não mostra.

### 4. As fotos 2 e 3: a contraparte do #27 passou, e o preço é o previsto

**A contraparte fechou nas duas.** Com a cancela instalada e fechada (foto 2) e com uma aberta e
uma fechada (foto 3), `torre_elevador_sem_cancela` **calou nas duas**, e o `18.11.13` não aparece
em NC nenhuma. É a primeira vez que essa contraparte é exercida sobre cena real — e a seção 1
mostra que ela passou pelo radical, não pelo desenho do sinal.

**O item que cobre de frente continua inalcançável.** `NR-18 18.13.1` — sinalização do canteiro —
**não está em dossiê nenhum das cinco**, como previsto, e as duas fotos deram NC de `8.3.2.2`
sobre a proteção da abertura, não sobre sinalização. **A previsão de `NR-26 26.3.1` sobre CORES
não se realizou**: sem risco de sinalização roteado, a NR-26 nem foi candidata. **É o terceiro
caso da série confirmado** — depois da barreira da área de corte (11/09) e do `18.10.2.4` do cabo
no piso (12/09): achado real, item existente, enquadramento fora de alcance. **Três domínios
seguidos**, e agora é o padrão, não a exceção.

**A foto 3 rendeu o dossiê mais sujo do lote, e por dois radicais.** Onze entradas, das quais
**seis curadas e QUATRO de escada** — `NR-18 18.8.6.13`, `18.8.6.14`, `18.8.6.12` e
`NR-35 Anexo III 5.2.2.5` —, todas de `escada_mao_irregular`, disparado pelo sinal
`escada apoiada solta na parede` a **0,75, faltando justamente `escad`**, sobre o fato *"Peça de
material de construção … **apoiada solta** sobre o piso, próxima à base da abertura frontal"*.
**Não há escada nenhuma na cena.** É a armadilha dos 4+ radicais em estado puro: o que falta é o
substantivo que nomeia o objeto do risco. O pré-registro previu "cinco itens de escada da NR-35"
nesta foto: **errou a contagem (são quatro) e errou a norma** (um é de NR-35, três são de NR-18).
Acertou a família, e a causa medida agora é o sinal, não o BM25.
**O mesmo fragmento também acionou `abertura_piso_desprotegida` a 1,00**, pelo par
`abertur`+`piso` vindo os dois do bloco solto no chão: é a **relação invertida** de 10/09 outra vez, e foi ela que pôs `NR-18 18.9.2` em D1 numa foto sem buraco no chão. O Analista não a
usou — foi ao `8.3.2.2` de D2 —, então o dano ficou no dossiê.

### 5. A âncora manteve, e repetiu os dois defeitos conhecidos

`NR-18 18.9.2` crítica, pela sexta execução com laudo lido. O dossiê reproduz **7 entradas**, com
`18.9.2` em D1 e `8.3.2.2` em D2 curados, e o **`NR-18 18.9.3` continua fora dele**, como em
toda execução medida desde 09/09 — a NC real do vão de acesso, confirmada pelo engenheiro em
12/09, segue sem sair. **Ele entrou no dossiê da foto 3**, em D11 e por busca textual, numa foto
sem poço nenhum: o item existe e é alcançável, só nunca na foto em que ele cabe.
**O ambiente diz "piso de terra" e o primeiro fato diz "piso de terra batida", no 13º
pavimento** — terceira execução com a mesma divergência de MATERIAL, confirmada pelo engenheiro
em 11/09.
**E o parecer volta a carregar hipótese** — *"pode deslocar-se e causar queda"* —, no campo que a
cláusula (d) não governa. **Quarta aparição** da mesma armadilha.

### 6. O que este lote acrescenta à decisão da fase separada de VISÃO

Três das cinco fotos foram decididas por **uma palavra do Olho**: `desgaste` em vez de `desfiado`
(foto 1, que salvou a recuperação), `abertura` em vez de `aberto` (foto 2, que desarmou o falso
positivo) e `quadrada` em vez de `quadro` (foto 4, que matou a colisão elétrica). **Nas três o
acaso léxico jogou a favor**, e é isso que torna o lote desconfortável de ler: o app não acertou
por desenho, e as três armadilhas continuam armadas atrás de um radical.
**A favor da fase separada**: o achado que faltou na foto 1 é o desfiamento, e ele é FATO, não
nome — é o caso do vão de acesso da âncora de 11/09 repetido, e o que o desenho recupera.
**Contra**: nenhuma das três fotos de cancela perdeu por falta de fato. Elas perderam porque o
item que cobre o achado do nome do arquivo não existe ao alcance, e descrever melhor a foto não
cria item.

---

## Pré-registro do lote de IÇAMENTO E CANCELA — 5 fotos (escrito em 13/09/2026, ANTES de rodar)

**RODADO em 14/09 — o resultado está na seção de validação acima.** O que esta seção previu e
o que ela errou se lê lá, previsão por previsão; ela fica intacta porque é o artefato contra o
qual o lote foi medido.

`main` em `cab299c`. **Segundo lote pré-registrado do histórico**, no molde do de elétrica: as
quatro fotos foram abertas aqui, os dossiês medidos sobre fatos SINTÉTICOS e a previsão escrita
antes de o lote existir. O que isso compra está medido em 12/09 — a previsão daquele lote
acertou o item inalcançável e errou o par de palavras, e as duas coisas só foram legíveis
porque estavam escritas antes.

**Medi X, afirmo Y, e aqui X é estreito.** O que está medido é o DOSSIÊ sobre fatos que
escrevi eu, imitando o Olho; o que o Olho vai escrever é hipótese até os laudos chegarem.
Toda previsão abaixo é condicional ao fato, e a condição está dita em cada uma.

| # | Foto | Papel | O que ela responde |
|---|---|---|---|
| 1 | `19 PAV. CINTAS DE ELEVAÇÃO DE MATERIAS UTILIZADOS PELA CARPINTARIA` | içamento | a taxonomia do #22 (`18.10.1.27`, `11.1.3.1`), escrita em 03/09 e **nunca validada**. É a foto que virou `NR-06 6.9.3` por colisão de radical no lote de 02/09 |
| 2 | `9 PAV. CANCELA CREMALHEIRA SEM SINALIZAÇÃO` | cancela FECHADA | a **contraparte** do conserto do #27: o risco de cancela ausente deve calar com a cancela instalada |
| 3 | `17 PAV AUSENCIA DE SINALIZAÇÃO NAS CANCELAS` | cancela FECHADA (duas) | a mesma contraparte noutro enquadramento, e o item de sinalização |
| 4 | `8 PAV. CANCELA CREMALHEIRA SEM SINALIZAÇÃO` | cancela ABERTA, 1 pessoa | `torre_elevador_sem_cancela`, que **nunca disparou em produção** |
| 5 | `13 PAV. PEÇO ELEVADOR SEM PROTEÇÃO` | âncora | `NR-18 18.9.2` em toda execução com laudo lido — 09/09, as duas passadas de 10/09, 11/09 e 12/09 —, e já em 05/09 |

### 1. A leitura das quatro imagens, feita antes de qualquer fato

Cega por construção: não há fatos do Olho ainda. **Não é gabarito** — regra 3 do desenho, e ela
tem número desde 11/09: a leitura de imagem feita nesta casa errou 2 das 7 respostas daquele
lote, e uma delas INVENTOU um achado. O que segue vira pergunta ao engenheiro (seção 5), nunca
veredito. As fotos foram lidas no original e na escala em que o Olho as recebe (`app.py:93` faz `img.thumbnail((lado, lado))`, e o
`lado` padrão do seletor da barra lateral é **896**, ajustando pela maior dimensão: as três fotos
retrato chegam com **504 px de largura**, e a foto 3, que é paisagem, com 896).

- **Foto 1** — cinta têxtil plana laranja, de ~5 cm, com costuras longitudinais tracejadas,
  amontoada e enrolada sobre laje de concreto. Três coisas visíveis: **bordas desfiadas**, com um
  tufo de fios arrancados; **argamassa endurecida** aderida em boa parte da superfície, escurecendo
  o tecido; e um **nó atado no próprio tecido**. Ao lado, uma barra metálica chata com um tubo na
  ponta e um estribo metálico em U. Nenhuma pessoa. **Nenhuma etiqueta de identificação aparece** —
  mas a peça está dobrada sobre si mesma, então isso é o caso da cláusula (e) e da terceira
  resposta possível do engenheiro, não uma ausência que a foto demonstre.
- **Foto 2** (retrato, 9º pav.) — vão de fachada para o exterior, com a torre da cremalheira do
  lado de fora. No acesso há **cancela metálica de quadro tubular vermelho com tela de malha
  soldada, instalada e fechada**, e painéis de compensado escuro fechando o resto do vão. Laje
  varrida, dois blocos de concreto no chão. **Nenhuma placa de sinalização em lugar nenhum do
  recorte.**
- **Foto 3** (paisagem, 17º pav.) — a mesma configuração, mais aberta: **duas cancelas vermelhas
  — a da esquerda ABERTA, girada para dentro, e a da direita fechada** (a primeira redação desta
  linha dizia "as duas fechadas", e a ampliação do montante central derrubou; ver a seção 5),
  guarda-corpo vermelho horizontal atrás delas, painéis escuros nos demais trechos,
  tela plástica laranja numa abertura à direita, **dispositivo de intertravamento com fiação nos
  montantes**, um anel escuro pendurado na parede. **Nenhuma placa.**
- **Foto 4** (retrato, 8º pav.) — **a cancela está aberta**, girada para dentro do pavimento. Há
  uma **chapa metálica de embarque** ligando o piso ao exterior, e **um trabalhador em pé sobre
  ela**, de uniforme azul, capacete branco, óculos e luva. A cremalheira dentada aparece na torre;
  há caixa azul de dispositivo elétrico no montante e tela laranja ao fundo. **Nenhuma placa.**
  **A plataforma do elevador está no nível do pavimento**: o piso atravessa a soleira sem
  interrupção e o trabalhador está em pé sobre ela. A altura do pavimento a imagem não resolve —
  a vegetação próxima puxa para a base e a fachada inteira do prédio vizinho puxa para o alto —,
  e **não precisa resolver**: em qualquer altura, não há vão de queda exposto no instante da
  foto. Era a pergunta P4, respondida na seção 5.

### 2. O que está MEDIDO: os cinco dossiês, sem rede

Fatos sintéticos escritos no estilo do Olho a partir da leitura acima; `montar_dossie` é
determinístico e roda sem rede.

| # | riscos roteados | entradas | curadas | itens de NR-18 no dossiê |
|---|---|---|---|---|
| 1 | `dispositivo_icamento_deteriorado` | **3** | 2 | `18.10.1.27` em **D1** |
| 2 | `sinalizacao_de_seguranca_ausente`, `espaco_confinado_sem_sinalizacao` | 11 | 5 | **nenhum** |
| 3 | os mesmos dois | 13 | 5 | **nenhum** |
| 4 | `torre_elevador_sem_cancela` + 4 | 13 | 9 | `18.11.13` **D1**, `18.11.14` D2, `18.16.18` D8, `18.16.19` D9 |
| 5 | `abertura_piso_desprotegida` | 7 | 2 | `18.9.2` **D1** |

A âncora reproduz o que 11 e 12/09 mediram, `18.9.2` em D1 e `8.3.2.2` em D2, e o
`NR-18 18.9.3` **continua fora do dossiê**, como 11 e 12/09 já haviam medido sobre os fatos
reais dessa mesma foto.

### 3. A previsão, foto a foto

**Foto 1 — o risco dispara, e o item que ele cita não cobre o defeito.**
`dispositivo_icamento_deteriorado` casa por `tecido da cinta desfiado` (cobertura 1,00, âncora 3)
e põe `NR-18 18.10.1.27` em D1 e `NR-11 11.1.3.1` em D2, **os dois curados**. A colisão
`cinta`/`cinto` do #20 está morta: um cinturão paraquedista íntegro routeia
`talabarte_mal_conectado` e nada de içamento, e **zero item de NR-06 entra neste dossiê**.
**Mas o texto do item não alcança o achado.** O `18.10.1.27` tem três alíneas — identificação
indelével (a), certificado ou projeto (b), inspeção pelo amarrador (c) — e **nenhuma fala de
desgaste**; o `11.1.3.1` fala de "cabos de aço, cordas, correntes, roldanas e ganchos", não de
cinta têxtil. A palavra **eslinga** aparece em dois itens vigentes da base, e os dois são de NR-12:
`12.8.4` e `Anexo XII 4.24` (este do anexo de plataformas elevatórias, sobre sistemas de
suspensão). O `12.8.4` só chega pelo risco CONCORRENTE (`cabo_aco_ou_lingada_deteriorados`, sinal `cinta rasgada`, gravidade base
crítica em vez de alta). **Previsão: NC de identificação — a alínea (a) —, com o desfiamento
evaporando.** É o aparo que apagou o desfiamento nesta mesma foto, registrado em 03/09 sobre o lote de
içamento, mas a causa agora está medida no TEXTO do item e não na escolha do Diretor: ali eu
registrei "o aparo apagou o achado grave"; aqui não havia item onde pendurá-lo.
**E o vocabulário decide antes disso.** Oito redações plausíveis do mesmo achado, medidas:
**2 alcançam o `18.10.1.27`** (as que trazem `tecid`+`cint`+`desfiad` ou `desgast`+`cint`+`icament`),
**1 vai para o risco concorrente** (`cinta rasgada`) e **5 não routeiam risco nenhum** — entre elas
"Cinta têxtil laranja com bordas desfiadas e fios soltos" (0,67, falta só `tecid`), "bordas
puídas", "encoberta por argamassa, sem etiqueta legível" e "com nó atado no próprio tecido".
Trocado `cinta` por `faixa`, o dossiê inteiro vai para **NR-26, cores de tubulação**, com zero
item de içamento. **O discriminante é `cinta`**, como `cabo` foi em 12/09.
**O nó e a argamassa não routeiam nada**, e o nó é achado real de içamento que a taxonomia não
tem: sem a palavra `desfiada`, o dossiê desta foto cai para **uma entrada** (`NR-08 8.3.1`,
pé-direito).

**Fotos 2 e 3 — a contraparte do #27 deve passar, e o item certo é inalcançável.**
Medido: `torre_elevador_sem_cancela` **cala nas duas** com a cancela nomeada, instalada e
fechada. É a primeira vez que essa contraparte é exercida sobre uma cena real em vez de um fato
escrito para testá-la.
**O preço é o dossiê.** Nenhuma das duas recebe **um item de NR-18**: entram `NR-26 26.3.1` e
`26.3.2` (cores) em D1/D2 curados, **`NR-33 33.5.13.1/.3/.4` — espaço confinado — em D3 a D5
curados**, NR-01 documental e, na foto 3, **cinco itens de escada da NR-35**. O espaço confinado
vem de `poço aberto sem placa` a 0,75 sobre "Sem placa de sinalização de advertência visível nas
cancelas": quatro radicais, e o que falta é justo `poco`.
**O item que cobre de frente é `NR-18 18.13.1`** — "o canteiro de obras deve ser sinalizado com
o objetivo de … c) advertir quanto aos riscos existentes, tais como queda de materiais e pessoas
e o choque elétrico; … e) identificar o isolamento das áreas de movimentação e transporte de
materiais". Ele passa por
`comprovavel_em_foto`, por `prescritivo` e por `setor_pertinente`, e **é inalcançável**: de seis
redações testadas, só chega quando a frase contém "canteiro de obras", que é quase citar o item.
A causa é medível e tem um gatilho estreito: o sinal `canteiro sem sinalizacao` tem três radicais
e fica em **0,67** — falta `canteir` —, e **basta a palavra `canteiro` aparecer no AMBIENTE** para
ele subir a 1,00 e pôr o `18.13.1` em **D1 curado**. **Previsão: 0 NC, ou NC de `NR-26 26.3.1`
sobre CORES de segurança**, que seria classe de erro 1 — item verdadeiro, situação errada.
**É o terceiro caso da série**, depois do item de barreira da área de corte (11/09) e do
`NR-18 18.10.2.4` do cabo no piso (12/09): achado real, item existente, enquadramento fora de
alcance.

**Foto 4 — o risco de cancela dispara pela primeira vez, e três dos cinco riscos são defeito.**
`cancela aberta` casa com cobertura 1,00 e põe `18.11.13` em D1 e `18.11.14` em D2. Os outros
quatro riscos disparam assim:

| risco | sinal | cobertura | por quê |
|---|---|---|---|
| `quadro_eletrico_aberto_ou_sem_sinalizacao` | `quadro aberto` | **1,00** | **colisão de radical**: `quadr` vem de "cancela metálica de **quadro** tubular" e `abert` da própria cancela. Traz `NR-10 10.10.1` a D3 curado |
| `tapume_galeria_ausente` | `obra aberta para a rua` | 0,75 | 4 radicais, falta `rua`. Traz `18.16.18`/`18.16.19` a D8/D9 |
| `poco_elevador_carga_sem_cercamento` | `vao do elevador sem protecao` | 0,75 | falta `sem`, e `proteca` vem de "óculos de **proteção**" do trabalhador. Traz `NR-11 11.1.1`/`11.1.2` a D6/D7 |
| `sinalizacao_de_seguranca_ausente` | `sem placa` | 1,00 | dois radicais, um é cola — e é o formato que o `PROMPT_OLHO` manda escrever |

A colisão do `quadro` é a do `cinta`/`cinto` noutro par, e é nova: trocada a palavra por
"moldura tubular", o risco some e o `10.10.1` sai do dossiê. `quadro` é o que esta casa já usou
para descrever moldura metálica — "dois painéis de tela metálica em **quadro** de aço", na
leitura de 10/09.
**A favor, e vale dizer**: o `NR-11 11.1.2` — "quando a cabina do elevador não estiver ao nível
do pavimento, a abertura deverá estar protegida" — é o item CERTO para cancela aberta sem cabine,
e ele chegou ao dossiê, ainda que pelo caminho errado. Se a P4 disser que o recorte é de
pavimento elevado, esta é a NC certa da foto.
**E o nome decide de novo**: se o Olho escrever "grade metálica de malha quadrada pintada de
vermelho, aberta" — literalmente o que ele escreveu no lote de içamento de 02/09 —, o risco cala
e **`18.11.13` e `18.11.14` saem do dossiê inteiro**.

### 4. O falso positivo latente, e é ele o achado principal deste pré-registro

Medido: com o achado nomeando *"Torre do elevador de obra de cremalheira … instalada junto à
fachada"* e o ambiente contendo a palavra **aberto** (*"vão de fachada aberto para o exterior"*),
o sinal `torre do elevador aberta` casa com **cobertura 1,00 e âncora 2** — `torr` e `elevador`
vêm do próprio achado, e o `abert` vem do **AMBIENTE**. O risco de cancela AUSENTE dispara numa
cena em que a cancela está instalada e fechada, e `18.11.13`/`18.11.14` vão para **D1 e D2
curados**. Tirada a palavra "aberto" do ambiente, o risco cala e o `18.11.13` ainda chega, mas em
**D3 e por busca textual** — que é a lição de 07/09 outra vez: destrancar ou trancar o roteamento
não tira o item que o BM25 traz.

**É a mesma família das armadilhas já registradas** — o `sem` que nega outra coisa no mesmo fato,
o particípio da negação ("sem trechos abertos") e a relação invertida ("abertura no piso" casando
"piso … da abertura") —, e o mecanismo aqui é o do AMBIENTE, com uma variante nova: **o adjetivo
que qualifica outro objeto da cena**. A âncora impede o ambiente de carregar o sinal sozinho; não
impede que ele forneça o único radical que discrimina. E o ambiente de qualquer foto de pavimento
de obra tem boa chance de conter "aberto".

**Medi X, afirmo Y**: o que está medido é o dossiê, dado o fato. Que o Olho escreva "aberto" no
ambiente e "torre do elevador" no achado é **hipótese** — e é exatamente o que o #27 o ensinou a
fazer. As fotos 2 e 3 são a medição dela.

### 5. As perguntas ao engenheiro — RESPONDIDAS EM 13/09, E A RESPOSTA MUDA A REGRA 3

**O engenheiro não tem a memória destas fotos.** Perguntado sobre as seis, respondeu que o que
eu vejo na foto é o que ele vê, que não se lembra do dia em que foram tiradas, e autorizou que
eu validasse o que a imagem permite. **Isso não é uma resposta a mais: é a segunda fonte
deixando de existir para este acervo**, e por isso vem antes das respostas.

**O que a regra 3 dizia, e por quê.** "Foto é pergunta, nunca veredito" se apoia numa premissa
declarada: *ele viu a obra, a imagem é um recorte dela*. Quando a premissa vale, a leitura de
imagem feita aqui é uma hipótese que ele arbitra — e o histórico mostra que o árbitro é
necessário: das sete respostas do lote de máquina, **duas derrubaram leituras minhas**, e uma
delas era um achado INVENTADO ("lâmina exposta sem coifa" numa serra que tem coifa).
**Quando a premissa não vale, não há a quem arbitrar.** As fotos são de uma inspeção passada, e
a memória acabou. Insistir em perguntar é gastar rodada com quem tem menos informação que a
imagem; e tratar a minha leitura como gabarito por falta de alternativa é o erro que a regra 3
existe para impedir, pela porta de trás.

**A regra que substitui, e ela é mais estreita de propósito:**

1. **A imagem decide o que é geométrico ou de presença** — há ou não há um objeto no recorte,
   onde ele está, se uma folha está no plano ou girada, se um piso é contínuo. Isso se lê, se
   amplia e se mostra; errar aqui é errar diante de um recorte que fica no repositório.
2. **A imagem NÃO decide material, nome próprio de equipamento, nem estado de funcionamento.**
   São exatamente as três classes de erro que este arquivo registra no Olho — MATERIAL, NOME,
   e agora o funcional —, e a minha leitura corre as mesmas. Onde a resposta for de uma dessas,
   ela fica **ABERTA**, e não vira gabarito nem contra o app nem a favor dele.
3. **Onde a imagem não decide, a consequência é a cláusula (e), não o silêncio.** Se nem quem
   inspecionou decide pela foto, uma NC que dependa daquela peça é enquadramento sem lastro
   visual — é a terceira resposta de 12/09 ("não consigo ver se a escada tem sapata") virada em
   procedimento, e agora ela vale para todo este acervo, não para uma escada.
4. **Para lote NOVO a regra 3 continua inteira**, e é por isso que ela não foi apagada: fotos
   tiradas agora, com o engenheiro em campo, têm árbitro. O que mudou vale para o acervo
   histórico, que é de onde saem todos os lotes deste arquivo.

**As respostas, lidas nas imagens originais com recorte ampliado**, e cada uma declarando se a
imagem decide:

| # | pergunta | o que a imagem mostra | decide? |
|---|---|---|---|
| **P1** | a cinta tem etiqueta de identificação? | **Os laços/olhais da fita aparecem no recorte e não há etiqueta em nenhum deles**; nenhum trecho visível traz etiqueta. Mas a peça está enrolada sobre si mesma, com trechos ocultos, e boa parte da superfície está sob crosta de argamassa | **PARCIAL** — decide que **não há identificação legível no que se vê**; não decide se existe etiqueta no trecho oculto |
| **P2** | o nó estava em uso? | **O nó existe e está apertado**, dado na própria fita, com o tecido deformado e achatado na volta — marca de tração, não de dobra solta | **PARCIAL** — decide que há nó e que ele foi tracionado; não decide se era assim durante o içamento |
| **P3** | o que é a peça metálica? | **Barra chata de aço, reta, com a ponta em bisel** e o gume polido pelo uso, com ferrugem e resíduo de concreto. Ao lado, um tubo metálico curto e um arame | **PARCIAL** — decide a GEOMETRIA, e por ela **exclui** o garfo de empilhadeira (que não tem gume biselado) e o estribo de armação (dobrado em U, não reto e chato). **O nome fica ABERTO**: "alavanca de desforma" é a leitura mais provável e é NOME, que a regra (b) não deixa decidir — foi o `/critico` que pegou, nesta mesma tabela |
| **P4** | foto 4: embarque ou pavimento elevado com vão exposto? | **A plataforma do elevador está NO NÍVEL do pavimento**: há piso contínuo atravessando a soleira, e o trabalhador está em pé sobre ela. A altura do pavimento a imagem **não** resolve — a vegetação próxima puxa para a base, a fachada inteira do prédio vizinho puxa para o alto | **SIM no que importa** — **não há vão de queda exposto no instante da foto**, seja qual for o pavimento. A altura fica ABERTA e não é necessária |
| **P5** | as cancelas estavam travadas ou só encostadas? | **Há dispositivo de intertravamento instalado nas três fotos**: caixa preta com fiação no montante nas fotos 2 e 3, caixa azul aparafusada na foto 4, com chapas de batente vermelhas. Não estão apenas encostadas | **PARCIAL** — decide que o dispositivo EXISTE e está montado; **não decide se funcionava**, que é estado, e cai na regra 2 acima |
| **P6** | o anel na parede da foto 3 | **Rolo flexível de seção circular, pendurado num pino** na parede de concreto, com uma peça metálica na parte baixa do rolo. Mangueira e cabo são as duas leituras compatíveis | **PARCIAL** — decide que é objeto FLEXÍVEL pendurado, e por isso **exclui** dispositivo de ancoragem e elemento estrutural, que são rígidos e fixados. Entre mangueira e cabo é NOME, e fica **ABERTO** |

**Nenhuma das seis decide um NOME, e isso não é acaso: é a regra 2 mordendo.** As três que
excluem alternativas (P3, P6) o fazem por GEOMETRIA — gume biselado contra garfo, flexível
contra rígido —, que é o que a regra 1 permite; o nome próprio de cada objeto continua aberto,
e é assim que tem de ficar enquanto ninguém puder arbitrá-lo. O caso que sustenta a régua está
neste arquivo com número: em 11/09 eu afirmei "serra de FITA" lendo pixels, e o engenheiro
respondeu **serra de bancada**.

**Duas correções à seção 1, e as duas são leituras minhas que a ampliação derrubou** — é a
regra 2 funcionando sobre mim mesmo, no mesmo dia em que foi escrita:

- **Foto 3 — "duas cancelas vermelhas fechadas" está ERRADO.** Ampliado o montante central, a
  cancela da ESQUERDA está **aberta**, girada para dentro; só a da direita está fechada. Isso
  muda o papel da foto no lote: ela deixa de ser a segunda contraparte de cancela fechada e
  passa a ter as duas condições na mesma imagem.
- **Foto 4 — "a vegetação sugere nível de embarque" está mal fundamentado.** A vegetação
  aparece, mas a fachada do prédio vizinho é vista inteira e de frente, o que aponta para o
  contrário. A imagem não decide a altura, e eu tinha declarado uma direção. O que ela decide
  é a plataforma no nível, que é o que a previsão precisava.

**E um achado que nenhuma das seis perguntas cobria**, encontrado ao ampliar os montantes: **as
três fotos de cancela mostram dispositivo de intertravamento instalado**. É evidência de
conformidade, e o que vigiar no lote é se o Olho o registra — se ele descrever a caixa como
"quadro elétrico" ou "caixa de comando", ela vira o `quadro aberto` da seção 3 e o falso
positivo elétrico ganha um segundo caminho.

### 6. Critério de aceite, e onde cada coisa se lê

1. **Na LISTA DE FATOS do Olho** — se ele escreve `cinta` (foto 1) e `cancela` (fotos 2, 3 e 4),
   e **se o AMBIENTE contém a palavra "aberto"**. Os três decidem o dossiê antes de qualquer
   agente de texto, e os três estão medidos acima.
2. **Na TRILHA dos laudos 2 e 3** — se `NR-18 18.11.13` aparece em foto de cancela fechada. Se
   aparecer, o falso positivo da seção 4 saiu do papel e o conserto é um sinal, não um prompt.
   **E o laudo 4 tem o mesmo aceite em duas metades que a foto 1, pela mesma razão — foi o
   `/critico` que pegou, na foto que a primeira correção não alcançou.** Que
   `torre_elevador_sem_cancela` DISPARE ali mede a recuperação, e é o que esta foto existe para
   responder: o risco nunca disparou em produção. **Não mede o laudo, e a P4 já fechou esse
   lado.** O `18.11.13` cobra que a barreira SEJA INSTALADA, e ela está — aberta, mas instalada,
   e com intertravamento aparafusado no montante; a plataforma está no nível e o piso é contínuo.
   Logo **qualquer NC de queda nesta foto é falso positivo**: nem o `18.11.13`, nem o
   `NR-11 11.1.2` (que cobra proteção quando a cabina NÃO está no nível), nem o
   `poco_elevador_carga_sem_cercamento`. O acerto desta foto é **0 NC de queda**, com a ausência
   de sinalização em ponto de atenção — e é assim que o laudo 4 se lê.
3. **Nas NÃO CONFORMIDADES** — fotos 2 e 3 **não** entregando NC de NR-33 nem de
   `NR-26 26.3.1` sobre cor; a âncora mantendo `18.9.2`.
   **Para a foto 1 o aceite tem duas metades, e a primeira redação deste critério colapsou as
   duas — foi o `/critico` que pegou.** Item de içamento em vez de EPI (`18.10.1.27` ou
   `12.8.4`) mede a RECUPERAÇÃO, e só ela: é o que responde se a taxonomia do #22 funciona.
   **Não mede o laudo.** A seção 3 prevê que a NC saia pela alínea (a) do `18.10.1.27` —
   identificação —, e o próprio artefato diz que a etiqueta não aparece no recorte: contar isso
   como acerto seria carimbar como sucesso um enquadramento sem lastro visual, que é a classe de
   erro 3 e o caso que a cláusula (e) manda mandar a ponto de atenção. **A P1 fechou esse lado
   pela metade, e a metade decide a redação**: os laços da fita aparecem sem etiqueta e a crosta
   de argamassa cobre onde a marcação estaria, mas a peça tem trechos ocultos. Então a NC de
   identificação **tem lastro para "sem identificação LEGÍVEL"** — que é o que a foto mostra e o
   que a alínea (a) do `18.10.1.27` cobra — e **não tem lastro para "sem identificação"**, que
   afirma sobre o trecho oculto. A diferença é uma palavra no laudo do cliente, e é ela que
   separa o acerto da classe de erro 2.

**O gabarito previsto é ruim, e isso é o ponto**: o achado do nome do arquivo é SINALIZAÇÃO em
três das quatro, e o item que a cobre é inalcançável. **Previsão registrada: 1 a 2 de 5**, com o
acerto mais provável sendo a âncora. Se sair melhor que isso, a razão está no que o Olho
escreveu, e é lá que se lê.

---

## Validação em produção de 12/09/2026 — o lote de ELÉTRICA, 5 fotos

Rodado no `ef3ca2c` — **inferido do merge, e não lido na barra lateral**, que é o mesmo dado
que faltou em 09/09; leia o hash da próxima vez. Obra "teste". **5 laudos, 3 NCs, 0 não auditadas, 1 ciclo em todos.**
É o **primeiro lote PRÉ-REGISTRADO** do histórico: as quatro fotos de elétrica foram abertas
aqui e os dossiês medidos sobre fatos sintéticos ANTES de rodar (commit `490b152`), com a
previsão escrita. Então esta seção compara previsão contra resultado, e não só resultado
contra nome de arquivo. Os cinco HTML foram lidos e os cinco dossiês reproduzidos sem rede
a partir dos fatos reais.

| # | Foto | O que o Olho escreveu do cabo | NC entregue |
|---|---|---|---|
| 1 | `5 PAV. FIAÇÃO EXPOSTA NO CHÃO` | "Cabo elétrico preto **estendido sobre o piso**" | `NR-18 18.8.6.12` **escada sem sapata**, alta |
| 2 | `CABOS ELETRICOS DISPOSTOS DIRETAMENTE NO CHÃO` | "Cabo elétrico preto enrolado em rolos sobre o **chão**" | 0 |
| 3 | `FIO EXPOSTO NO CHAO` | "Cabo elétrico preto enrolado em rolos sobre o piso" | `NR-18 18.9.2` **abertura no piso**, crítica — **FALSO POSITIVO confirmado** |
| 4 | `8 PAV. FIAÇÃO NO CHÃO` | "**Fiação** elétrica preta estendida ao longo do piso" | 0, com veto CERTO do Diretor |
| 5 | `13 PAV. PEÇO ELEVADOR SEM PROTEÇÃO` (âncora) | — | `NR-18 18.9.2`, crítica |

**Gabarito contra o nome do arquivo: 1 de 5**, e o único acerto é a âncora. **As quatro de
elétrica deram ZERO enquadramento elétrico** — é o lote de içamento de 02/09 repetido noutro
domínio, com a diferença de que aqui a causa estava medida e escrita antes.

### 1. A previsão acertou o item inalcançável, e é o achado principal

O `NR-10 10.2.8.2` e o `10.2.8.2.1` chegaram em **D1 e D2, CURADOS, em três das quatro fotos**
(1, 2 e 3), e **o Analista não usou nenhum dos dois em nenhuma delas**. Não é falha de
recuperação nem escolha ruim: o item trata de desenergização e de isolação de PARTES VIVAS, e
o cabo está íntegro. Ele recusou porque o item não serve.
**O que serviria continua inalcançável**: o `NR-18 18.10.2.4` (condutor de ferramenta que não
pode obstruir o trânsito) não apareceu em dossiê nenhum dos cinco, e a NR-18 sequer é candidata
por vocabulário elétrico. Nas fotos 1 e 3 o cabo foi para **pontos de atenção**, que é o
comportamento certo quando não há item — o app diz o que viu sem forçar citação imprópria.
**A previsão de NC falsa de partes vivas NÃO se realizou**, e a razão é essa: o item em D1
curado não vira NC quando não descreve a situação.

### 2. O vocabulário decide, mas por `cabo` contra `fiação` — a previsão errou o par

A previsão dizia que `chão` no lugar de `piso` derrubaria o roteamento. **Caiu.** Medido nos
fatos reais, com o sinal `"cabo eletrico estendido sobre o piso"` (cinco radicais):

| foto | cobertura | âncora | o que faltou | risco |
|---|---|---|---|---|
| 1 | **1,00** | 5 | — | `cabo_eletrico_danificado` |
| 2 (escreveu "chão") | **0,80** | 3 | `estendid` | `cabo_eletrico_danificado` |
| 4 (escreveu "fiação") | **0,60** | 3 | `cabo`, `sobr` | **nenhum** |

Na foto 2 o `piso` que faltava no achado veio do **AMBIENTE** ("piso de concreto aparente"), e
a âncora ficou satisfeita pelos três radicais do próprio achado. **A âncora de 01/09 impede o
ambiente de carregar o sinal SOZINHO; não impede que ele COMPLETE um sinal já ancorado** — e
foi isso que salvou a foto 2 da previsão.
**O discriminante real é `cabo`.** Na foto 4 o Olho escreveu `fiação`, o risco calou, e o
dossiê foi para **NR-13 vaso de pressão** e NR-17 mobiliário, com zero NR-10. É a mesma família
do `"fio desencapado"` que nunca casava "fios desencapados": o Olho alterna cabo, fiação e fio
para o mesmo objeto, e o sinal só conhece um deles.

### 3. VÃO INEXISTENTE confirmado pela SEGUNDA vez, e de novo virou NC crítica

O Olho escreveu na foto 3 *"Abertura retangular no piso, com bordas de concreto, localizada no
canto da parede de tijolos"*. **O engenheiro confirmou em 12/09: não há abertura de piso ali.**
A única NC daquele laudo — `NR-18 18.9.2`, crítica, prazo de 1 dia — nasceu de um vão que não
existe, exatamente como o laudo 3 do lote de MÁQUINA.
**São dois lotes seguidos, em domínios diferentes, e a classe se comporta igual**: o objeto
inventado carrega a propriedade de risco no nome, o roteamento cura o item, o Analista enquadra
e o Diretor aprova sem veto nem aparo — porque a conferência confere a constatação contra o
FATO, e o fato está lá. **Deixa de ser achado de um lote e passa a ser o defeito mais caro do
app**: nas duas vezes fabricou sozinha uma não conformidade crítica ou alta com prazo de 1 dia.

### 4. O Diretor acertou duas vezes, e uma está confirmada pelo engenheiro

Na foto 4 o Analista enquadrou `NR-18 18.9.2` para um **vão de PAREDE** coberto por tela
metálica, e o Diretor **vetou** com a razão exata: *"o item normativo regula especificamente
aberturas no piso"*. **O engenheiro confirmou que a tela é fechamento e está fixada**, então 0
NC ali é o resultado certo pelos dois motivos: o item era impróprio e a proteção existe.
**A conta do `18.9.2` sobre abertura VERTICAL fica assim**: ele passou em três laudos (o 1 de
09/09, a passada B de 10/09 e o 2 de 11/09) e foi vetado em dois (a passada A de 10/09 e esta).
É a segunda vez que o veto sai com a razão certa, e a **primeira em que a resposta do engenheiro
fecha o caso**.
**O `NR-08 8.3.2.2` nem estava disponível ali**: a NR-08 não é candidata na foto 4, então não
havia como trocar o item de piso pelo que cobre parede.

### 5. A escada da foto 1 é a classe de erro 2 reaparecendo, e o aparo não a matou

A NC entregue é `NR-18 18.8.6.12`, com a constatação *"a escada de alumínio apoiada contra a
parede não apresenta visivelmente sapatas antiderrapantes"*. **Aberta a foto, a base da escada
não aparece no recorte** — ela está encostada no canto direito ao fundo e some atrás da pilha
de blocos. É a frase que este arquivo registra nominalmente na classe de erro 2 ("escada
apoiada" virando "sem sapata antiderrapante"), e é também a cláusula (e) falhando pelo caminho
que 10/09 já mostrou: o aparo retirou *"descumprindo a exigência de estabilidade"* e manteve
uma afirmação sobre o que a foto não mostra.
**O engenheiro respondeu em 12/09, e a resposta é de um TIPO que este arquivo ainda não tinha:
"não consigo ver se a escada tem sapata".** Não é confirmação nem refutação — é a terceira
resposta possível, e para a regra da moldura ela vale mais que as outras duas. **Quem esteve na
obra não decide pela foto, e o app decidiu**: emitiu não conformidade de gravidade alta com prazo
de 1 dia sobre uma peça que a imagem não mostra. A NC não é falso positivo (a sapata pode faltar
mesmo), é **enquadramento sem lastro visual**, que é a classe de erro 2 e o caso exato que a
cláusula (e) existe para mandar ao ponto de atenção.
**Isso dá um critério externo para a moldura, e é barato de repetir**: quando a pergunta ao
engenheiro for respondível só indo ao local, a constatação tinha de ser verificação. Vale pôr essa
pergunta em toda auditoria de imagem daqui em diante — ela separa o que a foto mostra do que o
laudo afirma, sem depender do meu julgamento sobre o recorte.

### 6. Divergências candidatas, e por que NÃO há taxa fechada aqui

**32 fatos nas 5 fotos.** A comparação de taxa que este lote prometia — a mesma contagem do
lote de MÁQUINA noutro vocabulário — **não foi feita**, e é preciso dizer por quê: a auditoria
exaustiva fato a fato não rodou. O que houve foi leitura das quatro imagens ANTES do lote (que
é a regra 1 do desenho cumprida pela primeira vez) e duas reaberturas dirigidas depois. Anunciar
"7 em 30 contra N em 32" seria comparar duas medições diferentes.

| divergência candidata | foto | estado |
|---|---|---|
| "Abertura retangular no piso" onde não há abertura | 3 | **CONFIRMADA — VÃO INEXISTENTE** |
| "piso de terra batida" numa laje de concreto do 13º pavimento | 5 | **já confirmada em 11/09** (P4), repetida byte a byte |
| "Tambor cilíndrico de cor azul, possivelmente um compressor de ar" | 4 | **CONFIRMADA em 12/09: é um galão de água** — e é a divergência mais cara depois do vão, porque levou `NR-13 13.5.1.3` e `13.5.1.4` (placa de identificação de VASO DE PRESSÃO) a D1 e D2 |
| "Estrutura metálica de quatro pés (mesa de trabalho) coberta por uma lona branca plástica" — parece cavalete com papel de projeto | 1 | sem pergunta |
| "tubo de proteção amarelo fixado verticalmente na face" da coluna — parece cabo ou mangueira amarela | 2 | sem pergunta |

**Duas linhas fecharam em 12/09** — o vão da foto 3 e o galão da foto 4 —, e sobraram duas sem
pergunta (a mesa com lona da foto 1 e o tubo amarelo da foto 2). A quinta linha já vinha
confirmada de 11/09. **Mesmo assim não há taxa**, pela razão do parágrafo acima: sem a auditoria
fato a fato das 32 linhas, o numerador é de uma amostra dirigida e o denominador é de outra.
**O que este lote acrescenta à decisão da fase separada de VISÃO** é o caso do galão: um NOME
errado num objeto secundário arrastou duas vagas do dossiê para outra NR inteira. Nas medições
anteriores o nome errado custava item impertinente na mesma família; aqui ele troca a norma.

### 7. O que se confirmou sem divergência

- **A âncora manteve** `NR-18 18.9.2`, como em toda execução com laudo lido, e o
  `NR-18 18.9.3` **continua fora do dossiê** — 7 entradas, reproduzidas aqui, exatamente o que
  12/09 já tinha medido sobre o laudo 4 do lote de MÁQUINA.
- **O portão de pessoa não foi exercido de novo.** A foto 2 tem 2 trabalhadores contados e a 1
  tem 1, e nenhum risco com `exige_pessoa` routeou em foto nenhuma. Continua sem lote.
- **A contagem de gente bate com a imagem** nas duas: 1 pedreiro na foto 1, e na 2 a perna de
  uma pessoa mais a bota do fotógrafo.
- **O parecer volta a carregar hipótese** no laudo 5 (*"pode ceder ou deslocar-se sob carga"*),
  no campo que a cláusula (d) não governa. Terceira aparição da mesma armadilha.

---

## Validação em produção de 11/09/2026 — o lote de MÁQUINA, 5 fotos

Rodado no `b48f666` (hash informado pelo usuário — os laudos não o carregam), obra
"teste 6". **5 laudos, 4 NCs, 0 não auditadas, 1 ciclo em todos.** É o primeiro lote fora
do domínio de poço de elevador desde o de içamento, de 02/09, e o primeiro em que TODAS as
imagens foram abertas e auditadas contra os fatos do Olho.
**Os cinco HTML foram lidos nesta sessão**, então as listas de fatos estão disponíveis e os
dossiês são reproduzíveis sem rede — foi assim que as seções 1 e 5 derrubaram duas hipóteses
sobre o portão de máquina que tinham sido escritas sem medir. Ao registrar o próximo lote,
peça os laudos ANTES de concluir causa: a reprodução custa dois minutos e o palpite custou
duas rodadas de `/critico` aqui.

| # | Foto | Papel | NC | Aceite declarado | Resultado |
|---|---|---|---|---|---|
| 1 (laudo 1) | `SERRA DE BANCADA` | máquina real | `NR-17 17.7.2.1` média | portão ABRE, item de NR-12 pertinente | **falhou nos dois** |
| 2 (laudo 2) | `SERRALHERIA SEM BARREIRA DE ACESSO` | máquina + pessoas | `NR-18 18.9.2` crítica | portão de máquina e o de pessoa | **falhou nos dois — e a omissão da barreira está CONFIRMADA: NC real que o lote perdeu** |
| 3 (laudo 3) | `SERRAGEM AREA DE CARPINTARIA` | contraparte 1 | `NR-08 8.3.2.2` alta | 0 item de NR-12 | **cumpriu o aceite — e a NC que saiu é FALSO POSITIVO confirmado pelo engenheiro** |
| 4 (laudo **5**) | `OPERADOR BETONEIRA` | contraparte 2 | 0 | 0 de NR-12 e 0 de NR-06 | **cumpriu, com o portão ABERTO** |
| 5 (laudo **4**) | `13 PAV. PEÇO ELEVADOR SEM PROTEÇÃO` | âncora | `NR-18 18.9.2` crítica | mesmo item das 4 execuções | **âncora manteve, e a omissão do `18.9.3` está CONFIRMADA: a resposta é PARCIAL nas quatro execuções** |

**Gabarito contra o nome do arquivo: 2 de 5** (as fotos 4 e 5), pelo critério de 10/09 —
e **este número não depende da leitura das imagens**, só do nome do arquivo contra o laudo:
a 1 e a 2 nomeiam achados (serra, ausência de barreira) que o laudo não entrega, e a 3 não
aponta defeito e recebeu 1 NC. **As respostas do engenheiro chegaram em 11/09 e não o
movem**, como a seção 6 previa: a foto 3 continua falhando, agora por falso positivo
confirmado em vez de discutível, e a 2 continua falhando, agora com a causa medida (achado
não visto, não item errado). A auditoria das imagens é a seção 5, e ela não é gabarito.
**Ressalva que a resposta da P6 obriga, e ela não move o número mas qualifica um dos dois
acertos**: a foto 5 conta como fechada porque o laudo entrega UMA não conformidade sobre a
falta de proteção do poço, num item que se aplica — mas o engenheiro confirmou que o vão de
acesso também estava aberto, e esse enquadramento não saiu. **O acerto da âncora é parcial**,
e quem apertar o critério pode ler 1 de 5. Ficou 2 de 5 porque o critério escrito em 10/09
pede o achado do nome do arquivo num item aplicável, e isso o laudo entregou.

### 1. O portão de máquina não é o gargalo — e o NOME também não

Reproduzido sem rede sobre os fatos reais dos cinco laudos:

| foto | `ha_maquina_na_cena` | itens de NR-12 no dossiê |
|---|---|---|
| `SERRA DE BANCADA` | **False** | 0 |
| `SERRALHERIA` | **False** | 0 |
| `SERRAGEM` | False | 0 |
| `OPERADOR BETONEIRA` | **True** | 0 |
| `13 PAV.` | False | 0 |

**Zero itens de NR-12 nos cinco dossiês**, inclusive na única foto do acervo com uma
máquina de verdade em primeiro plano. O portão fechou na foto 1 porque o Olho escreveu
*"Máquina industrial de cor escura, com superfície metálica"* — e `maquina` está fora de
`MAQUINAS_NA_CENA` de propósito, pela armadilha do portão que só ABRE.

**O engenheiro respondeu em 11/09: é uma serra de bancada** — o que o nome do arquivo dizia
desde o começo. **A leitura da imagem feita aqui dizia serra de FITA, e estava errada**; ver
a taxa de erro dessa leitura na seção 5. Para o portão o erro é indiferente e a medição
fica mais limpa por causa disso: `serra de bancada` e `serra de fita` estão as DUAS em
`MAQUINAS_NA_CENA`, e medido agora, `ha_maquina_na_cena` devolve **True** com qualquer uma
das duas no lugar de "máquina industrial" no fato real.

**MAS abrir o portão não recupera nada, e isso foi medido nos laudos.** Com os cinco HTML em
mãos, os dossiês das fotos 1 e 2 foram reproduzidos sem rede, com e sem o nome da máquina no
fato. O portão abre nas duas, e o que entra é ruído:

| foto | com o nome | itens de NR-12 que entram |
|---|---|---|
| 1 (`serra de bancada`) | 14 → **19 entradas** | `12.4.8`, `Anexo III 7`, `Anexo XII 2.1` (**cestas aéreas**), `Anexo XII 3.2.2` (plataformas condutivas), `Anexo XII 3.6.1` |
| 2 (`policorte`) | 9 → **11 entradas** | `Anexo III 6.1` (**rampas com mais de 20º**), `Anexo XII 3.2.2` |

**Nenhum item da família de proteção de partes móveis (`12.5.x`) chega em nenhuma das duas**,
e na foto 2 a entrada dos dois itens de NR-12 **expulsa** o `NR-18 18.10.2.6`, que era o único
item do dossiê com alguma relação com a ferramenta de corte. **É a medição de 08/09 repetida
noutro portão**: destrancar não faz o item certo subir, e aqui piora o dossiê. Os anexos III e
XII da NR-12 não são ramos setoriais, então `setor_pertinente` não os filtra — uma foto de
serra de bancada recebe item de cesta aérea.
**Logo a cadeia NÃO está fechada**, e a redação anterior desta seção afirmou que estava: nome
ausente fecha o portão, mas o nome presente não entrega item pertinente. O gargalo é o Olho
não inspecionar a máquina — não escrever a proteção, a lâmina, a zona de corte —, que é o item
em aberto desde 01/09 e que nenhum dos três mecanismos que esperavam este lote (o portão, os
sinais dos #14/#15 e os `itens_so_com_maquina`) chegou a exercer. O que exercita os três é
FATO sobre a proteção, não o nome do objeto.
Não é limite de leitura como o erro de material de 10/09 — a fenda e a lâmina aparecem nos
504 px em que o Olho recebe a foto.

**O dossiê da foto 1 mostra o custo**: 14 entradas, nenhuma de serra, com `NR-13 13.4.2.6`
e `13.6.2.4` (caldeiras; o `13.4.2.6` fala de "painel de instrumentos", que é o caminho
plausível para o painel de comando da foto — o `13.6.2.4` não tem a palavra "painel" e
chegou por outro caminho, não medido) e cinco
itens de NR-17. O Analista escolheu `NR-17 17.7.2.1`, posicionamento ergonômico de painel,
para uma fiação solta — **classe de erro 1 pela porta do dossiê pobre**, com o agravante
de o achado ser elétrico e o item ser de ergonomia.

### 2. A armadilha da placa disparou, e quem segurou não foi o portão

`ha_maquina_na_cena` devolveu **True** na foto da PLACA, exatamente como o desenho do lote
previu: o Olho leu e transcreveu a palavra `BETONEIRA` do letreiro, e o portão não olha o
entorno. O laudo saiu certo assim mesmo — 5 entradas, **todas de NR-18**, zero de NR-12 e
zero de NR-06 —, mas não foi o portão que o salvou: **`NR-12` nem chegou a ser NR
candidata** (`dossie.nrs_candidatas == ['NR-18']`), então não havia o que destrancar. **A
porta está aberta e o aceite passou por outro caminho**; a conclusão "0 de NR-12" não pode
ser lida como o portão tendo funcionado.

**Correção ao desenho do lote**: a linha desta foto dizia "não há máquina nenhuma". Há —
uma estrutura amarela com tambor arredondado e alça aparece na borda direita do
enquadramento, **provavelmente a própria betoneira**, e o Olho a registrou como
*"Estrutura metálica de cor amarela parcialmente visível"*, sem nomeá-la, que é o que a
regra da moldura pede. Confirmar com o engenheiro.

### 3. A armadilha da `serragem` não existe mais — medida nos dois sentidos

O `/critico` levantou no #35 que `serra` solto abriria em "serragem", e isso nunca fora
medido em produção. Medido agora, e o conserto está no código: **não há `serra` solto em
`MAQUINAS_NA_CENA`** — os sete termos de serra são todos compostos (`serra circular`,
`serra de bancada`, `serra de fita`, `serra marmore`, `serra de disco`, `serra fita`,
`motosserra`), e a lista como um todo tem muito termo de uma palavra só (`betoneira`,
`grua`, `guincho`), então a régua é do termo, não da lista. Com isso `"pilha de serragem"`,
`"madeira serrada"` e `"pó de serragem"` devolvem **False**, e `setor_pertinente(18.10.1.5, "monte de serragem…")` também. Com
`"serra de bancada"` os dois abrem. **A contraparte 1 cumpriu o aceite, mas não exercitou
o mecanismo**: o Olho nem escreveu "serragem" — escreveu *"material granular de cor clara,
com aspecto de areia"*.
**O engenheiro confirmou em 11/09 que o monte é serragem**, da serra de bancada da foto 1.
Então o mecanismo continua sem ser exercido em produção, e a medição sintética é o que há:
`ha_maquina_na_cena("monte de serragem e restos de madeira")` devolve **False**. O que abre
é o termo composto — `"pilha de serragem da serra de bancada"` devolve True, e aí a máquina
está nomeada de verdade, que é o portão funcionando.

### 4. O portão de pessoa continua sem lote

Nenhum dos riscos roteados nas cinco fotos tem `exige_pessoa=True` — são
`quadro_eletrico_aberto_ou_sem_sinalizacao`, `empilhamento_instavel_de_material`,
`abertura_parede_desprotegida`, `entulho_sobras_acumulados` e
`abertura_piso_desprotegida`. A foto 2 tem 3 trabalhadores na cena e o segundo aceite
declarado dela era esse portão: **ele não foi exercido**, e os 25 riscos que dependem dele
seguem sem medição. Quem quiser medi-lo precisa de foto que roteie risco de EPI.

### 5. Auditoria das imagens contra os fatos — a contagem por classe de erro do Olho

**Duas ressalvas de método, e a segunda governa tudo o que vem abaixo.**

1. **A leitura NÃO foi cega.** Os cinco laudos e o pedido chegaram na mesma mensagem,
   então os fatos do Olho foram lidos antes das imagens — o que a regra 1 do desenho
   proíbe, justamente porque contamina. O que ela mais ameaça são as OMISSÕES, porque
   saber o que o laudo não disse dirige o olhar. **A contagem de omissões é piso, não
   medida** — pode haver mais do que as três listadas. **E o risco não era só deixar passar:
   das três, uma era inventada** (a coifa), o que a leitura não cega torna mais provável, não
   menos.
2. **A auditoria NÃO é gabarito — regra 3 do desenho, e esta seção a respeita.** Onde a
   leitura da imagem diverge de um fato, isso é **pergunta ao engenheiro**, nunca
   veredito: ele viu a obra, a imagem é um recorte dela, e sem esta regra o gabarito
   ganharia uma segunda fonte que é um modelo julgando outro, com ninguém acima. Logo a
   tabela abaixo é de **divergências a confirmar**, e a contagem é **provisória até a
   resposta dele**. A primeira redação desta seção violou isso — declarava a NC do laudo
   3 falsa e o vão inexistente —, e foi o `/critico` que pegou.
   **E a regra vale para as OMISSÕES do mesmo jeito**, que é o segundo gap que ele achou:
   a segunda redação as marcava só como "piso" pela ressalva 1 e não perguntava nada sobre
   elas. São leitura de imagem igual às divergências, e são a metade que carrega **risco
   real não reportado ao cliente** — uma barreira de acesso ausente de verdade é NC que o
   laudo não trouxe, e foi exatamente o que a resposta do engenheiro confirmou na foto 2.
   Por isso as três foram perguntadas, e é de lá que veio o achado mais caro do lote.

**AS RESPOSTAS CHEGARAM — seis em 11/09 e a sétima em 12/09.** As perguntas eram quatro
sobre divergências e três sobre omissões. Esta tabela é o registro, e é dela que a contagem
passa a depender:

| # | pergunta | resposta do engenheiro | efeito |
|---|---|---|---|
| **P1** | foto 3 — as faixas escuras ao fundo são vãos ou o solo recuado da contenção? | **solo recuado na contenção da escavação** | confirma as DUAS linhas que saem daquela superfície; **a classe VÃO INEXISTENTE existe**, e a única NC do laudo 3 é falso positivo |
| **P2** | foto 3 — o monte claro é serragem ou areia? | **serragem, da serra de bancada da foto 1** | confirma uma linha de MATERIAL |
| **P3** | foto 1 — a máquina é uma serra de fita? | **não: é serra de bancada** | a linha de NOME fica de pé (o Olho escreveu "máquina industrial"), e **a leitura feita aqui errou a máquina** |
| **P4** | foto 5 — o piso fora do poço é laje empoeirada? | **laje empoeirada** | confirma uma linha de MATERIAL |
| **P5** | foto 1 — a lâmina tem coifa? | **tem coifa** | **a omissão NÃO existe** — a leitura feita aqui inventou o achado |
| **P6** | foto 5 — o vão de acesso ao poço estava sem fechamento? | **estava sem proteção no dia** | **omissão CONFIRMADA: a segunda NC real que o lote perdeu**, e o `NR-18 18.9.3` nunca saiu em quatro execuções |
| **P7** | foto 2 — havia barreira isolando a área de corte? | **não havia barreira de acesso** | **omissão CONFIRMADA: NC real que o lote inteiro perdeu** |

**A leitura de imagem feita aqui errou 2 das 7, e as duas na mesma foto.** A máquina da
foto 1 não é serra de fita, e a lâmina dela TEM coifa. As duas são erros do mesmo sinal —
afirmar o que não está lá —, e a segunda é grave de um jeito específico: **ela é a mesma
classe de erro que esta seção estava acusando o Olho de cometer na foto 3**. Um achado
inventado, com a propriedade de risco embutida no nome ("lâmina exposta sem coifa"), pronto
para virar não conformidade se alguém o tratasse como fato. **É a regra 3 validada com
número**: tratada como gabarito, esta auditoria teria acrescentado ao laudo uma NC de NR-12
falsa, exatamente o dano que ela existe para medir. A ressalva 1 dizia que a leitura não
cega ameaça as omissões; ela ameaçou, e no sentido de INVENTAR, não só no de deixar passar.

**O que as respostas custaram ao laudo do cliente, que é o que importa fora daqui:** TRÊS
NCs erradas em cinco fotos. Uma saiu e não devia — o laudo 3, falso positivo, `NR-08
8.3.2.2`, alta, prazo de 1 dia, sobre um vão que não existe. **Duas deviam sair e não
saíram**: a ausência de barreira de acesso da foto 2, que é o achado do nome do arquivo, e o
vão de acesso ao poço da foto 5 sem fechamento provisório, que é o `NR-18 18.9.3`.
**A conta fica assim**: o app entregou 4 NCs nas cinco fotos, das quais **uma é falso
positivo confirmado**; e **duas NCs reais não saíram**. As outras três entregues não são
falso positivo, mas duas delas têm defeito de item registrado noutro lugar desta validação —
o `NR-17 17.7.2.1` da foto 1 (ergonomia para fiação solta, classe de erro 1) e o
`NR-18 18.9.2` da foto 2 (item de piso para abertura vertical). **Só a NC da âncora sai
ilesa, e ainda assim parcial.**
**A segunda É falha de recuperação, e o dossiê medido diz de que tipo.** Uma redação anterior
citava o `NR-18 18.10.2.6` no D6 da foto 2 como prova de que o item certo estava à mão — mas
aquele item é o **disco específico para o material cortado** e não alcança barreira de acesso
nenhuma. Usá-lo ali era a classe de erro 1 cometida dentro da análise, e foi o `/critico` que
pegou. **A redação seguinte errou de outro jeito**, apontando o `NR-12 12.5.13` como o item
certo e o portão de máquina como o que o trancava. Com os laudos em mãos isso foi medido nos
três desenhos, e nenhum entrega o item:

| dossiê da foto 2 | o que chega |
|---|---|
| como saiu (fato real) | nada de NR-12; `18.10.2.6` em D6 |
| com `policorte` no lugar de "ferramenta elétrica de disco" | NR-12 de **rampa** e de **plataforma condutiva**, e o `18.10.2.6` é **expulso** |
| com o achado do engenheiro escrito como FATO ("área de corte sem barreira, cerca ou isolamento") | `area_carpintaria_armacao_irregular` dispara e traz `NR-18 18.7.3.1` e `18.7.3.2` em **D5 e D6**, curados |

**O terceiro é o único que chega perto, e ainda assim não fecha**: o `18.7.3.1` cobre piso,
cobertura, iluminação e remoção de resíduos da área de carpintaria — **não tem cláusula de
isolamento** —, e o `18.7.3.2` isola especificamente a área de movimentação de VERGALHÕES. O
`12.5.13` passa por `comprovavel_em_foto`, por `prescritivo` e por `setor_pertinente`, e
**nunca ranqueia**. **Não há na base item que cubra de frente "área de corte sem barreira de
acesso"** — é a situação dos itens de içamento de 03/09 outra vez: o achado é real, o
enquadramento não existe ao alcance. Ver o item novo em aberto.
**A diferença entre as duas fotos fica assim**: na foto 1 o portão fechado não escondeu
defeito nenhum, porque a serra tem coifa; na foto 2 escondeu um achado real, mas abrir o
portão não o teria recuperado.

**A P6 fechou em 12/09, e só depois de a FOTO ser aberta.** A pergunta estava ambígua: os
fatos do Olho registram *"Grade metálica de malha quadrada (treliça) instalada verticalmente,
delimitando uma passagem ou vão lateral"* e *"Vão vertical (poço de elevador ou escada)
visível ao fundo, com estrutura de concreto e **grade metálica na borda**"*, os dois à
DIREITA ao fundo, enquanto a leitura feita aqui falava de um rasgo na parede à ESQUERDA. Sem
saber qual dos dois, reperguntar gastaria uma rodada.
**A imagem separa os dois elementos.** Há um vão do tamanho de uma porta na parede de
concreto à esquerda, por onde se entra direto no poço, com nada atravessando; o fundo do
poço está coberto por tábuas assentadas, que é o que o laudo enquadrou. A grade metálica de
malha que o Olho descreve está à direita, noutra abertura, **encostada e não instalada** —
ela não é o fechamento do vão de acesso. O engenheiro confirmou: **estava sem proteção no
dia**.
**Logo a âncora do lote tem uma segunda NC que nunca saiu** — o `NR-18 18.9.3`, vãos de
acesso às caixas dos elevadores — em nenhuma das quatro execuções com laudo lido (09/09, as
duas de 10/09 e esta; a de 08/09 é a lista reconstruída). **"Âncora manteve" passa a
significar que o app repete a mesma resposta PARCIAL quatro vezes, não que ela esteja
completa** — e é por isso que uma âncora estável não é a mesma coisa que uma âncora certa.
**A lição de método é a segunda deste lote e vale mais que o achado**: a pergunta só ficou
respondível depois de a foto ser aberta aqui. O `add_repo` do acervo custa um minuto, e este
arquivo já mandava fazer isso desde 10/09.

**E a causa é de FATO, não de dossiê — medido no laudo 4.** Com os fatos como saíram, o
dossiê da âncora tem 7 entradas e **o `NR-18 18.9.3` não está nele**: o Analista não podia
enquadrar o que não lhe foi oferecido. O vão de acesso aparece nos fatos do Olho só como
ENDEREÇO de outro achado (*"Esquerda, dentro do vão escuro"*), nunca como abertura que pede
fechamento. Acrescentado um fato que o descreva, o roteamento passa a acionar
`poco_elevador_carga_sem_cercamento` além do `abertura_piso_desprotegida`, e o dossiê ganha
`NR-11 11.1.1` (*"os poços de elevadores e monta-cargas deverão ser cercados"*) e `11.1.2`
**curados, em D3 e D4**, mais o `18.9.3` em D8 pela busca textual.
**É o segundo caso medido a favor da fase separada de VISÃO, e o mais limpo dos dois**: uma
frase do engenheiro recupera item CURADO na frente do dossiê. Na foto 2 o mesmo desenho
levava a família da área de carpintaria, que não fecha o achado; aqui ele leva o item que
fecha.

**30 fatos nas 5 fotos. 9 divergências levantadas, e o número FECHOU em 13/09: são 7
confirmadas em 30, com 2 linhas permanentemente ABERTAS.** Cinco foram confirmadas pelo
engenheiro em 11-12/09; as outras quatro nunca tiveram pergunta, e em 13/09 ele declarou que
**não tem a memória deste acervo** — logo não haverá resposta, e elas foram decididas pela régua
que essa declaração obrigou (ver a regra (a)-(d) no item em aberto *AUDITAR A FOTO CONTRA OS
FATOS*):
- **FORMA** (o objeto azul da foto 3) e **POSIÇÃO** (onde repousa a ferramenta de corte da foto
  2) são geométricas, então a imagem decide. Reabertas e ampliadas em 13/09, **as duas se
  confirmam como divergência**: a ferramenta está sobre a **bancada escura**, não sobre a mesa de
  pernas de madeira; e o objeto azul é um **recipiente metálico volumétrico, inclinado e
  apoiado** — nem o "painel rígido apoiado verticalmente" do Olho (é volume, não chapa plana),
  **nem a "caixa deitada no chão" que eu escrevi em 11/09**, que estava igualmente errada.
- **MATERIAL** (a laje da foto 1) e **NOME** (o policorte da foto 2) caem na regra (b) — a
  imagem não decide nenhuma das duas — e ficam **ABERTAS**, não pendentes. Não entram na
  contagem em nenhum sentido.
**A palavra "provisória" sai**, e não porque tudo fechou: sai porque não há mais resposta a
esperar. O teto de 9 é inalcançável por construção. Das 3 omissões levantadas, **2 confirmadas
e 1 refutada**, com as sete perguntas do lote todas respondidas.

| classe | n | onde | estado |
|---|---|---|---|
| **MATERIAL** | 4 | serragem chamada de "areia" (3); face de escavação em solo projetado chamada de "parede de alvenaria … expondo tijolos e blocos" (3); laje de concreto empoeirada chamada de "piso de terra batida" (1 e 5 — e a 5 é o **13º pavimento**) | **3 confirmadas** (serragem, contenção, laje da 5); **a laje da foto 1 fica ABERTA** — material, regra (b), e não há árbitro |
| **NOME do equipamento** | 2 | serra de bancada → "máquina industrial" (1); ferramenta de corte → "ferramenta elétrica de disco" (2) | **1 confirmada** (a 1 é serra de bancada, não de fita); **a 2 fica ABERTA** — se é policorte é NOME, regra (b), a mesma classe do "serra de FITA" que eu errei |
| **VÃO INEXISTENTE** | 1 | "aberturas retangulares na parede de fundo, sem portas ou janelas instaladas" (3) | **CONFIRMADA — a classe existe, e é a mais cara das cinco** |
| **FORMA / ORIENTAÇÃO** | 1 | "painel rígido de cor azul apoiado verticalmente" (3) é um **recipiente metálico volumétrico, inclinado e apoiado** | **CONFIRMADA em 13/09 pela geometria** — e a descrição desta linha estava errada até então: eu escrevera "caixa deitada no chão", que a ampliação também derrubou |
| **POSIÇÃO** | 1 | a ferramenta de corte repousa na **bancada escura**, e não na mesa de pernas de madeira, onde o Olho a situou (2) | **CONFIRMADA em 13/09 pela geometria** |
| *omissões* | 3 | ~~lâmina exposta sem coifa (1)~~; ausência de barreira de isolamento da serralheria (2); vão de acesso ao poço sem fechamento — o `18.9.3` (5) | **2 confirmadas** (a barreira e o `18.9.3`); a da coifa **REFUTADA** (a serra tem coifa) |

**Qual pergunta fechou qual linha desta tabela, e por que duas ficam ABERTAS em vez de
pendentes: seção 6.** As duas linhas que 13/09 fechou pela geometria trazem a descrição
corrigida aqui — **a tabela é a cópia canônica, e ela é a que quase escapou**: o commit que
fechou o número atualizou as seis ocorrências do total e deixou esta tabela dizendo "sem
pergunta" e "caixa deitada no chão", que ele mesmo acabara de refutar. Foi o `/critico` que
pegou, e é a terceira vez na mesma sessão que a armadilha do número aparece pela via da cópia
que ninguém listou. **Ao fechar uma linha, corrija a TABELA antes do total** — o total é o que
o `grep` acha, a descrição não.

**A classe candidata separou-se da FORMA de propósito.** A primeira redação punha as duas
divergências da foto 3 juntas sob "vão inexistente", com n=2 — e a caixa azul não é um vão
nem produziu nada. Juntá-las inflava de 1 para 2 justamente a classe de que a seção
inteira depende. São mecanismos diferentes: uma erra a orientação de um objeto real, a
outra **criaria** um objeto com a propriedade de risco embutida no nome.

**O engenheiro confirmou a foto 3, e a classe nova é a mais cara das cinco** — a única que
fabricou uma NC inteira: a única não conformidade daquele laudo, `NR-08 8.3.2.2`, alta,
prazo de 1 dia, nasceu de um vão que não existe. **É falso positivo medido, não mais
hipótese.** Diferente das três classes conhecidas, ela não erra um atributo de um objeto
real: **cria o objeto**. Nenhuma trava do pipeline pergunta se o vão existe, e o Diretor
aprovou sem veto nem aparo, porque a conferência confere a constatação contra o FATO e o
fato está lá. **Nos 504 px a leitura do Olho é defensável** — as faixas são escuras e
retangulares, e a face é solo projetado com placas de ancoragem —, então o mecanismo é o
mesmo do erro de material de 10/09; o que agrava é o *"sem portas ou janelas instaladas"*,
conclusão pendurada no objeto inventado.
**A contagem não caiu porque a resposta veio no sentido que a sustenta**: a P1 era a única
capaz de derrubar duas linhas de uma vez, e ela confirmou as duas. **O total fechou em 13/09 em
7 em 30** (ver o parágrafo do fechamento, acima) — e escrever "7 **de** 30" aqui, como a primeira
redação fez, tirava esta cópia do `grep -n "em 30"` que o próprio arquivo declara como handle. Uma redação anterior anunciava "entre 8 e 9"
tratando as duas linhas da foto 3 como independentes — é a armadilha do número que envelhece em
silêncio, cometida dentro da correção que a declarava, e foi o `/critico` que pegou.
**E ela voltou a morder aqui, em 13/09.** A lista da seção 6 declarava CINCO cópias deste
número; ao aplicar o fechamento, o `grep -n "em 30"` achou uma **SEXTA** — esta frase —, que a
lista nunca mapeou. É a armadilha *"a correção do número não alcança as cópias dele"*, cometida
dentro da lista escrita para impedi-la. **A lição que fica é do método, não do número: a lista
de cópias é ela mesma uma cópia, e envelhece igual** — quem for corrigir confia no `grep` do
denominador, nunca na contagem de cópias escrita ao lado.

**Para o defeito que o Analista de fato enquadrou, o dossiê já tinha a resposta certa em
duas das três fotos erradas** — ali a recuperação não é o gargalo, a escolha é (para o
achado do ENGENHEIRO na foto 2 vale o oposto, e é o item novo em aberto):
- foto 3: `NR-18 18.16.16` e `18.16.17` (remoção de entulho e resíduos acumulados) em
  **D1 e D2**, curados, e o Analista foi ao `8.3.2.2` do D7.
- foto 2: `NR-18 18.10.2.6` — *"a ferramenta elétrica utilizada para cortes deve ser
  provida de disco específico…"* — em **D6**, e o Analista foi ao `18.9.2` da abertura.
  **Ressalva que as respostas de 11/09 obrigam**: esse item responde a OUTRA pergunta que
  não a do nome do arquivo. O achado que a foto 2 perdeu é a ausência de barreira de acesso,
  e para ele o dossiê **não** tinha a resposta certa — ver a seção 5. Logo são duas das
  três fotos erradas só para o defeito que o Analista de fato enquadrou, não para o achado
  do engenheiro.

### 6. O que ainda não fechou, e onde o número mora

**A contagem desta validação vive em VÁRIOS lugares deste arquivo, e esta frase deliberadamente
não diz quantos.** Ela dizia: "cinco" até 13/09; "seis" quando o `grep` achou a cópia que a lista
não mapeava; "sete" quando se viu que o parágrafo da regra encerrada, escrito no mesmo commit,
criara outra; e o `/conferir` da mesma passada mostrou que eram **oito**. Quatro valores em dois
dias, todos escritos de boa-fé — porque **cada correção mexe no texto e cria ou apaga uma cópia**,
e a contagem envelhece no instante em que é escrita. **A lista nominal abaixo vale; o número não.**
O que se usa é o handle: `grep -n "em 30"`. Se uma cópia nova aparecer nele e não estiver na lista,
acrescente-a — sem recontar o total. Esta lista existe
porque, sem ela, quem recebe uma resposta atualiza a seção que está lendo e deixa as outras
quatro afirmando o valor velho — a armadilha do número que envelhece em silêncio, armada de
propósito. Foi o `/critico` que pegou, na quarta rodada; as seis respostas de 11/09 foram
aplicadas às cinco na mesma passada.

1. **A seção 5 desta validação** — é a CANÔNICA, e a única que carrega as tabelas. **São DUAS
   ocorrências nela**, não uma: o parágrafo do total e o parágrafo "a contagem não caiu". A
   segunda escapou desta lista até 13/09 — ver lá o que isso ensina.
2. **A seção 7, logo abaixo.**
3. **A linha ~~MÁQUINA~~ da tabela de lotes temáticos**, em "Onde a coisa parou".
4. **Em aberto → AUDITAR A FOTO CONTRA OS FATOS**, que é onde a contagem por classe vive.
5. **Em aberto → Separar a fase de VISÃO da fase de ENQUADRAMENTO**, que decide por ela.
6. **Esta seção 6**, no parágrafo que encerra a regra de atualização — cópia criada em 13/09
   pelo próprio commit que corrigia as outras.
7. **A seção 6 da validação de 12/09**, na frase que explica por que o lote de elétrica não
   tem taxa ("7 em 30 contra N em 32"). É de outro lote e carrega este número mesmo assim.

O handle de `grep` que sobrevive a mudança de número é o denominador: `grep -n "em 30"`.
O numerador não serve de handle justamente porque muda — é ele que se está caçando.
**E o handle só funciona se todas as cópias o escreverem igual**: em 13/09 uma delas foi
reescrita como "7 **de** 30" e sumiu do `grep`, o que é o handle quebrado por quem o mantinha.
Ao editar qualquer uma, preserve a forma literal `em 30`.

**O que fecha o número, e não é o que a redação anterior desta seção dizia.** Ela afirmava
que o total deixaria de ser provisório quando as quatro perguntas de divergência tivessem
resposta, e três parágrafos abaixo afirmava que sem as quatro linhas sem pergunta a
contagem nunca fecha. As duas não podiam valer juntas, e foi o `/critico` que pegou. Vale a
segunda: **as quatro perguntas de divergência foram respondidas e o total continua
provisório**, porque quatro das nove linhas nunca foram perguntadas.

**As quatro perguntas que faltavam — RESOLVIDAS em 13/09, e nenhuma delas pelo engenheiro.**
Ele declarou que não tem a memória deste acervo, e a régua nova (regra (a)-(d) no item em aberto
*AUDITAR A FOTO CONTRA OS FATOS*) separa as quatro em duas metades:

- **Foto 2 (`SERRALHERIA`) — POSIÇÃO: DECIDIDA pela imagem.** A ferramenta de corte repousa
  sobre a **bancada escura**, no tampo metálico; a mesa de pernas de madeira está à direita,
  separada, e nada há sobre ela. **A divergência se confirma.**
- **Foto 3 (`SERRAGEM AREA DE CARPINTARIA`) — FORMA: DECIDIDA pela imagem.** O objeto azul é um
  **recipiente metálico volumétrico, inclinado e apoiado** — não é chapa plana em pé, como o Olho
  escreveu, **nem caixa deitada no chão, como eu escrevi em 11/09**. A divergência se confirma, e
  as duas leituras anteriores caem juntas.
- **Foto 1 (`SERRA DE BANCADA`) — MATERIAL: ABERTA.** Laje empoeirada ou terra batida é
  material, e a regra (b) não deixa a imagem decidir. Fica aberta e não conta.
- **Foto 2 — NOME: ABERTA.** Se a ferramenta é um policorte é nome próprio de equipamento, a
  mesma classe do "serra de FITA" que eu errei em 11/09. Fica aberta e não conta.

**A P6 fechou em 12/09**: o vão de acesso ao poço da foto 5 estava sem proteção, e o
`NR-18 18.9.3` é a segunda NC real que o lote perdeu. Ela não moveu a contagem de fatos
errados — omissão não é fato errado —, moveu o que o laudo deixou de reportar. **Ela só ficou
respondível depois de a foto ser aberta**: o Olho registra uma grade metálica à direita ao
fundo e a leitura daqui falava de um rasgo à esquerda, e são elementos diferentes. Ver a
seção 5.

**A regra de atualização cumpriu o papel e foi encerrada em 13/09.** Ela dizia que a palavra
"provisória" só sairia quando as quatro perguntas tivessem resposta, e travou o número por dois
dias exatamente como devia. O que a encerrou não foi resposta: foi a fonte acabar. Com o
engenheiro sem memória do acervo, esperar virou espera infinita, e o honesto é fechar o número
no que há e marcar o resto como ABERTO por regra, não como pendente. **O total é 7 em 30**, e a
tabela de classes continua se mexendo só na cópia 1 — as outras quatro carregam o total, e o
handle de `grep` segue sendo o denominador.

**O que nenhuma resposta muda**, e por isso não espera por elas: o gabarito **2 de 5** (nome
do arquivo contra laudo, declarado independente na abertura desta validação), os **zero
itens de NR-12 nos cinco dossiês**, o portão aberto na foto da placa e todos os números da
seção 1. Saem de código executado e do texto dos laudos, não de leitura de imagem.

### 7. O que este lote diz sobre a fase separada de VISÃO

O item em aberto de 11/09 condicionava a decisão à taxa de erro do Olho: três casos
medidos não pagavam a mudança de arquitetura. **A taxa fechou em 13/09: 7 divergências
confirmadas em 30**, cinco pelo engenheiro e duas pela geometria da imagem, com 2 linhas
permanentemente abertas e num domínio novo, com uma classe que não estava mapeada (o VÃO
INEXISTENTE, confirmado). O que a taxa NÃO decide sozinha é a direção do
conserto, e as respostas separam as duas metades melhor que o número:
- **o que a fase separada recupera é o FATO, não o nome — medido agora em DUAS fotos**. Na
  2, nomear o `policorte` abre o portão e traz item de rampa e de plataforma condutiva,
  expulsando o que havia de pertinente, enquanto escrever o achado como fato dispara um risco
  CURADO e põe a família da área de carpintaria em D5 e D6. Na 5, a âncora, o efeito é mais
  limpo: uma frase sobre o vão de acesso aciona `poco_elevador_carga_sem_cercamento` e põe
  `NR-11 11.1.1` e `11.1.2` **curados em D3 e D4**, com o `18.9.3` entrando em D8 — e sem o
  fato o `18.9.3` **não está no dossiê**, então o Analista nunca teve o que enquadrar. **É a
  declaração do achado que move o dossiê, não a declaração do objeto**, o que é coerente com
  a fronteira medida em 09/09;
- **o que ela não recupera é o VÃO INEXISTENTE da foto 3**, porque nada no desenho manda o
  engenheiro conferir fato por fato o que o modelo escreveu — e é dele que saiu o falso
  positivo confirmado do lote. Contra ele a marcação por lista age menos ainda: o item já
  estava no dossiê por busca textual.
**É a primeira vez que os dois lados da decisão têm caso medido, e eles apontam para
desenhos diferentes**: a fase separada resolve o que o Olho não vê e não nomeia; contra o
que ele INVENTA, só a confirmação fato a fato — que é o que a proposta não inclui.
Só n=5. **O lote de elétrica da fila mede a mesma taxa noutro vocabulário**, e é isso que
diz se ela é do app ou destas fotos; o que ainda não fechou está na seção 6.

---

## Validação em produção de 10/09/2026 — o lote de VARIABILIDADE, 15 fotos duas vezes

As MESMAS 15 fotos do lote de poço, **duas passadas no mesmo dia**, sem marcação
nenhuma em nenhuma delas, no `eb43354` (os PRs #39 e #40). Passada A na conta do
usuário, passada B na conta da esposa, com "Zerar contagem" entre as duas. **30 laudos,
0 não auditadas, 1 ciclo em todos, 0 falhas de leitura.** É o primeiro dos "limites
honestos" deste arquivo medido de verdade: até hoje ele só tinha anedota.

**As duas passadas são idênticas em toda entrada.** O usuário escreveu "chave 1" e
"chave 2" para se orientar, mas escreveu no campo **Obra / unidade** (`app.py:397`), que
só decora o cabeçalho do laudo — quem alimenta o Olho, o roteamento e a busca textual é
o **Contexto da inspeção** (`app.py:408`), e ele ficou vazio nas duas. Não há variável de
confusão: mesma foto, mesmo código, mesma entrada, mesmo dia. **Sorte que ele escolheu o
campo decorativo**: medido aqui sem rede, pôr `"chave 1"` no campo de contexto mudaria o
dossiê de **5 das 15 fotos** (tira um item em 04, 09, 10 e 14 e troca um por outro em
02), sem introduzir item de "chave elétrica" — o efeito é indireto, pelo corte relativo
do BM25. Vale para qualquer texto administrativo naquele campo.

### 1. O Olho NÃO varia — e este é o achado do lote

**Os fatos do Olho saíram byte a byte idênticos nas 15 fotos.** Lista de achados,
posição de cada um, texto do ambiente e contagem de trabalhadores: 15 de 15, sem uma
vírgula de diferença, em contas Groq diferentes. A temperatura 0,0/0,1 dos três agentes
sempre foi conhecida; o que ninguém tinha medido é que ela basta para o modelo de visão
ser reprodutível na prática.

Isso reescreve o limite honesto nº 1. **A variabilidade que este app tem não está na
visão: está no Analista e no Diretor.** O dossiê é determinístico por construção
(`montar_dossie` é código puro sobre os fatos), então, com os fatos fixos, tudo o que
diverge entre A e B nasceu depois deles.

**Ressalva de escopo, e ela importa:** isto é UM par de passadas, no mesmo dia, com a
mesma resolução (896px) e o mesmo modelo. Não é "o Qwen 3.8 é determinístico"; é "nestas
15 fotos, nestas condições, ele foi". A anedota que motivou o limite honesto — o botão
de emergência crítico numa foto e despercebido em outra — era de **fotos diferentes do
mesmo painel**, que é outro fenômeno e continua de pé.

### 2. Quanto do gabarito é ruído: dois números

| o que se compara | A vs B |
|---|---|
| fatos do Olho (achados, ambiente, pessoas) | **15/15 idênticos** — idênticos, não corretos: ver o erro de material da foto 1 |
| contagem de não conformidades por foto | **14/15 iguais** |
| conjunto de itens enquadrados por foto | **13/15 iguais** |
| gravidade de todos os itens da foto | 10/15 iguais |
| citação complementar ("Também alcançado por") | 15/15 iguais (laudos 8, 10 e 11 nas duas) |
| parecer da revisão técnica | **0/15 idênticos** |

Totais: **11 NCs na passada A e 12 na B**. Vetos: 3 em A (laudos 1, 7 e 9), 2 em B
(laudos 4 e 9); 25 dos 30 laudos saíram "aprovado sem vetos". Pontos de atenção: 5
laudos/6 itens em A, 4 laudos/4 itens em B. Conformidades: **2 laudos dos 30** (B01 e
B14) — o item "os pontos de atenção quase não saem" vale ainda mais para as
conformidades.

**A leitura prática para quem monta lote:** um gabarito de 15 fotos carrega ruído de
**±1 NC no total** e **duas fotos** cuja resposta pode mudar. Diferença de uma ou duas
fotos entre dois lotes **não é sinal** — é a faixa do ruído. Diferença de item na mesma
foto tampouco, quando os dois itens são defensáveis. O que dá para comparar entre lotes é
o que ficou igual nas duas passadas: os fatos, o dossiê, e o grosso dos enquadramentos.

### 3. Onde as duas passadas discordaram, uma a uma

- **Laudo 1** (`18 PAV. PROTEÇÃO POÇO DE ELEVADOR`) — **a divergência mais cara, e ela é
  o defeito registrado em aberto**. Em A o Diretor VETOU `NR-18 18.9.2` com a razão
  exata ("o item 18.9.2 regula especificamente aberturas no piso, enquanto a constatação
  descreve uma abertura vertical"), a verificação foi para os pontos de atenção, e a NC
  que ficou é `NR-08 8.3.2.2`, que cobre piso E parede. Em B o mesmo `18.9.2`
  passou, com a constatação reescrita para falar do painel de madeira sem fixação. **A
  passada A conserta o defeito do laudo 1 de 09/09 e a B o repete.** Nada mudou entre as
  duas exceto a chamada.
  **A foto foi aberta e lida depois deste lote, e as DUAS passadas erram.** O poço está
  cercado por dois painéis de tela metálica em quadro de aço e não há abertura de piso:
  o `18.9.2` de B é falso positivo, e o `8.3.2.2` de A afirma que a abertura não tem
  proteção quando ela tem. O que o Olho escreveu como *"painel rígido de madeira"* é
  metal enferrujado — ver o item em aberto, que traz também a causa raiz no roteamento.
- **Laudo 7** (`11 PAV.`) — a única divergência de CONTAGEM. Em A, vetado (0 NC); em B,
  `NR-18 18.9.2` alta. Ver a cláusula (e), abaixo.
- **Laudo 4** — mesmo item nos dois (`8.3.2.2`), gravidade alta em A e crítica em B, e
  constatações sobre coisas diferentes da mesma foto: em A a tela frouxa no trecho
  inferior, em B a tela não ser fechamento rígido. As duas defensáveis.
- **Laudo 11** — os mesmos dois itens nos dois (`18.9.1` + `18.9.2`), com o `18.9.1`
  subindo de alta para crítica em B e a ordem de encabeçamento trocando.
- **Laudo 15** — mesmo item, alta em A e crítica em B.

### 4. O PR #39 em produção, e o que não deu para medir

- **A cláusula (e) mudou o comportamento nas duas passadas.** A "não conformidade que é
  uma VERIFICAÇÃO" — `"Verificar no local se a grade metálica possui travamento"` como
  constatação, que saiu duas vezes em 09/09 e escalou de alta para crítica — **não voltou
  em nenhuma das 30**. Em A o enquadramento foi vetado e a verificação saiu em ponto de
  atenção, que é o desenho da cláusula. Em B ele sobreviveu, mas **reformulado**: a
  constatação virou afirmação ("a base está apoiada diretamente no piso, sem evidência
  visual de travamento") e a gravidade caiu de crítica para alta, com o "verificar"
  movido para a ação corretiva, onde ele é legítimo. Aceite parcial: a forma que a
  cláusula proíbe morreu; o enquadramento sobre o que a foto não mostra sobrevive por
  reescrita, e contra isso quem age é a regra da moldura, que pegou em A e não em B.
- **O aparo que não vira linha de trilha: aceite limpo. 10 aparos nas 30, 5 em cada
  passada, e TODOS com retirada real** — "a afirmação de que a grade não impede a queda,
  que é uma inferência sobre a eficácia", "a exigência específica de altura mínima de
  1,10 m … que não é verificável pela imagem". Nenhuma linha do tipo "retirado: Nenhuma
  cláusula foi removida, pois…", que é o defeito do laudo 3 de 09/09 e o que o #39
  fechou. **E o aparo é a decisão MAIS estável do Diretor**: os laudos 5, 6 e 15 foram
  aparados nas duas passadas, no mesmo item, enquanto os vetos não coincidiram em nenhum
  laudo (A vetou 1, 7 e 9; B vetou 4 e 9 — só o 9 nos dois).
  **A ressalva de 09/09 continua de pé, e ela apareceu de novo:** o aparo do laudo B01
  retirou a referência a "aberturas no piso" com a razão certa ("o fato descreve um
  painel vertical contra estrutura") e **manteve o `NR-18 18.9.2`** — o mesmo item de
  piso, o mesmo defeito, palavra por palavra. É a classe de erro 1 pelo caminho do aparo,
  e ele não pergunta se o que sobrou ainda descumpre AQUELE item.
- **A repescagem NÃO foi medida, e o motivo é instrumentação nossa.** Zero "Supervisão
  incompleta" nas 30, e `_reconferir_exigencias` **não deixa marca quando dá certo**: o
  enquadramento simplesmente sobrevive. Logo "zero omissões" não separa o Diretor não ter
  omitido do reparo ter funcionado — e são conclusões opostas sobre o mecanismo. **É a
  armadilha "o sumário não distingue enquadramento ausente de enquadramento vetado" um
  nível abaixo**: a trilha registrava a omissão que MATOU e não a que foi REPARADA.
  Consertado nesta sessão (`conferencia_reparada`, com linha própria na trilha); **há
  três testes travando**, um deles a contraparte de a repescagem vazia não contar como
  reparada. O próximo lote responde.

### 5. Defeito novo, medido: o rótulo do dossiê impresso no laudo do cliente

A conformidade do laudo B14 (`GRUA`) saiu com *"atendendo aos requisitos de proteção
contra queda de pessoas **descritos no item D6**"*. `D6` é endereço interno do pipeline.
**Um vazamento em 30 laudos** — e a causa é maior que o sintoma: `laudo.conformidades`
era a **única lista do documento que não passava por limpeza nenhuma** (`pipeline.py`,
onde `sem_enquadramento` ao lado dela já chamava `_limpar_citacoes`). Sem essa chamada,
uma citação normativa digitada pelo modelo chegaria ao laudo **sem passar pela base** —
que é a garantia central deste projeto.

Consertado nesta sessão: `RE_ROTULO_DOSSIE` entra na mesma marcação de
`_limpar_citacoes`, então os doze pontos de chamada ganham a limpeza de uma vez, e as
conformidades passaram a chamá-la. O rótulo **nu** (`D6` solto) fica de propósito, pela
mesma razão que `RE_ROTULO_INTERNO` só remove `(V1)` entre parênteses — "Bloco D3 da
edificação" é frase de engenheiro. Exigimos o apresentador ("item D6", "conforme D6") ou
o delimitador ("[D6]"). **Há cinco testes travando**, um deles a contraparte do rótulo nu.

### 6. O que se confirmou sem divergência

- **Zero "torre de elevador" nas 30**, terceira medição seguida. `GRUAA` e `GRUAAA`
  trazem "Torre metálica treliçada"; `GRUAA` traz ainda "Torre de guindaste metálica
  distante"; `GRUA` tem "grua ou torre de elevação" no ambiente, com a lança e os
  contrapesos descritos.
- **As três fotos de grua deram 0 NC nas duas passadas**, e `GRUAAA` está em **0 NC pela
  terceira e pela quarta medição seguidas** (08/09, 09/09 e as duas de hoje), com 3
  trabalhadores na cena.
- **Zero riscos roteados continua prevendo 0 NC — agora com n=8.** As mesmas quatro fotos
  de 08/09 routeiam risco nenhum (`SOMENTE COM UM PONTO DE FIXAÇÃO`, `GRUAA`, `GRUAAA`,
  `GRUA`) e as oito execuções deram 0 NC. **Nenhum falso positivo saiu de dossiê sem
  risco curado**, que é o que o `18.12.22` do `GRUA` fez em 08/09: o portão setorial do
  #35 segurou nas oito.
- **O achado do engenheiro na foto 2 continua não sendo visto**, nas duas passadas. A
  fixação precária não está em fato nenhum do Olho, e por isso ela é o caso que o desenho
  D **não** recupera — é a fronteira medida em 09/09, confirmada aqui: marcação dirige o
  dossiê, não o Olho.

### 7. Gabarito contra o nome do arquivo: 13 de 15 em A, 12 de 15 em B

**Critério, declarado porque o número depende dele:** a foto fecha quando o laudo entrega
o achado que o engenheiro escreveu no nome do arquivo, num item que se aplica àquela
situação — ou quando devolve 0 NC e o nome não aponta defeito. Item verdadeiro na
situação errada (a classe de erro 1) não fecha, mesmo com a norma citada corretamente.
É o mesmo critério das quatro que 09/09 lista como não fechando (1, 2, 7 e 15).

| # | foto | A | B | por quê |
|---|---|---|---|---|
| 1 | `18 PAV. PROTEÇÃO POÇO DE ELEVADOR` | ❌ | ❌ | **A foto foi aberta e lida em 10/09.** O poço está cercado por dois painéis de tela metálica em quadro de aço, formando canto; não há abertura de piso. B usa `18.9.2`, item de PISO. A usa `8.3.2.2` afirmando que a abertura "não possui proteção" — e a proteção está instalada; o que existe é a fresta de montagem entre o painel e o pilar. **As duas passadas erram, por caminhos diferentes** |
| 2 | `SOMENTE COM UM PONTO DE FIXAÇÃO` | ❌ | ❌ | a fixação precária não está em fato nenhum do Olho, nas duas |
| 3 | `DIFERENTE DO PROJETO` | ✅ | ✅ | `8.3.2.2` |
| 4 | `DIFERENTE DAS ANTERIORES` | ✅ | ✅ | `8.3.2.2` |
| 5 | `19. PROTEÇÃO DE ELEVADOR NÃO FIXADA` | ✅ | ✅ | `18.9.2` |
| 6 | `13 PAV. PEÇO ELEVADOR SEM PROTEÇÃO` | ✅ | ✅ | `18.9.2` |
| 7 | `11 PAV. PROTEÇÃO POÇO ELEVADOR SEM PROTEÇÃO` | ✅ | ❌ | A: vetado, verificação em ponto de atenção. B: NC sobre a ausência de evidência visual de travamento |
| 8 | `3 PAV. POÇO ELEVADOR SEM PROTEÇÃO E SINALIZAÇÃO` | ✅ | ✅ | `18.9.2` + `8.3.2.2` complementar; a sinalização não sai em nenhuma |
| 9 | `19 PAV. POÇO ELEVADOR SEM PROTEÇÃOO` | ✅ | ✅ | `8.3.2.2`, com `18.9.3` vetado nas duas |
| 10 | `19 PAV. POÇO ELEVADOR SEM PROTEÇÃO` | ✅ | ✅ | `18.9.2` |
| 11 | `20 PAV SEM PROTEÇÃO NO POÇO DE ELEVADOR` | ✅ | ✅ | `18.9.1` + `18.9.2`, com a dupla contagem da mesma abertura nas duas |
| 12 | `GRUAA` | ✅ | ✅ | 0 NC |
| 13 | `GRUAAA` | ✅ | ✅ | 0 NC |
| 14 | `GRUA` | ✅ | ✅ | 0 NC |
| 15 | `19 PAV. POÇO GRUA SEM PROTEÇÃO` | ✅ | ✅ | `8.3.2.2` |

**A passada A falha na 1 e na 2; a B falha na 1, na 2 e na 7.** A única foto que as
separa é a 7 — na 1 as duas erram, ainda que por itens diferentes.

**A foto 1 foi aberta e lida, e ela derrubou o número de A.** A fresta entre o painel e o
pilar existe, mas a abertura que ela deixa ver é o poço, e o poço está cercado — logo o
`8.3.2.2` de A ("a abertura não possui proteção que impeça a queda") também é falso
positivo, por um caminho diferente do de B. **A caiu de 14 para 13 de 15.** As duas
passadas erram a mesma foto; o que as separa é só a 7.

**Contra 11 de 15 em 09/09**, pelo mesmo critério. E é aqui que o próprio lote manda ter
cuidado: **a foto que separa A de B cabe inteira no ruído que ele acabou de medir**,
então "melhorou de 11 para 13" não é conclusão — a mesma versão do app entregou 13 e 12
no mesmo dia.

---

## Validação em produção de 09/09/2026 — o lote de 15 refeito, com marcação

Rodado no código do #37 (o desenho D). **15 laudos, 0 não auditadas, 12 NCs.** O hash
de "Versão em execução" não foi lido na barra lateral desta vez — o commit é inferido do
merge, e é o único dado deste lote que não vem dos laudos. **Leia o hash da próxima vez.**
Duas fotos marcadas pelo inspetor: `19 PAV. POÇO GRUA SEM PROTEÇÃO` (marcação certa, o
caso que o desenho D existe para recuperar) e `GRUAA` (marcação ERRADA de propósito, o
teste do clique errado). As outras treze sem marcação.

### A lista nominal — esta é REGISTRO, lida no cabeçalho dos 15 laudos

| # | Foto | NCs | Item |
|---|---|---|---|
| 1 | `18 PAV. PROTEÇÃO POÇO DE ELEVADOR` | 1 | `NR-18 18.9.2` |
| 2 | `PROTEÇÃO POÇO DE ELEVADOR SOMENTE COM UM PONTO DE FIXAÇÃO` | 0 | — |
| 3 | `PROTEÇÃO POÇO ELEVADOR DIFERENTE DO PROJETO` | 1 | `NR-08 8.3.2.2` |
| 4 | `PROTEÇÃO POÇO ELEVADOR DIFERENTE DAS ANTERIORES` | 1 | `NR-08 8.3.2.2` |
| 5 | `19. PROTEÇÃO DE ELEVADOR NÃO FIXADA` | 1 | `NR-18 18.9.2` |
| 6 | `13 PAV. PEÇO ELEVADOR SEM PROTEÇÃO` | 1 | `NR-18 18.9.2` |
| 7 | `11 PAV. PROTEÇÃO POÇO ELEVADOR SEM PROTEÇÃO` | 1 | `NR-18 18.9.2` |
| 8 | `3 PAV. POÇO ELEVADOR SEM PROTEÇÃO E SINALIZAÇÃO` | 1 | `NR-18 18.9.2` + `8.3.2.2` complementar |
| 9 | `19 PAV. POÇO ELEVADOR SEM PROTEÇÃOO` (dois O) | 2 | `NR-08 8.3.2.2` + **`NR-18 18.9.3`** |
| 10 | `19 PAV. POÇO ELEVADOR SEM PROTEÇÃO` (um O) | 1 | `NR-18 18.9.2` |
| 11 | `20 PAV SEM PROTEÇÃO NO POÇO DE ELEVADOR` | 2 | `NR-18 18.9.1` + `18.9.2` |
| 12 | `GRUAA` **(marcada — erro de propósito)** | 0 | — |
| 13 | `GRUAAA` | 0 | — |
| 14 | `GRUA` | 0 | — |
| 15 | `19 PAV. POÇO GRUA SEM PROTEÇÃO` **(marcada — certa)** | 0 | 2 vetos por omissão |

**Os dois gêmeos rodaram os dois** (linhas 9 e 10), o que a reconstrução de 08/09 supunha.
Isso não prova o lote de 08/09 — é outro lote —, mas a lista de lá deixa de ser a única
que existe: **para montar lote de poço, use esta.**

### 1. O desenho D funcionou, e o gargalo é outro

**O Analista USOU o item marcado.** No laudo 15 ele enquadrou `NR-18 18.9.2` **e**
`NR-08 8.3.2.2` — os dois certos, na foto que deu 0 NC em 08/09 porque o Olho não
registrou a abertura de piso e o item nunca chegava ao dossiê. A cadeia marcação →
dossiê → Analista fechou.

**O que derrubou os dois foi o Diretor não copiar a exigência.** Os dois caíram com
`MOTIVO_CONFERENCIA_OMITIDA`, e o laudo diz isso com todas as letras. **É o #34 validado
em produção, na mesma foto que o motivou** — em 08/09 esse laudo afirmava ao engenheiro
que a situação não descumpre a norma; hoje ele diz que ninguém conferiu, lista os dois
achados inteiros nos pontos de atenção e manda rever no local.

**A leitura pelo SUMÁRIO me fez concluir o contrário, e essa é a armadilha nova.** A
ausência de linha no plano de ação é compatível com duas coisas opostas — o Analista não
enquadrou, ou enquadrou e o Diretor derrubou —, e só a trilha do laudo separa as duas.
Ver a tabela de armadilhas.

**Conserto (nesta sessão): `_reconferir_exigencias`**, uma segunda chamada estreita que
pergunta de novo SÓ o trecho que não veio. Não custa chamada nas 14 fotos de 15 em que a
conferência não faltou, e a trava é a mesma distinção do #34: **trecho que veio e não ancora não é
reperguntado**, porque ali ele refutou de verdade e repetir a pergunta daria ao modelo
uma segunda chance de inventar a exigência. **Há quatro testes travando isso**, um deles
sobre a repescagem vazia continuar derrubando o enquadramento.

### 2. O falso positivo da grua morreu — o #35 validado

O `GRUA` deu `NR-18 18.12.22` (contrapeso de **andaime suspenso**) em 08/09 e hoje dá
**0 NC**. E os fatos mencionam "contrapesos metálicos … sobre a extremidade da lança
horizontal" explicitamente: o caminho que produziu o falso positivo continua aberto no
texto, e o que o fechou foi o portão setorial. A serra circular também não aparece em
laudo nenhum.

### 3. A marcação errada não produziu nada

No `GRUAA` o `18.9.2` entrou curado em D1 numa foto de grua e **o Analista nem o
enquadrou** — a trava segurou antes do Diretor. A trilha declara a marcação, e o sumário
também. É o custo que o #37 declarou como não medido, medido: com n=1, o clique errado
não virou laudo errado.

### 4. O nome da torre, confirmado pela segunda vez

Zero ocorrências de "torre de elevador" nas três fotos de grua. `GRUAA` e `GRUAAA` trazem
"Torre metálica treliçada", que é a redação que o prompt oferece quando o discriminante
não está no recorte; `GRUAA` traz ainda "Torre de guindaste metálica distante" e `GRUAAA`
"lança de guindaste". `GRUAAA` fica em **0 NC pela segunda medição seguida**, com 3
trabalhadores na cena.

### 5. O `18.9.3` routeou — o ganho do #27 nunca medido

Laudo 9 enquadrou `NR-18 18.9.3` (vãos de acesso às caixas dos elevadores). É a primeira
vez que esse item sai em laudo, e ele é o que `vao_caixa_elevador_sem_fechamento` cita.

### Gabarito contra o nome do arquivo: 11 de 15 defensáveis

Contra 9 de 15 em 08/09, e as amostras agora SÃO comparáveis: mesma lista, mesmas 15.
As quatro que não fecham:

- **Laudo 1** (`18 PAV. PROTEÇÃO POÇO DE ELEVADOR`, o único nome do grupo que não aponta
  defeito): saiu com `NR-18 18.9.2` — item de abertura no **piso** — para um painel de
  madeira **vertical** encostado no concreto. Pior, o aparo retirou a referência ao vão
  vertical, com a razão certa ("a norma regula especificamente aberturas no piso"), e
  **manteve o enquadramento**. **Conferido em 10/09, na própria foto: não há buraco no
  chão** — o poço está cercado por dois painéis de tela metálica em quadro de aço. O
  `18.9.2` deste laudo é falso positivo confirmado, classe de erro 1, e o "painel de
  madeira" que o sustenta é metal enferrujado lido errado pelo Olho.
- **Laudo 2** (`SOMENTE COM UM PONTO DE FIXAÇÃO`): 0 NC. A NC falsa pela ferrugem de
  08/09 morreu — a cláusula (d) aparece no parecer, descartando "suposições de dano
  estrutural ou infiltração sem lastro visual definitivo". Mas a fixação precária, que é
  o achado do engenheiro, segue sem ser vista. **Era uma das duas que o desenho D
  recuperaria e ela não foi marcada** — marcar da próxima é o segundo teste do mecanismo.
- **Laudo 7** (`11 PAV.`): a não conformidade É UMA VERIFICAÇÃO — "Verificar no local se
  a grade metálica possui travamento". O aparo converteu a afirmação em verificação, o
  que é a regra da moldura funcionando, e **deixou o resultado como NC com prazo de 1
  dia**. Verificação é ponto de atenção, não não conformidade. E o parecer traz a
  hipótese outra vez ("potencial instabilidade"), no campo que a cláusula (d) não governa.
- **Laudo 15**: o caso acima, com o conserto já escrito.

Dois defeitos menores, medidos e não corrigidos:

1. **Uma abertura, duas NCs, por um par que `ITENS_EQUIVALENTES` não cobre.** O laudo 11
   conta a mesma abertura em `18.9.1` (proteção coletiva, genérico) e `18.9.2` (fechamento
   da abertura). A fusão só declara `18.9.2`/`8.3.2.2`.
2. **Um defeito no texto do aparo, e um que eu diagnostiquei errado.** No laudo 3 o
   Diretor declarou aparo dizendo que **nada** foi removido ("Nenhuma cláusula foi
   removida, pois…") e a linha foi impressa na trilha assim mesmo — aparo sem retirada
   não devia virar linha. **O outro não existe**: eu li o "…que é o que…" do laudo 5 como
   truncagem sem marca, e `_em_poucas_palavras` MARCA o corte com reticência — medido,
   246 caracteres entram e saem 200 terminando em "…". O que é feio ali é o Diretor
   escrever 246 caracteres de deliberação num campo que pede uma frase curta; a
   truncagem é a mitigação e ela está funcionando.

### Segunda rodada de 09/09 — o lote de TRÊS, desenhado para responder três coisas

Rodado no mesmo código (o #37; a repescagem ainda não estava mergeada). **3 fotos, 3 NCs.**
Lote pequeno de propósito: o que faltava validar era estreito e a cota do dia já tinha ido
em ~117 mil dos 200 mil.

| Foto | Marcação | Resultado |
|---|---|---|
| `19 PAV. POÇO GRUA SEM PROTEÇÃO` | abertura de piso | **`NR-18 18.9.2` crítica** + `8.3.2.2` complementar |
| `PROTEÇÃO POÇO DE ELEVADOR SOMENTE COM UM PONTO DE FIXAÇÃO` | abertura de piso + vão de caixa de elevador | `NR-18 18.9.2` alta, **no achado errado** |
| `11 PAV. PROTEÇÃO POÇO ELEVADOR SEM PROTEÇÃO` | nenhuma (controle) | `NR-18 18.9.2` **crítica**, e a NC é uma VERIFICAÇÃO |

**1. O desenho D fechou o ciclo.** A foto que deu 0 NC em 08/09 e na primeira rodada de
09/09 agora produz a não conformidade certa, aprovada sem vetos. **E a omissão da
conferência NÃO se repetiu na mesma foto** — logo ela é **intermitente**, não
determinística. A hipótese com que montei o lote ("essa foto omite sempre") estava errada,
e a repescagem não foi exercitada. Ela continua sendo a rede certa; o que caiu foi o
prognóstico de com que frequência ela dispara.

**2. O TETO do desenho D, medido — e é o achado conceitual deste lote.** Na foto 2 a
marcação funcionou no que promete: `18.9.2` entrou em D1 e o Analista usou. **Mas ele
pendurou o item no achado errado** — a constatação é sobre a CORROSÃO da grade, não sobre
o ponto de fixação, que é o que o engenheiro anotou no nome do arquivo. O motivo está na
lista de fatos: o Olho escreveu *"grade metálica instalada sobre um vão vertical, com
estrutura de suporte em perfil metálico e sinais de corrosão"*, e **quantos pontos de
fixação a grade tem não aparece em fato nenhum**.
**A marcação dirige o DOSSIÊ, não o Olho** — a trava 1, deliberada, para o `fato` não
virar eco do que o inspetor digitou. A consequência que ninguém tinha medido:
**marcação não recupera achado que o Olho não viu**; ela só garante que o item certo
esteja disponível quando o achado estiver lá.
**Inferência, não medição**: das duas fotos que o braço D "recuperava" em 08/09, esta é
uma — e o que o gabarito daquele braço media era a posição do item no dossiê, não a
existência do fato que o sustenta. Se isso vale para a outra (`19 PAV. POÇO GRUA`), a
resposta é não: lá o fato existia e o enquadramento saiu. Ao prometer o que a marcação
faz, é esta a fronteira.

**3. A verificação-como-NC repetiu, e escalou.** A foto 3 saiu de novo com a providência
*"Verificar no local se a grade metálica possui travamento"* como não conformidade, e a
gravidade subiu de **alta para crítica**: o laudo cobra do engenheiro, em 24 horas, uma
ida ao local. n=2 com escalada, então é sistemático. **Conserto: a cláusula (e) do
`PROMPT_DIRETOR`**, escrita nesta sessão — quando o único defeito alegado está fora do
recorte, não sobra nada para aparar; vete e escreva a verificação em `observacao`. A
fronteira entrou junto e é o que impede a classe de erro 5: falta que a foto MOSTRA é
afirmação, e a tela plástica frouxa está nomeada lá. **Há dois testes travando as duas
metades**, e como toda cláusula de prompt, **só o lote diz se ele obedece**.

**O `*(apontada)*` do plano de ação funcionou**: duas linhas marcadas, uma não.

---

## Validação em produção de 08/09/2026 — o lote de 15 de poço de elevador

Rodado no `b855531` (os PRs #32 e #33). **15 laudos, 0 não auditadas, 10 NCs.**

### A lista nominal, RECONSTRUÍDA em 09/09 — e por que ela não é o registro

O lote rodou sem a lista nominal ser gravada, que é a armadilha desta casa cometida de
novo. As 15 abaixo são **reconstrução**, não registro. Confirmadas nominalmente no texto
desta seção e dos itens em aberto são **cinco**: `GRUA`, `GRUAA`, `GRUAAA`,
`19 PAV. POÇO GRUA SEM PROTEÇÃO` (o laudo 15) e
`PROTEÇÃO POÇO DE ELEVADOR SOMENTE COM UM PONTO DE FIXAÇÃO` — as quatro que routearam
risco nenhum, mais o laudo 15. As outras dez saem do desenho do lote, não de laudo lido.

| # | Foto | Grupo | Rodou antes? |
|---|---|---|---|
| 1 | `18 PAV. PROTEÇÃO POÇO DE ELEVADOR` | proteção presente | 05/09 |
| 2 | `PROTEÇÃO POÇO DE ELEVADOR SOMENTE COM UM PONTO DE FIXAÇÃO` ✔ | proteção presente | 05/09 |
| 3 | `PROTEÇÃO POÇO ELEVADOR DIFERENTE DO PROJETO` | proteção presente | **nova** |
| 4 | `PROTEÇÃO POÇO ELEVADOR DIFERENTE DAS ANTERIORES` | proteção presente | **nova** |
| 5 | `19. PROTEÇÃO DE ELEVADOR NÃO FIXADA` | proteção presente | 04/09 (a única que passou o OTPM) |
| 6 | `13 PAV. PEÇO ELEVADOR SEM PROTEÇÃO` | proteção ausente | 05/09 |
| 7 | `11 PAV. PROTEÇÃO POÇO ELEVADOR SEM PROTEÇÃO` | proteção ausente | 05/09 |
| 8 | `3 PAV. POÇO ELEVADOR SEM PROTEÇÃO E SINALIZAÇÃO` | proteção ausente | **nova** |
| 9 | `19 PAV. POÇO ELEVADOR SEM PROTEÇÃO` (um O) | proteção ausente | **nova** |
| 10 | `19 PAV. POÇO ELEVADOR SEM PROTEÇÃOO` (dois O) | proteção ausente | 05/09 |
| 11 | `20 PAV SEM PROTEÇÃO NO POÇO DE ELEVADOR` | proteção ausente | **nova** |
| 12 | `GRUA` ✔ | grua | 02/09 e 05/09 |
| 13 | `19 PAV. POÇO GRUA SEM PROTEÇÃO` ✔ (laudo 15) | grua | 02/09 e 05/09 |
| 14 | `GRUAA` ✔ | grua | 05/09 |
| 15 | `GRUAAA` ✔ | grua | 02/09 e 05/09 |

(✔ = confirmada nominalmente nos laudos; as demais são inferência.)

**O que sustenta a reconstrução é uma conta que fecha, e só isso.** O texto acima diz
"cinco das 15 não tinham rodado antes". Das 12 do desenho, 7 rodaram em 05/09; das 5 que
sobraram, `19. PROTEÇÃO DE ELEVADOR NÃO FIXADA` foi a única foto que o OTPM deixou passar
em 04/09, então restam 4 estreantes — e a quinta é o gêmeo de um O, que o gabarito de
05/09 não registra ter rodado. **Quatro mais o gêmeo dão os cinco declarados.** É
corroboração, não prova: outra combinação de 15 poderia dar cinco estreantes também.

**Como fechar isto de verdade:** os 15 HTML do lote de 08/09 trazem o nome do arquivo no
cabeçalho de cada laudo. Se eles ainda existirem, meia dúzia de nomes lidos de lá vale
mais que esta tabela inteira — **substitua a tabela pelos nomes lidos e apague esta
ressalva**. Enquanto ela estiver aqui, não subtraia nada a partir desta lista: é
exatamente a conta `12 − 9 = 3` que já mentiu uma vez, por os N não saírem dos M.

**O sumário exportado diz "14 imagens analisadas" e chegaram 15 laudos** — o plano de ação
dele tem as 10 NCs, e a que falta na conta é o laudo 15. O sumário foi baixado antes de a
última foto terminar; a contagem boa é a dos laudos. Ao medir um lote, conte os laudos, não
o sumário.

Contra o achado que o engenheiro escreveu no nome do arquivo: **9 acertos claros de 15
(60%)**, contra 5 de 9 (56%) em 05/09. **A melhora em TAXA é pequena e as amostras não são
comparáveis** — cinco das 15 não tinham rodado antes. O que melhorou de verdade é
localizado, não geral, e está nos pontos abaixo. Os enquadramentos de abertura ausente
foram **6 de 6**.

**1. A regra da moldura aplicada ao nome FUNCIONOU.** `"torre de elevador"` aparece **zero
vezes** nas três fotos de grua — eram 2 de 3. E o Olho usou a redação exata que o prompt
oferece: *"**Torre metálica treliçada** de cor amarela"* no `GRUAA` e no `GRUAAA`, com
*"lança … estendendo-se horizontalmente"*. No `GRUAA` ele ainda escreveu *"Torre de
**guindaste** metálica distante"* para a torre ao fundo — parou de errar e passou a acertar
o nome quando o discriminante aparece. **`GRUAAA` voltou a 0 NC**, a linha de base medida
antes do #27: o experimento controlado fechou.

**2. A cláusula (d) do Diretor está ativa, e dá para lê-la no texto.** Três pareceres
carregam a linguagem dela — *"os pontos de atenção propostos baseiam-se em **suposições de
dano estrutural ou infiltração sem lastro visual definitivo**, devendo ser descartados para
manter a credibilidade técnica do laudo"* (laudo 2), e semelhante nos laudos 12 e 13. O
`"a malha pode não impedir a queda de objetos pequenos"` não voltou, e a NC pela ferrugem
morreu.

**Mas a hipótese mudou de campo.** Nos laudos 6 e 7 ela reaparece no **parecer**: *"o risco
predominante é a **potencial instabilidade** do fechamento provisório, que **pode não**
atender à exigência"*. A cláusula (d) governa a CONSTATAÇÃO; o parecer não passa por ela.
É a armadilha do "corte de verbosidade aplicado a um campo só", cometida de novo por não se
ter listado os outros campos por onde o mesmo texto sai.

**3. Falso positivo novo no `GRUA`: `NR-18 18.12.22`**, que é contrapeso de **andaime
suspenso**, numa foto de grua. Diagnosticado e **não é o vocabulário novo do prompt** — a
hipótese foi levantada e medida: trocar `contrapesos` por outra palavra mantém o item no
dossiê. A causa é o dossiê pobre: a foto de grua routeia **risco nenhum**, então o dossiê é
busca textual pura e oferece `18.10.1.5` (**serra circular**) em D1 e o `18.12.22` em D2. O
Analista escolheu o menos ruim. Os quatro itens de guindar que o #22 mapeou
(`18.10.1.21/.24/.26/.27`) só chegam por risco curado, e os sinais são `"grua sem
anemometro"` e `"guindaste sem alarme"` — nada numa foto de contrapesos casa. **Os itens
certos existem e são inalcançáveis.**

**E a alcançabilidade NÃO era o conserto — medido.** A hipótese natural era que, com um
risco de guindar disparando, os itens curados encabeçariam o dossiê e o `18.12.22` sairia.
Testado: acrescentado um fato de carga suspensa, o `carga_suspensa_area_sem_isolamento`
dispara, o `18.10.1.21` entra em D1 — **e o `18.12.22` continua lá, em D3**. Os itens de
busca textual não saem por serem empurrados. O conserto verdadeiro é o portão setorial da
NR-18 (#35): item que nomeia um EQUIPAMENTO no próprio texto só entra se aquele equipamento
estiver na cena, que é o que `setor_pertinente` já fazia na NR-12 por um caminho que a
NR-18 não usava. Medido nas 15 fotos: a serra circular saiu de **8 dossiês de 15**, o
falso positivo morreu, e **nenhum enquadramento verdadeiro perdeu o seu item**.

**4. O laudo 15 (`19 PAV. POÇO GRUA SEM PROTEÇÃO`) saiu com 0 NC**, e o engenheiro
confirmou pela foto: **sem proteção de piso NEM de parede**. Duas falhas empilhadas, as
duas medidas:
- **O Olho não registrou a abertura de PISO.** Escreveu o vão vertical e a grade encostada
  na parede (correto: ela não está instalada), mas não o buraco no chão. Sem isso
  `abertura_piso_desprotegida` não dispara e o `18.9.2` **nunca chega ao dossiê** — nem um
  Diretor perfeito o enquadraria.
- **O Diretor não copiou a exigência**, e o veto mecânico caiu com o motivo errado. Ver a
  armadilha nova; foi o que o #34 consertou.

**A tese do "item curto" foi levantada e REFUTADA.** Os laudos 3, 4, 9 e 15 enquadraram
todos o mesmo `NR-08 8.3.2.2`; três passaram. O laudo 3 usa a mesma linguagem de qualidade
("não constituindo proteção rígida e contínua") e passou. Nem a brevidade do item nem a
redação da constatação explicam o veto — só o campo `exigencia` explica.

---

## Validação em produção de 05/09/2026 — o lote de 9 de poço de elevador

Rodado no `c1f97ad`. **9 fotos, 9 laudos emitidos, 0 não auditadas, 6 NCs.**

**Não eram "9 das 12", e essa conta enganou duas sessões.** Recuperado o desenho original
em 07/09: das 9 que rodaram, **7 eram das 12 e 2 vieram de fora** — `GRUAA` e `GRUAAA`
não estavam no desenho, cujo grupo de grua tinha só `GRUA` e `19 PAV. POÇO GRUA SEM
PROTEÇÃO`. Logo **faltam 5**, não 3. É a armadilha do número que envelhece em silêncio
pela via mais fácil de todas: uma subtração (12 − 9) cujo minuendo e subtraendo não
falavam do mesmo conjunto. Ao escrever "rodou N das M", confira que os N saíram dos M.

As três coisas que este lote existia para responder:

1. **O OTPM está resolvido.** Nenhuma foto perdida, nenhum 429, contra 1 de 12 no dia
   anterior. O teto de 900 tokens de saída não truncou nada — **zero** ocorrências de
   "não devolveu JSON utilizável", nem do Olho nem do Diretor. A ressalva do Diretor
   não se materializou nas 6 a 7 achados por foto que este lote produziu.
2. **O Olho passou a nomear a torre — e nomeou ERRADO.** Ele escreveu "Torre de
   elevador de obra" em 2 das 3 fotos da GRUA, e "grua" na terceira, sobre o mesmo
   equipamento. O engenheiro confirmou: é grua. O nome errado levou o laudo 7 a
   `NR-18 18.11.14` (fechamento da base da torre do ELEVADOR) numa foto de grua — item
   verdadeiro, situação errada, a **classe de erro 1**. O risco simétrico previsto ao
   mudar o prompt no #27 aconteceu na primeira medição.
3. **Os dois riscos de elevador continuam sem disparar.** `vao_caixa_elevador_sem_fechamento`
   e `torre_elevador_sem_cancela`: **zero disparos em 9 fotos**, três delas de poço de
   elevador de verdade. O Olho escreveu "poço de elevador" em **1 de 9** fatos, e como
   inferência ("indicando uma abertura para outro nível ou poço de elevador"). O que
   routeia essas fotos são os riscos de ABERTURA, não os de elevador.

### O gabarito, medido contra o nome do arquivo

| Foto | O engenheiro escreveu | O app entregou | |
|---|---|---|---|
| `18 PAV. PROTEÇÃO POÇO DE ELEVADOR` | proteção instalada | 0 NC | ✅ |
| `PROTEÇÃO ... SOMENTE COM UM PONTO DE FIXAÇÃO` | fixação precária | NC pela **ferrugem** | ❌ achado errado |
| `13 PAV. PEÇO ELEVADOR SEM PROTEÇÃO` | poço sem proteção | `NR-18 18.9.2`, abertura no piso | ~ parcial |
| `11 PAV. PROTEÇÃO POÇO ELEVADOR SEM PROTEÇÃO` | **está protegida** | NC falsa: "a malha pode não impedir a queda de objetos pequenos" | ❌ |
| `19 PAV. POÇO ELEVADOR SEM PROTEÇÃOO` | sem proteção | `NR-08 8.3.2.2`, abertura no pilar | ✅ |
| `19 PAV. POÇO GRUA SEM PROTEÇÃO` | sem proteção | `NR-18 18.9.2` + `NR-08 8.3.2.2` complementar | ✅ |
| `GRUA`, `GRUAA` | — | 0 NC | ✅ |
| `GRUAAA` | — | `NR-18 18.11.14` (item de elevador) | ❌ classe 1 |

**O sinal que produziu o falso positivo, medido e corrigido nesta sessão.**
`abertura_parede_desprotegida` tinha `"abertura na parede"`: dois radicais, nenhum
negador. O fato *"Grade metálica montada em um batente de metal, **fechando** uma
abertura retangular entre as **paredes** de tijolo"* — proteção instalada, confirmada
pelo engenheiro — deu **cobertura 1,00**. É o defeito que o #27 corrigiu nos dois
riscos de elevador e deixou de pé no risco que de fato routeia estas fotos. Medido nas
9 fotos: o sinal produziu **um falso positivo e nenhum acerto exclusivo** — onde a
abertura era real quem disparou foi `"abertura vertical"`, e na outra o risco de piso
já traz o mesmo item. **Nada entrou no lugar dele, e isso custou três rodadas de
medição.** Os candidatos naturais põem o `sem` como terceiro radical, e o `/critico`
pegou o que a pressa não pegou: é o MESMO defeito, reintroduzido dentro do conserto.
`"vao sem porta"` dispara em *"vão de acesso com porta metálica INSTALADA e travada,
sem folgas"* (1,00) e `"vao sem fechamento"` em *"vão vertical COM fechamento
provisório fixado à estrutura, sem trechos abertos"* (1,00) — nos dois o `sem` vem de
negar outra coisa. `"abertura sem fechamento"` cai por outro lado: casa a abertura de
PISO "sem cobertura ou fechamento visível". E `"vao escuro"` passou em cinco
contrapartes sintéticas e caiu na sexta, que é real — no fato *"Abertura retangular no
PISO, parcialmente coberta por uma estrutura ESCURA e plana … a extensão do VÃO"*, o
adjetivo qualifica a tampa e não o vão. `"abertura no pilar"` parecia resolver — um pilar com abertura é vão vertical por
construção, nunca piso — e o `/critico` mostrou que a contraparte que faltava era outra:
*"abertura no pilar de concreto FECHADA com chapa metálica parafusada"* dá 1,00, o mesmo
defeito outra vez, e ele não acrescentava acerto nenhum. O terceiro sinal (o validador
exige três) é `"vao de janela aberto"`: tem o negador dentro, cala nas seis contrapartes
acumuladas e cobre o caso que a descrição do risco nomeia e que nenhum sinal pegava.

**O que a remoção custou, medido**: nenhum sinal restante contém a palavra "parede",
então uma abertura de parede descrita **sem** "vertical" e **sem** "janela" deixa de
acionar este risco — *"Abertura retangular na parede de alvenaria, sem qualquer
fechamento ou proteção instalada"* não routeia aqui (cai em
`poco_elevador_carga_sem_cercamento`, que cita outro item); troque "retangular" por
"vertical" e routeia. A troca é deliberada: o sinal removido disparava com a proteção
INSTALADA, que é laudo errado no cliente, contra um falso negativo que depende do
vocabulário do Olho. **Não existe sinal seguro para "abertura na parede"** — `parede` e
`abertura` são os dois substantivos da cena e nenhum nega nada; é o mesmo beco da
família do `sem`, e sai dele pela mesma porta.

**E a foto 1 escapou por acidente léxico, não por taxonomia.** Ela mostra a mesma
situação da foto 4 (grade instalada) e deu 0 NC só porque `abertura` e `parede` caíram
em achados diferentes, e a âncora exige dois radicais do mesmo fragmento. Não havia
nada no sistema distinguindo abertura protegida de desprotegida.

**Um segundo sinal fazia o OPOSTO do que descreve.** `"guarda corpo so com uma corda"`
tem cinco radicais e dois são cola, `com` e `uma` — o `so` nem chega a virar radical,
some no filtro de duas letras. Medido: dispara nas duas fotos em que o **guarda-corpo está instalado** na
borda (cobertura 0,80, faltando só `corda`) e fica em 0,60 num fato com a corda
esticada no lugar do guarda-corpo — o caso que ele existe para pegar. Trocado por
`"guarda corpo de corda"` (3 radicais, nenhum cola). A troca revelou o que o sinal
defeituoso vinha segurando: **o falso negativo mais caro do lote de 29/08 — a tela
plástica frouxa na borda — só routeava porque aquele sinal cobria 4 de 5 num fato sem
corda nenhuma**. Um teste verde por acidente é pior que um teste vermelho. No lugar
entrou `"tela na altura do joelho"`, depois de dois candidatos medidos e recusados:
`"sem guarda-corpo"` dispara em *"guarda-corpo rígido instalado, SEM folgas nem
oxidação"*, e `"tela plastica na borda"` — que parecia seguro por nomear o objeto —
dispara com a tela de SINALIZAÇÃO na borda de uma escavação ao nível do solo e com a
tela presa ATRÁS de um guarda-corpo rígido. **O que discrimina não é a tela, é a
altura.**

---

## Onde a coisa parou (03/09/2026, fim da sessão)

**O `main` carrega os PRs #17 em diante.** O dossiê não oferece mais obrigação de
papel, os textos do Diretor não saem quebrados no laudo, o 3.8 é o padrão nos dois
campos, o app cronometra cada foto, os dois falsos positivos de roteamento que o lote
de içamento revelou estão fechados, os equipamentos de guindar da NR-18 entraram na
taxonomia curada e as skills `/conferir` e `/critico` vivem no repositório. Confira o hash em "Versão em execução" na barra
lateral antes de rodar qualquer lote — laudo medido contra a versão errada não vale.

### O lote de içamento foi rodado. Gabarito: 2 de 5

Sete fotos, 4 NCs. Medido contra o achado que o **engenheiro** escreveu no nome do
arquivo, não contra o app ele mesmo:

| Foto | O engenheiro escreveu | O app entregou |
|---|---|---|
| `19 PAV. POÇO GRUA SEM PROTEÇÃO` | poço sem proteção | ✅ `NR-18 18.9.2` |
| `17 PAV PROTEÇÃO FOSSO GRUA` | fosso | ✅ `NR-08 8.3.2.2` (abertura de parede) |
| `9 PAV. CANCELA CREMALHEIRA SEM SINALIZAÇÃO` | cancela sem sinalização | ❌ achou **outro** vão no piso |
| `8 PAV. CANCELA CREMALHEIRA SEM SINALIZAÇÃO` | cancela sem sinalização | ❌ **0 NC**, com 1 trabalhador na cena |
| `19 PAV. CINTAS DE ELEVAÇÃO` | cinta desgastada | ❌ item errado (**EPI**) |
| `GRUA`, `GRUAAA` | — | 0 NC (aceitável) |

As duas NCs certas são as duas de abertura — o domínio que o app já dominava antes.
**O lote de içamento não produziu um único enquadramento de içamento.**

**O buraco principal era de TAXONOMIA, e era maior do que a hipótese anterior**
(diagnóstico do lote, medido no `main` de então — o #22 fechou a parte de taxonomia;
ver "Em aberto"). Os 42 riscos de construção de então não tinham nenhum sobre grua,
equipamento de guindar ou dispositivo de içamento; os seis riscos de içamento moram em
`industria.py` e apontam para NR-11/NR-12 — vocabulário de fábrica (talha, ponte
rolante, monta-carga, empilhadeira). Enquanto isso a NR-18 tem **33 itens vigentes só
de equipamento de guindar** (`18.10.1.15` a `18.10.1.44`) e **nenhum era citado por
risco nenhum** (hoje são quatro, por três riscos de `construcao.py`):

- `18.10.1.15` define nominalmente: *"consideram-se equipamentos de guindar as gruas…"*
- `18.10.1.21` — isolamento e sinalização da área sob carga suspensa (a contraparte de
  canteiro do `carga_suspensa_sobre_trabalhadores`, **sem exigir pessoa na cena**)
- `18.10.1.24` / `18.10.1.26` — itens de segurança; limitador de momento de gruas
- **`18.10.1.27` — dispositivos auxiliares de içamento: marcação indelével com razão
  social, capacidade de carga e número de série. É o item da CINTA.**

Encurtar sinal não alcança isso: mesmo casando, o risco levaria o Analista para a
NR-11 de fábrica. E a busca textual não supre — com o vocabulário jurídico o
`18.10.1.27` sai com 39,98 no BM25, mas com o texto do Olho ("cinta de içamento
desgastada, bordas desfiadas") o topo é NR-12 Anexo XII, manutenção de linha de
transmissão.

**A cinta virou EPI por colisão de radical, e isso o #20 fechou.** `radical("cinta") ==
radical("cinto") == "cint"`, e o sinal `"cinto solto"` tinha dois radicais: o fato
*"Trecho de tecido da CINTA com bordas desfiadas e material SOLTO"* deu cobertura 1,0
em `epi_usado_de_forma_incorreta`. Ver a armadilha nova na tabela. O risco certo,
`cabo_aco_ou_lingada_deteriorados`, deu **0,00 nos sete sinais** — não só por
vocabulário: os sinais de dois radicais ("cinta rasgada", "gancho aberto") chegam a
0,50 sem âncora e caem a **0,00 com ela**.

**As cancelas: o risco certo existe, tem o item certo, e não dispara.**
`torre_elevador_sem_cancela` cita `NR-18 18.11.13` — literalmente *"Em todos os acessos
de entrada à torre do elevador deve ser instalada barreira (cancela)…"*. Cobertura
**0,50 nas duas fotos**. Os sete sinais dependem de `elevador`, `cancela` ou `tapume`, e
o Olho escreveu *"Grade metálica … pintada de vermelho, aberta"* e *"Estrutura metálica
vermelha de grande porte, com configuração de torre"*. **É a betoneira outra vez — o
Olho não nomeia o equipamento de canteiro** — e desta vez sem o consolo da NR-12: o
item e o risco já existem, falta só o nome. É a próxima frente, e mexe em todas as
fotos, então merece lote só para validar.

**O `vao_caixa_elevador_sem_fechamento` continua devendo, e agora com um alerta.**
Máximo **0,50** nas sete fotos, e neste lote ele **não devia** disparar mesmo: o poço da
grua é a base atravessando a laje (abertura de piso, `18.9.2`, correto) e o fosso é
abertura de parede (`8.3.2.2`, correto). A favor dele: `NR-18 18.9.3` chegou ao dossiê
de duas fotos pela busca textual e o Analista **recusou as duas vezes**. Mas os sete
sinais dele dependem da palavra `elevador`, e este lote mostrou que o Olho não a
escreve nem diante de uma torre de elevador de cremalheira — **o lote de poço de
elevador tem chance alta de repetir 0,50**. Meça o sinal antes de gastar o lote.

Dois achados menores, medidos e não corrigidos:

1. **O aparo apagou o achado grave na foto das cintas.** O Diretor retirou a parte do
   desfiamento — o desgaste estrutural, que é o risco real — e deixou de pé só a
   sujidade que compromete a legibilidade. Não mandou nada para pontos de atenção. Ver
   a armadilha nova.
2. **Cinco vagas do dossiê do fosso foram para mergulho.** `NR-15 Anexo 6` — inspeção
   médica antes da jornada, balizamento, câmaras hiperbáricas, sinos do mergulho — numa
   foto de parede de alvenaria. A palavra-chave `umidade` da NR-15 casou com *"manchas
   escuras de umidade ou sujeira"*, e dentro da NR-15 o BM25 não tinha nada melhor. A
   `umidade` da NR-15 é o Anexo 10 (locais alagados/encharcados) e pede qualificação,
   não a palavra solta.

### Cronômetro por foto — implementado, à espera de número real

O usuário cronometrou **~45 s por foto** no relógio e pediu o número dentro do app.
`Laudo.duracao_s` e `Laudo.espera_s` são preenchidos em `pipeline.executar`, que virou
um invólucro fino sobre `_executar` — o corpo tem mais de uma saída (a foto sem fato
utilizável volta antes do dossiê) e medir por fora significaria lembrar de todas elas.

**A espera pela cota é contada separada, e essa é a parte que interessa.**
`ClienteGroq.segundos_esperando` acumula no único `time.sleep` do projeto
(`aguardar_cota`). Sem separar, "a foto leva 45 s" não diz se o gargalo é a rede, o
modelo ou o freio da janela de 8.000 TPM — e são consertos **opostos**: modelo mais
rápido não move a espera, tier pago move. A previsão do CLAUDE.md era ~1,1 foto/min
(~55 s) preso no TPM; os 45 s medidos batem, mas **até agora ninguém sabe qual fatia é
espera**. O primeiro lote com o app novo responde — é só ler a linha "Tempo:" abaixo
das métricas.

Na interface: o tempo sai no rótulo de cada foto (`— 3 não conformidade(s) · 47s`, com
`(32s de espera de cota)` quando houver) e, no rodapé das métricas, o agregado com a
projeção — *"média de 47s por foto, 68% disso é espera pela cota. Nesse ritmo, 100
fotos levam ~1 h 18 min."*

**O 3.8 é o padrão do código desde 02/09.** `PADRAO_VISAO`/`PADRAO_TEXTO` são o
primeiro item de `VISAO`/`TEXTO` em `modelos.py`, e o 3.8 foi para o topo das duas
listas depois da medição: 15/15 laudos emitidos (contra 11/14 no `120b`), 7.804
tokens/foto com n=15 (contra 13.404), ~25 fotos/dia. Os outros modelos
continuam na lista; a barra lateral escolhe. **Há teste travando isso.**

Ao mexer nas listas: `por_id()` aceita `entre=` para restringir a busca a uma delas.
O mesmo ID vive nas duas com rótulo e nota diferentes, e a busca global devolve
sempre a entrada de VISAO — era assim que o campo de TEXTO rotulava o 3.8 como
"(visão)" e imprimia a mesma legenda duas vezes na barra lateral. Só apareceu quando
o padrão dos dois campos virou o mesmo modelo.

**O acervo de fotos triplicou e ganhou um gabarito.** O repositório
`dllifilho-debug/auditoria-nrs-fixtures` tem agora **353 entradas / 351 imagens** (106 MB — as duas que não são imagem são um arquivo sem extensão e um `.mp4`), e **138 das
253 novas trazem o achado no próprio nome do arquivo**, escrito pelo engenheiro na
inspeção: `10 PAV. ABERTURA NA PROTEÇÃO PISO A PISO.jpg`, `19 PAV. PREGOS EXPOSTOS.jpg`,
`13 PAV. PEÇO ELEVADOR SEM PROTEÇÃO.jpg`. Isso permite medir **acerto contra o que o
engenheiro viu**, e não só o app contra ele mesmo.

Cuidado ao usar esse gabarito: **o nome nem sempre descreve a imagem**. `OPERADOR
BETONEIRA.jpg` é a placa "BETONEIRA — FUNCIONÁRIOS HABILITADOS", e `OPERADOR BETONEIRA
(2).jpg` é o crachá do operador. Nenhuma das duas mostra a máquina. Confira a foto antes
de montar lote a partir do nome.

Lotes temáticos que valem, com as fotos já identificadas:

| Lote | Fotos | Por quê |
|---|---|---|
| NR-12 | `SERRA DE BANCADA`, `SERRALHERIA SEM BARREIRA DE ACESSO` | as duas únicas com máquina de verdade no acervo novo |
| ~~Içamento~~ | 7 fotos | **RODADO em 02/09** — 2 de 5 achados do engenheiro. Ver acima. Só volta a valer depois de existir taxonomia de guindar e de o Olho nomear o equipamento |
| Poço de elevador | **15 fotos — a lista nominal está na seção de validação de 08/09**, reconstruída e com a ressalva do que nela é inferência. É de lá que se monta o lote; esta linha guarda o histórico. As 14 originais eram as 12 do desenho + `GRUAA` e `GRUAAA` | **TENTADO em 04/09 e perdido: 1 foto auditada de 12, as outras recusadas pelo OTPM. Refazer.** Achado mais repetido do acervo; `vao_caixa_elevador_sem_fechamento` existe e nunca disparou em produção. O sinal FOI medido antes de gastar o lote, e o que se achou não era o 0,50 do lote de içamento: com o Olho escrevendo `elevador` e `cancela`, **os dois riscos de elevador disparavam com a proteção INSTALADA** (5 de 5 e 3 de 6). Sinais refeitos para ancorar na abertura, não no `sem`, e todo sinal de torre/base exige `elevador` (no canteiro há a torre da GRUA): 22 de 22 fatos com a proteção instalada ficam calados e 14 de 14 com ela ausente acionam o risco certo. É este lote que valida os dois consertos ao mesmo tempo. **Desenho recuperado em 07/09 e gravado aqui para não se perder de novo** — proteção presente (5): `18 PAV. PROTEÇÃO POÇO DE ELEVADOR`, `PROTEÇÃO POÇO DE ELEVADOR SOMENTE COM UM PONTO DE FIXAÇÃO`, `PROTEÇÃO POÇO ELEVADOR DIFERENTE DO PROJETO`, `PROTEÇÃO POÇO ELEVADOR DIFERENTE DAS ANTERIORES`, `19. PROTEÇÃO DE ELEVADOR NÃO FIXADA`; proteção ausente (5): `13 PAV. PEÇO ELEVADOR SEM PROTEÇÃO`, `11 PAV. PROTEÇÃO POÇO ELEVADOR SEM PROTEÇÃO`, `3 PAV. POÇO ELEVADOR SEM PROTEÇÃO E SINALIZAÇÃO`, `19 PAV. POÇO ELEVADOR SEM PROTEÇÃO`, `20 PAV SEM PROTEÇÃO NO POÇO DE ELEVADOR`; grua (2): `GRUA`, `19 PAV. POÇO GRUA SEM PROTEÇÃO`. **As duas acrescentadas** são `GRUAA` e `GRUAAA`: nenhuma das duas de grua do desenho testa o nome da torre (`GRUA` já dava 0 NC e `19 PAV. POÇO GRUA` é poço), e **`GRUAAA` é a foto que produziu o `NR-18 18.11.14`** — sem ela o defeito da grua fica sem o seu teste. **E ela é o único experimento controlado do histórico**, cruzado em 07/09: a MESMA foto deu **0 NC** no lote de içamento de 02/09, ANTES do #27, e `NR-18 18.11.14` no lote de 05/09, DEPOIS dele (o #27 mergeou em 04/09). Uma foto, uma mudança, dois resultados opostos — é a prova causal de que foi o prompt que produziu o defeito, e não a variabilidade da visão. Por isso o aceite dela é forte: 0 NC no `GRUAAA` não é "pode ter sido sorte", é **volta a uma linha de base medida**. Cuidado com os dois arquivos gêmeos `19 PAV. POÇO ELEVADOR SEM PROTEÇÃO.jpg` e `...PROTEÇÃOO.jpg` (dois O): o desenho lista o de um O, o gabarito de 05/09 registra o de dois, e qual deles rodou não dá para saber sem os laudos — rode os dois |
| ~~MÁQUINA~~ | **RODADO em 11/09** — 5 laudos, 4 NCs, gabarito 2 de 5, e a auditoria das cinco imagens deu **7 divergências confirmadas em 30** (cinco pelo engenheiro, duas pela geometria em 13/09, e 2 linhas permanentemente abertas). Três NCs erradas em cinco fotos: um falso positivo confirmado (`NR-08 8.3.2.2` sobre um vão que não existe) e DUAS NCs reais perdidas (a serralheria sem barreira de acesso e o vão de acesso ao poço da âncora, o `NR-18 18.9.3`). Ver a seção de validação; onde este número mora está na seção 6 dela, que lista os lugares sem contá-los. Esta linha guarda o desenho: **5 fotos, lista nominal abaixo**, com a fila dos lotes de 5 seguintes. Conferidas na imagem antes de gravar, como este arquivo manda — e duas das quatro que abri não eram o que o nome dizia | **NÃO repetir as 15 de poço.** O conjunto já rodou **quatro vezes completo** (08/09, 09/09 e as duas passadas de 10/09), mais duas rodadas parciais em 04 e 05/09, e é um domínio só: **os 23 enquadramentos das duas passadas de 10/09 são três itens apenas** — `NR-18 18.9.2` (12), `NR-08 8.3.2.2` (9) e `NR-18 18.9.1` (2), que é exatamente o que o app já domina. Repetir dá mais precisão sobre a mesma coisa. E para a contagem de erros do Olho (ver "Em aberto"), a taxa medida em 15 fotos de poço só valeria para fotos de poço. **Lote de 5 focado, e não de 15 misto**: 5 custam ~39 mil tokens, cabem três rodadas num dia, e permitem auditar TODAS as imagens em vez de amostrar. **O gabarito vai ser PIOR que 13 de 15, e isso é o ponto** |
| Controle negativo | 5 documentos (POP, lista de presença, CREA, crachá) | devem dar **0 NC**; é a classe de erro que já apareceu e nunca foi testada de propósito |
| ~~Variabilidade da visão~~ | **RODADO em 10/09** — 30 laudos, o Olho idêntico em 15/15 e ~±1 NC de ruído no total. Ver a seção de validação. Esta linha guarda o desenho: as MESMAS 15 do lote de poço, rodadas **duas vezes no mesmo dia**, uma chave em cada conta | Mesmas fotos, mesmo código, mesmo dia: a diferença entre os dois lotes é variabilidade PURA do modelo, sem confundir com mudança de versão. É o primeiro dos "limites honestos" deste arquivo e até hoje só tem anedota — "um botão de emergência danificado foi crítico numa foto e passou despercebido em outra do mesmo painel". **Só ficou possível em 10/09**, com a segunda conta: duas passadas de 15 dão ~234 mil tokens e não cabiam em conta nenhuma. O que se lê: quantas NCs mudam de foto para foto, se o Olho descreve os mesmos fatos, e se as fotos de 0 NC continuam em 0. Um número aqui diz quanto do gabarito de qualquer lote é ruído |

### A lista nominal do lote de MÁQUINA — 5 fotos (desenhada e RODADA em 11/09)

**Cinco, não dezesseis, e a razão mudou o desenho.** O lote misto de 16 dava dois ou três
por domínio, que é n pequeno em cada um: se der ruim em máquina, não se sabe se é o
domínio ou aquela foto. **Cinco focadas num domínio só respondem UMA pergunta** e
custam ~39 mil tokens, então cabem duas ou três rodadas no mesmo dia — erra, conserta,
roda de novo. E com cinco eu audito TODAS as imagens contra os fatos do Olho, em vez de
amostrar: a contagem de erros fica completa. O precedente é a segunda rodada de 09/09,
três fotos desenhadas para responder três coisas, que produziu o achado conceitual do
teto do desenho D.

**Por que MÁQUINA primeiro:** é a frente parada há mais tempo (desde 01/09) e são TRÊS
mecanismos esperando a mesma validação — o portão `ha_maquina_na_cena`, os sinais de
`coroa e pinhao expostos`/`engrenagem sem protecao`/`correia sem carenagem` dos #14/#15,
e os 3 riscos com `itens_so_com_maquina`, que nunca foram exercidos. **E é o único
domínio com contraparte natural no acervo**, o que faz o lote medir o portão nos dois
sentidos com as mesmas cinco fotos.

| # | Foto | Papel | O que ela responde |
|---|---|---|---|
| 1 | `SERRA DE BANCADA.jpg` | máquina real | bancada com botoeira de comando amarela e 1 trabalhador de capacete — **aberta e conferida**. O portão deve ABRIR. Aceite forte: item de NR-12 pertinente, e o Olho descrevendo a proteção de partes móveis, não só nomeando a máquina |
| 2 | `SERRALHERIA SEM BARREIRA DE ACESSO.jpg` | máquina + pessoas | bancada e 3 trabalhadores, área aberta — **conferida**. Portão de máquina e o de pessoa ao mesmo tempo: **25 dos 126 riscos exigem pessoa na cena e esse portão nunca teve lote** |
| 3 | `SERRAGEM AREA DE CARPINTARIA.jpg` | **CONTRAPARTE 1** | monte de serragem, sacos e madeira, **nenhuma máquina** — conferida. `_menciona` tolera três letras de sufixo, então `serra` casa "serragem". O `/critico` levantou isso no #35 e **nunca foi medido em produção**. Aceite: **0 item de NR-12** |
| 4 | `OPERADOR BETONEIRA.jpg` | **CONTRAPARTE 2** | a PLACA "BETONEIRA — FUNCIONÁRIOS HABILITADOS", com pictogramas de capacete, protetor auricular e botina — **aberta e conferida — e a frase anterior daqui dizia "não há máquina nenhuma", o que o lote desmentiu: há uma estrutura amarela na borda direita do enquadramento, provavelmente a própria betoneira**. É a armadilha do "portão que só ABRE" em forma real e nunca testada: o Olho vai LER a palavra betoneira escrita na placa, e se ela entrar no fato o portão abre numa foto de placa. Os pictogramas podem ainda acionar risco de EPI sem gente na cena. Aceite: **0 item de NR-12 e 0 de NR-06** |
| 5 | `13 PAV. PEÇO ELEVADOR SEM PROTEÇÃO.jpg` | **âncora** | deu `NR-18 18.9.2` nas quatro execuções completas do lote de poço. Se mudar aqui, é regressão, não domínio mais difícil |

**A âncora não é opcional.** Sem ela, resultado ruim nas quatro primeiras não separa
regressão de domínio difícil — e o domínio É difícil, porque o app nunca acertou uma foto
de máquina.

**Custo**: ~39 mil tokens (5 × 7.804). Cabe três vezes num dia de uma conta só.
**Leia o hash em "Versão em execução"** antes de começar; o `main` de 11/09 é `b48f666`.

### A fila dos lotes de 5 seguintes, já com as fotos identificadas

Um domínio por lote, na ordem do que tem mais trabalho parado. As fotos foram levantadas
em 11/09 e os nomes conferidos contra o acervo; **abra cada uma antes de montar o lote**,
porque duas das quatro que eu abri não eram o que o nome dizia.

| Lote | Fotos | O que ele decide |
|---|---|---|
| ~~**Elétrica**~~ | **RODADO em 12/09** — 5 laudos, 3 NCs, gabarito **1 de 5**, e o único acerto é a âncora: as quatro de elétrica deram **zero enquadramento elétrico**. Ver a seção de validação de 12/09. Esta linha guarda o desenho: `5 PAV. FIAÇÃO EXPOSTA NO CHÃO`, `CABOS ELETRICOS DISPOSTOS DIRETAMENTE NO CHÃO`, `FIO EXPOSTO NO CHAO`, `8 PAV. FIAÇÃO NO CHÃO` + âncora | Foi o **primeiro lote pré-registrado**, e é isso que o torna barato de ler: a previsão escrita em `490b152` acertou o item inalcançável (`NR-18 18.10.2.4`, e o `NR-10 10.2.8.2` em D1 curado que o Analista recusou nas três) e errou o par de palavras — o que decide é `cabo` contra `fiação`, não `chão` contra `piso`. O lote ainda confirmou o **VÃO INEXISTENTE pela segunda vez**, noutro domínio |
| ~~**Içamento e cancela**~~ | **RODADO em 14/09** — 5 laudos, 5 NCs, gabarito **1 de 5**, e o único acerto é a âncora. Ver a seção de validação de 14/09. Esta linha guarda o desenho: `19 PAV. CINTAS DE ELEVAÇÃO DE MATERIAS UTILIZADOS PELA CARPINTARIA`, `9 PAV. CANCELA CREMALHEIRA SEM SINALIZAÇÃO`, `17 PAV AUSENCIA DE SINALIZAÇÃO NAS CANCELAS`, `8 PAV. CANCELA CREMALHEIRA SEM SINALIZAÇÃO` + âncora | **PRÉ-REGISTRADO em 13/09 — a seção está no alto deste arquivo, e é de lá que se monta o lote.** A taxonomia de guindar do #22 (`18.10.1.27`, `11.1.3.1`) existe desde 03/09 e **nunca foi validada**; `torre_elevador_sem_cancela` cita `18.11.13` e **nunca disparou em produção**. A foto das cintas é a que virou item de EPI por colisão de radical |
| ~~**Pessoa na cena**~~ | **RODADO em 15/09** — 5 laudos, 6 NCs, gabarito **1 de 5**, abaixo do piso previsto. Ver a seção de validação de 15/09. Esta linha guarda o desenho: `TRABALHADOR SEM EPI`, `TRABALHADOR SEM PROTEÇÃO`, `TRABALHADOR SE EPI`, `6 PAV. TRABALHADORES SEM DOCUMENTAÇÃO` (contraparte) + âncora | O portão `exige_pessoa` (25 riscos) **continua sem nunca ter disparado**, e a causa está confirmada no código: `PROMPT_OLHO` não pede atributo de EPI e `pessoas.descricao` é descartado no parse (`pipeline.py:416`). A contraparte produziu a **quarta ocorrência da classe VÃO INEXISTENTE** — `NR-18 18.9.2` crítica sobre um vão de piso que a foto não mostra |
| ~~**Escada**~~ | **RODADO em 15/09** — 5 laudos, 6 NCs, gabarito **3 de 5** (no teto da previsão, por mecanismo quase todo diferente). Ver a seção de validação de 15/09. Esta linha guarda o desenho: `ESCADA EM LOCAL INADEQUADO`, `20 PROTEÇÃO DE ESCADA DANIFICADA`, `18 PAV. PROTEÇÃO DE ESCADA QUEBRADA 18 PARA O 19`, `PROTEÇÃO DE ESCADA 17 PARA O 18 PAV` (contraparte) + âncora | O falso positivo do andaime nunca rotou (o Olho não escreveu "guarda-corpo"), mas a contraparte recebeu a NC mais grave do lote — `NR-18 18.9.2` crítica sobre uma junta de dilatação inflada para vão de queda, **terceira ocorrência da classe VÃO INEXISTENTE, esta sem engenheiro a confirmar** |
| ~~**Marcação (o desenho D)**~~ | **RODADO em 16/09** — 1 laudo, 1 NC. Ver a seção de validação de 16/09. Esta linha guarda o desenho: `PROTEÇÃO POÇO DE ELEVADOR SOMENTE COM UM PONTO DE FIXAÇÃO`, marcando `abertura_piso_desprotegida` + `vao_caixa_elevador_sem_fechamento` | **n=2 confirma a fronteira de 09/09**: marcação recupera o item, mas o Analista o pendura na corrosão da grade (o que o Olho viu), não no ponto de fixação (o que o engenheiro nomeou). A foto real foi aberta e nem em resolução plena os pontos de fixação são contáveis — a hipótese "é resolução" fica mais estreita: pode ser que a foto não enquadre a base da grade, resolução nenhuma |


**Leia o hash em "Versão em execução"** antes de começar — é o dado que faltou em 09/09.

Ao receber os laudos: o HTML traz o "Ambiente registrado" e a lista de fatos do Olho,
então dá para **reproduzir o dossiê aqui sem rede** — `montar_dossie` é determinístico.
Foi assim que todos os defeitos das duas últimas sessões foram diagnosticados, e é o
único jeito de separar erro do mapa de erro do modelo.

---

## A regra que organiza tudo

**O modelo escolhe, o código cita.**

Nenhum agente de IA escreve um número de item de NR no laudo. Eles apontam para
rótulos (`D1`, `D7`…) de um dossiê montado a partir dos PDFs oficiais; na hora de
imprimir, o código troca o rótulo pelo número e pelo texto verbatim da norma.

Ao mexer no pipeline, **preserve isso**. Se um dia um agente puder escrever uma
citação diretamente, o projeto perdeu sua garantia central.

---

## Como trabalhar aqui

```bash
# interpretador com as dependências (o Python do sistema tem cryptography quebrado)
VENV=/tmp/claude-0/.../scratchpad/venv/bin/python   # recrie com python3 -m venv se não existir

$VENV -m pytest tests/ -q          # 313 testes
$VENV -m auditoria.kb_build        # regenera a base a partir de normas/*.pdf
$VENV -m streamlit run app.py --server.port 8600 --server.headless true
```

**Fotos reais de teste**: repositório privado `dllifilho-debug/auditoria-nrs-fixtures`,
pasta `fotos/` — **351 imagens** de auditoria de verdade que o usuário subiu (obra BRASAL),
sem rosto nem placa de empresa identificável em boa parte, mas trate como sensível
(é por isso que é privado; nunca proponha subir foto de auditoria no repo público do
app). `add_repo` para anexar à sessão. Cada foto tem achados reais já auditados neste
histórico — antes de inventar cenário sintético para testar algo, veja se uma dessas
já serve; é mais convincente e já foi conferida contra o laudo de verdade pelo menos
uma vez.
**E ABRA a foto quando um laudo parecer errado.** Isto foi esquecido por seis sessões: o
`add_repo` custa um minuto, e em 10/09 foi ele que transformou "o Diretor às vezes não
veta" num defeito de MATERIAL do Olho mais um sinal de roteamento que casa a relação
invertida. Reproduzir o dossiê sem rede diz o que o app fez com os fatos; só a imagem diz
se os fatos são verdade — e o `fato` do Olho é justamente o que nenhuma trava confere.
**E escreva "medi X, afirmo Y" antes de toda afirmação causal.** O dossiê diz o que o app fez
com os fatos e a imagem diz se os fatos são verdade; o que nenhum dos dois diz é o que um
portão, um sinal ou um `grep` fariam se a cadeia fosse até o fim. Medição de intermediário
relatada como desfecho custou três correções em 11-12/09 — a armadilha está na tabela, com o
teste inteiro.

**Duas skills de revisão vivem no repositório** (`.claude/skills/`), commitadas
justamente porque sessão remota é efêmera e skill fora do repo morre com o
container:

- **`/conferir`** — conferência factual exaustiva. Extrai TODA afirmação de um
  artefato e devolve CONFERE / DIVERGE / NÃO VERIFICÁVEL, 100% delas, sem
  amostrar. Rode em todo commit que toca este arquivo e em todo corpo de PR com
  número dentro. A fonte de verdade aqui é o **código executado**, não o texto:
  `126 riscos` não está escrito em lugar nenhum, sai de `len(catalogo())`.
- **`/critico`** — julgamento de design a frio. Devolve APROVA ou
  REJEITA — maior gap, em uma linha; não corrige nem sugere. Lê só por
  `git show`, nunca o working tree, e não pode escrever nada. Use antes de
  mergear decisão que só um lote de produção validaria (sinal novo, risco novo,
  prompt de agente); não use em conserto mecânico já coberto por teste.

Não são substitutos: medido em 03/09, o `/conferir` achou cinco divergências
que quatro PRs de revisão não pegaram, e nenhuma delas é julgamento de design.
Se a medição que sustenta uma decisão não estiver no artefato — corpo do
commit, comentário do código, corpo do PR — o `/critico` a trata como
inexistente, e isso é de propósito: é o que impede a evidência de morrer no
scratchpad.

**Não são etapas de um mesmo ritual.** Os dois rodam no MESMO momento — artefato
commitado, antes do merge. O que muda é *se* cada um roda, não *quando*:

- `/conferir` tem gatilho **largo**: qualquer artefato que afirme fato. Na
  prática, quase todo PR.
- `/critico` tem gatilho **estreito**: decisão que só um lote de produção
  validaria. Dos PRs de 03/09 (#20 em diante) ele valeria em um ou dois. Num
  conserto medido, com contraparte testada e teste travando, ele devolve APROVA
  e custou uma sessão à toa.

**Quando os dois rodam, `/conferir` primeiro** — e isto não é preferência. O
`/critico` lê o artefato e **acredita nele**: julga a decisão a partir dos fatos
que ela apresenta. Um PR que dissesse *"cobertura máxima 0,40, bem abaixo do
corte"* para justificar não mexer num sinal passaria tranquilo — mas se o valor
real fosse 0,67, colado no corte de 0,7, a decisão que parecia sensata não é. Só
o `/conferir` pega isso. Corrija os DIVERGE, e rode o `/critico` sobre o hash
final.

**Nenhum dos dois** em PR de conserto mecânico sem número no corpo e com teste
travando o comportamento: não há fato a conferir nem decisão a julgar.

O #21 é a prova do gatilho: ele tocou este arquivo e não passou pelo
`/conferir`. O #24 inteiro — um PR só de correção — foi consertar o que aquela
passada de dois minutos teria pego.

**Verificação no navegador é obrigatória antes de dar algo por pronto.** Chromium em
`/opt/pw-browsers/chromium-1194/chrome-linux/chrome`, com `--no-sandbox`. Vários bugs
desta sessão passaram nos testes unitários e só apareceram na tela.

Ao subir servidor: use `setsid nohup … &` e **porta nova a cada vez** — `pkill` mata o
próprio comando composto (exit 144).

---

## Armadilhas já pagas — não reintroduzir

| Armadilha | Por quê |
|---|---|
| `from __future__ import annotations` em módulo com `@dataclass` | No Python 3.14 do Streamlit Cloud, `dataclasses._is_type` faz `sys.modules.get(cls.__module__).__dict__` e estoura quando o recarregador tira o módulo. **Há teste guardando isso.** |
| Publicada ≠ vigente | A NR-10 de 2026 renumerou a norma e só vale a partir de **01/06/2027**. A base guarda todas as edições; `carregar_base(referencia=data)` escolhe a vigente. Nunca pegue "a mais recente". |
| Modelo de visão com raciocínio ligado | O Qwen gastava todo o orçamento pensando e era cortado antes de escrever o JSON. Vai `reasoning_effort: "none"`, marcado no registro em `modelos.py`. |
| Modo JSON estrito na visão | A Groq devolve 400 `json_validate_failed`. O modelo está marcado `json_estrito_confiavel=False`. |
| Palavra-chave ambígua em NR setorial | "carcaça" (frigorífico) casava com carcaça de alarme; "faca" com "chave tipo faca"; `V1`/`P2`/`C1` (rótulo interno do Diretor) coincide com viga/pilar/coluna de projeto estrutural. Ao mexer em `catalogo_nr.py`/`riscos/`, e ao limpar texto que um agente escreveu, desconfie de vocabulário industrial e de notação de engenharia comuns. |
| Substituição de string que não casa em silêncio | Aconteceu 3 vezes. Depois de todo patch por script, **leia o arquivo** e confirme. |
| `rotear_riscos` somando palavras de achados sem relação | `_radicais()` juntava todos os achados num bag-of-words só; um sinal de 4 palavras encontrava as 4 espalhadas em achados que não tinham nada a ver entre si e acionava risco inexistente (viu isso: nenhuma escada na foto, risco de escada disparado). Corrigido tratando cada achado como fragmento isolado — ambiente/contexto entram em todos (são descrição da cena inteira), achados nunca se misturam entre si. Ao adicionar heurística de matching textual, pense em "de onde vêm as palavras", não só "quais palavras". |
| Sinal de roteamento escrito por extenso | A cobertura é parcial (70%): um sinal de 4 radicais casa com 3, e o que falta é justamente o **discriminante**. `"painel eletrico sem tampa"` fazia "painel de fôrma de madeira sem tampa protetora" virar quadro elétrico aberto; `"escada apoiada em piso irregular"` fazia escada **fixa** de concreto virar escada de mão. Sinal curto, em que nenhum radical pode faltar, é mais seguro que sinal descritivo. **Toda vez que acrescentar sinal, teste a contraparte que NÃO deve disparar.** |
| Filtrar candidato depois do corte relativo do BM25 | O `minimo_relativo` é calculado sobre o topo bruto. Um item ruim no topo levanta a régua e derruba os bons abaixo dele — filtrando depois, o dossiê fica vazio em vez de trocar o item. Por isso `buscar_pontuado` recebe `aceitar` e peneira **antes**. |
| Mesmo vocabulário para reconhecer o ramo no **item** e na **cena** | Os dois lados correm riscos opostos. Dentro da NR-12, "calçado" só aparece em item de máquina calçadista — serve para classificar o item. Mas na cena "calçado" é o que um laudo escreve o tempo todo ("calçado de segurança", EPI da NR-06), e usá-lo ali destrancaria o Anexo X em qualquer foto. Por isso `Setor` tem `no_item` e `na_cena` separados. É a armadilha do sinal por extenso vista de outro ângulo: o que discrimina de um lado não discrimina do outro. |
| Classificar o ramo de um item pelo texto antes do anexo | Os anexos setoriais se citam entre si ("as disposições deste Anexo não se aplicam às máquinas dispostas no Anexo X"), e item do Anexo X **fala de prensa**. Pelo texto, ele passava como se fosse do Anexo VIII — que uma foto de estamparia legitimamente destranca. O anexo decide primeiro; o texto só para o que a extração deixou fora dele (`12.1`, "máquinas de montar base de calçados", ficou no corpo principal). |
| Portão que só ABRE, com sinal que aparece em negação | `ha_maquina_na_cena` destrancaria a NR-12 com "**nenhuma máquina** visível na cena" se aceitasse a palavra "máquina" — exatamente a foto que se quer barrar. Por isso a lista é de substantivos concretos ("betoneira", "grua"), e inclui as máquinas dos ramos setoriais: sem elas o portão fecharia numa foto de padaria, trocando erro de enquadramento por buraco de cobertura. |
| Rótulo do risco curado como nome da não conformidade | O rótulo descreve o risco que trouxe o item ao dossiê, não a situação que o Analista enquadrou. Para item **genérico** — `NR-18 18.9.1` ("proteção coletiva onde houver risco de queda"), `NR-06 6.5.1` (EPI, oito riscos) — qual risco o trouxe é acidente do roteamento. Um laudo real saiu intitulado "Andaime sem guarda-corpo e rodapé" para uma constatação sobre a tela frouxa na borda da laje, enquanto o fato dizia que o andaime TINHA guarda-corpo; dois modelos de texto diferentes erraram igual. Hoje `itens_compartilhados()` marca os 24 itens (de 232) que mais de um risco reivindica, e para eles o rótulo cai — o relatório identifica a linha pela constatação. Só o rótulo: o portão de pessoa e a gravidade base continuam vindo do risco. |
| **`sem` é radical-cola: conta, mas não discrimina** | Ele tem 3 letras, então passa o filtro de `_radicais` e vira um radical como outro qualquer. Só que não distingue nada: um sinal de dois radicais em que um é `sem` vale por um. Custou dois defeitos no mesmo dia. `"sem carenagem"` casou com "Carenagem do motor íntegra e fixada, **sem** folgas visíveis" — carenagem em ordem, o oposto do risco. E `"vao no piso sem tampa"` casou numa foto de betoneira porque `sem` e `tampa` vieram de "Abertura circular do tambor **sem tampa**". Ao escrever ou revisar sinal, conte os radicais **discriminantes**, não os radicais. **E `sem` nunca é o negador**: em 04/09, consertando os sinais de elevador, `"elevador de obra sem cancela"` foi encurtado para `"sem cancela"` — dois radicais, um deles cola, e o fato *"Cancela metálica vermelha, fechada e travada, SEM sinalização de advertência"* deu cobertura 1,0. O agravante é sistemático: o `PROMPT_OLHO` **manda** escrever "sem &lt;peça&gt; visível" quando o lugar dela aparece vazio, então quase todo fato do Olho carrega um `sem` solto. O que nega numa foto é a **abertura** — `aberta`, `ausente`, `faltando`, `quebrada` —, e é nela que o sinal deve ancorar. **Terceira aparição em 17/09**, e desta vez o `/conserto` que a reintroduziu foi pego pelo `/critico` antes do merge: `"tanque sem placa"` (a reescrita de `area_de_risco_nao_delimitada`) batia num tanque CORRETAMENTE isolado — cerca e faixa instaladas — só porque `sem` negava a placa de identificação do fabricante, não a área de risco. E `"tanque sem cerca"`, o único sinal do mesmo risco nunca tocado, sofre da mesma colisão por outro caminho (`cerca` afirmada, `sem` negando manutenção) — ficou registrado como ressalva conhecida. **ATACADA em 18/09** pela hipótese do bigrama: `"sem"` só nega o radical que vem logo depois DELE no sinal (`_radicais_negados`), e esse radical só conta se um `"sem"` de verdade estiver perto dele NO TEXTO, contando só pra frente (`_proximidade_da_negacao`) — a direção sozinha já separa "sem cerca" (cerca depois do sem) de "isolado com cerca... sem manutenção" (cerca antes do sem). Continua fora do alcance o caso em que o NEGADOR está no TEXTO e não no sinal — `"sem trechos abertos"`, na entrada abaixo, onde o sinal é afirmativo (`"poço aberto"`) e é o achado que nega. |
| **Quatro radicais é onde a cobertura parcial abre** | O corte é 0,7. Com três radicais, faltar um dá 0,67 e **não passa** — todo radical é obrigatório. Com quatro, faltar um dá 0,75 e **passa**, e o que falta costuma ser justo o discriminante. `"abertura vertical sem fechamento"` casava uma abertura de PISO "sem cobertura ou fechamento visível", faltando só `vertical`. Sinal de até três radicais é seguro por construção; de quatro para cima, escreva sabendo que um pode faltar. **256 dos 882 sinais têm 4+ radicais** e correm esse risco (257 de 883 até 26/09, quando `"cancela aberta"` saiu e `"obra aberta para a rua"` virou `"obra aberta rua"`; 259 até 24/09, quando o reforço do prompt de andaime encurtou dois; era 262 antes do conserto de 17/09 em `area_de_risco_nao_delimitada`, que tirou três — o `/conferir` pegou "tirou dois" na primeira redação: foram cinco sinais reescritos, não quatro, e um quinto, `"qualquer um passa perto do tanque"`, tinha radical de domínio mas foi trocado por precaução contra esta mesma armadilha). |
| **Sinal de radicais 100% discriminantes, mas nenhum exclusivo do próprio domínio** | Diferente da armadilha acima: aqui a cobertura bate 1,00 (todo radical do sinal casou), e ainda assim o sinal não prova nada, porque nenhum dos radicais é vocabulário exclusivo do risco. `"perimetro sem isolamento"` (3 radicais: `sem` cola, `perimetr`, `isolament`) casava 100% num achado de VERGALHÃO espalhado sem isolamento — nada a ver com inflamável, explosivo ou radiação, que é o domínio de `area_de_risco_nao_delimitada`. Não é a armadilha dos 4+ radicais (aqui não falta nada) nem a do `sem` sozinho (aqui `sem` é só um dos três) — é o sinal inteiro ter sido escrito com vocabulário genérico de "área sem proteção", que serve para qualquer risco de isolamento, não só o deste. Medido em 17/09: pôs `NR-16 16.8` em D1 de um dossiê de vergalhão, na frente do item certo. Ao escrever sinal de risco NARROW (que só deveria disparar num subdomínio: inflamável, elétrico, altura…), confira se pelo menos um radical NÃO discriminante-por-acaso é exclusivo daquele subdomínio — `tanque`, `paiol`, `radioativa`, não `área`, `perímetro`, `isolamento`, `placa`. |
| Regra global para a cobertura parcial — **tentada e descartada** | A saída óbvia (excluir palavras-cola do conjunto que pode ancorar) **quebra 25 sinais legítimos**: `"sem capacete"`, `"sem luva"`, `"sem bota"`, `"sem placa"`, `"sem manometro"` — onde a cola e o discriminante são tudo o que existe. Também não adianta exigir que o radical faltante seja cola (deixa "escada COM sapata" casar "escada sem sapata") nem que seja não-cola (devolve o caso da betoneira). **Não há regra simples**: é encurtar sinal a sinal, com medição. Não gaste a sessão reinventando isto. |
| Verificação mecânica no caminho errado | O aparo do Diretor ganhou verificação de lastro no #13; no lote seguinte, o mesmo enquadramento falso voltou por **aprovado**, sem aparo, e passou inteiro. Ao fechar uma porta num agente, pergunte por quais outras a mesma coisa entra — decisão de modelo muda de caminho de uma rodada para outra. Hoje a exigência é cobrada de todo enquadramento que sobrevive. |
| **Plural de radical curto não reduzia** | `radical()` só singularizava palavra com mais de 4 letras, então `"fios"` ficava `"fios"` e `"fio"` ficava `"fio"` — dois radicais para a mesma palavra. O sinal `"fio desencapado"` foi cadastrado justamente porque o Olho escreve **"fios desencapados"**, e o par nunca casou: um quadro de tomadas aberto routeava **zero** riscos. Corrigido; a regra do `s` simples agora vale de 4 letras para cima, mas `PLURAIS` continua em 5 — aplicá-la a 4 transformaria `"mais"` em `"mal"`. |
| **Sinal cujas palavras somem no filtro de radicais** | `"t em cima de t"` tem cinco palavras e quatro têm duas letras: `radicais()` descarta todas e sobra `cima` sozinho, com cobertura 1.0 em "pregos expostos voltados **para cima**". Uma foto de madeira de fôrma routeava gambiarra. É a armadilha do `sem` levada ao extremo — o sinal inteiro vira cola. Hoje o validador da taxonomia quebra no import se um sinal não tiver radical discriminante (`PALAVRAS_COLA` em `riscos/__init__.py`). **O validador não pega o caso de sobrar UM discriminante mais cola**: `"andaime so com o piso"` virava `andaim`+`com`+`piso`, e com `piso` vindo do ambiente disparava `andaime_sem_guarda_corpo` (crítico) com o guarda-corpo descrito presente — consertado em 24/09. |
| **Citação removida do meio da frase deixa verbo sem objeto** | `_limpar_citacoes` tira a citação e a limpeza de órfãs arruma preposição encostada na pontuação ("conforme."). No MEIO do trecho ela não alcança: "violando a NR-10 e a NR-26" virou **"violando a e."** num parecer impresso. Nenhuma regra de pontuação conserta — o que sobra não é pontuação órfã, é um verbo sem objeto. Hoje o texto é fatiado por vírgula/ponto-e-vírgula/fim de sentença e o fragmento que só apresentava a citação sai inteiro. **A citação é MARCADA antes de fatiar**, nunca removida: ela atravessa vírgula ("NR-35, item 5.2.2.5") e fatiar antes a partiria em duas, deixando o número do item para trás — pior que não limpar, porque o renderizador o relê como citação legítima. |
| **Corte de verbosidade aplicado a um campo só** | O `retirado` do aparo ganhou `_em_poucas_palavras` no #13, quando o `motivo` do veto ainda era sempre escrito pelo código. Quando o veto passou a carregar o texto do Diretor, os 493 caracteres de argumentação voltaram por ali — dentro do ponto de atenção que vai ao cliente. É a irmã da armadilha "verificação mecânica no caminho errado": ao pôr uma trava num campo, liste os outros campos por onde o mesmo texto sai. |
| **Dois radicais é tudo-ou-nada, e o radical pode colidir** | A irmã invertida da armadilha dos quatro. A âncora exige dois radicais do PRÓPRIO achado, então num sinal de dois radicais nenhum pode vir da cena: ou o achado traz os dois, ou a cobertura é 0,00, não 0,50. Isso corta nos dois sentidos. Perde: `"cinta rasgada"` e `"gancho aberto"` deram **0,00** na foto de uma cinta de içamento rasgada de verdade. E dispara: com dois radicais só, uma colisão de radical basta para acionar o risco inteiro — `radical("cinta") == radical("cinto") == "cint"` fez `"cinto solto"` casar *"tecido da CINTA … material SOLTO"* com cobertura 1,0, e o acessório de içamento saiu no laudo enquadrado como EPI (`NR-06 6.9.3`). Não adianta acrescentar o discriminante: `"cinto de seguranca solto"` também casaria, porque `seguranc` pode vir do ambiente e a âncora já está satisfeita pelos outros dois. **Sinal de dois radicais só é seguro se nenhum dos dois for ambíguo por radical** — corrigido em #20 trocando por `"cinturao solto"` (reduz a `cintura`, não colide). Ao escrever sinal curto, rode o radical das duas palavras e procure por vizinho de outro gênero. |
| **O aparo pode apagar o achado grave e deixar a metade irrelevante** | O aparo existe para restringir a constatação ao que o fato sustenta, e nisso funciona. Mas ele escolhe QUAL parte sobrevive, e pode escolher errado: na foto das cintas o Diretor aparou o desfiamento — o desgaste estrutural, que é o risco de ruptura — e manteve só a sujidade que compromete a legibilidade das marcações. O laudo saiu tecnicamente correto e materialmente inútil, e **nada foi para os pontos de atenção**. É a classe de erro 5 (achado que evapora) por um caminho que não estava mapeado: não pelo veto, pelo aparo. Ao revisar o aparo, pergunte se o que sobrou é o achado ou o resto dele. |
| **Contraparte que não pode falhar não é contraparte** | A regra "toda vez que acrescentar sinal, teste a contraparte que NÃO deve disparar" foi cumprida na letra e não no espírito: a contraparte do prompt do Olho eram três fatos — tapume íntegro, portão de veículos, bandeja de fachada — e **nenhum continha `elevador` nem `cancela`**, as palavras dos sinais que o risco casa. Passava com qualquer taxonomia, inclusive a defeituosa. Foi o `/critico` que pegou; escrita a contraparte com as palavras dentro, apareceu o defeito: **5 de 5 fatos com a cancela INSTALADA acionavam o risco de cancela ausente**, e 3 de 6 no risco do vão da caixa, sempre a 0,75, sempre faltando só o negador (`"caixa do elevador COM fechamento"` cobrindo `"caixa do elevador sem fechamento"`). Ao escrever contraparte, pergunte **por qual sinal ela passaria** — se a resposta é "por nenhum", ela não está medindo nada. |
| **Ensinar o Olho a nomear muda o risco de todo sinal que casa aquele nome** | O falso positivo acima era latente havia sessões e nunca apareceu em lote, porque o Olho não escrevia `cancela` nem `elevador`. Mudar o prompt para ele nomear o elemento de canteiro converte o latente em provável — e justamente nas 17 fotos do lote seguinte. **Ao acrescentar vocabulário ao prompt de um agente, rode os sinais que casam esse vocabulário contra fatos em que a condição NÃO existe**, antes do lote. O prompt não é uma mudança isolada: ele é o gatilho de toda a taxonomia que fala aquela língua. |
| **`except` largo em volta de uma chamada de rede engole o motivo — e conta a foto como auditada** | O `agente_olho` tinha `try/except ErroDeAuditoria` em volta do **parse** do JSON. Ao migrá-lo para `_conversar_sem_cortar` em 04/09, o mesmo `except` passou a envolver a **chamada inteira** — e `ClienteGroq.conversar` levanta `ErroDeAuditoria` para qualquer falha da API, cota esgotada inclusive. Resultado no lote de 12 da mesma tarde: **8 fotos de 12 saíram com laudo de "a leitura da imagem falhou · 0s"** sem nunca terem chegado à Groq (`0s` é a assinatura: erro de cota volta na hora), com veredito "aprovado sem vetos" e **contadas como auditadas** — o sumário disse "9 de 12 analisadas" e listou só 3 em "Imagens não auditadas". Um laudo que diz "nenhuma não conformidade" sobre uma foto que ninguém olhou é pior que nenhum laudo. Hoje `RespostaIlegivel` (em `modelos.py`) separa as duas: só ela vira laudo de leitura falhada; erro de cota, rede ou chave sobe e a foto entra em "não auditadas". **Ao mover uma chamada para dentro de um `try` que já existia, confira o que mais aquele `except` passa a capturar** — e, num pipeline que emite documento, pergunte se o erro engolido faz o documento MENTIR sobre o que foi examinado. **Há teste guardando isso**, e ele falha no commit quebrado. |
| **Número deste arquivo envelhece em silêncio** | Os números daqui não estão escritos em lugar nenhum do código — são computados (`123 riscos` saía de `len(catalogo())`, `6.358 itens` de `carregar_base()`). Quando um PR muda o catálogo, o texto continua afirmando o valor velho e ninguém recorre à fonte, porque o entorno parece conferido. Medido em 03/09 rodando `/conferir` contra este arquivo: **cinco divergências**. Três nasceram de PRs desta mesma sessão (`123 riscos` → 126, `177 testes` → 182 em dois lugares); uma era herdada e desatualizada (`22 de 228` → 24 de 232); e uma **nasceu errada** — `272 dos 866 sinais` foi escrito quando o valor real era 271 de 866 (só o numerador; o denominador estava certo), e sobreviveu a três sessões e quatro PRs. A pior delas (`cinco dos sete sinais`, quando são sete de sete) estava num commit cuja própria mensagem dizia "números conferidos contra o código": seis números foram conferidos, e o sétimo escapou por estar no meio de um parágrafo em vez de numa lista. **A correção também erra**: a mensagem do #24 anunciou "off-by-one nos DOIS números" e o texto daqui copiou o `867`, que nunca existiu — conferir o conserto contra o código custa o mesmo que conferir o original, e ninguém fez. **Ao mexer aqui, rode `/conferir`** — e note que `grep` não pega nenhuma dessas: só executar o catálogo pega. |
| **Medir tempo por fora de uma função com várias saídas** | `executar` volta cedo quando o Olho não devolve fato utilizável. Cronometrar no `app.py`, em volta da chamada, funcionaria — até alguém acrescentar a próxima saída antecipada e o número virar zero em silêncio. Por isso `executar` virou um invólucro fino que cronometra e delega a `_executar`: existe **um** ponto de saída para medir. **Há teste guardando o caminho da visão que falha.** |
| **A tradução do erro apaga o texto que nomeia a causa** | `traduzir()`, em `modelos.py`, devolvia "Cota da Groq esgotada (limite de tokens por minuto ou por dia)" para todo 429 — uma frase escrita no código, um palpite. A Groq havia respondido "output tokens per minute (OTPM): Limit 1000, Requested 1113", e esse texto era descartado. Custou horas de diagnóstico atrás do TPM, com a resposta certa dentro da exceção. Hoje `ErroDeAuditoria.detalhe` guarda a mensagem crua de TODO erro traduzido, e o app a mostra em "O que a Groq respondeu" — persistente no `session_state`, porque `st.error` some no rerun seguinte, que foi como ela se perdeu durante o lote inteiro. **Ao traduzir um erro de serviço externo, guarde o original**: o próximo limite novo chega com um nome que este código ainda não conhece. |
| **429 tem duas causas opostas, e uma delas não passa com o tempo** | Cota estourada é fila: espera e passa, `recuperavel=True`, o lote continua. Recusa por TAMANHO da requisição (OTPM/ITPM, "Request too large") não passa nunca — repetir é queimar foto após foto contra o mesmo limite, que foi o que aconteceu com onze fotos seguidas em 04/09. `RECUSA_POR_TAMANHO` separa as duas em `traduzir()`, e a segunda interrompe o lote com a instrução certa (reduzir o teto de saída), em vez de mandar aguardar um minuto. |
| **Limite de fornecedor lido uma vez vira número do código para sempre** | O teto diário do `qwen3.8-27b` foi lido no console em 30/08 como 2.000.000, entrou em `Modelo.tpd`, virou a nota da barra lateral ("dez vezes o dos demais"), a justificativa do padrão, dois testes e cinco parágrafos deste arquivo — tudo derivado de uma leitura de tela, num campo que o fornecedor muda quando quer. O console de 04/09 mostra **200.000**, na tabela da organização e no modal do projeto. Nenhum `/conferir` pega isso, porque a fonte de verdade não está no repositório: o código executado devolve fielmente o número errado que lhe deram. **Todo número que vem de fora do repositório precisa da data da leitura ao lado e de reconferência quando um print novo chegar** — e quando ele cair, caem juntas todas as contas derivadas (aqui: ~256 fotos/dia → ~25, e "um lote de 100 cabe num dia" → ~4 dias). |
| **Mergear PR com lote rodando** | O merge dispara o redeploy do Streamlit Cloud, que **reinicia o app e apaga o `st.session_state`** — onde o lote em andamento vive. No plano gratuito um lote é de horas de parede, e o usuário recomeça do zero. Vale para qualquer merge: **pergunte se há lote rodando antes**, e espere os laudos serem baixados. |
| **Desenho de lote que só existe no chat se perde, e a subtração mente** | O lote de poço de elevador foi desenhado numa conversa e nunca gravado aqui: só o resumo "12 fotos: 5 com proteção, 5 sem, 2 de grua". Duas sessões depois ninguém sabia quais eram, e a sessão de 07/09 gastou uma rodada reconstruindo por nome de arquivo — que o próprio CLAUDE.md avisa não ser confiável. Pior: o resumo permitiu a subtração `12 − 9 = 3` que o texto repetiu como "faltam 3 fotos", quando as 9 que rodaram incluíam **duas fotos que não estavam nas 12** (`GRUAA`, `GRUAAA`) e faltavam **5**. O erro não é de contagem, é de conjunto: "rodou N das M" só subtrai se os N saírem dos M, e nenhum `/conferir` pega isso, porque a resposta não está no repositório — estava num chat. **Grave a lista NOMINAL de todo lote aqui, não o resumo por grupo**, e ao escrever "rodou N das M" confira um a um de onde vieram os N. |
| **Cada conserto de portão prende itens que ninguém mediu** | No #35 o MESMO defeito — item genérico preso atrás de equipamento — apareceu **três vezes**, e as duas últimas nasceram do conserto da vez anterior: (1) `no_item=("elevador",)` prendeu o `18.9.3`, item de ABERTURA; (2) `no_item=("andaime",)` prendeu o `18.16.4.1`, o item dos PREGOS EXPOSTOS; (3) o `anexos=("II",)` acrescentado para consertar o (2) prendeu o `Anexo II 1`, que é requisito geral de "cabos de aço utilizados em OBRAS DE CONSTRUÇÃO" — perdido numa foto de cabo esgarçado de grua ou de cinta de içamento, que é achado real deste acervo. O `/critico` pegou as três, uma por rodada. **Ao fechar um portão, liste TODOS os itens que ele passa a prender e leia cada um** — não só os que motivaram a mudança. `setor_do_item` sobre a NR inteira custa dois segundos e teria mostrado as três de uma vez. |
| **Onde o ramo é a SEÇÃO, classificar pelo texto erra** | O `Setor` nasceu para a NR-12, onde o ANEXO decide o ramo, e a NR-18 entrou no #35 classificando por texto do item. Duas vezes isso prendeu item GENÉRICO: o `18.9.3` — "os vãos de acesso às caixas dos ELEVADORES" — que é item de ABERTURA e é o que `vao_caixa_elevador_sem_fechamento` cita; e o `18.16.4.1` — "as madeiras retiradas de ANDAIMES, tapumes, fôrmas e escoramentos … retirados ou rebatidos os pregos" — que é o item dos PREGOS EXPOSTOS e vale para madeira empilhada sem andaime nenhum. O primeiro foi consertado com uma lista de formas compostas; o segundo sobreviveu na família que não tinha sido testada, e o `/critico` pegou. Na NR-18 `18.12` é andaimes inteiro e `18.11` é elevadores inteiro: `Setor.secoes` casa o `capitulo` por prefixo, é exato, vem antes do texto e **aposentou o remendo das formas compostas**. `18.10.1` continua por texto porque serra e guindar dividem a seção. **Quando existir um critério exato — anexo ou seção —, o texto é aproximação e vai errar no item genérico que menciona o ramo de passagem.** |
| **O objeto que confunde dois equipamentos não pode ser o discriminante de nenhum** | O `18.12.22` regula o CONTRAPESO do andaime suspenso, e foi por ele que a foto da grua virou não conformidade de andaime. Ao escrever o portão do #35 eu pus `contrapeso` no `na_cena` dos equipamentos de guindar — recriando a mesma confusão no sentido inverso: medido, `setor_pertinente(18.10.1.24, "andaime suspenso … com contrapesos")` devolvia **True**, e uma foto legítima de andaime suspenso passava a destrancar item de grua. O `/critico` pegou. A regra: quando um objeto é o que confunde A com B, ele não serve para reconhecer A **nem** B — use o nome do equipamento (`grua`, `guindaste`), não a peça compartilhada. Vale para o próximo portão: liste o que os dois ramos TÊM EM COMUM antes de escolher o vocabulário de cena. |
| **`na_cena` genérico abre o portão em vocabulário que não é máquina** | O `_menciona` tolera três letras de sufixo. `serra` solto no `na_cena` abre em "madeira serrada", "tábua serrada" e "pó de serragem" — vocabulário corrente de canteiro, nenhum deles uma máquina — e como é o `18.10.1.5` (serra circular) que ocupava vaga em 8 dossiês de 15, isso desfaria em silêncio o principal ganho do portão do #35. O `/critico` pegou depois de a mesma régua ter sido aplicada ao `lanca` do guindar (excluído porque "concreto lançado" abriria) e **não** ao termo que sustentava o número de manchete. `na_cena` é o NOME DA MÁQUINA, como o docstring do `Setor` sempre pediu — e a régua do sufixo se aplica a TODOS os termos, não ao que primeiro chamou atenção. **Ressalva que fica de pé**: todo `na_cena` abre em negação ("sem andaime visível" abre o portão de andaime), porque `_menciona` não olha o entorno. É a armadilha do "portão que só ABRE", e aqui ela erra para o lado permissivo — restaura o comportamento anterior, não cria falso positivo novo. Consertar exige mexer no `_menciona`, que vale para a NR-12 também, e pede medição própria. |
| **A correção do número não alcança as cópias dele** | O `/conferir` do #35 achou "7 dossiês de 15" (eram 8) e o conserto foi aplicado à mensagem do commit e a este arquivo — e **não ao comentário no código**, que ficou afirmando 7 a trinta linhas de um segundo comentário que dizia 8. O mesmo artefato carregava os dois números para a mesma medição, e foi o `/critico` que pegou, uma rodada depois. É a irmã da armadilha "número deste arquivo envelhece em silêncio", pela via mais fácil: quem corrige olha onde o DIVERGE foi apontado, não onde o número mora. **Ao corrigir número, faça `grep` do valor VELHO no repositório inteiro** — código, teste e documento — e confira que sobrou um só. |
| **A NR-18 também tem ramo por equipamento, e ela não usa anexo para isso** | O `setor_pertinente` foi escrito para a NR-12, onde o ANEXO decide o ramo. A NR-18 não tem anexo setorial: o equipamento está no texto do item, e por isso ela ficou de fora do filtro por três sessões. O preço apareceu no lote de 08/09 — a foto do topo de uma grua recebeu `18.12.22` (contrapeso de ANDAIME SUSPENSO) e virou não conformidade impressa, e o `18.10.1.5` (SERRA CIRCULAR) ocupava vaga em **8 dossiês de 15**. **A hipótese natural foi medida e refutada**: fazer um risco de guindar disparar não expulsa o item de BM25, só o empurra para D3 — item de busca textual não sai por ser empurrado, sai por ser filtrado antes do corte relativo. Ao ver item de equipamento errado num laudo, pergunte se aquela NR tem ramo e por onde ele se reconhece. |
| **`no_item` genérico prende item genérico da mesma NR** | Ao pôr `no_item=("elevador",)` no portão da NR-18, ele capturou o `NR-18 18.9.3` — *"os vãos de acesso às caixas dos ELEVADORES devem ter fechamento provisório"* —, que é item de ABERTURA, mora na seção 18.9 e é o que `vao_caixa_elevador_sem_fechamento` cita. Prendê-lo atrás da palavra "elevador" na cena desfaria, pela busca textual, justamente o risco que o lote de poço existe para validar — e logo depois de o #32 ter ensinado o Olho a NÃO escrever "elevador" quando a torre é ambígua. **A forma composta resolve** (`"torre do elevador"`, `"elevador de materiais"`, `"cremalheira"`), e continua prendendo os 16 itens de equipamento de elevador. Quem pegou foi o teste que exige `setor_do_item` None para os itens genéricos de abertura — escreva esse teste ANTES de escolher o vocabulário do `no_item`. |
| **Duas causas colapsadas num motivo só fazem o documento afirmar o que ninguém verificou** | `_exigencia_ancorada` devolve falso em dois casos opostos: o trecho VEIO e não está no item (a constatação inventou a exigência — é o que a rede existe para pegar, e a frase "a constatação não descumpre o texto oficial deste item" é verdadeira), e o trecho NÃO VEIO (o supervisor não respondeu — nada foi refutado). O código dizia a mesma frase nos dois. No lote de 08/09 isso saiu impresso: `19 PAV. POÇO GRUA SEM PROTEÇÃO`, um poço sem proteção de piso nem de parede, com 0 NC e o laudo afirmando ao engenheiro que a situação não descumpre a norma. Prova de que foi omissão e não juízo: o ponto de atenção saiu com o texto da CONSTATAÇÃO, que é o fallback de `observacoes.get(ref) or nc.constatacao` — o Diretor não preencheu nenhum dos dois campos que devia. É a irmã da armadilha do `except` largo, e a pergunta é a mesma: **o erro engolido faz o documento MENTIR sobre o que foi examinado?** Hoje `_exigencia_omitida` separa os dois, o enquadramento continua caindo (reabrir a porta devolveria o painel empoeirado ao laudo) e a trilha diz "Supervisão incompleta". **Há quatro testes travando isso.** |
| **Lista do laudo preenchida por `append` acumula entre os ciclos do Gauntlet** | `laudo.vetos = motivos` é ATRIBUIÇÃO, e é por isso que os vetos não duplicam quando o laço roda mais de um ciclo. `laudo.aparos.append(...)` não tem essa proteção. Ao acrescentar `conferencia_omitida` com `append`, o teste pegou o item repetido duas vezes com `max_ciclos=2` (o padrão de `Configuracao`, embora o `app.py` use 1 no modo Padrão). **Ao pôr campo novo no `Laudo` dentro do laço, monte a lista local e atribua no fim do ciclo**, como `motivos`. |
| **Medir o roteamento não vê o item que a busca textual traz** | O `NR-18 18.11.14` saiu impresso numa foto de grua, e o risco curado que cita esse item teve **zero disparos nas 9 fotos** do lote. As duas coisas são verdadeiras: o item chegou ao dossiê pela **busca textual**, que a palavra "torre de elevador" no fato basta para acionar. Medido: um fato que routeia risco NENHUM enche cinco vagas do dossiê com a seção 18.11. O reflexo desta casa é reproduzir `rotear_riscos` sem rede — barato e certeiro para defeito de taxonomia, e **cego para metade do dossiê**. `montar_dossie` é igualmente determinístico e custa o mesmo. Ao investigar item errado num laudo, rode o dossiê inteiro antes de concluir que a taxonomia está limpa; "o risco não disparou" não é álibi. |
| **Conserto que reintroduz o defeito que ele cita como trava** | A repescagem da conferência nasceu citando o #34 — "duas causas colapsadas num motivo só" — como a razão de só repescar o SILÊNCIO. E colapsou as duas de novo na saída: um trecho repescado que não ancorasse caía em `MOTIVO_EXIGENCIA_NAO_ANCORA`, e o laudo voltava a dizer "a constatação não descumpre o texto oficial deste item" sobre uma supervisão que nunca respondeu. O `/critico` pegou; era a terceira vez que a armadilha aparecia, e a segunda **dentro do conserto de si mesma** (a primeira foi o #35, com o portão prendendo item genérico três vezes seguidas). A pergunta que faltava: **depois desta mudança, por quantos caminhos o veto passa a ser decidido, e o que cada um diz ao engenheiro?** Ao consertar um mecanismo, releia a saída DELE, não só a entrada. |
| **O sumário não distingue enquadramento ausente de enquadramento vetado** | Lendo o sumário do lote de 09/09, concluí que o Analista tinha IGNORADO o item marcado na foto `19 PAV. POÇO GRUA SEM PROTEÇÃO` — porque ela não aparece no plano de ação. Errado: ele enquadrou os dois itens certos, e o Diretor os derrubou por não copiar a exigência. A ausência de linha no plano é compatível com as duas coisas, e elas pedem consertos OPOSTOS (dossiê/roteamento de um lado, conferência do supervisor do outro). O sumário só lista o que sobreviveu; **quem separa é a trilha do laudo**, que nomeia cada veto e sua causa. É a irmã da armadilha "medir o roteamento não vê o item que a busca textual traz", num nível acima: **ao medir um lote, o sumário conta QUANTO, e só o laudo conta POR QUÊ** — não conclua causa a partir dele. |
| **Widget de framework traz afordância que o desenho não pediu** | O `st.multiselect` do Streamlit 1.63 oferece **"Select all"** por padrão (`select_all=1000`: aparece sempre que há até mil opções). No campo de marcação por foto, um clique nele marcaria os 40 riscos de uma vez — e como o item marcado entra na FRENTE num dossiê de 22 entradas, isso expulsaria o roteamento e a busca textual inteiros: o app pararia de auditar a foto e devolveria a lista que lhe deram. Não apareceu em teste nenhum e não está na assinatura que se lê de cabeça; **apareceu na tela**, no primeiro print do painel. Hoje vai `select_all=False` e `max_selections=3`. Ao pôr widget novo, leia a assinatura inteira do construtor e pergunte o que ele faz **por padrão** — e olhe a tela, que é onde o padrão do framework aparece. |
| **Expansor do Streamlit fecha a cada rerun, e cada marcação é um rerun** | O painel de marcação nasceu sem `expanded`, e no navegador se viu o que teste nenhum veria: marcar a primeira foto fechava o painel, de modo que marcar a segunda de um lote de 100 exigiria reabrir e rolar, cem vezes. `expanded=com_marcacao > 0` resolve — a primeira marcação abre o painel para valer. Vale para todo expansor que contenha widget: o estado dele não sobrevive ao rerun que o próprio widget dispara. |
| **Rede que só registra quando FALHA é rede que não se pode medir** | `_reconferir_exigencias` deixa linha na trilha quando o enquadramento cai ("Supervisão incompleta") e **nenhuma** quando o reparo dá certo — o enquadramento simplesmente sobrevive. No lote de 10/09 isso deu 30 laudos sem uma linha de omissão e nenhum jeito de dizer se o Diretor não omitiu ou se a repescagem salvou, que são conclusões opostas sobre o mesmo mecanismo. É a irmã da armadilha "o sumário não distingue enquadramento ausente de enquadramento vetado", um nível abaixo: lá o documento não separava duas causas de ausência, aqui ele não registra o sucesso. **Ao construir uma rede de segurança, pergunte o que o documento diz quando ela FUNCIONA** — se a resposta é "nada", o próximo lote não a mede. Consertado com `conferencia_reparada`; há três testes travando. |
| **A lista que não passa pela limpeza é a que ninguém lembra que existe** | `laudo.conformidades` recebia as strings do Analista cruas — sem `_limpar_citacoes`, ao lado de `laudo.sem_enquadramento` que já chamava. Em 10/09 saiu impresso "atendendo aos requisitos … descritos no item **D6**", com o rótulo interno do dossiê no documento do cliente. O sintoma é cosmético; o buraco não: sem a limpeza, uma citação normativa digitada pelo modelo chegaria ao laudo **sem passar pela base**, que é a garantia central deste projeto. É a terceira aparição da armadilha "corte aplicado a um campo só", e o padrão é sempre o mesmo — a lista esquecida é a que quase nunca sai (conformidades apareceram em **2 de 30 laudos**), então ela não aparece em lote nenhum até aparecer. **Ao pôr uma limpeza num campo, liste TODOS os campos de texto livre que chegam ao documento e confira um a um** — inclusive os que costumam vir vazios. |
| **A âncora não protege contra a RELAÇÃO invertida entre os dois radicais** | A âncora de 01/09 exige dois radicais do PRÓPRIO achado, e isso fechou a porta do ambiente carregando o sinal sozinho. Não fecha esta: em 10/09, `"abertura no piso"` deu cobertura 1,00 e âncora 2 no fato *"**Piso** de concreto com aspecto áspero e irregular, visível na parte inferior da **abertura** ao fundo"* — os dois radicais no mesmo achado, e a relação entre eles **invertida**: o fato descreve o piso visto pelo PÉ de um vão vertical, não uma abertura no piso. Foi por aqui que `NR-18 18.9.2` chegou a D1 numa foto sem buraco no chão, três vezes em quatro execuções, e só um Diretor de quatro vetou. É a terceira armadilha da família, ao lado do `sem` e do ambiente, e a que menos se vê: o sinal está curto, os dois radicais são discriminantes, e ainda assim ele casa o oposto. A preposição que carregaria a relação (`no`) tem duas letras e some no filtro. **ATACADA em 18/09**: `_bigrama_proximo` (`pipeline.py`) exige os dois radicais a até `JANELA_PROXIMIDADE` (7) palavras um do outro para sinal de exatamente dois radicais sem negador — o caso acima (distância 9) não roteia mais, medido em `test_abertura_no_piso_nao_casa_com_a_relacao_invertida`. Ao revisar sinal de duas palavras, leia-o como frase e pergunte se a ordem inversa também casa. |
| **`abertura` e `aberta` são radicais DIFERENTES, e três sinais dependem disso** | `radical("abertura")` devolve `abertur` e `radical("aberto"/"aberta"/"abertas")` devolve `abert`; nada aproxima o substantivo do particípio. Medido em 14/09, e decidiu três das cinco fotos do lote: `torre do elevador aberta` ficou em **0,67 nos sete fragmentos** da foto de cancela instalada, faltando sempre `abert`, porque o Olho escreveu `abertura` sete vezes e `aberto` nenhuma — o falso positivo latente que o pré-registro mediu **não se realizou por uma letra**, e acrescentado `aberto` ao ambiente REAL daquela foto ele dispara. A mesma régua matou a colisão prevista de `quadro`: o Olho escreveu `malha quadrada`, e `quadrad` não é `quadr`. **Ao escrever ou medir sinal, rode `_radicais` na palavra que o Olho de fato usa**, não na que você escreveria — e note que isso corta nos dois sentidos: um sinal que ancora no particípio não pega o substantivo, e vice-versa. |
| `git fetch origin main <branch-que-não-existe-mais>` falha inteiro, silenciosamente | Fetch de múltiplos refs é atômico: se um ref já foi deletado no remoto (branch mergeada), o comando inteiro falha e **nenhum ref é atualizado** — inclusive o `main`, que existia e seria atualizado sozinho. `origin/main` local fica congelado na versão de antes, e comparações feitas contra ele mentem. Já causou uma sessão inteira concluir errado que "a reescrita nunca foi mergeada". Se o histórico parecer suspeito, rode `git fetch origin main` sozinho antes de confiar em qualquer diff. |
| **Medir um INTERMEDIÁRIO e relatar o DESFECHO** | Não é falta de medição — nas três vezes de 11-12/09 havia medição, e ela era de outra coisa. Afirmei *"nome ausente fecha o portão, logo a NC se perde"* tendo medido só o booleano de `ha_maquina_na_cena`; rodado `montar_dossie` sobre os fatos reais, abrir o portão traz **cesta aérea** na foto 1 e **rampa com mais de 20º** na foto 2, onde ainda **expulsa** o `NR-18 18.10.2.6`, e nenhuma das duas recebe um item da família `12.5.x`. Afirmei que o `NR-12 12.5.13` era o item que cobriria a barreira da serralheria tendo medido só que a palavra existe na base, por `grep`; ele passa por `comprovavel_em_foto`, por `prescritivo` e por `setor_pertinente`, e **nunca ranqueia**. Afirmei que a máquina da foto 1 era serra de FITA tendo medido pixels numa foto reduzida; o engenheiro respondeu que é serra de BANCADA. **Portão é intermediário do dossiê, `grep` é intermediário da recuperação, foto é intermediário da obra.** O teste é escrito no molde da cláusula (d) do Diretor — um procedimento que se executa na frente do texto: **antes de escrever afirmação causal, escreva literalmente "medi X, afirmo Y"** — se X e Y forem coisas diferentes, ou mede Y, ou rebaixa a frase a hipótese, com a palavra *hipótese* dentro. E ele aponta para dois lugares diferentes: afirmação sobre **o que o app entrega** termina no dossiê ou no laudo, nunca num portão, num sinal ou num `grep` (`montar_dossie` é determinístico, roda sem rede e custa dois minutos); afirmação sobre **o mundo** — material, nome, existência de um objeto — só tem duas fontes, o engenheiro e a foto, e **foto é pergunta, nunca veredito** (é a regra 3 do desenho da auditoria, e agora tem número: a leitura de imagem feita na sessão errou 2 das 7 respostas, e uma delas INVENTOU um achado). É a **forma geral** de três casos particulares que este arquivo já registrava um a um: *"medir o roteamento não vê o item que a busca textual traz"* (nesta tabela), *"a alcançabilidade NÃO era o conserto — medido"* (validação de 08/09) e *"defeito de saída de código se confere rodando o código, não lendo o produto dele"* (o item do aparo, em Em aberto). Como a (d), ele tem UM passo de julgamento — decidir se X e Y são a mesma coisa —, e a diferença é que esse passo fica escrito, onde o `/critico` e o `/conferir` o alcançam. **Nenhuma das três foi pega antes do commit, e nenhuma delas pelo `/critico`**: duas caíram quando os cinco HTML chegaram e `montar_dossie` rodou sobre os fatos reais, a terceira na resposta do engenheiro. O `/critico` rejeitou oito vezes ao longo do registro deste lote e, destas, pegou só o ECO que sobrou no título da seção 1 depois de a medição já existir — porque ele lê o artefato e acredita nele, e medição de intermediário parece medição. |

---

## Estado atual (o `main` de 03/09, com os PRs #17 em diante)

- **6.358 itens** vigentes de **24 NRs** (de 36 vigentes), extraídos dos PDFs em `normas/`
- **126 riscos** curados mapeando para itens reais; 25 exigem pessoa na cena e
  3 têm item que só entra com máquina nomeada na cena (`itens_so_com_maquina`)
- **Achado apontado pelo inspetor, foto a foto** (o desenho D, medido em 08/09). Um
  `st.multiselect` por foto oferece os **40** riscos de `riscos_marcaveis()` — os de
  construção que não exigem pessoa na cena —, e o que for marcado entra na FRENTE dos
  riscos roteados em `montar_dossie`. A marcação **não chega ao agente de visão**: ele
  segue descrevendo às cegas, senão o `fato` viraria eco do que o inspetor apontou e a
  conferência do Diretor ficaria circular. Foto sem marcação sai idêntica à de hoje, e
  toda marcação é declarada **nos dois documentos** — a trilha do laudo por foto e o
  sumário executivo, que traz a lista nominal das imagens dirigidas e marca a linha do
  plano de ação. Um laudo dirigido em parte por quem inspecionou não tem o mesmo valor de
  evidência que um em que o app chegou sozinho ao item, e quem lê o documento precisa
  saber de qual dos dois se trata.
- **O roteamento exige proximidade, não só presença, para negação e para sinal-bigrama.**
  `rotear_riscos` sabia só perguntar "os radicais do sinal estão em algum lugar do
  achado?" — o que deixava `"sem carenagem"` casar "carenagem íntegra... sem folgas" e
  `"abertura no piso"` casar "piso... da abertura" (a mesma armadilha em duas roupas
  diferentes: um radical presente no lugar errado da frase). Hoje `"sem X"` só nega X se
  um `"sem"` de verdade estiver perto DELE no texto (`_proximidade_da_negacao`,
  `pipeline.py`), e sinal de exatamente dois radicais sem negador exige os dois próximos
  (`_bigrama_proximo`). Ver "Conserto de roteamento de 18/09/2026" para a medição.
- **313 testes**
- Sem texto: NR-14, 19, 22, 25, 29, 30, 31, 32, 34, 36, 37, 38 — nenhuma de construção civil.
  O app sinaliza aplicabilidade dessas normas mas **nunca cita item delas**.
- **Diretor audita o laudo inteiro**, não só as não conformidades: recebe também pontos
  de atenção e conformidades propostos, e roda mesmo com zero não conformidades (antes
  o laço quebrava antes de chamá-lo). Faz conferência obrigatória — copia o trecho
  literal do fato que sustenta cada constatação; não achar fato é veto automático.
- **O veto apara antes de derrubar.** A conferência decide entre aprovado, aparado e
  vetado. Quando parte da constatação não tem lastro no fato, o Diretor devolve a
  constatação restrita ao que o fato sustenta, em vez de derrubar o conjunto — mas só
  depois de reler o texto oficial e confirmar que o que sobrou ainda descumpre **aquele**
  item. A distinção é o coração disso: a NR-35 exige piso estável *e* sapata (cortada a
  sapata, ainda descumpre → aparar); a NR-18 18.8.6.12 trata só de sapata (cortada a
  sapata, não descumpre mais nada → vetar).
- **A segunda metade da conferência também é mecânica.** Em `conferencia`, o Diretor
  copia por enquadramento DOIS trechos literais: o **fato** que sustenta a constatação e
  o trecho do **TEXTO OFICIAL** que ela descumpre. `_exigencia_ancorada` confere o
  segundo contra o item, e o que não ancora vira veto — em aprovado e em aparado. **O veto
  distingue duas causas** (desde o #34): trecho que veio e não ancora é refutação — "a
  constatação não descumpre o texto oficial deste item"; trecho que não veio é omissão da
  supervisão, dito assim no laudo e listado na trilha como "Supervisão incompleta". O
  enquadramento cai nos dois casos; o que muda é o documento não afirmar um juízo que
  ninguém emitiu. Pega exigência **inventada**; não pega trecho verdadeiro citado fora de propósito, e contra
  esse continua agindo só o prompt. Este é o único uso em código do bloco `conferencia`:
  o `fato` copiado segue sem verificação automática.
- **Todo texto livre do laudo passa por `_limpar_citacoes`** — a lista de conformidades
  entrou por último, em 10/09, depois de sair impressa com o rótulo do dossiê dentro. A
  função remove a citação normativa escrita à mão pelo modelo e o rótulo do dossiê
  apresentado (`item D6`, `conforme D6`, `[D6]`); o rótulo NU fica de propósito, porque
  "Bloco D3 da edificação" é frase de engenheiro. **Há cinco testes travando**, um deles
  essa contraparte.
- **A conferência do Diretor tem repescagem.** Quando ele deixa `exigencia` em branco,
  `_reconferir_exigencias` pergunta de novo, numa chamada estreita que leva só os
  enquadramentos que faltaram. **Só o trecho AUSENTE é repescado**: trecho que veio e não
  ancora é refutação, e reperguntar ali daria ao modelo uma segunda chance de inventar a
  exigência, que é o que a rede existe para impedir. Repescagem vazia derruba o
  enquadramento como antes, com "Supervisão incompleta" na trilha; repescagem ilegível
  também, sem matar a foto. Motivada pelo laudo 15 de 09/09, em que os dois
  enquadramentos certos de um poço sem proteção caíram por omissão.
  **Repescagem que dá certo deixa linha na trilha** ("Conferência repescada"), desde o
  lote de 10/09: sem ela o mecanismo era invisível no documento e um lote sem nenhuma
  "Supervisão incompleta" não separava o Diretor não ter omitido do reparo ter
  funcionado. **Há três testes travando**, um deles a contraparte de a repescagem vazia
  não contar como reparada.
  **Havendo aparo, a pergunta é feita sobre a constatação APARADA**, nunca sobre a
  original: o que tem de descumprir o item é o que sobra do corte, e perguntar pela frase
  inteira salvaria justamente o caso que o aparo manda vetar. Foi o `/critico` que pegou,
  e **há teste travando** — ele falha quando a constatação original volta à pergunta.
  **E quem entrou na repescagem cai sempre como OMISSÃO**, mesmo que o reparo devolva um
  trecho que não ancore: ele entrou porque a supervisão ficou em silêncio, e o silêncio
  não vira refutação por causa do que um reparo produziu. Sem isso o laudo diria "a
  constatação não descumpre o texto oficial deste item" sobre quem ninguém conferiu — a
  frase exata que o #34 tirou deste mesmo laudo. Foi o `/critico` de novo, na segunda
  rodada, e **há teste travando**.
- **Aparo que devolve a constatação idêntica não vira linha de trilha.** A comparação é
  exata (só normaliza espaço e caixa), porque o aparo existe para RESTRINGIR e qualquer
  restrição real muda o texto. Nasceu do laudo 3 de 09/09, que imprimiu "constatação
  restrita ao fato registrado — retirado: Nenhuma cláusula foi removida, pois…" — a trilha
  anunciando um corte que não houve, com o próprio Diretor dizendo no mesmo texto que não
  houve. **Há dois testes travando**, um deles a contraparte: aparo que muda uma cláusula
  continua virando linha.
- **Uma abertura, uma não conformidade.** `ITENS_EQUIVALENTES` (em `riscos/__init__.py`)
  declara os itens que impõem a MESMA exigência sobre o mesmo objeto —
  `NR-18 18.9.2` e `NR-08 8.3.2.2`. O primeiro do grupo que o Analista enquadrar
  encabeça; os demais viram **citação complementar** ("Também alcançado por"), impressa
  pelo código com texto verbatim da base. A fusão não injeta a NR-18 quando só a NR-08
  foi enquadrada — abertura de piso em escritório ou galpão é da NR-08, e a NR-18 é
  norma da construção. A trilha declara a edição de toda NR citada, complementar
  inclusive.
- **Regra da moldura.** A constatação só afirma que algo não existe se aquilo apareceria
  no recorte da foto. Ancoragem na cobertura, aterramento dentro do quadro: fora da
  moldura vira verificação ("não é possível determinar pela imagem"), não afirmação. É
  motivo de aparo, nunca de veto sozinha — senão anularia a regra acima.
- **O Olho qualifica a barreira, não a nomeia pela função.** "Rede de proteção" para uma
  tela plástica de sinalização é conclusão, não descrição. O prompt exige material,
  rigidez, fixação, continuidade, altura e estado; "sem <peça> visível" só quando o lugar
  dela aparece vazio na foto.
- **Mas o Olho NOMEIA a máquina.** Nomear o que uma máquina é descreve; atribuir a ela
  função de segurança conclui. "Betoneira" é o nome do objeto, "rede de proteção" é uma
  afirmação sobre o que a tela faz. Sem o nome, `ha_maquina_na_cena` fecha e a NR-12
  nunca entra. **Validado em produção em 01/09**: a mesma foto que dava "tambor
  cilíndrico de metal escuro" passou a dar "Betoneira com tambor cilíndrico…", quatro
  vezes no mesmo laudo.
- **Dossiê sem obrigação de papel.** `RE_OBRIGACAO_DE_PAPEL` (em `dossie.py`) filtra
  **686 dos 6.358 itens (10,8%)** por famílias, e não frase a frase como os
  `MARCADORES_DOCUMENTAIS` que vieram antes: treinamento e capacitação; documento,
  plano, programa, procedimento e registro; metodologia de avaliação de risco
  (probabilidade, severidade, nível de risco, taxa metabólica); competência
  institucional e dever de comunicar. Vale, como os marcadores e como
  `prescritivo()`, **só para a recuperação textual** — item documental curado à mão
  (quadro da CIPA, ficha de EPI) entra por `montar_dossie` e não passa por aqui.
  Medido em 14 cenas reconstruídas de fotos reais: a `foto (59)` foi de 10 entradas
  (9 de papel) para 7, cinco delas de proteção elétrica da NR-10; o **controle
  negativo** (foto de um POP impresso) foi de 3 para **0**. As contrapartes estão em
  teste: "o dispositivo de ancoragem deve **ser certificado**" e "os **planos de
  trabalho**" da NR-17 (a bancada, não o documento) continuam passando — por isso
  `certificado` só entra no padrão como substantivo (`o certificado`), não como
  particípio.
- **Os três agentes refazem a chamada quando o JSON não vem.** `_conversar_sem_cortar`
  cobre os dois casos — a API sinalizar corte (`finish_reason == "length"`) e o parser
  falhar sem sinal nenhum. O Olho tinha retentativa própria, escrita antes, que cobria
  só o primeiro; ficou de fora quando a segunda metade foi escrita, e o `/conferir` de
  04/09 achou a divergência entre o código e a docstring, que afirmava o contrário.
  **A conta do Olho é a mais favorável do pipeline, não a menos**: a retentativa custa
  ~2.750 tokens e só acontece na chamada que falhou, enquanto a foto perdida custa os
  ~7.800 de auditá-la inteira de novo — e é a única falha que não produz laudo nenhum,
  porque nada segue sem os fatos. **O dobro de teto na segunda tentativa não é
  desperdício, é o mecanismo**: os três rodam a temperatura 0,0 ou 0,1, então repetir a
  chamada idêntica devolveria o mesmo JSON quebrado; o teto é a única coisa que muda.
  Não existe a versão barata disto. A função devolve `(dados, bruto)` porque o Olho
  guarda a resposta crua também no caminho de sucesso — com JSON válido e zero achados,
  `visao_falhou` fica verdadeiro e a tela mostra o cru, que é o que distingue "não viu
  nada" de "respondeu num formato ilegível". **Há teste guardando os dois** — e um terceiro guardando o que a migração quebrou: só `RespostaIlegivel` vira laudo de leitura falhada; erro de cota, rede ou chave sobe e a foto entra em "não auditadas", em vez de sair com laudo de foto examinada.
- **Cronômetro por foto.** `Laudo.duracao_s` e `Laudo.espera_s`, preenchidos em
  `pipeline.executar` — que é um invólucro fino sobre `_executar` justamente porque o
  corpo tem mais de uma saída. A espera pela janela de 8.000 TPM é contada separada
  (`ClienteGroq.segundos_esperando`, no único `time.sleep` do projeto): sem separar,
  "a foto leva 45 s" não diz se o gargalo é rede, modelo ou o freio da cota — e são
  consertos opostos. Sai no rótulo de cada foto e no agregado abaixo das métricas,
  com projeção para 100 fotos. **Não entra no laudo**: tempo de processamento não é
  informação de documento de segurança do trabalho.
- **Laudo e interface sem pictograma.** Gravidade é texto (`Crítica`, `Alta`…), não
  emoji — sobrevive a laudo impresso em preto e branco. Mensagens de progresso não
  expõem nome de agente ("Leitura da imagem", não "Agente Olho"); os nomes continuam
  intactos dentro dos prompts, onde dar papel ao modelo é o que funciona.

### Módulos

```
kb_build.py   PDF oficial → base estruturada (vigência por item e por edição)
kb.py         consulta, BM25 com bigramas, extração de citações
catalogo_nr.py  as 38 NRs: título, status, palavras-chave de roteamento
riscos/       taxonomia curada risco→item; o portão valida no import e quebra se um item sumir
dossie.py     recuperação dos itens candidatos. Três peneiras sobre a busca
              textual, nenhuma delas alcançando a taxonomia curada (onde há item
              documental de propósito): comprovavel_em_foto() tira obrigação de
              papel, prescritivo() tira o que não impõe conduta, e
              setor_pertinente() tira a parte da norma que é de outro ramo.
              ha_maquina_na_cena() é o portão que a NR-12 precisa atravessar
pipeline.py   Gauntlet Loop e a aferição determinística
modelos.py    registro dos modelos (teto diário de cada um) e cliente Groq:
              cota, degradação por parâmetro, truncamento
relatorio.py  Markdown e HTML imprimível
consumo.py    contabilidade do teto diário de tokens, um balde por modelo
lote.py       sincronização entre fotos do lote e laudos emitidos
demo.py       dublê de modelo para o Modo Demonstração
```

---

## Classes de erro que este projeto existe para evitar

Foram encontradas em produção. Ao revisar qualquer mudança, procure por elas:

1. **Item verdadeiro, situação errada.** Pior que item inventado, porque sobrevive à
   conferência. Foi o bug original: abertura no piso enquadrada em guarda-corpo de
   periferia. O portão automático só confere existência — **pertinência exige leitura**.
   Reapareceu num laudo real como fio desencapado enquadrado no item que manda o
   inventário de riscos ocupacionais listar informações — o roteamento curado não
   reconheceu o vocabulário técnico do Olho, a busca textual só tinha item documental
   pra oferecer, e o Analista escolheu o menos ruim dos nove. Foi dado por corrigido
   dos dois lados (taxonomia + filtro documental na busca) — e **não estava**: o sinal
   `"fio desencapado"` da taxonomia nunca casou com o "fios desencapados" que o Olho
   escreve, por causa do plural de 4 letras, e o filtro documental era uma lista de
   frases que não alcançava as famílias inteiras. Os dois lados foram refeitos em
   02/09. O padrão de fundo — dossiê pobre força escolha ruim — reaparece em qualquer
   domínio em que o roteamento não pegue o achado; **medir o dossiê da foto é o jeito
   de ver isso**, e é barato: `montar_dossie` é determinístico e roda sem rede.
2. **Constatação afirmando mais que o fato.** "tampa quebrada" virando "expondo partes
   energizadas"; "escada apoiada" virando "sem sapata antiderrapante"; "madeira
   empilhada" virando "sem retirada de pregos". O Diretor pega isso quando julga — o
   problema visto num lote de 10 laudos reais é que ele **julgava pouco**: aprovava sem
   examinar. Por isso a conferência agora é mecânica (copiar o fato, não avaliar se
   convence) e cobre pontos de atenção e conformidades, não só as não conformidades.
3. **Enquadramento sem evidência visual.** Já aconteceu de o Olho voltar vazio e o
   Analista enquadrar a partir do texto de contexto. Hoje o pipeline para antes.
4. **Laudo que se contradiz.** Parecer do Diretor descrevendo achados que ele mesmo
   vetou, ao lado de "nenhuma não conformidade". Também apareceu como a mesma barreira
   de proteção elogiada em "conformidades" e criticada em "pontos de atenção" no mesmo
   laudo — agora o Diretor vê as duas listas e pode descartar uma das duas.
5. **Achado que evapora.** Veto derruba o enquadramento, não o problema: a observação
   vai para os pontos de atenção com o motivo da recusa.
6. **Inventário da foto em vez de risco.** Pontos de atenção listando estado normal de
   obra em andamento — parede sem reboco, marca de fôrma, tijolo aparente — como se
   fossem achado preocupante. Não tinha ninguém auditando essa lista até esta sessão.

---

## Limites honestos

- **Variabilidade — MEDIDA em 10/09, e não é onde se supunha.** A mesma foto, em duas
  execuções do mesmo dia, produz **os mesmos fatos**: 15 de 15 byte a byte, achados,
  posições, ambiente e contagem de gente, em contas Groq diferentes. **O Olho não varia
  nestas condições**; quem varia é o Analista e o Diretor, e a faixa é ~±1 NC no total de
  um lote de 15, com **duas fotos** de 15 mudando de resposta e o parecer reescrito em
  15 de 15. A anedota que sustentava este item — o botão de emergência crítico numa foto
  e despercebido em outra do mesmo painel — era de **fotos diferentes**, o que é outro
  fenômeno e continua de pé. Ver a seção de validação de 10/09 para o que isso obriga ao
  comparar dois lotes. O app é apoio, não substituto do olho do engenheiro — e o rodapé
  do laudo diz isso a sério.
- **Cota.** O teto diário é **por modelo**, e é de **200.000 tokens para os quatro**
  — `gpt-oss-120b`, `gpt-oss-20b`, `qwen3.6-27b` e o `qwen3.8-27b`. Por três sessões
  este arquivo e o registro em `modelos.py` deram **2.000.000 ao 3.8**, de uma leitura
  de 30/08, e o app anunciou ~256 fotos/dia sobre esse número; o console de 04/09
  mostra 200.000 para ele **nos dois lugares** — na tabela de limites da organização e
  no modal de limites do projeto ("Tokens per Day 200 000 · Org limit: 200 000").
  A 7.804 tokens/foto isso dá **~25 fotos/dia**, e um lote de 100 fotos leva ~4 dias.
  **Confirmado por evidência independente** no painel `dashboard/usage?tab=activity`
  (print de 04/09): nos dias 01 e 02 o `qwen3.8-27b` consumiu ~150K e ~160K tokens em
  ~57 e ~66 solicitações — ou seja, **80% da cota do dia**, não 8%. As mesmas barras
  dão ~2.500 tokens por chamada e ~7.900 por foto (3 chamadas), batendo com os 7.804
  medidos no lote de 15. O usuário já encostava no teto diário nos dias 01 e 02 sem
  saber, e o app dizia que sobrava cota para mais 250 fotos. As barras são leitura de
  gráfico; só o tooltip de 04/09 é exato.
  O 3.8 continua o padrão pelo que ele gasta e pelo que ele emite (15/15 laudos, 7.804
  tokens/foto contra 13.404), não por folga de cota, que nunca existiu. Também por
  modelo:
  8.000 TPM e 1.000 requisições/dia. **E, desde algum momento entre 02 e 04/09, um
  OTPM de 1.000** — tokens de SAÍDA por minuto, limite de organização que não aparece
  na tabela pública e que recusa a requisição pelo tamanho declarado. É ele que decide
  o teto de saída de cada chamada hoje; ver a seção sobre o lote travado de 04/09. O registro em `modelos.py` carrega o teto de cada
  um (`Modelo.tpd`) e `consumo.py` guarda um balde por modelo — antes o app somava os
  três e comparava com um número só, anunciando 28 fotos/dia e mandando parar de
  auditar com cota sobrando.
  **Medido em produção em 30/08, uma foto por configuração** (n=1, com a ressalva
  abaixo):

  | configuração | tokens/foto | chamadas | fotos/dia |
  |---|---|---|---|
  | Olho no 3.8, texto no `120b` | 13.404 (1.946 + 11.458) | 4 | ~16, preso no `120b` |
  | tudo no `qwen3.8-27b` | **7.060** | 3 | **~28**, preso no TPD |

  A execução de 13.404 teve uma **retentativa** no `120b` — o `_conversar_sem_cortar`
  refazendo JSON que não parseou, com o dobro do teto de saída. Sem ela seriam ~4.600
  no texto, ou ~43 fotos/dia. Os dois números são a mesma medição: o que varia é a
  frequência da retentativa, que uma foto não determina. Entrada por agente, medida
  antes no 3.6: Olho ~1.956 (1.600 são a imagem em 896px), Analista ~1.716 (dossiê
  sozinho: 921), Diretor ~1.551.
  **Um lote de 100 fotos não cabe num dia**: a ~25 fotos/dia pelo teto de 200.000,
  são ~4 dias, e dentro de cada dia o relógio ainda freia pela janela de 8.000 TPM
  (~1,1 foto/min). Os dois limites apertam; o diário é o que decide o calendário.

  **O teto diário DOBRA com uma segunda conta Groq, e isso foi testado em 10/09.** O
  usuário tem acesso a uma segunda conta (da esposa, que a emprestou) e confirmou que
  funciona: cada conta tem balde próprio de 200.000 por modelo, então **~25 fotos/dia
  viram ~50**, e o lote de 100 cai de ~4 dias para ~2. Não é preciso mexer em código —
  a barra lateral já tem "Usar minha própria chave" com o campo, e trocar a chave entre
  lotes basta.
  **O que NÃO dobra**, e é onde a conta engana: cada foto continua levando ~45 s, porque
  a janela de 8.000 TPM é por conta e o app roda um lote de cada vez, sequencial. E o
  **OTPM de 900 continua igual** — a segunda conta tem o OTPM dela, mas cada chamada
  segue limitada ao mesmo teto de saída, então o Diretor não ganha espaço nenhum. O ganho
  é de CALENDÁRIO, não de relógio nem de tamanho de resposta.
  **A pegadinha que vai enganar quem trocar a chave**: `Consumo` (em `consumo.py`) vive no
  `st.session_state` e é indexado só pela DATA — ele **não sabe que a chave mudou**.
  Depois de trocar, o painel continua somando no balde da conta anterior e vai anunciar
  cota esgotada com a conta nova zerada. O botão **"Zerar contagem"** resolve, e é preciso
  clicar nele a cada troca. O contador só informa: quem interrompe o lote de verdade é o
  429 da API, então esquecer de zerar não perde foto, só mente na tela.
  **Alternar as duas chaves DENTRO do mesmo lote não existe e seria outro ganho** — aí
  dobraria também a janela de TPM e o relógio cairia junto. Custa fazer o contador ser por
  chave e mexer na espera adaptativa, que vive dentro do `ClienteGroq`. Não foi feito.
- **Documento gerado não substitui laudo assinado por profissional habilitado.**

---

## Em aberto

- **`PROMPT_OLHO` não pedia atributo de EPI — achado em 15/09, a causa raiz CONSERTADA
  em 16/09 (PR #57), e o conserto ITERADO por mais duas rodadas de prompt (PR #58, #59)
  até o usuário decidir, depois da quarta medição, PARAR de iterar. Ver "COMECE POR AQUI"
  no topo deste arquivo para a decisão, e "o lote de EPI" / as três validações seguintes
  para a análise completa de cada rodada.** Resumo da cadeia, do início ao fim e com a
  atribuição de PR conferida contra o código (`git diff` de cada merge em
  `auditoria/pipeline.py`, não só o texto): o **PR #57** mudou só a causa raiz — pediu o
  atributo de EPI no schema e parou de descartar `pessoas.descricao` no parse — e mediu,
  na rodada seguinte, 0 de 3: `epi_nao_utilizado` disparou pela primeira vez em produção,
  mas o Olho alucinou sobre o corpo da pessoa de três jeitos. Reagindo a essa medição, o
  **PR #58** escreveu as quatro regras que hoje formam o parágrafo (mão que
  segura/apoia/manuseia sempre "aparece"; limitar o que aparece da pessoa proíbe afirmar
  o estado do que ficou fora; proibição de deduzir "usa capacete/boné/luva" por contexto;
  pessoa múltipla vira achado próprio) — 244→248 testes — e mediu, na rodada seguinte,
  1 de 3: das quatro, duas (mão, o que fica fora do recorte) seguraram, a do boné falhou
  no caso exato que a motivou, a quarta não foi exercida. O **PR #59** reforçou a regra do
  boné com um critério checável (borda/aba/viseira distinta do couro cabeludo, dentro do
  MESMO parágrafo de pessoa) e acrescentou, fora do parágrafo de pessoa, a trava do vão
  inexistente (exige profundidade real) — 248→250 testes — e mediu, na rodada seguinte,
  0 de 3 de novo: **a regra 1 (mão) e a regra 4 (achado próprio por pessoa), com o MESMO
  texto da rodada anterior, regrediram** — a foto 2 reproduziu a contradição que a regra
  1 existe para impedir, e os dois homens da foto 3 voltaram ao mesmo achado; só a trava
  do vão (fora do parágrafo de pessoa) segurou. **Decisão final, registrada no PR #60: não há quinta
  trava.** O parágrafo de pessoa fica como está — pedido do atributo (#57), as quatro
  regras (#58) e o reforço do boné (#59) — e a trava do vão (#59) fica; nenhum ajuste
  novo até o usuário pedir. 250 testes passam, cobrindo o texto do prompt — não a
  estabilidade de execução do modelo, que nenhum teste unitário alcança.
- **"O modelo ainda é o melhor?" não se responde desta sessão — remedido em 12/09.** O
  usuário perguntou, e a verificação honesta é esta: `groq.com`, `api.groq.com` e
  `console.groq.com` devolvem falha de conexão (código 000, não 403), então **não há como
  ver o catálogo atual nem os limites de hoje**. Busca na web devolve só agregadores de
  terceiros, que **divergem da medição deste projeto** — um deles anuncia 30.000 TPM no
  plano gratuito contra os 8.000 medidos aqui, e lista modelos que não estão no registro.
  É a mesma regra que vale para norma: **fonte oficial ou nada**, e a oficial é o console.
  **O que sustenta o padrão continua sendo medição, não novidade**: o `qwen3.8-27b` emitiu
  15/15 laudos contra 11/14 do `gpt-oss-120b` e gastou 7.804 tokens por foto contra 13.404,
  e é por isso que ele é o primeiro item de `VISAO` e de `TEXTO` em `modelos.py`. Nada disso
  envelheceu: o lote de 11/09 rodou nele nos dois campos, 5 laudos de 5, 1 ciclo em todos.
  **Como verificar quando valer a pena**, e a ordem importa: (1) ler o catálogo e os limites
  no console, anotando a DATA da leitura ao lado, como a armadilha do limite de fornecedor
  manda; (2) usar o campo **"Outro (digitar o ID)"** da barra lateral, que aceita ID novo sem
  mexer em código; (3) medir com a âncora do lote de máquina mais duas ou três fotos, no
  mesmo dia, trocando UM campo por vez. O precedente é o `GRUAAA`, a única troca causal do
  histórico. **Trocar os dois campos de uma vez não mede nada.**
  **Risco imediato, visto no print de 12/09**: o campo **Texto (enquadramento e supervisão)**
  aparece em `GPT-OSS 120B`, não no padrão. Rodar lote assim não é comparável com nada deste
  arquivo — é o modelo que perdeu 3 laudos em 14 e custa ~13.400 tokens por foto, o que
  derruba o rendimento de ~25 para ~16 fotos no dia. **Confira os dois campos antes de
  executar.**

- **"Área de corte sem barreira de acesso" não tem item alcançável — medido em 11/09, com
  os laudos do lote de máquina em mãos.** É a NC real que a foto 2 perdeu, confirmada pelo
  engenheiro, e os três desenhos de dossiê reproduzidos sem rede mostram que nenhum caminho
  entrega o enquadramento: o fato como saiu não traz NR-12 nenhuma; nomear o `policorte`
  abre o portão e traz `NR-12 Anexo III 6.1` (rampa com mais de 20º) e `Anexo XII 3.2.2`
  (plataforma condutiva), **expulsando** o `NR-18 18.10.2.6`; e escrever o achado como fato
  dispara `area_carpintaria_armacao_irregular`, que traz `NR-18 18.7.3.1` e `18.7.3.2` em D5
  e D6 — mas o `18.7.3.1` cobre piso, cobertura, iluminação e resíduos, **sem cláusula de
  isolamento**, e o `18.7.3.2` isola a área de movimentação de VERGALHÕES, não a de corte.
  O `NR-12 12.5.13` passa por `comprovavel_em_foto`, por `prescritivo` e por
  `setor_pertinente`, e **nunca ranqueia** — busca textual sobre o vocabulário do Olho não o
  alcança. **É a situação dos itens de guindar de 03/09 outra vez**: o achado é real e o
  enquadramento não existe ao alcance, então nem um Olho perfeito o produziria. Duas saídas,
  nenhuma medida: risco curado novo para área de máquina sem delimitação, ou aceitar que a
  NR-18 não cobre isso e citar a NR-12 por taxonomia curada, que é o caminho do
  `itens_so_com_maquina`. **Meça o dossiê antes de escrever o risco** — foi medir que
  derrubou duas hipóteses minhas seguidas aqui.
  **Reinvestigado em 17/09, ainda sem item — mas achou um defeito DIFERENTE, medido e
  CONSERTADO.** Busca fresca na base inteira (NR-12, NR-18, NR-26) atrás de vocabulário de
  isolamento/barreira/demarcação não achou nada melhor que `NR-12 12.2.1` (demarcação de
  circulação — sobre via de passagem, não sobre isolar terceiros do risco de projeção), que é
  o mesmo tipo de mismatch do `18.7.3.1`. **Decisão: não forçar.** Citar `12.2.1` para a
  serralheria seria a classe de erro 1 de novo — item verdadeiro, situação errada — e este
  projeto existe para evitar isso, não para produzi-lo de propósito.
  O que a reinvestigação achou foi outra coisa: o acervo de fixtures ganhou uma foto nova,
  nunca rodada em lote nenhum — `AUSENSIA DE ISOLAMENTO.jpg`, vergalhões de aço espalhados no
  piso sem isolamento, três trabalhadores ao fundo. **Não é o caso da serralheria** (sem
  ferramenta de corte, sem bancada metálica) — é o caso que `area_carpintaria_armacao_irregular`
  já cobre, via `NR-18 18.7.3.2` ("a área de movimentação de vergalhões de aço deve ser isolada").
  Reproduzido o dossiê sem rede sobre um fato sintético imitando a foto: o risco certo disparou,
  **e também disparou `area_de_risco_nao_delimitada`** (NR-16 16.8, explosivos/inflamáveis),
  pondo o item errado em D1 e empurrando o `18.7.3.2` certo para D5. Medido sinal por sinal:
  quatro dos sete sinais desse risco (`"sem faixa isolando a area"`, `"sem placa de area de
  risco"`, `"perimetro sem isolamento"`, `"sem corrente delimitando"`) não tinham radical
  exclusivo de inflamável/explosivo/radiação — casavam com QUALQUER área sem isolamento, dois
  deles ainda pela armadilha dos 4+ radicais. **Consertado**: os quatro reescritos para sempre
  exigir o objeto (`tanque`/`tancagem`/`radioativa`) como radical obrigatório, em sinais de 3
  radicais — onde 2 de 3 falha o corte de 0,7 e o domínio não pode ser o que falta.
  **Um quinto sinal foi trocado por precaução, não por falso positivo medido**:
  `"qualquer um passa perto do tanque"` tinha radical de domínio (`tanqu`), mas com 4 radicais
  ele é descartável pela mesma armadilha — `qualquer`+`pass`+`pert` sozinhos (sem `tanqu`) já
  batem 0,75 de cobertura. Virou `"livre acesso ao tanque"`, 3 radicais, `tanqu` obrigatório.
  **São cinco sinais reescritos ao todo, não quatro** — o `/conferir` pegou a conta errada na
  primeira redação ("tirou dois" onde o certo é três, ver a tabela de armadilhas). De quebra,
  `"radioativa sem isolamento"` cobre a classe que a descrição do risco já prometia
  ("radiações") e nenhum sinal alcançava. Medido depois do conserto: o falso positivo sumiu
  (`NR-16 16.8` fora do dossiê) e o item certo subiu de D5 para D3; o caso positivo genuíno
  (tanque de combustível sem cerca) continua disparando. **258 testes passam** (256 + 2, o
  falso positivo e a contraparte). Não há lote de produção validando isso, e não precisa: é
  código determinístico de roteamento, sem prompt de agente envolvido — mesmo raciocínio do
  PR #62/#63. **O item da serralheria continua em aberto**, sem mudança de código proposta.
  **O `/critico` REJEITOU a primeira versão do conserto, e o gap era real.** Os cinco sinais
  reescritos usavam `"tanque sem placa"` e `"tanque sem faixa"` — e `placa`/`faixa` são
  substantivos comuns em contextos de segurança do trabalho sem relação nenhuma com
  isolamento de área (placa de identificação de equipamento, faixa reflexiva de colete).
  Medido: o achado *"Tanque de gás industrial, isolado com cerca completa e faixa de
  segurança, sem placa de identificação do fabricante visível"* batia cobertura 1,00 em
  `"tanque sem placa"` descrevendo um tanque CORRETAMENTE isolado — a armadilha "sem nunca é
  o negador" (já na tabela desde 04/09) reintroduzida pelo próprio conserto que existia para
  evitar essa classe. Trocados por `"tanque sem isolamento"` e `"tanque sem delimitacao"` —
  vocabulário mais amarrado ao próprio conceito do risco, não genérico de EPI/sinalização.
  Medido de novo: os cinco sinais reescritos não disparam mais no caso adversarial. **259
  testes passam** (258 + 1, o caso adversarial exato do `/critico`).
  **A ressalva `"tanque sem cerca"` foi RESOLVIDA em 18/09**, junto da hipótese do bigrama —
  ver a seção dedicada logo abaixo de "COMECE POR AQUI". Ficou registrada aqui como estava
  escrita até então porque é o caso de teste que a motivou
  (`test_tanque_sem_cerca_nao_colide_mais_com_a_ressalva_conhecida`): *"Tanque de gás
  industrial, isolado com cerca completa ao redor, sem manutenção recente na pintura da
  estrutura"* batia cobertura 1,00 porque `tanqu`+`sem`+`cerc` apareciam todos no mesmo
  achado, com `cerca` afirmada e `sem` negando outra coisa. Não era regressão daquela sessão
  (o sinal é anterior aos dois PRs) — era o caso que sobrava sem o roteador saber que "sem"
  só nega o radical que vem logo depois dele no SINAL, e perto de um "sem" de verdade no
  TEXTO.
  **FECHADO em 22/09/2026 — busca exaustiva nas 24 NRs carregadas, sem código novo.** A
  reinvestigação de 17/09 tinha buscado só em NR-12/NR-18/NR-26. Repeti com **14
  consultas** de vocabulário novo pela mesma `base.buscar_pontuado` — 5 delas **sem
  filtro nenhum de `nrs`**, contra as 24 NRs inteiras ("área de corte isolada de
  terceiros", "acesso de terceiros à área onde se realiza corte", "proteção contra
  projeção de partículas na área de circulação", "delimitação da área de trabalho com
  risco de projeção", "cerca ou barreira impedindo aproximação de pessoas estranhas ao
  serviço"); as outras 9 repetiram o universo de 17/09 (7 em NR-12/18/26) e checaram
  NR-01 à parte (2, atrás de hierarquia de controle). Testei cada candidato novo contra
  o TEXTO LITERAL do item, não só contra o score do BM25:
  - `NR-18 18.7.2.2`/`18.7.2.30` — cobertura mais alta que qualquer coisa achada em 17/09
    ("A área de fogo deve ser protegida para evitar a projeção de partículas..."), mas a
    seção é **"Escavação, fundação e desmonte de rochas"** (`titulo_da_secao`) — "área de
    fogo" é termo de desmonte com explosivo, não de bancada de corte. O `18.7.2.2` já é o
    item citado por `escavacao_sem_isolamento_sinalizacao`, risco existente com escopo
    certo; o `18.7.2.30` não é citado por nenhum risco da taxonomia — não porque falte,
    é porque também não tem para onde ir.
  - `NR-18 18.16.18` ("tapume... impedir o acesso de pessoas estranhas aos serviços") —
    seção **"Disposições gerais"**, perímetro do CANTEIRO inteiro contra gente de fora da
    obra, não a bancada de corte dentro dele.
  - `NR-18 18.10.1.29(a)`/`NR-12 12.8.6.2`/`18.13.1(e)` — perímetro de carga suspensa,
    passarela sobre transportador contínuo e sinalização de "área de movimentação de
    materiais", nesta ordem: nenhum é sobre corte.
  - `NR-12 12.2.1`/`12.2.1.2`/`12.2.2`/`12.2.3` — os quatro itens que
    `area_circulacao_maquinas_obstruida` já cita (risco existente; o candidato de 17/09
    era só o `12.2.1`, revisitado agora com o grupo inteiro). A base não guarda título de
    seção para eles (`titulo_da_secao` devolve vazio; ao contrário da NR-18, a NR-12
    extraída não tem item curto fazendo cabeçalho ali), mas o TEXTO é consistente:
    demarcar e desobstruir via de circulação, distância mínima entre máquinas para
    manutenção/limpeza, espaço para o corpo se mover — não impedir alguém de se
    aproximar de quem está cortando. Esse risco já está registrado como ruído no
    PRÉ-REGISTRO sintético do lote de escada (15/09): disparou sobre um fato inventado
    aqui, sem máquina nenhuma na cena, pelo sinal `"passagem estreita entre maquinas"` a
    0,75. Não há confirmação de que isso se repetiu num laudo real.
  - `NR-01` inteira (hierarquia de controle, EPC antes de EPI) — nenhum item fala de
    barreira física; é o nível de política, não de execução.
  Não achei candidato que não caísse num desses grupos: todo item novo devolvido pelas
  14 consultas, ao ser lido, ou já pertencia a um risco existente com escopo diferente do
  de "corte", ou repetia o mesmo mismatch já descartado em 17/09.
  **Decisão mantida: não forçar.** A garantia central do projeto — "o modelo escolhe, o
  código cita" — pressupõe uma citação que resista à leitura do texto oficial; nenhuma
  das candidatas resiste. Isto não é um roteamento que falha por sinal mal escrito (a
  classe de bug que este arquivo em geral resolve) — é a base normativa carregada (24
  NRs, focadas em construção) genuinamente não ter um item de "isolar a bancada de corte
  contra terceiros" fora dos contextos vizinhos (vergalhão, desmonte de rocha, carga
  suspensa, perímetro do canteiro). Só existiria um jeito de fechar por código: uma
  edição de NR nova em `normas/` que traga esse item — não uma mudança em `riscos/`.
  **O caminho que sobra para este achado não é uma NR nova, é o que já existe**:
  `PROMPT_ANALISTA` já instrui, na regra 2, "se um fato PREOCUPA mas nenhum item do
  dossiê o cobre, escreva-o em `sem_enquadramento`" — vira ponto de atenção sem citação,
  em vez de sumir ou forçar item errado. Isso é comportamento de MODELO (o Analista
  escolher escrever ali), não algo que `/conferir` ou teste unitário possa travar, e só
  um lote confirma se ele obedece — sem acesso à Groq nesta sessão, não dá para medir.
  **O que É separável, e continua em aberto, é outro item já registrado**: "Nada pede
  que todo achado de risco seja endereçado" (mais abaixo nesta lista) — hoje nada no
  pipeline garante que um achado do Olho vire NC, `sem_enquadramento` OU conformidade;
  ele pode simplesmente não ser mencionado por nenhum dos três. Esse mecanismo, sim, é
  código determinístico (checar que todo achado tem destino, sem depender do prompt
  escolher bem) e poderia consertar o sintoma sem depender de item de norma nenhum — mas
  é tarefa distinta desta, com escopo maior (toda foto, não só corte), e não foi pedida
  aqui.
- **"Cabo no piso" não tem item alcançável — previsto em 12/09 e CONFIRMADO no lote do mesmo
  dia.** O `NR-10 10.2.8.2` e o `10.2.8.2.1` chegaram em D1 e D2 curados em três das quatro
  fotos e o Analista **não usou nenhum**, porque o item trata de partes vivas e o cabo está
  íntegro; nas fotos 1 e 3 o cabo saiu em ponto de atenção. O `NR-18 18.10.2.4` não apareceu em
  dossiê nenhum dos cinco. O que segue é o pré-registro, que continua valendo palavra por
  palavra, com UMA correção marcada no fim.
  **Medido em 12/09, ANTES do lote de elétrica.** As quatro fotos do lote foram abertas aqui e
  as quatro mostram a mesma coisa: cabo com o isolamento APARENTEMENTE ÍNTEGRO atravessando
  área de circulação, **nenhuma com condutor desencapado**. O `FIO EXPOSTO NO CHAO` é exposto
  no sentido de descoberto, não de sem isolamento. O item que cobre isso de frente existe:
  `NR-18 18.10.2.4` — *"o condutor de alimentação da ferramenta elétrica deve ser manuseado de
  forma que não sofra torção, ruptura ou abrasão, nem obstrua o trânsito de trabalhadores e
  equipamentos"*. Ele passa por `comprovavel_em_foto`, por `prescritivo` e por
  `setor_pertinente`, **nenhum risco curado o cita**, e em quatro redações diferentes — a do
  vocabulário do sinal, a do texto do próprio item, "extensão no chão" e "rolo de cabo" — ele
  **nunca chega ao dossiê**. A causa não é ranquear baixo: a **NR-18 não chega a ser NR
  candidata** com vocabulário elétrico. Medido: `nrs_candidatas` devolve `['NR-01','NR-08','NR-10']`
  e, nomeando a furadeira, `['NR-08','NR-10','NR-12']`. **O que chega no lugar** é
  `NR-10 10.2.8.2` e `10.2.8.2.1`, que tratam de desenergização e de isolação de PARTES VIVAS
  — para cabo íntegro no chão é a classe de erro 1 pronta, e é a previsão registrada para este
  lote. Duas saídas, nenhuma medida: risco curado novo para condutor obstruindo circulação,
  citando o `18.10.2.4`, ou eleger a NR-18 quando o vocabulário elétrico aparece em cena de
  canteiro — a segunda mexe em todas as fotos e pede lote próprio.
  **E a palavra que o Olho escolher para o chão decide o dossiê**, o que faz deste lote a
  medição direta do que a linha dele na fila promete. O sinal cadastrado é
  `"cabo eletrico estendido sobre o piso"`, cinco radicais:

  | fato | riscos | dossiê |
  |---|---|---|
  | "cabos elétricos dispostos diretamente no **chão**" | `sinalizacao_de_seguranca_ausente` | NR-26 e NR-08, **zero NR-10** |
  | a mesma frase com **piso** | nenhum | NR-08, zero NR-10 |
  | "cabos elétricos **estendidos sobre o piso**" | `cabo_eletrico_danificado` | `NR-10 10.2.8.2` em D1 |
  | "fiação elétrica estendida no **chão** da laje" | nenhum | **vazio** |

  Trocar `piso` por `chão` derruba a cobertura para 0,40, e **os QUATRO nomes de arquivo dizem
  CHÃO**, um deles sem o til.
  **A CORREÇÃO que o lote obrigou**: o par `chão`/`piso` NÃO é o discriminante. Na foto 2 o Olho
  escreveu "chão" e o risco disparou assim mesmo, a 0,80, porque o `piso` veio do AMBIENTE e a
  âncora já estava satisfeita por três radicais do achado — a âncora impede o ambiente de
  carregar o sinal sozinho, não de COMPLETAR um sinal ancorado. Quem decide é `cabo`: na foto 4
  o Olho escreveu `fiação`, a cobertura caiu a 0,60 e o dossiê foi para NR-13 de vaso de pressão. As contrapartes ficam caladas: canaleta instalada, eletroduto rígido e extensão
  suspensa com isolamento íntegro dão zero risco nas três.
  **Medi X, afirmo Y**: o que se mediu é o dossiê sobre fatos SINTÉTICOS escritos aqui, não
  sobre os fatos do Olho, que ainda não existem. O que o lote vai entregar é **hipótese** até os
  laudos chegarem — o que está medido é que, dado o fato, o item de frente não é alcançável.
- ~~Os anexos III e XII da NR-12 não são ramos setoriais, e por isso `setor_pertinente` não
  os filtra~~ — **CONSERTADO em 16-17/09 (PR #62, `076e4cb` de 16/09 + `c471f5d` de 17/09),
  sem lote de produção.** Medido em 11/09: com `serra de bancada` no fato, o dossiê da foto
  1 ia de 14 para 19 entradas e ganhava `12.4.8`, `Anexo III 7`, `Anexo XII 2.1` (cestas
  aéreas), `Anexo XII 3.2.2` e `Anexo XII 3.6.1` — a NR-12 voltando a ser a lixeira do
  dossiê pela porta que o #35 não fechou. Dois `Setor` novos em `SETORES["NR-12"]`, no
  mesmo molde dos sete ramos (Anexo III: meios de acesso a máquinas — `rampa de acesso`,
  `passarela de acesso`, `plataforma de acesso`, mais `escada de degraus` e
  `gaiola de protecao`; nunca `escada`/`rampa`/`plataforma` soltos, que são o vocabulário
  mais genérico de todo canteiro; Anexo XII: cesta aérea/cesto acoplado/cesto
  suspenso/cesta de transferência, o equipamento que iça PESSOA). **São DOIS portões em
  série** (`ha_maquina_na_cena` destranca a NR-12 para a busca textual; `nrs_candidatas`,
  via `CATALOGO_NR`, decide antes se ela sequer disputa vaga) — e foi exatamente aí que a
  primeira versão do conserto errou: o `/critico` rejeitou por medir só o primeiro portão
  (`setor_pertinente` isolado) e não o dossiê inteiro, onde uma cena de cesta aérea pura
  não roteava NR-12 nenhuma porque `CATALOGO_NR["NR-12"]` não tinha essas palavras. As
  mesmas frases entraram em `palavras_chave` no segundo commit, e o teste positivo passou a
  rodar `_dossie_da_cena`. **Medi X, afirmo Y**: o que está medido são as duas funções de
  teste novas (uma reproduzindo o vazamento de 11/09 em duas cenas, outra confirmando o
  dossiê real nas duas cenas positivas) e o `/critico` aprovando o range final — 252 testes
  passam (250 + 2). Não há lote de produção validando isso ainda, e não precisa: é código
  determinístico, sem prompt de agente envolvido.
- ~~O `NR-18 18.9.2` enquadrou uma abertura VERTICAL pela terceira vez~~ — **CONSERTADO em
  17/09 (PR #63, `c840964`+`2a2f09e`), sem lote de produção.** No laudo 2 de 11/09 a
  constatação dizia *"abertura vertical na estrutura de concreto, sem porta ou
  fechamento, revelando o interior de outro cômodo"* e citava o `18.9.2`, que é item de
  **abertura no PISO**; o `NR-08 8.3.2.2`, que cobre piso E parede, entrava só como
  citação complementar, quando era ele o item de frente. Três casos em três lotes com o
  mesmo defeito (laudo 1 de 09/09, passada B de 10/09, laudo 2 do lote de máquina em
  11/09), sempre com o `8.3.2.2` disponível ao lado — era a fusão de `ITENS_EQUIVALENTES`
  invertendo a ordem por precedência FIXA, sem olhar a constatação.
  `_regula_a_abertura()` agora checa a constatação (já aparada pelo Diretor, no ponto em
  que a fusão roda) por "abertura vertical"/"vão vertical" **adjacentes** — não
  `vertical` solto, que foi a primeira versão e que o `/critico` rejeitou por derrubar
  o `18.9.2` numa abertura de PISO real cuja constatação só citasse algo vertical ao
  lado (ex.: "escada vertical" próxima). É o mesmo discriminante já usado em
  `abertura_parede_desprotegida` (`riscos/construcao.py`). No caso comum (abertura de
  piso, sem menção a vertical), a ordem de `ITENS_EQUIVALENTES` continua decidindo, sem
  mudança de comportamento.
  **O outro lado, medido em 12/09, continua de pé e não muda com este conserto**: na
  foto 4 do lote de elétrica o Diretor VETOU o mesmo `18.9.2` num vão de parede fechado
  com tela, com a razão certa, e o engenheiro confirmou que a tela é fechamento e está
  fixada — ali o `8.3.2.2` não estava disponível (a NR-08 não era candidata naquela
  foto), então não havia fusão a corrigir; quem resolveu foi o veto do Diretor, um
  mecanismo diferente.
  **Medi X, afirmo Y**: o que está medido são quatro testes (o caso real de 11/09, a
  contraparte de piso inalterada, o limite declarado de "parede" sem "vertical", e o
  caso adversarial que o `/critico` achou) e o `/critico` aprovando o range final — 256
  testes passam (252 + 4). Não há lote de produção validando isso ainda, e não precisa:
  é código de fusão de citação, sem prompt de agente envolvido.

- **O `sem` satisfaz um sinal negando OUTRA coisa no mesmo fato — e isso derruba uma
  família inteira de riscos.** Achado no lote de 05/09 e **medido**: o fato *"Guarda-corpo
  metálico rígido instalado na borda da laje, com travessão superior e rodapé, **sem
  folgas** nem oxidação visível"* — proteção em ordem — aciona **quatro sinais de três
  riscos diferentes**, todos porque o `sem` de "sem folgas" completa um sinal sobre a
  falta de outra peça:
  `"periferia da laje sem guarda-corpo"` (1,00 — o `periferi` vem do ambiente),
  `"sem rodape na borda"` (1,00, sobre um guarda-corpo que TEM rodapé),
  `"andaime sem guarda corpo"` (0,75, sem andaime nenhum) e
  `"passarela sem guarda corpo"` (0,75, sem passarela nenhuma).
  **E há um quinto, achado ao escrever a contraparte do sinal novo**: o mesmo
  `"periferia da laje sem guarda-corpo"` dispara a **0,80 sem precisar do `sem`** —
  no fato *"Guarda-corpo metálico rígido instalado na borda da laje, com tela plástica
  presa por trás"*, com `periferi` vindo do ambiente, ele cobre 4 de 5 e a cobertura
  parcial faz o resto. É a armadilha dos 4+ radicais e a do `sem` no mesmo sinal, que é
  o principal do risco. Encurtá-lo não resolve: tirado o `sem`, sobra "guarda-corpo na
  periferia da laje", que dispara com o guarda-corpo instalado; e sem ele o risco perde
  o caso mais óbvio de todos ("borda da laje sem guarda-corpo"), porque
  `"borda de laje aberta"` fica em 0,67 ali.
  Não é caso isolado: é consequência direta de o `PROMPT_OLHO` mandar escrever "sem
  &lt;peça&gt; visível" e de o `sem` contar como radical. **RESOLVIDO em 18/09 pela
  hipótese do bigrama** (ver "Conserto de roteamento de 18/09/2026", logo abaixo de
  "COMECE POR AQUI") — não coube numa troca de sinal, era mesmo mudança estrutural no
  roteamento: `_radicais_negados` + `_proximidade_da_negacao`, em `pipeline.py`, fazem
  "sem" só contar como tendo negado o que vem depois DELE no sinal, e só se um "sem" de
  verdade estiver perto NO TEXTO. Medido contra os quatro sinais citados acima MAIS o
  quinto (a versão sem precisar do `sem`, via `_bigrama_proximo`): nenhum dos três riscos
  (`periferia_laje_sem_guarda_corpo`, `andaime_sem_guarda_corpo`, `rampa_passarela_irregular`)
  dispara mais contra o achado do guarda-corpo instalado.

  **Segunda instância, medida em 07/09 ao escrever a contraparte do conserto da grua — e
  ela cai justamente nos riscos de elevador que o #27 consertou.** O fato *"Grade
  metálica rígida parafusada **fechando por inteiro** o poço de elevador, **sem trechos
  abertos**"* — proteção instalada por inteiro — aciona três riscos:
  `"poco de elevador aberto"` a **1,00** em `vao_caixa_elevador_sem_fechamento` **e** em
  `poco_elevador_carga_sem_cercamento`, e `"poço aberto sem placa"` a 0,75 em
  `espaco_confinado_sem_sinalizacao` (NR-33, espaço confinado, numa foto de poço). O
  `abert` vem de "sem trechos **abertos**": não é o `sem` completando o sinal, é o
  **particípio da negação** virando o radical afirmativo que o sinal pede. É a mesma
  família e um mecanismo a mais — o conserto do #27 ancorou os sinais na abertura em vez
  de no `sem`, e a abertura também pode aparecer negada. **A hipótese do bigrama IMPLEMENTADA
  em 18/09 não cobre este caso** — e não por falta de janela: o mecanismo (`_radicais_negados`)
  só entra em jogo quando `"sem"` está no PRÓPRIO SINAL; aqui o sinal é afirmativo
  (`"poco de elevador aberto"`) e é o TEXTO do achado que nega com `"sem trechos abertos"` —
  não há negador nenhum para ancorar no sinal. Resolver isso exigiria o mecanismo inverso:
  quando o radical de um sinal afirmativo aparece no texto, checar se ELE está perto de um
  "sem" que o negue, mesmo sem o sinal pedir. Não implementado — é mudança de escopo maior
  (afeta todo sinal afirmativo, não só os que já têm "sem"), e o custo é imediato: são os
  cinco "com proteção" do lote de 12 que correm esse risco.
- **O Olho chama grua de "torre de elevador" — PROMPT MUDADO em 07/09, à espera de
  lote.** Medido em 05/09: 2 das 3 fotos do mesmo equipamento saíram como "Torre de
  elevador de obra" e a terceira como "grua"; o engenheiro confirmou que é grua. O
  `PROMPT_OLHO` lista "torre de elevador" entre os elementos de canteiro a nomear desde
  o #27, e ele passou a aplicar o nome a toda torre amarela. Consequência já impressa em
  laudo: `NR-18 18.11.14` (fechamento da base da torre do elevador) numa foto de grua.
  **Nome errado é fato falso, e o `fato` do Olho é justamente o que nenhuma trava do
  pipeline confere.**

  **O caminho não era o que se supunha, e isso mudou o conserto.** O risco curado
  `torre_elevador_sem_cancela` teve **zero disparos nas 9 fotos** — o item não veio da
  taxonomia. Veio da **busca textual**: medido sem rede, o fato *"Estrutura vertical
  treliçada amarela identificada como torre de elevador de obra, montada junto à
  fachada"* routeia **risco nenhum** e ainda assim enche o dossiê com **cinco itens da
  seção NR-18 18.11** (elevadores de obra). A palavra sozinha basta. Quem só medisse o
  roteamento — que é o reflexo desta casa — não veria o defeito que produziu o laudo.

  **O conserto é a regra da MOLDURA aplicada ao nome**, não ensinar o Olho a distinguir
  melhor: numa foto da base da torre nem a lança nem a cremalheira aparecem, e escolher
  entre os dois é adivinhar. O prompt agora dá os dois discriminantes (grua: lança
  horizontal e contrapesos; elevador de cremalheira: cabine que sobe pela própria torre,
  cremalheira dentada, cancela por pavimento) e manda escrever **"torre metálica
  treliçada"**, sem escolher, quando nenhum deles está no recorte. Medido nos dois
  sentidos: com o nome recusado, nem o risco nem a busca textual alcançam o 18.11; com o
  discriminante presente, o elevador de verdade continua chegando ao `18.11.13`/`18.11.14`.
  **O portão setorial do #35 fecha o mesmo caminho pelo lado da busca textual — mas só ele;
  ver a porta que sobra em "Em aberto".**
  A ressalva que a regra carrega: ela vale para a torre **no canteiro** e não para o poço
  (caixa, shaft) do elevador dentro da edificação — sem ela, a mesma frase calaria
  `vao_caixa_elevador_sem_fechamento`, que é o risco que o lote de poço existe para
  validar. Conferido: o dossiê do poço e o do shaft trazem `18.9.2`/`18.9.3`/`8.3.2.2` e
  NR-11 (o do poço traz ainda NR-33 e NR-01 — ver o achado do `sem` acima), e **nunca**
  `18.11`. **Há quatro testes travando isso**, e o custo declarado é o simétrico: uma
  torre de elevador de verdade fotografada só na base perde os dois itens do `18.11`.
  Mexe em todas as fotos — **só o lote diz se ele obedece**.

  **O `/critico` REJEITOU a primeira versão, e o gap era o defeito do #27 reintroduzido
  dentro do conserto dele.** A tabela de discriminantes punha `cabine` na coluna do
  ELEVADOR três linhas abaixo do exemplo — anterior a esta mudança, e mantido — que
  chama de GRUA uma *"estrutura metálica elevada de cor amarela, com cabine e
  contrapesos"*. E essa é exatamente a frase que o modelo escreveu para a grua em
  produção, no lote de içamento. Duas regras competindo no mesmo prompt, sobre a palavra
  que o modelo de fato usa, é como o defeito do #27 nasceu — e a versão 1 deste conserto
  o repetia. Hoje o prompt resolve o conflito em vez de o criar: a cabine sozinha não
  decide nada (a grua também tem uma), o que decide é **onde ela fica** — no topo, junto
  da lança, é grua; correndo pela torre, é elevador; e se a foto não mostra qual das
  duas, cai na regra da moldura. **Há teste travando as duas metades.**
- **A constatação hipotética passa pelo Diretor.** Duas das seis NCs do lote de 05/09
  não afirmam um fato, afirmam uma possibilidade sobre uma proteção que existe: *"a
  malha **pode não** impedir a queda de objetos pequenos"* e *"manchas de oxidação
  **indicando possível** comprometimento da integridade estrutural"*. O Diretor aprovou
  as duas (aparou a metade mais forte de cada). Ele não erra a conferência: o fato-âncora
  existe mesmo — a grade existe, a ferrugem existe. O que passa é o **salto** do fato
  para a hipótese, e nada no pipeline olha para ele. A regra da moldura cobre afirmar
  que algo NÃO existe; não cobre afirmar que algo que existe PODE falhar. Conserto
  candidato: uma regra na PARTE 2 do `PROMPT_DIRETOR` vetando constatação cujo núcleo é
  uma possibilidade sobre proteção instalada. É mudança de prompt de agente — vale lote.
  **Cuidado ao escrevê-la**: "pode causar queda" é a *consequência*, que é legítima e
  fica em campo próprio; o que se veta é a possibilidade dentro da CONSTATAÇÃO.

  **ESCRITA em 07/09, à espera de lote.** É a cláusula (d) da PARTE 2, e o teste que ela
  dá ao Diretor é mecânico como o resto da conferência: risque da constatação toda
  palavra de hipótese ("pode", "poderia", "possível", "eventual", "sujeito a",
  "indicando", "não se pode garantir") e leia o que sobra — se o que sobra é proteção
  instalada em estado normal, vete. Os dois casos reais estão escritos na cláusula, com
  a razão de a Parte 1 os aprovar (o fato-âncora existe; o que não existe é o defeito).
  A fronteira entrou junto e é o que impede a cláusula de virar veto geral: o exemplo
  "abertura no piso, que pode causar queda" está lá como o que **não** se veta. **Não há
  como conferir isto por código** — `_exigencia_ancorada` confere o trecho que o Diretor
  copia no campo `exigencia` contra o texto do item, e a constatação nunca entra nessa
  comparação; aqui, além disso, o item e o fato estão ambos certos, e o que é falso é o
  salto entre eles.
  **Há teste travando as duas metades da cláusula**, a que veta e a fronteira.

  **A cláusula se anuncia mecânica e tem UM passo de julgamento**, achado ao rodar o
  `/critico`: o teste final é "o que sobra é proteção instalada em **estado normal**?", e
  isso não é cópia, é avaliação. O caso que ele erraria já custou caro — a **tela
  plástica frouxa na borda da laje** é o falso negativo mais caro do lote de 29/08, e uma
  constatação do tipo *"a tela pode não resistir ao impacto"* teria, ao risco da hipótese,
  o resto lido como "tela instalada na borda" e viraria veto: a **classe de erro 5** pela
  porta que a própria correção abriria. Por isso "estado normal" ficou definido dentro da
  cláusula — íntegro, **do tipo certo e no lugar certo** —, com a tela frouxa nomeada como
  o que NÃO é estado normal. **Há teste travando as duas asserções.** O que continua sem
  resposta é se a definição basta: é julgamento num prompt, e só o lote diz.
- **Contexto POR FOTO: medido em 08/09, implementado em 09/09 (o desenho D), e
  VALIDADO no lote de 09/09 — com uma ressalva que virou conserto.** O usuário perguntou
  se descrever o que vê em cada foto ajudaria o enquadramento. Hoje o campo "Contexto da
  inspeção" é **um só para o lote inteiro** (`app.py:408`) e alcança TRÊS consumidores:
  o Olho (`pipeline.py:375`), o roteamento (como `extra` colado em cada fragmento) e a
  busca textual (dentro do `blob` que alimenta `_pontuar_nrs` e os portões). Medidos
  quatro desenhos sobre os fatos reais das 15 fotos, com um contexto plausível por foto e
  o item que o engenheiro esperaria como gabarito (10 das 15 têm item esperado):

  | braço | esperado | posição média | riscos | dossiê | ruído |
  |---|---|---|---|---|---|
  | **A** hoje (sem contexto) | 8 de 10 | D1,0 | 18 | 126 | 21 |
  | **B** prosa no campo atual | 9 de 10 | D2,7 | 31 | 142 | 29 |
  | **C** fragmento próprio, fora dos portões | 8 de 10 | D1,0 | 23 | 142 | 32 |
  | **D** marcado numa lista de riscos | **10 de 10** | **D1,0** | 20 | 129 | **21** |

  ("ruído" = itens de NR-12/33/15/17/11/09/32 num lote de poço e grua.)

  **A prosa livre (B) não compensa**: +1 acerto contra +72% de riscos roteados, +8 de
  ruído, e o item certo caindo de D1 para D2,7 — encher o dossiê e empurrar o item certo
  para baixo é a classe de erro 1 pela porta do "dossiê pobre força escolha ruim". O ruído
  caiu em 2 fotos, subiu em 7, ficou igual em 6.

  **O desenho C foi proposto com confiança e REPROVADO pela própria medição.** A hipótese
  era que o ganho vinha do roteamento, e que bastava isolar o contexto num fragmento
  próprio e tirá-lo dos portões. Medido: `abertura_piso_desprotegida` **não dispara nem
  com o contexto** — o `18.9.2` do laudo 15 chegou pela BUSCA TEXTUAL, alimentada pelo
  `blob` que inclui o contexto. O C cortava exatamente esse caminho, então não entrega
  nada e ainda é o mais ruidoso dos quatro. **Medir antes de construir foi o que pegou.**

  **A lista marcada (D) domina os outros três ao mesmo tempo**, o que é raro aqui: 10 de
  10, item sempre em D1, **ruído idêntico ao de hoje**, e as 5 fotos sem marcação saem
  byte a byte iguais. As duas que o app perdia — `PROTEÇÃO POÇO DE ELEVADOR SOMENTE COM UM
  PONTO DE FIXAÇÃO` e o laudo 15 `19 PAV. POÇO GRUA SEM PROTEÇÃO` — são exatamente as que
  ela recupera. A lista sai da taxonomia que já existe: **40 riscos de construção sem
  exigir pessoa na cena**, dos quais ~15 cobrem o uso do engenheiro.

  **O custo, medido**: marcar por engano `abertura_piso_desprotegida` no `GRUAAA` põe
  `NR-18 18.9.2` em D1, curado, numa foto de grua onde hoje **nenhum caminho** leva esse
  item. A trava que sobra é o Diretor exigir o trecho literal do fato do Olho — e o #34
  mostrou que ela também falha por omissão. **Isso muda a natureza do app**: hoje ele é um
  segundo olhar independente; com a lista passa a ser parcialmente dirigido, e o erro pode
  ser do engenheiro, entrando na posição mais forte do dossiê.

  **Uma armadilha prática que a medição achou**: escrever `"sem achado"` no contexto de uma
  foto boa **aciona risco**. Na `GRUA`, `"grua do canteiro, vista do topo, sem achado"`
  dispara `andaime_sem_guarda_corpo` e `rampa_passarela_irregular` — sem andaime nem
  passarela na cena. Tirando o `"sem achado"`, zero riscos; `"tudo conforme"` também é
  seguro. É a armadilha do `sem`, agora vinda da caneta do engenheiro — e o formato natural
  de anotação de vistoria ("sem proteção", "sem sinalização") é o pior caso para o roteador.
  Vale para qualquer campo de texto livre que se acrescente ao app.

  **Duas travas de desenho para quem implementar**, e uma terceira que foi levantada e cai:
  1. **A marcação NÃO vai ao Olho.** Ele continua descrevendo às cegas. Se o contexto
     chegar nele, ele escreve o que lhe disserem — veja ou não —, o `fato` vira eco do
     que o engenheiro digitou, e a conferência do Diretor contra os fatos fica circular.
     É a classe de erro 3, e é o que hoje protege contra o clique errado.
  2. **Nunca ler o nome do arquivo automaticamente.** É a tentação óbvia (zero trabalho, o
     dado já existe em 138 das 253 fotos), e queimaria o gabarito inteiro: se o que o
     engenheiro escreve virar entrada, "o app acertou" passa a significar "o app repetiu o
     que eu disse". Campo separado, preenchido de propósito.
  3. ~~Item marcado entra sem o rótulo do risco, para não empurrar o Analista~~ —
     **levantada e derrubada na conferência**: `Entrada.linha()` monta
     `[D<n>] <nr> <item> — <resumo>` e **não inclui o `origem`**. O rótulo do risco nunca
     chega ao Analista; ele é usado só em `aferir()` (gravidade base, portão de pessoa,
     nome da NC). O que empurra é a POSIÇÃO no dossiê, não o rótulo — não há trava a
     escrever aqui.

  **O que foi construído (09/09), e o que sobrou para o lote decidir.** `riscos_marcaveis()`
  em `riscos/__init__.py` devolve os **40** riscos ofereciveis; `montar_dossie` ganhou
  `marcados`, que põe os riscos apontados **na frente** dos roteados, e `executar` os
  repassa sem tocar no `agente_olho`. Na interface é um expansor com um `st.multiselect`
  por foto, entre a lista de fotos e o botão de executar. **São onze testes novos**, dos
  quais quatro travam as travas de desenho — a marcação ausente do prompt do Olho, a foto
  sem marcação idêntica à de hoje, o portão de pessoa continuando a valer para o risco
  marcado, e a lista não oferecendo o que aquele portão descartaria. Os outros sete medem
  a posição no dossiê, a robustez a id desconhecido e a declaração nos dois documentos.

  **O `/critico` REJEITOU a primeira versão, e o gap era a armadilha do corte aplicado a
  um campo só, com dois DOCUMENTOS no lugar de dois campos.** A marcação era declarada na
  trilha do laudo por foto e **não** no sumário executivo — que é o documento que o
  engenheiro entrega, e cujo plano de ação lista a providência como linha solta, longe do
  laudo de origem. O commit argumentava que "sem essa linha dirigir o dossiê seria
  invisível no documento que vai ao cliente" e deixava exatamente isso no outro documento.
  Hoje `consolidado()` traz a contagem de imagens dirigidas, a lista nominal com o risco
  apontado, e a marca `*(apontada)*` na linha do plano de ação. **Há dois testes travando
  as duas metades**, e a pergunta que o gap deixa para o próximo campo: ao declarar algo
  no laudo, pergunte por qual outro documento o mesmo conteúdo chega ao mesmo leitor.

  **Três decisões que a medição não cobre**, tomadas no desenho e não medidas:
  1. **Teto de três marcações por foto.** Os itens marcados entram primeiro num dossiê de
     22 entradas, então marcação em massa expulsa o roteamento e a busca textual inteiros
     — o app pararia de auditar a foto e passaria a devolver a lista que lhe deram. Três é
     acima do que o acervo mostra por foto (o nome de arquivo nomeia um achado, às vezes
     dois: `3 PAV. POÇO ELEVADOR SEM PROTEÇÃO E SINALIZAÇÃO`). **Quantas marcações por
     foto o braço D usou não ficou registrado**, então o teto não tem medição por trás:
     é aritmética de dossiê, não resultado.
  2. **A lista é só de construção.** Os 43 riscos de indústria e os 38 de ambiental ficam
     de fora: num app de canteiro eles encheriam a lista de vocabulário de fábrica, e
     lista que ninguém lê inteira é lista em que se marca por engano. O custo é não poder
     marcar risco genuinamente industrial que apareça numa obra.
  3. **Risco que exige pessoa não é ofereciável.** O portão `exige_pessoa` de
     `montar_dossie` continua valendo para o marcado, então um risco de EPI marcado numa
     foto sem ninguém seria descartado **em silêncio** — o inspetor clica e nada acontece,
     sem uma linha no laudo explicando por quê. Melhor não oferecer.

  **RESULTADO DO LOTE (09/09), n=2 marcações.** A cadeia marcação → dossiê → Analista
  fechou: na foto marcada certa o Analista enquadrou os dois itens corretos, e quem os
  derrubou foi o Diretor, por não copiar a exigência (ver a seção de validação de 09/09 e
  a repescagem que ela motivou). Na foto marcada ERRADA de propósito, o item curado em D1
  não virou enquadramento nenhum. As treze sem marcação saíram como sairiam.
  **O que ainda não foi testado é a segunda foto que o desenho D recuperaria** —
  `PROTEÇÃO POÇO DE ELEVADOR SOMENTE COM UM PONTO DE FIXAÇÃO`, que não foi marcada neste
  lote e segue com o achado do engenheiro (fixação precária) não encontrado.

  **O critério de aceite do lote se lê na TRILHA do laudo, não nas não conformidades.** A
  linha "Risco(s) apontado(s) pelo inspetor" declara toda marcação, e é ela que separa o
  laudo dirigido do laudo em que o app chegou sozinho ao item — a distinção que o valor de
  evidência do documento depende. O que vigiar: (a) nas fotos marcadas, se o item marcado
  aparece na NC ou se o Analista o ignora, que é a única coisa que a reprodução sem rede
  não responde; (b) nas fotos marcadas ERRADO de propósito, se o Diretor derruba — a única
  trava contra o clique errado é ele exigir o trecho literal do fato do Olho, e o #34
  mostrou que ela falha por omissão; (c) nas fotos sem marcação, que o laudo seja o de
  hoje.
- **A não conformidade que é uma VERIFICAÇÃO — cláusula (e) MEDIDA em 10/09, aceite
  parcial.** Nas 30 execuções do lote de variabilidade a forma que a cláusula proíbe
  (a constatação sendo `"Verificar no local se…"`) **não voltou uma vez sequer**. Mas na
  passada B a mesma foto produziu o enquadramento outra vez, **reformulado**: a
  constatação virou afirmação ("a base está apoiada diretamente no piso, sem evidência
  visual de travamento"), o "verificar" foi para a ação corretiva, onde é legítimo, e a
  gravidade caiu de crítica para alta. Na passada A ele foi vetado. **A cláusula matou a
  FORMA e não o enquadramento**; contra a versão reescrita quem age é a regra da moldura,
  que pegou numa passada e não na outra. O histórico abaixo fica porque é ele que nomeia
  o caso. `11 PAV. PROTEÇÃO POÇO ELEVADOR SEM PROTEÇÃO` saiu duas vezes no mesmo dia com
  a providência "Verificar no local se a grade metálica possui travamento" como **não
  conformidade** — na segunda vez CRÍTICA, prazo de 1 dia, cobrando em 24 horas uma ida
  ao local. n=2 com escalada de alta para crítica.
  O mecanismo é a regra da moldura aplicada até a metade: o Diretor apara a afirmação
  categórica (certo — a fixação não aparece no recorte) e mantém o enquadramento, quando
  o que restou já não afirma descumprimento nenhum. O prompt sempre mandou escrever a
  verificação em `observacao`; o que faltava era dizer que, nesse caso, **não sobra nada
  para aparar**. É a cláusula (e) da PARTE 2, com o caso real dentro.
  **A fronteira é o que impede a classe de erro 5**, e foi escrita junto: falta que a foto
  MOSTRA é afirmação, não verificação — borda de laje que aparece inteira, abertura
  escancarada, **tela plástica frouxa na borda** (o falso negativo mais caro do histórico,
  nomeado na cláusula). E o teste é sobre a CONSTATAÇÃO, nunca sobre a ação corretiva, que
  legitimamente pode mandar verificar o resto. **Há dois testes travando as duas metades.**
  **Não há conserto por código aqui**, e isso foi decidido, não esquecido: detectar
  "verificação" por texto livre é a armadilha do sinal escrito por extenso mudada de
  lugar, e a moldura é `motivo de aparo, nunca de veto sozinha` justamente para o aparo
  não virar veto geral. O aceite se lê na lista de VETADOS e nos pontos de atenção.
- **Uma abertura, duas NCs, por um par que `ITENS_EQUIVALENTES` não cobre.** Laudo 11 de
  09/09 conta a mesma abertura em `NR-18 18.9.1` (proteção coletiva, genérico) e
  `NR-18 18.9.2` (fechamento da abertura). A fusão declara só `18.9.2`/`8.3.2.2`. **Não é
  o mesmo caso**: `18.9.1` e `18.9.2` são da MESMA NR e não impõem a mesma exigência —
  um manda proteger o entorno, o outro fechar o vão. Declará-los equivalentes seria
  mentira; o que cabe medir é se o Analista devia enquadrar os dois.
- **~~Dois defeitos no texto do aparo~~ — um consertado, o outro não existia.** O laudo 3
  de 09/09 declarou aparo dizendo que **nada** foi removido e a linha saiu impressa na
  trilha; hoje o aparo cuja constatação volta idêntica não vira linha nenhuma. O segundo
  eu diagnostiquei errado: `_em_poucas_palavras` marca o corte com reticência, medido.
  **Fica a lição**: eu afirmei "corta sem marcar" olhando o laudo, e a função executada
  desmentiu em dois segundos. Defeito de saída de código se confere rodando o código,
  não lendo o produto dele.
- **A foto 1 foi ABERTA em 10/09, e o defeito é do Olho, não do Diretor. Ele errou o
  MATERIAL da barreira.** O engenheiro respondeu que não há buraco no chão, e o acervo de
  fixtures foi anexado à sessão para ler a imagem. O que ela mostra: o poço de elevador
  **cercado por dois painéis de tela metálica expandida em quadro de aço**, enferrujados,
  formando um canto, com a foto tirada rente ao plano de um deles. Não há abertura de
  piso, e a proteção do poço está instalada — o que bate com o nome do arquivo, que não
  aponta defeito.
  **O primeiro fato do Olho é falso**: *"Painel rígido de madeira de cor marrom, com
  superfície áspera e marcas de desgaste, posicionado verticalmente e apoiado contra a
  estrutura de concreto, sem fixação visível"*. É metal, não madeira; a cor marrom é
  ferrugem e a "superfície áspera" é a malha expandida vista de perfil. **É a terceira
  classe de erro do Olho, e ela é nova**: as anteriores eram o NOME do equipamento (grua
  chamada de torre de elevador) e a OMISSÃO (a abertura de piso não registrada no laudo
  15 de 08/09). Errar o MATERIAL de uma barreira é pior que as duas, porque o
  `PROMPT_OLHO` exige justamente material, rigidez, fixação, continuidade, altura e
  estado — ele respondeu o campo e respondeu errado, e **nenhuma trava do pipeline confere
  o `fato`**.
  **O dano não é no dossiê — medido.** Reescrito o fato com o material certo, o
  roteamento é o mesmo (`abertura_piso_desprotegida` + `abertura_parede_desprotegida`) e
  `NR-18 18.9.2` continua em D1. O dano é na CONSTATAÇÃO: foi "madeira apoiada sem
  fixação" que deu ao Analista da passada B a frase "não constituindo fechamento
  provisório travado ou fixado à estrutura", com que ele enquadrou o item de piso.
  **A CAUSA RAIZ do `18.9.2` em D1 é um sinal, e ele é uma armadilha NOVA.** Medido: o
  único sinal que dispara `abertura_piso_desprotegida` nesta foto é `"abertura no piso"`,
  com cobertura 1,00 e âncora 2, no fato *"**Piso** de concreto com aspecto áspero e
  irregular, visível na parte inferior da **abertura** ao fundo"*. Os dois radicais vêm do
  MESMO achado, então a âncora de 01/09 é satisfeita — **e a relação entre eles é a
  inversa da que o sinal descreve**: o fato fala do piso visto pelo pé de um vão
  VERTICAL, não de uma abertura no piso. A âncora protege contra radicais vindos de
  achados diferentes; não protege contra "X no Y" casando "Y … da X". Não é a armadilha
  do `sem` nem a do ambiente: é uma terceira, e a hipótese do **bigrama** já registrada
  para o `sem` cobriria as duas (exigir adjacência entre `abertur` e `piso`). É mudança
  estrutural no roteamento e **só um lote valida** — não se faz reagindo a uma foto.
  **Implementada em 18/09** (`_bigrama_proximo`, ver "Conserto de roteamento de
  18/09/2026"): este achado exato não routeia mais `abertura_piso_desprotegida`.
  **A conta do Diretor fica em 1 de 4.** O `18.9.2` saiu nos dois laudos de 09/09 e na
  passada B de 10/09; só na passada A ele foi vetado, com a razão exata ("o item regula
  especificamente aberturas no piso"). O texto que veta já está no prompt e ele o executa
  às vezes — **cláusula nova não é o conserto**, e agora se sabe que o conserto de raiz
  está um nível antes, no sinal.
  O caminho do defeito em 09/09, que continua valendo como registro: o aparo retirou a
  referência ao vão vertical — com a razão certa, "a norma regula especificamente
  aberturas no piso" — e **manteve o enquadramento**. É a classe de erro 1 pelo caminho
  do aparo: ele corta o que não tem lastro e não pergunta se o que sobrou ainda descumpre
  AQUELE item. **Em 10/09 o aparo do laudo B01 fez exatamente isso de novo, palavra por
  palavra.**
  **E a passada A também erra esta foto**, o que só a imagem mostrou: o `NR-08 8.3.2.2`
  dela afirma que a abertura *"não possui proteção que impeça a queda de pessoas ou
  objetos"*, e a proteção está lá. O que existe é a fresta de montagem entre o painel e o
  pilar, por onde se vê o interior do poço — estreita, e não é o que o item cobra.
- **AUDITAR A FOTO CONTRA OS FATOS, e contar — combinado em 11/09, a rodar no lote misto.**
  O `fato` do Olho é o único ponto do pipeline que ninguém confere, e em 10/09 isso custou
  seis sessões de diagnóstico no lugar errado. A partir do próximo lote, quem confere é a
  leitura da imagem aqui. **O desenho importa mais que a ideia, e a primeira versão dele
  estava errada:**
  1. **A leitura é CEGA.** Descrever a foto ANTES de ler os fatos do Olho, e só então
     comparar as duas listas. Ler primeiro e olhar depois é conferir com a resposta na
     mão — foi assim que eu afirmei, em 10/09, que ele tinha confundido as tábuas do piso
     com um painel vertical, hipótese que o primeiro recorte da imagem desmentiu.
  2. **Amostra dirigida, não exaustiva.** As fotos cujo laudo não fecha contra o nome do
     arquivo, mais duas ou três de CONTROLE sorteadas entre as que fecharam. O controle é
     o que pega o laudo certo pelo motivo errado, que é literalmente a passada A na foto 1
     de 10/09. Auditar as 15 produz dezenas de divergências sem valor, porque o Olho
     recebe a foto reduzida e tem 900 tokens de saída, e a lista longa afoga o achado.
  3. **A auditoria NÃO é gabarito.** Onde a leitura da imagem muda um enquadramento, isso
     vira uma pergunta curta ao engenheiro, nunca uma conclusão.
     **E a resposta dele tem TRÊS valores, não dois — achado de 12/09.** Sobre a escada da foto 1
     ele respondeu *"não consigo ver se tem sapata"*, e essa é a resposta mais útil das três para a
     regra da moldura: se quem esteve na obra não decide pela foto, o app que decidiu emitiu
     enquadramento sem lastro visual, e o caso é da cláusula (e), não do gabarito. **Pergunte
     sempre que a NC depender de uma peça no limite do recorte** — custa a mesma linha e dá um
     critério externo, que não depende do meu julgamento sobre o que a imagem mostra. Ele viu a obra; a imagem
     é um recorte dela. Sem essa regra, o gabarito ganha uma segunda fonte que é um modelo
     julgando outro, e ninguém acima — a mesma estrutura que a regra "nunca ler o nome do
     arquivo" existe para impedir, contaminando pelo outro lado.
     **A REGRA 3 TEM UMA PREMISSA, E EM 13/09 ELA CAIU PARA O ACERVO HISTÓRICO.** A premissa
     está escrita duas linhas acima: *ele viu a obra*. Perguntado sobre as seis do lote de
     içamento e cancela, o engenheiro respondeu que **não tem a memória daquele dia** — o que ele
     vê é a foto, igual a mim — e autorizou que eu validasse o que a imagem permite. Então, para
     as **351 imagens** do acervo, **não existe árbitro**: continuar formulando perguntas é gastar
     rodada com quem tem menos informação que a imagem, e tratar a minha leitura como gabarito
     por falta de alternativa é a regra 3 furada pela porta de trás. A regra que vale daqui em
     diante, e ela é mais estreita de propósito:
     **(a)** a imagem decide o que é GEOMÉTRICO ou de PRESENÇA — objeto no recorte, posição,
     folha no plano ou girada, piso contínuo ou interrompido —, porque isso se amplia e se
     mostra, e o recorte fica no repositório;
     **(b)** a imagem NÃO decide MATERIAL, NOME próprio de equipamento nem ESTADO de
     funcionamento, que são as três classes de erro que este arquivo registra no Olho e que a
     minha leitura corre igual — ali a resposta fica **ABERTA**, e não conta nem contra o app nem
     a favor dele;
     **(c)** onde a imagem não decide, a consequência é a **cláusula (e)**, não o silêncio: uma NC
     que dependa daquela peça é enquadramento sem lastro visual, que é a terceira resposta de
     12/09 virada em procedimento;
     **(d)** para lote NOVO, fotografado agora com o engenheiro em campo, a regra 3 continua
     inteira — o que mudou vale para o acervo, que é de onde saem todos os lotes deste arquivo.
     **E a regra (b) foi exercida sobre mim no mesmo dia**: a ampliação derrubou duas leituras
     minhas do pré-registro — "duas cancelas fechadas" na foto 3 (a da esquerda está aberta) e
     "a vegetação sugere nível de embarque" na foto 4 (a imagem não decide a altura). Ver a seção
     5 do pré-registro, que é onde as seis respostas moram.
  **O produto não é a lista de divergências, é a CONTAGEM por classe de erro do Olho.**
**MEDIDA pela primeira vez em 11/09 e FECHADA em 13/09, no lote de máquina: 7 divergências
  confirmadas em 30** — cinco pelo engenheiro, duas pela geometria da imagem depois de ele
  declarar que não tem a memória do acervo, e **2 linhas permanentemente ABERTAS** porque são
  MATERIAL e NOME, que a regra (b) não deixa decidir (a seção 6 da validação de 11/09 lista as
  cinco cópias deste número, esta inclusive). As classes eram três, uma por lote — o NOME do equipamento
  (grua chamada de torre de elevador, 05/09), a OMISSÃO de um achado (a abertura de piso do
  laudo 15, 08/09) e o MATERIAL da barreira (metal chamado de madeira, 10/09) —, e o lote de
  máquina acrescentou o **VÃO INEXISTENTE**, confirmado, que fabricou sozinho uma NC inteira,
  mais a FORMA/ORIENTAÇÃO e a POSIÇÃO, ainda candidatas.
  **O VÃO INEXISTENTE é a classe mais cara do histórico** porque não erra um atributo de um
  objeto real: cria o objeto, com a propriedade de risco embutida no nome, e nenhuma trava
  do pipeline pergunta se ele existe.
  **CONFIRMADO PELA SEGUNDA VEZ em 12/09, noutro domínio**: na foto 3 do lote de elétrica o Olho
  escreveu "abertura retangular no piso, com bordas de concreto" e o engenheiro respondeu que
  não há abertura ali. A única NC daquele laudo saiu crítica, com prazo de 1 dia. Dois lotes
  seguidos, dois falsos positivos inteiros, e o mesmo caminho nos dois: risco curado, item em
  D1, Analista enquadra, Diretor aprova sem veto nem aparo. **Deixa de ser achado de um lote.**
  **E a regra 3 ganhou a validação que faltava, pelo pior caminho possível: a leitura de
  imagem feita aqui errou 2 das 7 respostas, e uma delas INVENTOU um achado** — "lâmina
  exposta sem coifa" numa serra que tem coifa, que é a mesma classe de erro que a auditoria
  estava medindo no Olho. Tratada como gabarito, ela teria acrescentado uma NC de NR-12
  falsa ao laudo. **Auditoria de imagem é pergunta, nunca veredito**, e agora há número por
  trás disso.
  **TERCEIRA OCORRÊNCIA em 15/09, numa variante nova, e desta vez SEM engenheiro a
  confirmar.** No lote de ESCADA, a foto 4 (a contraparte, desenhada para dar 0 NC)
  recebeu `NR-18 18.9.2` crítica sobre "abertura vertical no piso, com bordas de
  concreto, localizada ao lado da grade metálica". Aberta a foto, pela leitura geométrica
  de quem escreve este registro (é acervo histórico, sem árbitro humano — a régua (a)-(d)
  é o que autoriza tratar isso como decidido): não é um vão fabricado do zero como nas
  duas ocorrências anteriores, as duas confirmadas pelo ENGENHEIRO — é uma **junta de
  dilatação de concreto real, ínfima, inflada** para "abertura sem proteção contra
  quedas". A classe cobre as duas variantes: cria o objeto
  do zero, ou infla um objeto real até ele carregar a propriedade de risco que não tem. Ver
  a validação de 15/09, seção 2.
  **As omissões mexem no outro sentido**: confirmadas, não mudam a contagem de fatos errados,
  mudam o que o LAUDO deixou de reportar — e é lá que está o dano ao cliente. Neste lote deu
  **duas confirmadas** (a serralheria sem barreira de acesso e o vão de acesso ao poço da
  âncora) e uma refutada, com as sete perguntas todas respondidas.
  **A segunda só ficou respondível depois de a foto ser aberta aqui**, porque a pergunta
  confundia dois elementos da mesma cena: a grade que o Olho registrou está à direita e
  encostada, e o vão sem proteção está à esquerda. **Quem escrever a próxima leva abra as
  imagens ANTES de perguntar** — perguntar sobre um objeto que a lista de fatos não localiza
  gasta uma rodada com o engenheiro. **Taxa medida num domínio só
  não generaliza**, e por isso o próximo lote de 5 (elétrica) mede a mesma coisa noutro
  vocabulário; é a comparação que diz se 30% é do app ou daquelas fotos.
- **Separar a fase de VISÃO da fase de ENQUADRAMENTO — proposto e REJEITADO por enquanto,
  em 11/09.** O engenheiro propôs descrever cada foto ao subir, para o Olho complementar em
  vez de adivinhar. A ideia ataca o buraco certo, e é o único que sobrou: a marcação por
  lista dirige o dossiê e **não** recupera achado que o Olho não viu. O desenho que
  absorveria a proposta é maior que ela — rodar o Olho no lote inteiro, mostrar as listas de
  fatos, deixar o engenheiro corrigir ou acrescentar, e só então rodar Analista e Diretor,
  **com a origem marcada em cada fato** (observado pelo modelo / declarado pelo inspetor).
  Isso resolve as duas metades: quem já sabe descreve antes, quem viu erro corrige depois,
  e a evidência do laudo continua rastreável. Sem a origem por fato o documento deixa de
  ser um segundo olhar, porque a conferência do Diretor passa a rodar contra o que o
  inspetor digitou.
  **Por que não agora, e o gap é o que este arquivo cobra de toda mudança de prompt**: são
  TRÊS casos medidos. Mexer na arquitetura por n=3 é fazer, um nível acima, o que aqui se
  proíbe para uma cláusula. E a proposta assume um comportamento nunca observado, que é o
  engenheiro ler 100 listas de fatos; o padrão dele é subir as fotos e voltar com os laudos.
  **A contagem do item acima é o que decide**: taxa alta paga a fase separada, taxa baixa
  diz que o conserto é outro.
  **A contagem fechou em 13/09 — 7 divergências confirmadas em 30, com 2 linhas
  permanentemente abertas — e ela NÃO decide sozinha, porque parte do erro fica fora do alcance
  da proposta.** O que ela
  recupera tem agora caso medido, e ele é mais estreito do que eu escrevi duas vezes: o que
  move o dossiê é o ACHADO declarado como fato, não o nome do objeto. Medido em duas fotos.
  Na 2, nomear o `policorte` traz item de rampa e de plataforma condutiva, enquanto escrever
  "área de corte sem barreira, cerca ou isolamento" dispara um risco curado e põe a família
  da área de carpintaria em D5 e D6 — **e nem assim a NC perdida fecha**, porque o item que a
  cobriria de frente não existe ao alcance (ver o item em aberto sobre a área de corte sem
  isolamento). Na 5 ela fecha: uma frase sobre o vão de acesso põe `NR-11 11.1.1` e `11.1.2`
  curados em D3 e D4 e traz o `18.9.3`, que sem o fato **não está no dossiê**. **Dois casos,
  e só um deles a arquitetura resolve sozinha** — o outro depende de cobertura de item. O
  que ela não alcança é o **VÃO INEXISTENTE** da foto 3: nada no desenho manda conferir fato
  a fato o que o modelo escreveu, e foi dele que saiu o falso positivo confirmado do lote.
  **Os dois lados têm caso medido e apontam para desenhos diferentes** — contra o que o Olho
  não vê e não nomeia, a fase separada basta; contra o que ele INVENTA, só a confirmação
  fato a fato, que é o que a proposta não inclui. Antes de pagar a arquitetura, vale
  perguntar se o barato é mostrar a lista de fatos para CONFIRMAÇÃO, não só para complemento
  — e este lote é a primeira evidência de que a confirmação é a metade que falta.
  **O lote de elétrica acrescentou um caso NOVO de nome errado, e ele é de outra espécie**: na
  foto 4 o Olho chamou de *"tambor cilíndrico de cor azul, possivelmente um compressor de ar"* o que
  o engenheiro confirmou ser **um galão de água**, e isso levou `NR-13 13.5.1.3` e `13.5.1.4` — placa de
  identificação de VASO DE PRESSÃO — a D1 e D2. Nas medições anteriores o nome errado custava
  item impertinente dentro da mesma família; **aqui ele trocou a NORMA inteira**, e num objeto
  secundário da cena. É argumento a favor da confirmação fato a fato, não do complemento.
  **O argumento da coifa MORREU, e vale registrar como**: a redação anterior deste item
  dizia que a pergunta da coifa era a que mais movia a decisão, porque confirmada faria da
  foto 1 o caso completo. O engenheiro respondeu que a serra TEM coifa. O caso completo é a
  foto 2, e a lição é a da regra 3 — o achado que sustentava o argumento era leitura de
  imagem não confirmada.
  **Dois dados medidos em 11/09 que a decisão vai precisar:**
  - **A imagem chega MENOR do que se supunha.** `app.py:93` faz `img.thumbnail((896,896))`,
    que ajusta pela MAIOR dimensão. Uma foto retrato de 899x1599 chega ao Olho com **504 de
    largura**, 56% do original. Recriado o recorte do "painel de madeira" nessa escala: a
    malha metálica ainda aparece, mas fraca, e o que domina é a cor ferrugem — que é a cor
    de madeira envelhecida. **O erro de material não foi descuido, foi limite de leitura**,
    e isso é o que torna o conserto por prompt pouco promissor ali. O caminho alternativo
    (1024px, que a barra lateral já oferece) morde a cota e nunca foi medido contra erro
    de fato.
  - **O campo `confianca` do `Achado` existe e NUNCA é lido.** `pipeline.py:45` o declara,
    o Olho o preenche em todo achado, e não há um único uso no projeto. É instrumento
    pronto e desligado: achado de baixa confiança poderia entrar como ponto de atenção em
    vez de base de enquadramento, sem custar chamada nenhuma.
- **A `cancela` entrega os itens de elevador sem passar por portão nenhum** — **em parte FECHADO em
  26/09**: `"cancela aberta"` saiu (ver a seção "Cancela aberta no embarque"); os três sinais de
  cancela que sobram (`ausente|faltando|quebrada`) seguem sem exigir `elevador`, e o resto deste item
  continua valendo para eles. Achado pelo
  `/critico` no #35, e **medido**: os filtros do `dossie.py` valem só para a recuperação
  textual — item de risco CURADO entra por `montar_dossie` e não passa por
  `setor_pertinente`. E quatro dos sete sinais de `torre_elevador_sem_cancela` são
  `"cancela aberta|ausente|faltando|quebrada"`, que **não exigem `elevador`** (só os de
  torre e base exigem, desde o #27). Reproduzido: a cena *"Cancela metálica vermelha aberta
  no acesso"* + *"Torre metálica treliçada amarela de canteiro, com a base aberta"* — torre
  deliberadamente SEM nome, como o #32 ensinou o Olho a escrever — routeia
  `torre_elevador_sem_cancela` e entrega `NR-18 18.11.13` e `18.11.14` em D1 e D2. **É a
  mesma porta da classe de erro 1 que produziu o laudo 7 de 05/09**, agora pelo caminho
  curado. Não foi consertado no #35 de propósito: exigir `elevador` nos sinais de cancela
  reduz cobertura justamente onde o risco finalmente passou a funcionar, e é decisão que só
  um lote valida — não se faz reagindo a um crítico. **O que primeiro se mede**: com que
  frequência o Olho escreve "cancela" numa cena que não é de elevador. No lote de içamento
  ele chamou de "Grade metálica … pintada de vermelho, aberta" e não de cancela; depois do
  #32 ele nomeia mais.
  **O pré-registro de 13/09 acrescentou um segundo caminho, medido, e ele não precisa da
  palavra `cancela`:** com o achado dizendo *"Torre do elevador de obra … instalada junto à
  fachada"* e o ambiente dizendo *"vão de fachada aberto"*, o sinal `torre do elevador aberta`
  casa a **1,00 com âncora 2** — `torr` e `elevador` do achado, `abert` do AMBIENTE — e os
  mesmos `18.11.13`/`18.11.14` vão a D1 e D2 curados, numa cena de cancela INSTALADA E
  FECHADA. Os sinais de torre exigem `elevador` desde o #27, e isso não os protege: quem
  fornece o radical que discrimina é a cena, não o achado. Tirada a palavra "aberto" do
  ambiente, o risco cala. É a mesma família da âncora, pela variante do AMBIENTE (ver a
  seção do lote de içamento e cancela), e as fotos 2 e 3 daquele lote são a medição dela em produção.
- **Zero riscos roteados prevê laudo ruim, e o dossiê textual é oferecido do mesmo jeito.**
  Medido nas 15 fotos de 08/09: **4 routearam risco nenhum** — `SOMENTE COM UM PONTO DE
  FIXAÇÃO`, `GRUAA`, `GRUAAA` e `GRUA`. Três deram 0 NC (certo) e a quarta produziu **a
  única não conformidade do lote que veio de dossiê sem risco curado — o falso positivo**.
  As 11 que routearam ao menos um risco saíram todas certas ou defensáveis. O portão
  setorial do #35 tira o item errado, mas **não fecha a classe**: o dossiê do `GRUA`
  depois dele ainda traz plataforma flutuante, escada extensível e escada fixa vertical,
  porque a NR-18 não tem item genérico que se aplique a uma foto de topo de grua. O que
  fecharia é não oferecer dossiê textual quando a taxonomia curada não reconhece nada na
  cena — quando ela cala, a busca textual está adivinhando. **Contra**: é n=4, e remove
  justamente a cobertura que a busca textual existe para dar; o controle negativo de
  02/09 (8 documentos, 0 NC) provavelmente é mais evidência a favor, mas os fatos daquelas
  fotos não estão registrados para conferir. **Meça antes de implementar** — dá para
  reprocessar os fatos de qualquer lote passado sem rede.
- **A taxonomia corrigida não fecha a porta da foto 4.** Medido depois do conserto: sem
  o risco, o `NR-08 8.3.2.2` ainda chega ao dossiê dela em D3, agora pela busca textual
  (o fato menciona "abertura" e "paredes"). Cai de item curado para item textual, sem o
  rótulo do risco empurrando — mas o Analista ainda pode escolhê-lo. **Quem fecharia
  essa porta é o item acima**, não a taxonomia.
- **~~Faltam 5 fotos do lote de poço de elevador~~ — RODADO em 08/09, 15 fotos, medido na
  seção de validação no alto deste arquivo.** O que sobrou dele em aberto está nos itens
  desta lista: o `18.12.22` no `GRUA` (itens de guindar inalcançáveis), a hipótese que
  migrou para o parecer, e o Olho não ter visto a abertura de piso do laudo 15. O histórico
  abaixo fica porque a lista nominal das 14 continua valendo para refazer o lote. O de 05/09
  rodou **7 das 12 mais 2 de fora** (`GRUAA` e `GRUAAA`) e está medido acima — não
  "9 das 12"; ver a correção da conta no cabeçalho daquela seção. O de 04/09 não mediu
  nada: 1 foto auditada de 12, as outras recusadas pelo OTPM.
  **A lista nominal das 14 está na tabela de lotes**, com as cinco que faltam, e é de lá
  que se monta o lote — o desenho já se perdeu uma vez e custou uma rodada de conversa.
  Ele valida cinco coisas ainda não validadas em produção — o `PROMPT_OLHO` que passou a
  nomear elemento de canteiro (#27), os sinais de elevador refeitos (#27), a retentativa
  de JSON do Olho (#27/#28), e agora a **regra da moldura aplicada ao nome** e a
  **cláusula (d) do Diretor** (#32) — mais o teto de saída.
  **O critério de aceite se lê na LISTA DE FATOS do Olho, não nas não conformidades**:
  o que se quer saber é se ele escreve "cancela", "elevador", "poço" — o roteamento dado
  o fato certo já foi medido sem rede. As três leituras, cada uma num lugar diferente do
  laudo: em `GRUAAA`, o nome da torre e a ausência do `NR-18 18.11.14` — que é aceite forte, porque essa foto tem linha de base de 0 NC medida ANTES do #27 (ver a tabela de lotes); nas 5 de proteção
  presente, a contagem de NCs (deve ser 0 — é onde a cláusula (d) e os sinais do #31 se
  provam); nas 5 de proteção ausente, se o `18.9.3` routeia, que é o ganho do #27 nunca
  medido.
  **Único dado até agora, com n=1**: na foto que passou ("19. PROTEÇÃO DE ELEVADOR NÃO
  FIXADA") o Olho escreveu *"Grade metálica de malha quadrada … que delimita uma
  abertura vertical no piso"* — **sem** "poço de elevador" e **sem** "cancela", que é o
  padrão de ANTES da mudança. O enquadramento saiu certo assim mesmo (`NR-18 18.9.2` +
  `NR-08 8.3.2.2`, os dois aparados pelo Diretor). Uma foto não conclui nada; é o que
  vigiar no lote refeito.

  **O próximo lote carrega mais duas coisas (07/09), e o critério de aceite de cada uma
  se lê num lugar diferente do laudo** — é por isso que as duas cabem no mesmo lote sem
  confundir a atribuição:
  1. **O nome da torre**, na LISTA DE FATOS do Olho. Nas fotos de grua, aceite é ele
     escrever "grua" (com a lança/contrapesos no recorte) ou "torre metálica treliçada"
     (sem eles) — e **nunca** "torre de elevador". Nas de poço, que ele siga escrevendo
     "poço de elevador": a regra não alcança o poço, e se ele parar de nomeá-lo a
     cláusula ficou larga demais.
  2. **A constatação hipotética**, na lista de VETADOS do Diretor. Aceite é sumir do
     laudo constatação cujo núcleo é "pode", "possível" ou "indicando" sobre proteção
     que existe. O que vigiar do outro lado é o veto largo: se a contagem de NCs cair
     nas fotos SEM proteção, ou se sumir a consequência ("pode causar queda") das que
     ficaram, a fronteira da cláusula não segurou.
- **O OTPM exato não foi confirmado numa tela de limites, e as duas candidatas já
  foram descartadas.** Os 1.000 vêm da mensagem de erro em **Registros**, que é a
  fonte. `settings/limits` mostra só o TPM somado, sem coluna de saída — o modal de
  limites do projeto também não tem —, e `dashboard/usage` dá consumo, não limite;
  as duas foram olhadas em 04/09. **Não gaste outra rodada procurando**: se o número
  mudar, é pela mensagem de erro que se descobre, e é o campo "Limite de saída por
  minuto da conta (OTPM)" na barra lateral que ajusta, sem mexer em código. A frase
  anterior deste item dizia que o detalhamento "X in / Y out" aparecia passando o
  mouse sobre o TPM — era suposição, escrita antes de qualquer print, e o do painel
  de uso a desmentiu. Ela sobreviveu ao mesmo PR que corrigiu a afirmação gêmea
  vinte linhas acima, que é exatamente a armadilha do "número envelhece em silêncio"
  cometida dentro do conserto dela.
- **O Diretor não trunca, ele OMITE — medido em 09/09.** A ressalva era que ele morresse
  por truncamento com 900 tokens de saída, como morrera com 1.600 em 29/08. Não foi o que
  aconteceu: em 15 fotos **zero** ocorrências de "Diretor não devolveu JSON utilizável".
  O que apareceu foi JSON válido com o campo `exigencia` em branco: **1 laudo dos 15**, e
  nele os DOIS enquadramentos, que eram os dois certos de um poço sem proteção. Das 15
  fotos, 11 tinham enquadramento a conferir, então a omissão foi de 1 em 11.
  A saída registrada aqui ("fatiar a conferência") foi implementada como REPARO e não
  como divisão fixa: `_reconferir_exigencias` só é chamada quando o trecho falta. **Falta
  medir em produção** se a segunda pergunta é respondida — o dublê responde, o modelo de
  verdade não foi testado. **O lote de 10/09 não respondeu isso, e o motivo era nosso**:
  30 laudos sem uma linha de "Supervisão incompleta", e a repescagem bem-sucedida não
  deixava marca nenhuma, de modo que não havia como separar "não omitiu" de "omitiu e o
  reparo funcionou". Instrumentado nesta sessão (`conferencia_reparada`); o próximo lote
  responde lendo a linha **"Conferência repescada"** na trilha.
  **E não dá para dizer que a omissão caiu**: o lote de 10/09 mede omissões que MATARAM o
  enquadramento (zero em 22), não omissões que houve — a repescagem pode ter reparado
  todas em silêncio. O 1 em 11 de 09/09 é de um código SEM repescagem, então os dois
  números não são a mesma grandeza e subtrair um do outro seria a armadilha do "rodou N
  das M" outra vez. A frequência real da omissão só volta a ser observável no próximo
  lote, pela linha nova.
- **Por que ele omite continua sem resposta.** Não é truncamento (o JSON fecha) nem falta
  de espaço declarada. As hipóteses não medidas: o schema pedir `exigencia` dentro de um
  objeto que já tem `fato` e `decisao`, e o modelo economizar o campo mais longo; ou o
  laudo com MAIS de um enquadramento gastar a atenção no primeiro. O laudo 15 tinha dois
  enquadramentos e três pontos de atenção, que é o mais carregado do lote — mas n=1.

- **Taxonomia de içamento — FEITA no #22, à espera de lote.** Três riscos novos em
  `construcao.py`: `dispositivo_icamento_deteriorado` (`NR-18 18.10.1.27`,
  `NR-11 11.1.3.1`), `carga_suspensa_area_sem_isolamento` (`18.10.1.21`, sem exigir
  pessoa) e `equipamento_guindar_sem_itens_seguranca` (`18.10.1.24`, `.26`). O resto dos
  33 itens de guindar ficou de fora de propósito: é obrigação de papel, que foto não
  comprova. Medido: a cinta passa a trazer `18.10.1.27` e `11.1.3.1` como D1 e D2
  **curados**, e o `NR-06 6.9.3` cai para D4 — ele **não sai** do dossiê, porque a NR-06
  entra sempre por `NRS_TRANSVERSAIS` e é o único item dela que pontua ali (7,42). A
  escolha final segue do Analista, e **só um lote diz se ele troca**. Duas ressalvas:
  `equipamento_guindar_sem_itens_seguranca` não tem foto positiva neste histórico (só
  contrapartes), e `18.11.13` para a cancela já estava mapeado em
  `torre_elevador_sem_cancela` — lá o problema nunca foi taxonomia, é o Olho não nomear.
- **O Olho não nomeia o equipamento de canteiro — PROMPT MUDADO em 04/09, à espera de
  lote.** Nomeou a betoneira depois do #14, mas na grua escreveu "Estrutura metálica
  elevada de cor amarela, com cabine e contrapesos" (sem "grua", sem "guindaste" — e aí
  a NR-11 nem pontua em `_pontuar_nrs`; "grua" é palavra-chave da NR-18, que é a norma
  certa) e na torre do elevador escreveu "Grade metálica … aberta" e "estrutura com
  configuração de torre". **O diagnóstico é que ele estava obedecendo**: o parágrafo da
  barreira lista "grade" e manda qualificar; o de nomear falava de máquina e não
  mencionava cancela. Duas regras competindo, e ele seguiu a mais específica. O
  `PROMPT_OLHO` agora nomeia elemento de canteiro (cancela, tapume, bandeja, torre de
  elevador, shaft), diz que o nome **não dispensa** os atributos, e restringe a cláusula
  de escape ao caso ambíguo de verdade. Medido sem rede: com o nome, a cancela passa a
  routear `torre_elevador_sem_cancela` (`NR-18 18.11.13`), que nunca disparara.
  **Mexe em todas as fotos e só um lote diz se ele obedece** — o ganho medido é do
  roteamento dado o fato certo, não do modelo escrevendo o fato certo. O risco simétrico
  a vigiar no lote é o Olho nomear ERRADO: nome errado é fato falso, e o `fato` do Olho
  é justamente o que nenhuma trava do pipeline confere.
- ~~A palavra-chave `umidade` da NR-15 destranca o Anexo 6 (hiperbárico)~~ — **CONSERTADO em
  26/09, sem lote.** "Manchas escuras de umidade" numa parede de alvenaria levou cinco itens de
  mergulho ao dossiê (02/09), e voltou no laudo 3 do lote de andaime (24/09). A palavra saiu de
  `palavras_chave` da NR-15, e **não foi trocada por termos qualificados** — medido: a umidade da
  NR-15 é o `Anexo 10 1` ("locais alagados ou encharcados … em decorrência de laudo"), que
  `comprovavel_em_foto` descarta; com "alagado"/"encharcado" no lugar, uma vala alagada de verdade
  só punha no dossiê o `15.1.1`, item de definição. Removida, as duas cenas reais ficam sem NR-15
  candidata. `test_mancha_de_umidade_nao_poe_a_nr15_no_dossie` trava as duas e falha no catálogo
  antigo.
- **Nada pede que todo achado de risco seja endereçado — agora com dois casos.** Já
  estava registrado nas fotos (59)/(60); no lote de içamento reapareceu duas vezes na
  mesma foto: o laudo 5 enquadrou um vão no piso e deixou a cancela (o achado que o
  engenheiro nomeou no arquivo) sem tratamento, e o laudo 6 fechou com 0 NC tendo
  registrado "Abertura retangular no teto de concreto, sem cobertura ou fechamento
  visível" e uma cancela aberta, com 1 trabalhador na cena. **Nenhum sinal cobre
  "abertura no teto"** — a laje do pavimento de cima vista de baixo.
- **Autenticação.** Discutida, não implementada. Recomendação: app privado no
  Streamlit Cloud (Settings → Sharing), que não cria segredo novo. Alternativas:
  `st.login()` (OIDC, disponível na versão instalada) ou senha nos Secrets com
  `hmac.compare_digest`. **Nunca senha no código** — o repositório é público.
- **Ampliar cobertura.** Basta pôr o PDF oficial em `normas/`: a base guarda a
  impressão digital do acervo e se reconstrói sozinha. O nome precisa conter `nr` e o
  número. Depois, mapear riscos para a norma nova — sem isso ela só entra pela busca
  textual, em modo degradado.
- **Tier pago da Groq** é o que resolve o lote de 100 fotos de verdade.
- **Ganhos de cota que sobraram**, em ordem de retorno (a troca do padrão para o
  3.8 já foi feita em 02/09):
  1. Separar o Diretor num modelo diferente do Analista (`gpt-oss-20b`) — **só faz
     sentido se o 3.8 não vingar**. Levaria o texto de ~43 para ~80 fotos/dia contra
     as ~25 do 3.8 — e, com os quatro modelos no mesmo teto de 200.000, dividir o
     trabalho entre dois baldes passou a ser o ganho de cota mais óbvio que sobra. Ganho secundário que continua valendo: os dois hoje dividem uma
     janela de 8.000 TPM, e é ela que faz a espera adaptativa frear.
  2. Resolução padrão 768px em vez de 896px (a imagem é ~31% da entrada) — mas isso
     morde direto na variabilidade da visão, que já é o limite honesto do app. Manter
     896px como opção pra foto de detalhe.
  3. Cortar o resumo do item no dossiê de 300 para ~220 caracteres. Ganho pequeno
     (~4%), baixo risco.
  - **Não vale a pena**: dedup de fotos por hash perceptual. Testado no lote de 100 —
    o primeiro corte (limiar frouxo) deu 14% de "duplicata" que na verdade eram fotos
    diferentes (agrupou por composição: duas telas de proteção viraram "iguais" a uma
    betoneira). Com limiar apertado, achado real foi 3 fotos em 100 — não move a
    agulha do rendimento.
  - **A retentativa custa caro e ninguém está medindo.** Uma retentativa de texto
    levou a foto de ~7.100 para 13.404 tokens. Se ela for frequente, é um problema de
    cota maior que a escolha de modelo — e hoje o app não conta quantas aconteceram.
- **Achados de produção 30/08 ainda não corrigidos.** Do laudo do 3.8:
  1. **Os pontos de atenção quase não saem — agora medido com n=15.** Apareceram em
     **1 de 15 laudos**, e só onde o veto forçou. O `120b` mandava piso irregular e
     corda enrolada para a seção; o 3.8 é seco. Não é omissão de uma foto: é o
     comportamento dele. O inverso da classe de erro 6 (inventário da foto) — e o
     risco agora é a classe 5, achado que evapora sem deixar rastro.
  2. **A gravidade divergiu entre os dois modelos** na mesma foto: a abertura no piso
     saiu Alta/3 dias no `120b` e Crítica/1 dia no 3.8. O 3.8 parece certo (vão
     desprotegido em laje elevada), o que sugere que o `120b` subestima — o oposto do
     item "gravidade inflada" registrado abaixo, e vindo do mesmo lugar.
  3. **O Diretor do `120b` aparou o que o do 3.8 manteve e fundamentou** ("não atende
     aos requisitos de proteção coletiva rígida"). Achei o 3.8 certo: tela plástica
     frouxa não é proteção projetada por habilitado. É o item do aparo, do outro lado.
- **A NR-12 virava a lixeira do dossiê — três rodadas, ainda sem validação em
  produção.** `d2d92b2` (1ª) tirou `máquina`, `equipamento` e `sem proteção` sozinhos
  das palavras-chave de roteamento textual. `905fdf4` (2ª) foi atrás da taxonomia
  **curada** (`riscos/industria.py`), que tinha o mesmo problema por um caminho que o
  roteamento textual nem alcança: sete riscos citavam item de NR-12 (12.2.4, 12.3.x —
  todos "de máquinas e equipamentos" no próprio texto) **sempre**, para sinais tão
  genéricos quanto "cabo rasgado". Também encurtou o sinal `"guilhotina sem protecao
  frontal"` (4 radicais, casava por cobertura parcial em qualquer "sem proteção …
  frontal" **sem** a palavra "guilhotina" — era esse o caminho pelo qual a betoneira do
  lote anterior virou `NR-12 Anexo VIII 2.1`, prensas), e pôs a avaliação de
  aprendizagem de EAD em `MARCADORES_DOCUMENTAIS`.
  A 3ª rodada mediu o dossiê em vez de adivinhar, e achou o que sobrava — **mais grave
  do que o registrado**. Numa cena de canteiro **com** máquina, o filtro anterior não
  age: uma betoneira gastava os **cinco** lugares da NR-12 com o **Anexo X (calçados)**
  — "máquina de pregar salto", "injetora rotativa de carrossel móvel" — e uma serra
  circular de bancada recebia **três itens de serra fita de AÇOUGUE** (Anexo VII) e dois
  de "máquina boca de sapo". Os itens certos nem chegavam a caber. **O anexo setorial
  não era só ruído: era o que consumia a cota.** Duas peças novas, ambas em `dossie.py`:
  - `ha_maquina_na_cena()` — o `exige_maquina` que estava pendente, nos dois lugares em
    que ele faz sentido. Como portão de NR (a NR-12 não entra no escopo da busca textual
    sem máquina nomeada) e, na taxonomia curada, como `itens_so_com_maquina`: o item de
    NR-12 volta aos três riscos cujo objeto **é** a máquina (piso da área de máquina,
    aterramento da carcaça, cabo de alimentação) e entra só quando ela está na cena.
    Isso desfaz a perda que a 2ª rodada tinha aceitado — a betoneira com cabo
    descascado volta a citar `12.3.4`, medido. Os outros quatro riscos, que descrevem
    elétrica **predial**, seguem só em NR-10: lá o item de NR-12 não acrescentava nada.
  - `setor_pertinente()` — tabela `SETORES` com os sete ramos da NR-12 (motosserras,
    panificação, açougue, prensas, injetoras, calçados, agrícola), 61% dos 920 itens da
    norma. Vai como `aceitar` de `buscar_pontuado`, portanto **antes** do corte relativo.
  Medido em 10 cenas de canteiro reconstruídas do lote real: **10 itens de anexo setorial
  → 0**, e de quebra sumiram as duas vagas que o glossário da NR-01 ocupava.
  **Validado no lote de 15 de 01/09: zero itens de anexo setorial.** O filtro funciona.
  Mas a validação também mostrou que o portão fechava demais — e que abri-lo não
  bastava, porque o roteamento não tinha sinal para o vocabulário de canteiro. As duas
  metades foram corrigidas nos #14/#15 (o Olho nomeia; `coroa e pinhao expostos`,
  `engrenagem sem protecao`, `correia sem carenagem`). **O que falta agora é o Olho
  inspecionar a proteção, não só nomear a máquina** — ver "Em aberto".
- **Duas lacunas de roteamento achadas ao medir. A primeira foi corrigida no #14**
  (a betoneira com coroa e pinhão expostos agora routeia); a segunda continua aberta:
  1. A betoneira com **coroa e pinhão expostos** não bate em
     `maquina_sem_protecao_zona_perigo` — os sinais são "polia exposta", "engrenagem a
     mostra", "correia sem protecao", e nenhum cobre o vocabulário do Olho. É a NC mais
     óbvia da foto e ela não routeia.
  2. Uma cena de panificação (masseira, cilindro de massa) não pontua NR-12 nenhuma em
     `_pontuar_nrs` — e ainda dispara `atmosfera_ipvs_sem_protecao_respiratoria`, que
     não tem nada a ver. Fora do domínio do usuário (construção), mas é o mesmo padrão.
- **Enquadramento que não descumpre o item — RESOLVIDO e validado.** O painel
  empoeirado em `NR-10 10.10.1` (item de SINALIZAÇÃO, com a etiqueta "PERIGO" legível
  na foto) apareceu pelo aparo, o #13 fechou essa porta; voltou pelo aprovado sem
  aparo, o #15 fechou a outra; e a `foto (59)` de 02/09 **saiu vetada**, como se
  esperava. O que a verificação NÃO alcança continua igual: o Diretor copiar um trecho
  verdadeiro do item e aplicá-lo fora de propósito — contra isso só o prompt age.
- **O `fato` copiado pelo Diretor não é conferido por código.** `_exigencia_ancorada`
  confere a **exigência** contra o texto do item; o **fato** que sustenta a constatação
  segue sem verificação automática, e é por aí que a classe de erro 2 ainda passa. Na
  `foto (59)`, "acúmulo de poeira na superfície" virou "comprometendo a legibilidade da
  sinalização" numa foto em que o Olho **leu** o texto da etiqueta. A simetria é óbvia
  — o mesmo `_exigencia_ancorada`, mirando a lista de fatos do Olho em vez do item —
  mas o fato é texto livre e a régua de 0,8 pode ser apertada demais. **Merece medição
  antes de implementar.**
- **O texto do ponto de atenção que nasce de um veto não passa por revisão de
  CONTEÚDO.** Em `pipeline.py`, `observacoes.get(ref) or nc.constatacao`: sem observação
  do Diretor, a constatação vetada vai inteira. O tamanho já foi resolvido (o motivo e a
  observação passam por `_em_poucas_palavras`), mas o conteúdo não: na `foto (59)` da
  rodada anterior isso pôs "a poeira compromete a legibilidade da sinalização" três
  linhas acima de a etiqueta aparecer nas conformidades. **No lote de 12 não se repetiu**
  — o Diretor escreveu observação própria na `foto (60)` — então o defeito depende de ele
  se dar ao trabalho, o que não é garantia.
- **Fotos da mesma cena enquadram achados diferentes.** As fotos (59) e (60) são o mesmo
  painel empoeirado: a 59 enquadrou a poeira em `NR-10 10.4.2`, a 60 foi atrás da
  abertura sem tampa, levou veto e fechou com 0 NC — com o fato "superfície coberta por
  poeira e resíduos de cimento" registrado e não usado. Não é divergência de item para o
  mesmo achado (isso o dossiê resolve); é escolha de qual achado enquadrar. **Nada no
  pipeline pede que todo achado de risco seja endereçado**, e essa é a porta.
- **O Olho nomeia a máquina mas não inspeciona as proteções.** Na betoneira ele
  descreveu corrosão, pintura descascada e o tambor aberto; nunca coroa, pinhão ou
  correia. O prompt já pede "as peças que vê e as que não vê (… proteção de partes
  móveis)" e ele não faz. **É a próxima frente da NR-12** — os sinais existem e
  funcionam, falta o Olho fornecer o que casar. Mexer nesse prompt afeta todas as
  fotos, então merece um lote só para validar.
- **O Gauntlet Loop não faz loop no modo Padrão.** `app.py` define `max_ciclos=1` para
  "Padrão" (e 3 para "Máximo"). O laço roda uma vez e cai em
  `if ciclo >= config.max_ciclos: break` — a linha "Devolvendo para novo ciclo de
  enquadramento…" é **inalcançável** no padrão. Consequência: todo veto é perda
  definitiva, o Analista nunca recebe o motivo e nunca tenta de novo. Aquele
  "1 ciclo" que aparece em todos os laudos **não é o supervisor aprovando de primeira,
  é o teto** — o critério de aceite nunca foi exercido. O segundo ciclo só rodaria
  quando há veto: no lote de 15, teria custado **+7%** de chamadas (e talvez 13–20%
  agora que o #15 veta mais). Decisão do usuário, porque mexe na cota. Se ficar em 1,
  a mensagem "Ciclos esgotados" está mentindo.
- **Gravidade inflada e constatação inventada ainda passam.** Entulho no chão como
  crítica com prazo de 1 dia; e "os degraus não apresentam fixação aos montantes" quando
  o Olho escrevera "sem fixação visível na base ou no topo" — sobre o apoio, não sobre os
  degraus. A conferência literal do Diretor deixou passar.
- **Persistir os resultados do lote.** Hoje vivem só em `st.session_state`: um redeploy
  do Streamlit Cloud (ou um F5) apaga o lote em andamento. No plano gratuito um lote de
  100 fotos leva vários dias, então a chance de perder trabalho no meio não é pequena.
- **Efeito colateral a vigiar em produção**: o Olho começar a inventar ausência ("sem
  rodapé") de peça que está fora do enquadramento. É o preço de risco da mudança do
  Olho, e a razão da cláusula "não dá para ver". Até aqui não apareceu.

---

## Validação em produção de 02/09/2026 — o lote de 12 (o #17 e o #18)

**12 fotos, 4 NCs.** Rodado no commit `0c7ac83`, com o 3.8 nos dois campos. Tudo abaixo
foi lido nos laudos reais e reproduzido aqui sem rede.

As três apostas do #17 se confirmaram:

1. **Controle negativo: 8 de 8 documentos deram 0 NC**, todos "aprovado sem vetos" —
   registro de empregado (PIS/PASEP, Data Admissão, Função), lista de treinamentos com
   carga horária, três certificados de NR-06/NR-01/NR-18, termo de anuência de trabalho
   em altura e um LAUDO DE ENSAIO DE ARRANCAMENTO EM DISPOSITIVO DE ANCORAGEM com ART
   do CREA. É a classe de erro que já tinha aparecido (o registro de empregado
   enquadrado em item de avaliação de aprendizagem) e nunca fora testada de propósito.
   Os pareceres que saíram são o raciocínio certo: *"a foto isolada não permite
   verificar a validade temporal ou a adequação do conteúdo do termo"*. (Sete foram
   lidos no HTML; o oitavo fecha pela conta do sumário — e o sumário sinalizaria foto
   não auditada se alguma tivesse falhado, o que ele não faz.)
2. **A `foto (59)` trocou de item — e para o item certo.** Antes: `NR-10 10.10.1`
   (sinalização) → vetado → 0 NC. Depois: **`NR-10 10.4.2`**, que nomeia "poeira"
   literalmente entre os riscos adicionais a controlar. **É a hipótese central do #17
   respondida**: o item certo não estava no dossiê antigo, e o Analista o escolheu
   assim que passou a estar.
3. **"Fiação elétrica exposta … sem proteção de canaleta ou conduíte"** saiu como
   `NR-10 10.2.8.2.1`, crítica, 1 dia — o item que `partes_vivas_expostas` mapeia e que
   só routeia depois da correção do plural de 4 letras. Na mesma foto, a abertura na
   parede com armadura exposta saiu como `NR-08 8.3.2.2` (o risco novo do #13).

**O `10.10.1` apareceu dos DOIS lados no mesmo lote, e é isso que fecha a história que
vem do #13.** No laudo 1 (painel com etiqueta só do logotipo comercial "FERI", sem
placa de perigo) ele foi **usado** — falta sinalização, e é o que o item exige. Na
`foto (60)` (etiqueta "PERIGO / ELETRICIDADE SOMENTE PESSOAL AUTORIZADO" presente e
legível) ele foi **vetado**. Usar onde falta e recusar onde existe era o objetivo. O
dossiê do laudo 1, reproduzido aqui, tem 8 entradas e **zero obrigação de papel**.

**E o veto melhorou.** Na `foto (60)` o Diretor fundamentou a recusa usando OUTRO fato:
*"a etiqueta de sinalização está descrita como presente e legível em outro fato"*. **Não
houve contradição** — o ponto de atenção virou "não é possível determinar pela imagem" e
a etiqueta ficou nas conformidades sem briga. É o defeito que a `foto (59)` da rodada
anterior tinha, e ele não se repetiu.

Dois textos saíram impressos quebrados no laudo do cliente, e viraram o **#18**:

1. **`"violando a e."`** no parecer do laudo 1 — ver a armadilha "citação removida do
   meio da frase deixa verbo sem objeto".
2. **493 caracteres de argumentação do Diretor** dentro do ponto de atenção do laudo 12
   — ver "corte de verbosidade aplicado a um campo só". 493 → 85 caracteres.

---

## Validação em produção de 01–02/09/2026 — o lote de 15 no Qwen 3.8

Primeiro lote inteiro no `Qwen 3.8 27B` nos dois campos. **15 fotos, 21 NCs, 15 laudos
emitidos.** Tudo abaixo foi lido nos laudos reais e reproduzido aqui sem rede.

O que ficou provado:

- **O 3.8 emite onde o `120b` falhava.** 15/15 laudos contra 11/14 antes. As 3 fotos
  que morriam com "não devolveu JSON utilizável" saíram. Valida a correção do
  `_conversar_sem_cortar` (refazer também quando o parser falha, não só quando a API
  sinaliza corte).
- **Custo confirmado com n=15**: 7.804 tokens/foto, contra 7.060 previstos com n=1.
  ~25 fotos/dia no teto de 200.000. O excesso de ~11.200 tokens no lote
  sugere **~2 retentativas em 15 fotos (~12%)** — a retentativa não é o problema de
  cota que se temia.
- **`itens_compartilhados()` funcionou no caso que o motivou**: a tela frouxa na borda
  da laje saiu nomeada pela constatação, não como "Andaime sem guarda-corpo".
- **O balde por modelo aparece na barra lateral** (`qwen/qwen3.8-27b — 117.069 de
  2.000.000` — o denominador estava errado; ver "Cota" nos limites honestos).

O que o lote revelou de defeito, e virou os PRs #13/#14/#15:

1. **O ambiente carregava o sinal sozinho** — "abertura" do achado do tambor mais
   "piso" do ambiente casavam `"abertura no piso"` inteiro. Sistemático, porque quase
   todo ambiente de obra menciona "piso". Corrigido com a âncora (dois radicais do
   próprio achado).
2. **Abertura em parede saía intitulada "Abertura no piso"** — `NR-08 8.3.2.2` cobre
   piso E parede; a NR-18 18.9.2 só piso. Novo risco `abertura_parede_desprotegida`.
3. **O aparo salvava enquadramento que era veto** — painel empoeirado em item de
   sinalização. Virou a verificação de exigência.
4. **O campo `retirado` vazava raciocínio** — 674 caracteres de "Vou manter a lógica
   de que…" impressos no laudo do cliente.
5. **Uma abertura contada duas vezes** — 6 das 21 NCs eram 3 aberturas em dobro.

**Segunda rodada, 4 fotos, depois dos merges** — o que se aprendeu:

- **O Olho passou a nomear a máquina** ("Betoneira…", "Martelete…"). O portão abre.
  Foi a correção mais bem-sucedida da sessão.
- **A betoneira ainda deu 0 NC**, e por um motivo novo: o Olho **nomeia mas não
  inspeciona as proteções**. Descreveu corrosão, pintura descascada e o tambor aberto;
  nunca coroa, pinhão ou correia. Os sinais existem e funcionam — não há o que casar.
- **O painel empoeirado voltou por outro caminho**: desta vez APROVADO sem aparo, com
  gravidade subida de baixa para média. E o laudo saiu se contradizendo — acusava a
  sinalização de comprometida e a listava em "conformidades observadas". Foi o que
  motivou o #15. **Sem validação ainda.**

---

## Validação em produção de 29/08/2026 — o que ficou provado

As mesmas 14 fotos do lote de 27/08, com os laudos de volta. **2 NCs → 19 NCs.**
Sem rede à Groq nesta sessão, este é o único jeito de validar mudança de prompt; o
que vem abaixo foi lido nos laudos reais, não inferido.

Funcionou, com evidência no laudo:

- **O Olho qualifica a barreira.** "Rede de proteção laranja de malha plástica" virou
  "Tela plástica flexível de malha larga, cor laranja, pendurada e amarrada em postes
  verticais, cobrindo parcialmente a borda do piso e **deixando trecho aberto**", mais um
  fato separado: "sem barreira física rígida (como guarda-corpo metálico ou rodapé)
  **visível**". A forma canônica "sem <peça> visível" saiu como pedida.
- **As três periferias foram reconhecidas** (eram 0 NC), e a conformidade falsamente
  atestada ("proteção coletiva contra quedas" para tela de sombreamento) **desapareceu**.
- **O andaime sem guarda-corpo** (0 NC, 0 pontos antes) saiu com `NR-18 18.9.4.2` crítica.
- **A regra da moldura fez o que devia.** O veto da sapata mandou para os pontos de
  atenção "*não é possível determinar pela imagem se a escada possui sapatas
  antiderrapantes; verificar no local*" — antes ia a afirmação inteira que o Diretor
  acabara de recusar. É o comportamento novo mais difícil de provar sem rede.
- **Fotos equivalentes passaram a concordar**: as duas do mesmo quadro de tomadas deram
  3 e 2 NCs, contra 3 e 0 antes.
- **A ressalva impressa nas conformidades** aparece no laudo.

Regressão introduzida e corrigida na mesma sessão: o schema do Diretor cresceu com as
chaves do aparo, a resposta passou do teto de saída e **três laudos morreram com JSON
truncado** — não inválido, truncado. O Olho já refazia a chamada nesse caso; o Analista
e o Diretor não. Hoje os três compartilham `_conversar_sem_cortar` — o Olho entrou em
04/09, depois de o `/conferir` achar que a docstring afirmava isso havia meses sem ser
verdade. **Toda vez que crescer o que se pede a um agente, verificar o teto de
saída dele.**

**A mesma mensagem voltou no lote de 29/08, com outra causa.** O sumário do lote de 14
listou 3 fotos não auditadas com "Diretor/Analista não devolveu JSON utilizável" — a
retentativa acima já estava em produção, então não era truncamento (`finish_reason ==
"length"`) de novo; era JSON malformado por outro motivo (suspeita: aspas de citação
oficial não escapadas) que a API não sinaliza. `_conversar_sem_cortar` só refazia a
chamada quando a API confirmava o corte; agora refaz também sempre que o parser falha,
sinalizado ou não. **Validado no lote de 15 de 01/09: 15 de 15 laudos saíram**, contra
11 de 14 antes. As 3 fotos que morriam com "não devolveu JSON utilizável" foram
embora. A segunda correção só alcançou o Olho em 04/09; até lá, JSON malformado sem
sinal ainda matava a foto na leitura da imagem, que é a falha que não deixa laudo
nenhum.

---

## Como o usuário trabalha

Escreve em maiúsculas, manda print da tela e anexa os HTML dos laudos. Testa em
produção e volta com o resultado. **Levar cada retorno a sério**: quase todo defeito
importante desta sessão saiu de um laudo real que ele mandou, não dos testes.

Pede confirmação explícita antes de mergear PR — implementar e mergear são pedidos
separados, mesmo quando vêm próximos.

Responder em **português do Brasil**.
