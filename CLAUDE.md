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

**Sem acesso de rede à Groq a partir desta sessão remota.** `api.groq.com` é bloqueado
pela política de egress do container (403 no proxy) — confirmado, não é intermitente.
Isso significa: nada de `ClienteGroq` real aqui, só `ClienteDemonstracao` e testes da
camada determinística (roteador, dossiê, aferição). Testar com o modelo de visão de
verdade é sempre com o usuário, em produção, com fotos e laudos que ele manda de volta.

---

## Onde a coisa parou (02/09/2026)

O lote de 15 fotos rodou inteiro no `Qwen 3.8 27B` nos dois campos, e a partir dele
saíram os PRs #13 (cinco defeitos do lote) e #14 (a NR-12 alcança a betoneira). Uma
segunda rodada, de 4 fotos, validou o #14 e revelou o defeito que virou o #15
(exigência cobrada de todo enquadramento). **O #15 é o único ainda sem validação em
produção.**

**O próximo passo é um só, e só o usuário pode fazer: rodar de novo a `foto (59)`** —
o painel elétrico empoeirado. Ela é o caso que resistiu a duas correções seguidas e
diz se a terceira pegou:

- **Esperado:** a NC de `NR-10 10.10.1` **desaparece** e a poeira reaparece em pontos
  de atenção, com o motivo do veto. A trilha deve registrar um **veto**, não um aparo.
- **Se persistir uma terceira vez:** significa que o Diretor copiou um trecho
  *verdadeiro* de `10.10.1` (provavelmente "identificação de circuitos elétricos") e o
  aplicou à poeira. Aí a verificação mecânica fez o que podia — o trecho existe no item
  — e o que resta é erro de pertinência, o limite conhecido desde o #13. **Nesse caso,
  ler a `exigencia` que o Diretor copiou**: ela está na resposta dele e diz exatamente
  qual trecho foi usado.

O 3.8 **virou o padrão de fato** na prática do usuário (ele seleciona nos dois campos),
mas `PADRAO_VISAO`/`PADRAO_TEXTO` em `modelos.py` **ainda não foram trocados** — é uma
linha cada, e a medição já justifica: 15/15 laudos emitidos (contra 11/14 antes),
7.804 tokens/foto medidos com n=15 contra 7.060 previstos com n=1, ~256 fotos/dia.

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
| Içamento | `GRUA`, `19 PAV. POÇO GRUA SEM PROTEÇÃO`, `17 PAV PROTEÇÃO FOSSO GRUA`, `CANCELA CREMALHEIRA`, `CINTAS DE ELEVAÇÃO` | domínio inteiro que o app nunca viu |
| Poço de elevador | 6 das 19 disponíveis | achado mais repetido do acervo; `vao_caixa_elevador_sem_fechamento` existe e nunca disparou em produção |
| Controle negativo | 5 documentos (POP, lista de presença, CREA, crachá) | devem dar **0 NC**; é a classe de erro que já apareceu e nunca foi testada de propósito |

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

