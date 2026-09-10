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
  **manteve o enquadramento**. Falta conferir a foto: há buraco no chão ali?
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
`dllifilho-debug/auditoria-nrs-fixtures` tem agora **353 fotos** (106 MB), e **138 das
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
| Controle negativo | 5 documentos (POP, lista de presença, CREA, crachá) | devem dar **0 NC**; é a classe de erro que já apareceu e nunca foi testada de propósito |
| **Variabilidade da visão** | as MESMAS 15 do lote de poço, rodadas **duas vezes no mesmo dia**, uma chave em cada conta | Mesmas fotos, mesmo código, mesmo dia: a diferença entre os dois lotes é variabilidade PURA do modelo, sem confundir com mudança de versão. É o primeiro dos "limites honestos" deste arquivo e até hoje só tem anedota — "um botão de emergência foi crítico numa foto e passou despercebido em outra do mesmo painel". **Só ficou possível em 10/09**, com a segunda conta: duas passadas de 15 dão ~234 mil tokens e não cabiam em conta nenhuma. O que se lê: quantas NCs mudam de foto para foto, se o Olho descreve os mesmos fatos, e se as fotos de 0 NC continuam em 0. Um número aqui diz quanto do gabarito de qualquer lote é ruído |

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

$VENV -m pytest tests/ -q          # 232 testes
$VENV -m auditoria.kb_build        # regenera a base a partir de normas/*.pdf
$VENV -m streamlit run app.py --server.port 8600 --server.headless true
```

**Fotos reais de teste**: repositório privado `dllifilho-debug/auditoria-nrs-fixtures`,
pasta `fotos/` — 100 fotos de auditoria de verdade que o usuário subiu (obra BRASAL),
sem rosto nem placa de empresa identificável em boa parte, mas trate como sensível
(é por isso que é privado; nunca proponha subir foto de auditoria no repo público do
app). `add_repo` para anexar à sessão. Cada foto tem achados reais já auditados neste
histórico — antes de inventar cenário sintético para testar algo, veja se uma dessas
já serve; é mais convincente e já foi conferida contra o laudo de verdade pelo menos
uma vez.

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
| **`sem` é radical-cola: conta, mas não discrimina** | Ele tem 3 letras, então passa o filtro de `_radicais` e vira um radical como outro qualquer. Só que não distingue nada: um sinal de dois radicais em que um é `sem` vale por um. Custou dois defeitos no mesmo dia. `"sem carenagem"` casou com "Carenagem do motor íntegra e fixada, **sem** folgas visíveis" — carenagem em ordem, o oposto do risco. E `"vao no piso sem tampa"` casou numa foto de betoneira porque `sem` e `tampa` vieram de "Abertura circular do tambor **sem tampa**". Ao escrever ou revisar sinal, conte os radicais **discriminantes**, não os radicais. **E `sem` nunca é o negador**: em 04/09, consertando os sinais de elevador, `"elevador de obra sem cancela"` foi encurtado para `"sem cancela"` — dois radicais, um deles cola, e o fato *"Cancela metálica vermelha, fechada e travada, SEM sinalização de advertência"* deu cobertura 1,0. O agravante é sistemático: o `PROMPT_OLHO` **manda** escrever "sem &lt;peça&gt; visível" quando o lugar dela aparece vazio, então quase todo fato do Olho carrega um `sem` solto. O que nega numa foto é a **abertura** — `aberta`, `ausente`, `faltando`, `quebrada` —, e é nela que o sinal deve ancorar. |
| **Quatro radicais é onde a cobertura parcial abre** | O corte é 0,7. Com três radicais, faltar um dá 0,67 e **não passa** — todo radical é obrigatório. Com quatro, faltar um dá 0,75 e **passa**, e o que falta costuma ser justo o discriminante. `"abertura vertical sem fechamento"` casava uma abertura de PISO "sem cobertura ou fechamento visível", faltando só `vertical`. Sinal de até três radicais é seguro por construção; de quatro para cima, escreva sabendo que um pode faltar. **262 dos 883 sinais têm 4+ radicais** e correm esse risco. |
| Regra global para a cobertura parcial — **tentada e descartada** | A saída óbvia (excluir palavras-cola do conjunto que pode ancorar) **quebra 25 sinais legítimos**: `"sem capacete"`, `"sem luva"`, `"sem bota"`, `"sem placa"`, `"sem manometro"` — onde a cola e o discriminante são tudo o que existe. Também não adianta exigir que o radical faltante seja cola (deixa "escada COM sapata" casar "escada sem sapata") nem que seja não-cola (devolve o caso da betoneira). **Não há regra simples**: é encurtar sinal a sinal, com medição. Não gaste a sessão reinventando isto. |
| Verificação mecânica no caminho errado | O aparo do Diretor ganhou verificação de lastro no #13; no lote seguinte, o mesmo enquadramento falso voltou por **aprovado**, sem aparo, e passou inteiro. Ao fechar uma porta num agente, pergunte por quais outras a mesma coisa entra — decisão de modelo muda de caminho de uma rodada para outra. Hoje a exigência é cobrada de todo enquadramento que sobrevive. |
| **Plural de radical curto não reduzia** | `radical()` só singularizava palavra com mais de 4 letras, então `"fios"` ficava `"fios"` e `"fio"` ficava `"fio"` — dois radicais para a mesma palavra. O sinal `"fio desencapado"` foi cadastrado justamente porque o Olho escreve **"fios desencapados"**, e o par nunca casou: um quadro de tomadas aberto routeava **zero** riscos. Corrigido; a regra do `s` simples agora vale de 4 letras para cima, mas `PLURAIS` continua em 5 — aplicá-la a 4 transformaria `"mais"` em `"mal"`. |
| **Sinal cujas palavras somem no filtro de radicais** | `"t em cima de t"` tem cinco palavras e quatro têm duas letras: `radicais()` descarta todas e sobra `cima` sozinho, com cobertura 1.0 em "pregos expostos voltados **para cima**". Uma foto de madeira de fôrma routeava gambiarra. É a armadilha do `sem` levada ao extremo — o sinal inteiro vira cola. Hoje o validador da taxonomia quebra no import se um sinal não tiver radical discriminante (`PALAVRAS_COLA` em `riscos/__init__.py`). |
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
| `git fetch origin main <branch-que-não-existe-mais>` falha inteiro, silenciosamente | Fetch de múltiplos refs é atômico: se um ref já foi deletado no remoto (branch mergeada), o comando inteiro falha e **nenhum ref é atualizado** — inclusive o `main`, que existia e seria atualizado sozinho. `origin/main` local fica congelado na versão de antes, e comparações feitas contra ele mentem. Já causou uma sessão inteira concluir errado que "a reescrita nunca foi mergeada". Se o histórico parecer suspeito, rode `git fetch origin main` sozinho antes de confiar em qualquer diff. |

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
- **232 testes**
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
- **A conferência do Diretor tem repescagem.** Quando ele deixa `exigencia` em branco,
  `_reconferir_exigencias` pergunta de novo, numa chamada estreita que leva só os
  enquadramentos que faltaram. **Só o trecho AUSENTE é repescado**: trecho que veio e não
  ancora é refutação, e reperguntar ali daria ao modelo uma segunda chance de inventar a
  exigência, que é o que a rede existe para impedir. Repescagem vazia derruba o
  enquadramento como antes, com "Supervisão incompleta" na trilha; repescagem ilegível
  também, sem matar a foto. Motivada pelo laudo 15 de 09/09, em que os dois
  enquadramentos certos de um poço sem proteção caíram por omissão.
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

- **Variabilidade da visão.** A mesma foto, em duas execuções, produz leituras
  diferentes. Um botão de emergência danificado foi crítico numa foto e passou
  despercebido em outra do mesmo painel. O app é apoio, não substituto do olho do
  engenheiro — e o rodapé do laudo diz isso a sério.
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
  &lt;peça&gt; visível" e de o `sem` contar como radical. **Não cabe numa troca de sinal**
  — são quatro sinais de três riscos, e o CLAUDE.md já registra que a regra global
  (excluir cola da ancoragem) foi tentada e quebra 25 sinais legítimos. O que a medição
  de hoje acrescenta é uma hipótese que **não** foi tentada: tratar `"sem X"` como
  bigrama, exigindo adjacência entre o `sem` e o substantivo que ele nega — `kb.py` já
  indexa bigramas no BM25. Isso separaria "sem rodapé" de "rodapé … sem folgas". É
  mudança estrutural no roteamento e só um lote valida.

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
  de no `sem`, e a abertura também pode aparecer negada. **A hipótese do bigrama não
  cobre este caso**: aqui não há `sem X` adjacente a cobrir, há `sem trechos abertos`,
  em que o negador está a duas palavras do que ele nega. Quem for atacar o item acima
  precisa decidir se trata os dois mecanismos ou só um. E o custo é imediato: são os
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
- **A não conformidade que é uma VERIFICAÇÃO — CLÁUSULA (e) ESCRITA em 09/09, à espera de
  lote.** `11 PAV. PROTEÇÃO POÇO ELEVADOR SEM PROTEÇÃO` saiu duas vezes no mesmo dia com
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
- **Item de abertura no PISO usado para vão VERTICAL, com o aparo agravando.** Laudo 1 de
  09/09: `NR-18 18.9.2` para um painel de madeira vertical encostado no concreto, e o
  aparo retirou a referência ao vão vertical — com a razão certa, "a norma regula
  especificamente aberturas no piso" — e **manteve o enquadramento**. É a classe de erro
  1 pelo caminho do aparo: ele corta o que não tem lastro e não pergunta se o que sobrou
  ainda descumpre AQUELE item, que é justamente o que o `PROMPT_DIRETOR` manda fazer.
  Falta conferir a foto antes de chamar de falso positivo.
- **A `cancela` entrega os itens de elevador sem passar por portão nenhum.** Achado pelo
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
  verdade não foi testado.
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
- **A palavra-chave `umidade` da NR-15 destranca o Anexo 6 (hiperbárico).** "Manchas
  escuras de umidade" numa parede de alvenaria levou cinco itens de mergulho ao dossiê.
  A `umidade` da NR-15 é o Anexo 10, locais alagados/encharcados — pede qualificação,
  não a palavra solta. Conserto barato em `catalogo_nr.py`.
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
