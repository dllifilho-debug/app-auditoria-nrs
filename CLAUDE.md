# Contexto do projeto para sessões futuras

App Streamlit que analisa fotos de inspeção de segurança do trabalho e emite laudo
de não conformidades enquadrado nas Normas Regulamentadoras brasileiras.

Usuário: engenheiro de segurança do trabalho. Auditorias reais chegam a **100 fotos**.
Conta Groq no **plano gratuito**. Publicado em `auditoria-nrs-08.streamlit.app`, a partir
do `main` do repositório GitHub `dllifilho-debug/app-auditoria-nrs`.

Fluxo de trabalho agora passa por PR: branch `claude/...`, testes, navegador, PR contra
`main`, e só mergear — nesse ponto ou quando o usuário pedir — depois disso o Streamlit
Cloud redeploya sozinho em ~1-2 min (confirme pelo hash em "Versão em execução" na
barra lateral). **Antes desta sessão, `main` estava travado num protótipo antigo e a
reescrita inteira vivia numa branch nunca mergeada** — se `git diff main...HEAD` um dia
mostrar milhares de linhas de novo, desconfie do `main` local antes de concluir que o
`main` remoto está desatualizado (ver armadilha do `git fetch` abaixo).

**Sem acesso de rede à Groq a partir desta sessão remota.** `api.groq.com` é bloqueado
pela política de egress do container (403 no proxy) — confirmado, não é intermitente.
Isso significa: nada de `ClienteGroq` real aqui, só `ClienteDemonstracao` e testes da
camada determinística (roteador, dossiê, aferição). Testar com o modelo de visão de
verdade é sempre com o usuário, em produção, com fotos e laudos que ele manda de volta.

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

$VENV -m pytest tests/ -q          # 119 testes
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
| `git fetch origin main <branch-que-não-existe-mais>` falha inteiro, silenciosamente | Fetch de múltiplos refs é atômico: se um ref já foi deletado no remoto (branch mergeada), o comando inteiro falha e **nenhum ref é atualizado** — inclusive o `main`, que existia e seria atualizado sozinho. `origin/main` local fica congelado na versão de antes, e comparações feitas contra ele mentem. Já causou uma sessão inteira concluir errado que "a reescrita nunca foi mergeada". Se o histórico parecer suspeito, rode `git fetch origin main` sozinho antes de confiar em qualquer diff. |

---

## Estado atual (commit `b21ffce`)

- **6.358 itens** vigentes de **24 NRs** (de 36 vigentes), extraídos dos PDFs em `normas/`
- **122 riscos** curados mapeando para **228 itens** reais; 25 exigem pessoa na cena e
  3 têm item que só entra com máquina nomeada na cena (`itens_so_com_maquina`)
- **119 testes**
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
- **Regra da moldura.** A constatação só afirma que algo não existe se aquilo apareceria
  no recorte da foto. Ancoragem na cobertura, aterramento dentro do quadro: fora da
  moldura vira verificação ("não é possível determinar pela imagem"), não afirmação. É
  motivo de aparo, nunca de veto sozinha — senão anularia a regra acima.
- **O Olho qualifica a barreira, não a nomeia pela função.** "Rede de proteção" para uma
  tela plástica de sinalização é conclusão, não descrição. O prompt exige material,
  rigidez, fixação, continuidade, altura e estado; "sem <peça> visível" só quando o lugar
  dela aparece vazio na foto.
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
modelos.py    cliente Groq: cota, degradação por parâmetro, truncamento
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
   pra oferecer, e o Analista escolheu o menos ruim dos nove. Corrigido dos dois lados
   (taxonomia + filtro documental na busca), mas o padrão de fundo — dossiê pobre força
   escolha ruim — pode reaparecer noutro domínio se o roteamento não pegar o achado.
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
- **Cota.** ~7.100 tokens por foto no rigor Padrão. O teto que aperta é o diário, não
  o por minuto — e ele é **por modelo**, conferido no console em 30/08: 200.000
  tokens/dia para `gpt-oss-120b`, `gpt-oss-20b` e `qwen/qwen3.6-27b` cada um
  (`qwen/qwen3.8-27b` tem 2.000.000, ver "Em aberto"). Também por modelo: 8.000
  TPM e 1.000 requisições/dia, nenhum dos dois limitante hoje.
  O app somava os três num balde só e por isso anunciava **28 fotos/dia**; o gargalo
  real é o `120b`, que carrega Analista **e** Diretor, em torno de **43 fotos/dia**.
  A conta errada mandava parar de auditar com cota sobrando. Corrigido: `consumo.py`
  guarda um balde por modelo e a barra lateral mostra qual deles vai estourar
  primeiro. Um lote de 100 ainda não cabe num dia — por isso o app retoma de onde
  parou. Medido onde a cota vai (entrada, Padrão): Olho ~1.956 tokens (1.600 são só
  a imagem em 896px), Analista ~1.716 (dossiê sozinho: 921), Diretor ~1.551. A
  repartição da **saída** por modelo nunca foi medida — agora dá, porque o cliente
  discrimina; confirmar no próximo lote real antes de confiar nos ~43.
- **Documento gerado não substitui laudo assinado por profissional habilitado.**

---

## Em aberto