$VENV -m pytest tests/ -q          # 143 testes
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
| Rótulo do risco curado como nome da não conformidade | O rótulo descreve o risco que trouxe o item ao dossiê, não a situação que o Analista enquadrou. Para item **genérico** — `NR-18 18.9.1` ("proteção coletiva onde houver risco de queda"), `NR-06 6.5.1` (EPI, oito riscos) — qual risco o trouxe é acidente do roteamento. Um laudo real saiu intitulado "Andaime sem guarda-corpo e rodapé" para uma constatação sobre a tela frouxa na borda da laje, enquanto o fato dizia que o andaime TINHA guarda-corpo; dois modelos de texto diferentes erraram igual. Hoje `itens_compartilhados()` marca os 22 itens (de 228) que mais de um risco reivindica, e para eles o rótulo cai — o relatório identifica a linha pela constatação. Só o rótulo: o portão de pessoa e a gravidade base continuam vindo do risco. |
| **`sem` é radical-cola: conta, mas não discrimina** | Ele tem 3 letras, então passa o filtro de `_radicais` e vira um radical como outro qualquer. Só que não distingue nada: um sinal de dois radicais em que um é `sem` vale por um. Custou dois defeitos no mesmo dia. `"sem carenagem"` casou com "Carenagem do motor íntegra e fixada, **sem** folgas visíveis" — carenagem em ordem, o oposto do risco. E `"vao no piso sem tampa"` casou numa foto de betoneira porque `sem` e `tampa` vieram de "Abertura circular do tambor **sem tampa**". Ao escrever ou revisar sinal, conte os radicais **discriminantes**, não os radicais. |
| **Quatro radicais é onde a cobertura parcial abre** | O corte é 0,7. Com três radicais, faltar um dá 0,67 e **não passa** — todo radical é obrigatório. Com quatro, faltar um dá 0,75 e **passa**, e o que falta costuma ser justo o discriminante. `"abertura vertical sem fechamento"` casava uma abertura de PISO "sem cobertura ou fechamento visível", faltando só `vertical`. Sinal de até três radicais é seguro por construção; de quatro para cima, escreva sabendo que um pode faltar. **272 dos 866 sinais têm 4+ radicais** e correm esse risco. |
| Regra global para a cobertura parcial — **tentada e descartada** | A saída óbvia (excluir palavras-cola do conjunto que pode ancorar) **quebra 25 sinais legítimos**: `"sem capacete"`, `"sem luva"`, `"sem bota"`, `"sem placa"`, `"sem manometro"` — onde a cola e o discriminante são tudo o que existe. Também não adianta exigir que o radical faltante seja cola (deixa "escada COM sapata" casar "escada sem sapata") nem que seja não-cola (devolve o caso da betoneira). **Não há regra simples**: é encurtar sinal a sinal, com medição. Não gaste a sessão reinventando isto. |
| Verificação mecânica no caminho errado | O aparo do Diretor ganhou verificação de lastro no #13; no lote seguinte, o mesmo enquadramento falso voltou por **aprovado**, sem aparo, e passou inteiro. Ao fechar uma porta num agente, pergunte por quais outras a mesma coisa entra — decisão de modelo muda de caminho de uma rodada para outra. Hoje a exigência é cobrada de todo enquadramento que sobrevive. |
| `git fetch origin main <branch-que-não-existe-mais>` falha inteiro, silenciosamente | Fetch de múltiplos refs é atômico: se um ref já foi deletado no remoto (branch mergeada), o comando inteiro falha e **nenhum ref é atualizado** — inclusive o `main`, que existia e seria atualizado sozinho. `origin/main` local fica congelado na versão de antes, e comparações feitas contra ele mentem. Já causou uma sessão inteira concluir errado que "a reescrita nunca foi mergeada". Se o histórico parecer suspeito, rode `git fetch origin main` sozinho antes de confiar em qualquer diff. |

---

## Estado atual (commit `ae28fcc`)

- **6.358 itens** vigentes de **24 NRs** (de 36 vigentes), extraídos dos PDFs em `normas/`
- **123 riscos** curados mapeando para itens reais; 25 exigem pessoa na cena e
  3 têm item que só entra com máquina nomeada na cena (`itens_so_com_maquina`)
