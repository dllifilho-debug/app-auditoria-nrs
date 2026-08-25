# 🦺 App de Auditoria de NRs

Analisa fotos de inspeção de segurança do trabalho e emite laudo de não conformidades
enquadrado nas **Normas Regulamentadoras** brasileiras.

A regra que organiza o projeto inteiro: **o modelo escolhe, o código cita.** Nenhum
agente de IA escreve um número de item de NR no laudo. Eles apontam para entradas de um
dossiê montado a partir dos PDFs oficiais do MTE; na hora de imprimir, o código troca o
rótulo pelo número e pelo texto verbatim da norma. Citação inventada deixa de ser
improvável e passa a ser impossível.

---

## Como rodar

```bash
pip install -r requirements.txt
streamlit run app.py
```

Abra o app e deixe o **Modo demonstração** ligado para conhecê-lo sem chave de API — o
pipeline roda inteiro, com respostas simuladas do modelo. Para analisar fotos de verdade,
desligue o modo demonstração e informe a chave da [Groq](https://console.groq.com/keys),
ou defina `GROQ_API_KEY` no ambiente / nos *Secrets* do Streamlit Cloud.

```bash
pytest tests/          # 41 testes das garantias do produto
```

---

## O pipeline

```
Foto → Agente Olho → Dossiê normativo → Agente Analista → Aferição → Agente Diretor → Laudo
        (visão)       (código)           (enquadramento)   (código)    (supervisão)
                                              ↑                            │
                                              └──────── veto → novo ciclo ─┘
```

| Etapa | Quem executa | O que garante |
|---|---|---|
| **Agente Olho** | modelo de visão | Descreve a foto e nada mais: não conhece norma, não julga, não propõe. Se não há ninguém na imagem, registra isso — e o sistema passa a proibir qualquer cobrança de EPI ou treinamento. |
| **Dossiê normativo** | código | Roteia os fatos por uma taxonomia curada de 122 riscos e por busca BM25 sobre os itens extraídos dos PDFs. O analista só enxerga o que pode se aplicar. |
| **Agente Analista** | modelo de texto | Enquadra os fatos referenciando rótulos do dossiê (`D1`, `D7`…). Nunca escreve um número de NR. |
| **Aferição** | código | Descarta rótulo inexistente, item fora de vigência na data, item repetido e cobrança de EPI sem gente na foto. |
| **Agente Diretor** | modelo de texto | Relê cada enquadramento ao lado do texto oficial do item e veta o que a norma não sustenta. No rigor Máximo, o veto volta ao analista. |
| **Renderização** | código | Escreve as citações a partir dos objetos da base e transcreve o texto oficial. |

O laudo traz, ao final, a trilha completa: quantos ciclos rodaram, o que o supervisor
vetou e o que a aferição descartou.

---

## Base normativa

`auditoria/data/kb.json.gz` — **6.420 itens de 24 NRs**, extraídos dos PDFs oficiais em
`normas/`, com o texto verbatim, o anexo de origem e as datas de vigência de cada item.

**Publicada não é o mesmo que vigente.** A base guarda todas as edições de cada norma e
escolhe, na data da inspeção, a que está em vigor. A NR-10 publicada em 2026 é o caso que
exige isso: ela **renumerou a norma inteira** e só entra em vigor em **01/06/2027** — dos
60 números que existem nas duas edições, 59 têm texto diferente. Citá-la hoje daria número
certo com a redação errada, que é o erro mais difícil de detectar, porque o item existe.
Até junho de 2027 o app cita a edição de 2019, e avisa na barra lateral que há edição
posterior à espera.

Para ampliar a cobertura, **basta colocar o PDF oficial em `normas/`**: a base guarda a
impressão digital do acervo e se reconstrói sozinha quando ele muda. O nome do arquivo
precisa conter `nr` e o número (`nr-20-atualizada-2025.pdf`); um nome que não permita
identificar a norma é sinalizado na barra lateral em vez de ser ignorado em silêncio.

Para forçar a reconstrução:

```bash
python -m auditoria.kb_build
```

### Ampliando a cobertura

`auditoria/catalogo_nr.py` cataloga **as 38 NRs** (36 vigentes; NR-02 e NR-27 revogadas).
Das 36 vigentes, 24 têm o texto integral carregado. Para as demais, o app **sinaliza a
possível aplicabilidade mas nunca cita item** — é a diferença entre admitir o limite e
inventar. Basta colocar o PDF oficial em `normas/` e rodar `kb_build` para que a NR entre
no dossiê.

Faltam: NR-14, 19, 22, 25, 29, 30, 31, 32, 34, 36, 37, 38 — nenhuma delas aplicável a obra civil.

---

## Estrutura

```
app.py                     interface Streamlit
auditoria/
  kb_build.py              PDF oficial → base estruturada de itens
  kb.py                    consulta, busca BM25 e extração de citações
  catalogo_nr.py           as 38 NRs: título, status, palavras-chave
  riscos/                  taxonomia curada: risco observável → itens de NR
  dossie.py                recuperação dos itens candidatos
  pipeline.py              o Gauntlet Loop e a aferição determinística
  modelos.py               cliente Groq com controle de cota
  relatorio.py             renderização em Markdown e HTML imprimível
  demo.py                  dublê de modelo para o modo demonstração
tests/                     testes das garantias
normas/                    PDFs oficiais das NRs
```

---

## Limitações honestas

- Uma foto mostra condições físicas. Ausência de documento (PGR, ordem de serviço,
  ficha de treinamento) **não se enxerga em imagem** e o app não a alega.
- 12 das 36 NRs vigentes ainda não têm texto carregado (nenhuma delas de construção civil).
- A Groq desligou modelos quinze vezes desde 2024, em média a cada um ou dois meses.
  Modelo desligado responde `404`. Quando acontecer, a troca é feita na barra lateral
  — o seletor aceita um ID digitado à mão — consultando as
  [depreciações da Groq](https://console.groq.com/docs/deprecations). Não é preciso
  esperar por uma nova versão do app.
- Só existe um modelo multimodal na Groq hoje, então não há para onde cair dentro do
  mesmo provedor se ele sair.
- O documento gerado é apoio à inspeção. **Não substitui laudo assinado por profissional
  legalmente habilitado.**
