---
name: conferir
description: "Conferência factual exaustiva, não julgamento. Extrai toda afirmação factual de um artefato — número, hash, nome de função, item de NR, afirmação sobre o que outro documento diz — e confere cada uma contra o repositório e contra o código executado. Devolve inventário de 100% das afirmações como CONFERE, DIVERGE ou NÃO VERIFICÁVEL. Use em todo commit que toca o CLAUDE.md e em todo corpo de PR que cite número."
allowed-tools: Bash(git show:*), Bash(git log:*), Bash(git diff:*), Bash(git grep:*), Bash(grep:*), Bash(python3 -c:*), Bash(PYTHONPATH=. python3 -c:*), Read, Grep, Glob
---

# /conferir — conferência factual

Você não julga se a decisão é boa. Você confere se os fatos que ela cita são
verdadeiros. Um artefato pode estar inteiro CONFERE e ainda ser uma péssima
decisão — esse julgamento é de `/critico`, não seu.

## Por que existe

Densidade de texto e citação abundante passam sensação de rigor sem serem
rigor. O erro sobrevive exatamente onde o tema principal está certo: um número
citado de passagem, num parêntese, longe do assunto central, ao lado de uma
conclusão correta. Ninguém reconfere porque o entorno parece conferido.

Medido neste repositório em 03/09: cinco divergências, das quais uma nasceu
errada e sobreviveu a três sessões e quatro PRs (`272 dos 866 sinais` — eram
271 de 867 no commit em que a frase foi escrita), e uma foi escrita no mesmo
commit cuja mensagem declarava "números conferidos contra o código".

## O contrato

**Entrada:** um artefato — caminho de arquivo, referência git, ou corpo de PR.

**Saída:** inventário de **100%** das afirmações factuais. Não amostra, não
"as principais", não "as mais relevantes". Se o artefato tem 40 afirmações, o
inventário tem 40 linhas. Uma afirmação que você decidiu não conferir é uma
afirmação NÃO VERIFICÁVEL com o motivo escrito, nunca uma linha ausente.

Formato de cada linha:

```
CONFERE          | <afirmação, abreviada> | <como conferiu>
DIVERGE          | <afirmação, abreviada> | real: <valor> | <como conferiu>
NÃO VERIFICÁVEL  | <afirmação, abreviada> | <por que não dá para conferir aqui>
```

Feche com a contagem: `N afirmações · X CONFERE · Y DIVERGE · Z NÃO VERIFICÁVEL`.

## O que conta como afirmação factual

- **Número de qualquer espécie**: contagens, percentuais, medições, tokens,
  cobertura, prazos, quantidade de testes, quantidade de itens ou riscos
- **Identificador**: hash de commit, número de PR, nome de arquivo, nome de
  função, nome de variável, chave de risco, rótulo de dossiê
- **Citação normativa**: número de NR, número de item, texto atribuído à norma
- **Afirmação sobre outro documento**: "o `CLAUDE.md` diz que…", "o item X
  exige…", "o teste Y trava isso"
- **Afirmação sobre comportamento do código**: "esse sinal não dispara",
  "esse item entra no dossiê", "essa função retorna vazio"
- **Afirmação histórica**: "isso foi corrigido no #14", "esse defeito apareceu
  no lote de 15"

Não conta: opinião, recomendação, previsão, e prosa que não afirma fato
("merece medição antes de implementar" não é afirmação factual).

## As três fontes de verdade, nesta ordem

**1. O código executado — é a fonte principal deste projeto, não o texto.**

Os números daqui não estão escritos em lugar nenhum: são computados. `123
riscos` não vive num arquivo, sai de `len(catalogo())`. `6.358 itens` sai de
`carregar_base()`. Conferir por `grep` marcaria NÃO VERIFICÁVEL justamente as
afirmações que mais erram — quatro das cinco divergências de 03/09 só
apareceram porque o catálogo foi executado.

```bash
PYTHONPATH=. python3 -c "
from auditoria.riscos import catalogo, itens_compartilhados
from auditoria.kb import carregar_base, radicais, radical
c = catalogo()
print('riscos:', len(c))
print('construcao:', sum(1 for r in c.values() if r.dominio == 'construcao'))
print('exige_pessoa:', sum(1 for r in c.values() if r.exige_pessoa))
sinais = [s for r in c.values() for s in r.sinais]
print('sinais:', len(sinais), '| 4+ radicais:', sum(1 for s in sinais if len(radicais(s)) >= 4))
"
```

O núcleo (`kb`, `riscos`, `dossie`, `pipeline`) é stdlib puro e roda sem venv.
Para `pytest`, `streamlit` e a interface, use o venv do scratchpad.

**Execute apenas leitura.** `python3 -c` que importa, conta e imprime é
leitura. Nunca escreva arquivo, nunca rode `kb_build`, nunca altere estado.

**2. O repositório, por git.** Para afirmação histórica, use `git log -S`,
`git show`, `git log --oneline`. Conferir "isso foi corrigido no #14" contra o
que o #14 de fato mudou, não contra o que outro documento diz que ele mudou.

**3. O texto oficial da norma, pela base.** Toda citação de item de NR se
confere contra `carregar_base()`, com a data de referência correta — publicada
não é vigente, e `carregar_base(referencia=data)` escolhe a edição certa.

```bash
PYTHONPATH=. python3 -c "
from auditoria.kb import carregar_base
from datetime import date
b = carregar_base(referencia=date(2026, 9, 2))
i = b.obter('NR-18', '18.10.1.27')
print(i.texto[:200] if i else 'ITEM NÃO EXISTE NA BASE')
"
```

Item que não existe na base é DIVERGE, não NÃO VERIFICÁVEL.

## Armadilhas desta conferência

**Número herdado não é número conferido.** Uma afirmação copiada de versão
anterior do documento conta como afirmação nova: reconfira. Foi assim que o
`272 dos 866` atravessou três sessões.

**Confira contra o commit em que a frase foi escrita, não só contra HEAD.**
Um número pode estar certo na origem e ter ficado velho (é desatualização), ou
ter nascido errado (é erro). Os dois são DIVERGE, mas a distinção importa para
quem vai consertar, e cabe na coluna "como conferiu".

**A conclusão certa não garante o número certo.** A frase "cinco dos seus sete
sinais dependem da palavra `elevador`" acompanhava uma conclusão correta — o
risco realmente não dispara. Eram sete de sete. Confira o número mesmo quando
concorda com a tese.

**Não pare no primeiro DIVERGE.** O inventário é de 100%; achar um erro não
encerra a passada.

**Denominador também é afirmação.** "22 itens de 228" são dois números, e os
dois se conferem.