- **143 testes**
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
  segundo contra o item, e o que não ancora vira veto — em aprovado e em aparado. Pega
  exigência **inventada**; não pega trecho verdadeiro citado fora de propósito, e contra
  esse continua agindo só o prompt. Este é o único uso em código do bloco `conferencia`:
  o `fato` copiado segue sem verificação automática.
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
- **Cota.** O teto que aperta é o diário, não o por minuto — e ele é **por modelo**,
  conferido no console em 30/08: 200.000 tokens/dia para `gpt-oss-120b`, `gpt-oss-20b`
  e `qwen/qwen3.6-27b`; **2.000.000 para o `qwen/qwen3.8-27b`**. Também por modelo:
  8.000 TPM e 1.000 requisições/dia. O registro em `modelos.py` carrega o teto de cada
  um (`Modelo.tpd`) e `consumo.py` guarda um balde por modelo — antes o app somava os
  três e comparava com um número só, anunciando 28 fotos/dia e mandando parar de
  auditar com cota sobrando.
  **Medido em produção em 30/08, uma foto por configuração** (n=1, com a ressalva
  abaixo):

  | configuração | tokens/foto | chamadas | fotos/dia |
  |---|---|---|---|
  | Olho no 3.8, texto no `120b` | 13.404 (1.946 + 11.458) | 4 | ~16, preso no `120b` |
  | tudo no `qwen3.8-27b` | **7.060** | 3 | **~283**, preso no TPD |

  A execução de 13.404 teve uma **retentativa** no `120b` — o `_conversar_sem_cortar`
  refazendo JSON que não parseou, com o dobro do teto de saída. Sem ela seriam ~4.600
  no texto, ou ~43 fotos/dia. Os dois números são a mesma medição: o que varia é a
  frequência da retentativa, que uma foto não determina. Entrada por agente, medida
  antes no 3.6: Olho ~1.956 (1.600 são a imagem em 896px), Analista ~1.716 (dossiê
  sozinho: 921), Diretor ~1.551.
  **Com tudo no 3.8, um lote de 100 fotos cabe num dia** e o limite passa a ser tempo
  de parede pela janela de 8.000 TPM (~1,1 foto/min), não mais a cota diária.
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
- **Trocar `PADRAO_VISAO`/`PADRAO_TEXTO` para o `qwen3.8-27b` — uma linha cada, e a
  medição já justifica.** O lote de 15 confirmou: 15/15 laudos emitidos, 7.804
  tokens/foto, ~256 fotos/dia. O usuário já seleciona o 3.8 nos dois campos à mão; o
  padrão do código é que ficou para trás. **Não feito por não ter sido pedido.**
  O que sobra da lista antiga, em ordem de retorno:
  1. Separar o Diretor num modelo diferente do Analista (`gpt-oss-20b`) — **só faz
     sentido se o 3.8 não vingar**. Levaria o texto de ~43 para ~80 fotos/dia contra
     as ~283 do 3.8. Ganho secundário que continua valendo: os dois hoje dividem uma
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
- **Enquadramento que não descumpre o item — duas correções, a segunda sem validar.**
  O caso vive na `foto (59)`: painel empoeirado em `NR-10 10.10.1`, que exige
  SINALIZAÇÃO, com a etiqueta "PERIGO" legível na própria foto. Apareceu primeiro pelo
  aparo (o #13 fechou essa porta) e voltou pelo **aprovado sem aparo** (o #15 fechou a
  outra). **Rodar a `foto (59)` é o próximo passo.** O que a verificação NÃO alcança:
  o Diretor copiar um trecho verdadeiro do item e aplicá-lo fora de propósito — contra
  isso só o prompt age.
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

## Validação em produção de 01–02/09/2026 — o lote de 15 no Qwen 3.8

Primeiro lote inteiro no `Qwen 3.8 27B` nos dois campos. **15 fotos, 21 NCs, 15 laudos
emitidos.** Tudo abaixo foi lido nos laudos reais e reproduzido aqui sem rede.

O que ficou provado:

- **O 3.8 emite onde o `120b` falhava.** 15/15 laudos contra 11/14 antes. As 3 fotos
  que morriam com "não devolveu JSON utilizável" saíram. Valida a correção do
  `_conversar_sem_cortar` (refazer também quando o parser falha, não só quando a API
  sinaliza corte).
- **Custo confirmado com n=15**: 7.804 tokens/foto, contra 7.060 previstos com n=1.
  ~256 fotos/dia; um lote de 100 cabe num dia. O excesso de ~11.200 tokens no lote
  sugere **~2 retentativas em 15 fotos (~12%)** — a retentativa não é o problema de
  cota que se temia.
- **`itens_compartilhados()` funcionou no caso que o motivou**: a tela frouxa na borda
  da laje saiu nomeada pela constatação, não como "Andaime sem guarda-corpo".
- **O balde por modelo aparece na barra lateral** (`qwen/qwen3.8-27b — 117.069 de
  2.000.000`).

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
e o Diretor não. Hoje os três compartilham `_conversar_sem_cortar`. **Toda vez que
crescer o que se pede a um agente, verificar o teto de saída dele.**

**A mesma mensagem voltou no lote de 29/08, com outra causa.** O sumário do lote de 14
listou 3 fotos não auditadas com "Diretor/Analista não devolveu JSON utilizável" — a
retentativa acima já estava em produção, então não era truncamento (`finish_reason ==
"length"`) de novo; era JSON malformado por outro motivo (suspeita: aspas de citação
oficial não escapadas) que a API não sinaliza. `_conversar_sem_cortar` só refazia a
chamada quando a API confirmava o corte; agora refaz também sempre que o parser falha,
sinalizado ou não. **Validado no lote de 15 de 01/09: 15 de 15 laudos saíram**, contra
11 de 14 antes. As 3 fotos que morriam com "não devolveu JSON utilizável" foram
embora.

---

## Como o usuário trabalha

Escreve em maiúsculas, manda print da tela e anexa os HTML dos laudos. Testa em
produção e volta com o resultado. **Levar cada retorno a sério**: quase todo defeito
importante desta sessão saiu de um laudo real que ele mandou, não dos testes.

Pede confirmação explícita antes de mergear PR — implementar e mergear são pedidos
separados, mesmo quando vêm próximos.

Responder em **português do Brasil**.