- **Autenticação.** Discutida, não implementada. Recomendação: app privado no
  Streamlit Cloud (Settings → Sharing), que não cria segredo novo. Alternativas:
  `st.login()` (OIDC, disponível na versão instalada) ou senha nos Secrets com
  `hmac.compare_digest`. **Nunca senha no código** — o repositório é público.
- **Ampliar cobertura.** Basta pôr o PDF oficial em `normas/`: a base guarda a
  impressão digital do acervo e se reconstrói sozinha. O nome precisa conter `nr` e o
  número. Depois, mapear riscos para a norma nova — sem isso ela só entra pela busca
  textual, em modo degradado.
- **Tier pago da Groq** é o que resolve o lote de 100 fotos de verdade.
- **Rendimento diário — discutido, não implementado.** Em ordem de retorno:
  0. **`qwen/qwen3.8-27b` tem 2.000.000 de TPD — dez vezes todos os outros**, com o
     mesmo RPM/RPD/TPM. Se ele aceitar imagem, o teto do Olho sai de ~80 fotos/dia
     para a casa das centenas e a cota deixa de ser o problema de uma auditoria de
     100 fotos; se servir só para texto, Analista e Diretor passariam de ~43 para
     ~430. Duas incógnitas que só produção responde: se é multimodal (o registro diz
     que o 3.6 é o único, mas o 3.8 é posterior) e se o JSON dele se comporta — o 3.6
     está marcado `json_estrito_confiavel=False` e a família provavelmente herda isso.
     **Testável sem código**: a barra lateral aceita ID digitado à mão.
  1. Separar o Diretor num modelo diferente do Analista (ex.: `gpt-oss-20b` em vez de
     `gpt-oss-120b`). Teto por modelo **confirmado** no console em 30/08; hoje
     Analista e Diretor dividem o balde do `120b`, que por isso é o gargalo. Separando,
     o teto vai de ~43 para ~80 fotos/dia e o gargalo **passa a ser o Olho** — e não
     há segundo modelo de visão para dividir, o que é o que torna o item 0 mais
     importante que este. Ganho secundário independente do diário: os dois hoje
     dividem uma janela de 8.000 TPM, e é ela que faz a espera adaptativa frear.
     Como a conferência obrigatória tornou o trabalho do Diretor mais mecânico, um
     modelo menor deve dar conta.
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
  **Sem validação em produção ainda** — precisa rodar o lote de 14 de novo (linha de
  base: 19 NCs) e comparar. O que vigiar no retorno: item de máquina **sumindo** onde
  deveria aparecer (o portão fecha por nome de máquina; se o Olho descrever a máquina
  sem nomeá-la, a NR-12 não entra).
- **Duas lacunas de roteamento achadas ao medir, não corrigidas.** São de recall, não da
  frente da lixeira, e mexer em sinal pede validação em produção:
  1. A betoneira com **coroa e pinhão expostos** não bate em
     `maquina_sem_protecao_zona_perigo` — os sinais são "polia exposta", "engrenagem a
     mostra", "correia sem protecao", e nenhum cobre o vocabulário do Olho. É a NC mais
     óbvia da foto e ela não routeia.
  2. Uma cena de panificação (masseira, cilindro de massa) não pontua NR-12 nenhuma em
     `_pontuar_nrs` — e ainda dispara `atmosfera_ipvs_sem_protecao_respiratoria`, que
     não tem nada a ver. Fora do domínio do usuário (construção), mas é o mesmo padrão.
- **O aparo pode salvar enquadramento que devia ser vetado.** Visto em produção: NC em
  `NR-12 12.3.8` (partes energizadas expostas) com a trilha dizendo
  `retirado: partes energizadas expostas`. Cortado justamente o que o item exige, o que
  sobrou ("cabo amarelo pendurado na parede") não descumpre mais nada — era veto. A regra
  está escrita no prompt (a distinção NR-35 apara / NR-18 18.8.6.12 veta) e o modelo
  errou o lado. Reforçar depois da frente da NR-12.
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
e o Diretor não. Hoje os três compartilham `_conversar_sem_cortar`. **Toda vez que
crescer o que se pede a um agente, verificar o teto de saída dele.**

**A mesma mensagem voltou no lote de 29/08, com outra causa.** O sumário do lote de 14
listou 3 fotos não auditadas com "Diretor/Analista não devolveu JSON utilizável" — a
retentativa acima já estava em produção, então não era truncamento (`finish_reason ==
"length"`) de novo; era JSON malformado por outro motivo (suspeita: aspas de citação
oficial não escapadas) que a API não sinaliza. `_conversar_sem_cortar` só refazia a
chamada quando a API confirmava o corte; agora refaz também sempre que o parser falha,
sinalizado ou não. Sem validação em produção ainda — o lote de 14 tem 3 fotos que nunca
saíram de jeito nenhum, então qualquer redução nesse número já é sinal de progresso.

---

## Como o usuário trabalha

Escreve em maiúsculas, manda print da tela e anexa os HTML dos laudos. Testa em
produção e volta com o resultado. **Levar cada retorno a sério**: quase todo defeito
importante desta sessão saiu de um laudo real que ele mandou, não dos testes.

Pede confirmação explícita antes de mergear PR — implementar e mergear são pedidos
separados, mesmo quando vêm próximos.

Responder em **português do Brasil**.
