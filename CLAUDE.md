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

$VENV -m pytest tests/ -q          # 103 testes
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
| `git fetch origin main <branch-que-não-existe-mais>` falha inteiro, silenciosamente | Fetch de múltiplos refs é atômico: se um ref já foi deletado no remoto (branch mergeada), o comando inteiro falha e **nenhum ref é atualizado** — inclusive o `main`, que existia e seria atualizado sozinho. `origin/main` local fica congelado na versão de antes, e comparações feitas contra ele mentem. Já causou uma sessão inteira concluir errado que "a reescrita nunca foi mergeada". Se o histórico parecer suspeito, rode `git fetch origin main` sozinho antes de confiar em qualquer diff. |

---

## Estado atual (commit `b21ffce`)

- **6.358 itens** vigentes de **24 NRs** (de 36 vigentes), extraídos dos PDFs em `normas/`
- **122 riscos** curados mapeando para **232 itens** reais; 25 exigem pessoa na cena
- **103 testes**
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
dossie.py     recuperação dos itens candidatos; comprovavel_em_foto() filtra item
              documental (inventário de riscos, carga horária...) da busca textual —
              não alcança a taxonomia curada, onde alguns estão lá de propósito
pipeline.py   Gauntlet Loop e a aferição determinística
modelos.py    cliente Groq: cota, degradação por parâmetro, truncamento
relatorio.py  Markdown e HTML imprimível
consumo.py    contabilidade do teto diário de tokens
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
- **Cota.** ~7.100 tokens por foto no rigor Padrão. O teto que aperta é o diário
  (200.000 no gratuito), não o por minuto: cerca de **28 fotos/dia**. Um lote de 100
  não cabe num dia — por isso o app retoma de onde parou. Medido onde a cota vai
  (entrada, Padrão): Olho ~1.956 tokens (1.600 são só a imagem em 896px), Analista
  ~1.716 (dossiê sozinho: 921), Diretor ~1.551. Ver "Em aberto" para onde cortar.
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
  1. Separar o Diretor num modelo diferente do Analista (ex.: `gpt-oss-20b` em vez de
     `gpt-oss-120b`). No plano gratuito o teto diário é *por modelo*; hoje Analista e
     Diretor dividem o mesmo balde. Como a conferência obrigatória tornou o trabalho
     do Diretor mais mecânico, um modelo menor deve dar conta. **Confirmar limites
     reais no console da Groq antes de contar com isso** — não dá pra verificar desta
     sessão (sem rede).
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
- **A NR-12 virou a lixeira do dossiê — é a próxima frente, e a mais importante.**
  Validado em produção (ver abaixo): quatro das nove NCs das últimas três fotos caíram
  na NR-12 em cenas de obra **sem máquina nenhuma**. Entulho no chão virou `12.2.4`
  ("o piso do local de trabalho onde se instalam *máquinas e equipamentos*"), crítica,
  1 dia; cabo pendurado na parede e caixa de distribuição de obra viraram `12.3.8`
  ("são proibidas *nas máquinas e equipamentos*"). A NR-12 tem 920 itens — quase um
  quarto da base indexável — e texto genérico o bastante ("áreas de circulação",
  "condutores de alimentação elétrica") para casar com qualquer coisa de canteiro.
  Do mesmo lote anterior: betoneira enquadrada em `NR-12 Anexo VIII 2.1` (**prensas** —
  o título da NC saiu "Prensa, guilhotina ou dobradeira"), e foto de tela de computador
  enquadrada em `NR-01 Anexo II 4.6.1`, que é avaliação de aprendizagem de EAD.
  **Frente já iniciada em `d2d92b2`**, que tirou `máquina`, `equipamento` e
  `sem proteção` sozinhos das palavras-chave da NR-12 — casavam com quase qualquer
  achado e eram provavelmente o caminho pelo qual ela entrava no escopo nos casos acima.
  Quanto isso resolve só o próximo lote real dirá; a linha de base para comparar são as
  **19 NCs**, não as 2.
  O que ainda não existe, e tem precedente no próprio código: a taxonomia já tem
  `exige_pessoa`, que impede cobrar capacete em foto sem ninguém. O análogo é **exigir
  máquina ou equipamento na cena para a NR-12 entrar no dossiê**, somado a um filtro de
  anexo setorial fora de contexto (prensa, panificação, calçados) — este último é o que
  pega a betoneira virando prensa, que o `d2d92b2` não alcança. É código, testável sem
  rede, e reaproveita `titulo_da_secao`, criada para o filtro de item não prescritivo.
  **Cuidado com a contraparte**: NR-35 Anexo III (escadas) e NR-12 Anexo XII (içamento)
  são anexos que *devem* passar.
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

---

## Como o usuário trabalha

Escreve em maiúsculas, manda print da tela e anexa os HTML dos laudos. Testa em
produção e volta com o resultado. **Levar cada retorno a sério**: quase todo defeito
importante desta sessão saiu de um laudo real que ele mandou, não dos testes.

Pede confirmação explícita antes de mergear PR — implementar e mergear são pedidos
separados, mesmo quando vêm próximos.

Responder em **português do Brasil**.
