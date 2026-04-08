# Metodologia — Análise de Automações Tolky/Uniube

Documento completo sobre como o dashboard foi construído, como os números são calculados, e o processo de validação de acurácia dos classificadores.

## 1. Contexto

A IA Tolky atende candidatos da Uniube via WhatsApp. Para cada conversa, ela pode acionar automações específicas (SAE, Tickets, Concurso, etc.). Este projeto analisa **se essas automações estão acionando corretamente**.

**Base de dados:** 6.652 conversas únicas (39.650 requests) — período **01/03/2026 a 07/04/2026** (dia 07 excluído por ser parcial).

## 2. Pipeline de acionamento da IA

Cada request roda em paralelo:

1. **decisionChain-<fluxo>** → retorna `{"response": ["CODE"]}` ou `[]`
2. **decisionChain-validation-<fluxo>** → confirma ou rejeita
3. **Confirmado** = ambos retornam o mesmo código
4. **Injetado** = instrução vai como tag `<realtime>` no system prompt
5. **Enviado** = a IA efetivamente menciona a instrução ao usuário

O dashboard mostra esse funil dia a dia.

## 3. Códigos das automações (atualização em 01/04)

| Código antigo | Código novo | Automação |
|---|---|---|
| D71, N43 | **D710** | SAE |
| F27 | **F270** | Tickets Geral |
| O24 | **O242** | Tickets — valores/mensalidade |
| O74 | **O744** | Tickets — mestrado/pós |
| E46 | **E461** | Tickets — email cadastrado |
| W25 | **W253** | Tickets — acesso/login |

A migração aconteceu em **01/04/2026** (rename, mesmo comportamento).

## 4. Como os números são calculados

### 4.1 Funil do dashboard

Para cada conversa, o script `process_sae.py` (e `process_tickets.py`) percorre todos os requests e:

- **total** = todas as conversas únicas
- **confirmed** = chain ∩ validation contém código da automação
- **injected** = `<realtime>` com marcador específico no payload do `createAssistantResponse`
- **replied** = marcador específico aparece na resposta da IA ao usuário

### 4.2 Marcadores usados

**SAE:**
- `Entre em contato diretamente com o SAE`
- `WhatsApp da Mentoria`

**Tickets:** verifica se o código retornado pertence ao set `{F27, F270, O242, O744, E461, W253}`.

### 4.3 Veredito CORRETO/ERRADO

Aplicado **apenas em conversas confirmadas**. Cada conversa recebe um julgamento via classificador regex (`process_sae.py` e `process_tickets.py`):

- **CORRETO** = acionamento foi adequado dado o contexto da conversa
- **ERRADO** = falso positivo (não deveria ter acionado)

## 5. Critérios de cada automação

### 5.1 SAE

> Acionar **apenas para alunos ativos** tratando de assuntos acadêmicos.

**CORRETO se:** "sou aluno", "ex-aluno", "estudo na Uniube", "trancar curso", "meu histórico", "AVA não acessa", "atestado matrícula", "termo estágio", "diploma", problemas de acesso/login, mensalidade de aluno ativo, cancelar compra, etc.

**ERRADO se:** "pretendo ser aluno", "não sou aluno", aluno de outra instituição, prospectivo perguntando valores, transferência externa de candidato, etc.

### 5.2 Tickets

> Acionar quando o usuário menciona um dos 5 critérios definidos no prompt.

**Sub-códigos e critérios:**

| Código | Critério |
|---|---|
| **F270/F27** (umbrella) | Vale se qualquer um dos abaixo bater |
| **O242/O24** | valor, preço, mensalidade, custo, "quanto custa", desconto |
| **O744/O74** | mestrado, pós-graduação, doutorado, especialização, MBA |
| **E461/E46** | email cadastrado errado/perdido, alterar email |
| **W253/W25** | área do candidato, não consegue acessar/logar, senha, token não chega |
| **F270/F27** específico | Medicina Humana (não veterinária) |

## 6. Processo de melhoria de acurácia

Aplicado iterativamente em cada classificador:

1. **Versão inicial:** regex baseado em palavras-chave dos critérios
2. **Amostragem:** 100 CORRETO + 100 ERRADO (random_state fixo) extraídos com `extract_full_convs.py` / `extract_sae_sample.py`
3. **Extração de contexto completo:** `all_request_messages` da raw data, salvo como JSONL
4. **Compactação:** `sample_*_compact.jsonl` — user msgs (300 chars) + 5 IA msgs (250 chars) para caber no contexto
5. **Validação manual:** leitura batch a batch (~15 conversas por vez) com julgamento humano salvo em `manual_review_*.csv`
6. **Análise de erros:** identificar padrões nos falsos CORRETO e falsos ERRADO
7. **Refinamento de regex:** novos padrões adicionados sem quebrar os antigos
8. **Re-validação:** mesma amostra, novos números

### 6.1 Mudanças críticas no classificador

**Tickets — passos da melhoria:**

| Iteração | Ação | Acurácia |
|---|---|---|
| v1 | Regex genérico, F27 com `RE_HUMANO` (palavras como "problema", "erro") | ~33% (subestimando errado) |
| v2 | F27 vira "umbrella" — vale se qualquer sub-critério bater | 86,9% |
| v3 | Match SÓ no texto do usuário (não na resposta da IA) + regex de medicina exclui veterinária + email/token expandidos | **91,5%** |

**SAE — passos da melhoria:**

| Iteração | Ação | Acurácia |
|---|---|---|
| v1 | Regex `\bsou\s+(aluno\|ex-aluno)\b` + temas básicos | ~73,5% |
| v2 | Adiciona `RE_NAO_ALUNO` (prioridade), `RE_OUTRA_INSTIT` (exclui Unifran/UFU/etc), `RE_SOU_ALUNO_FORTE` mais preciso, `RE_ALUNO_TEMA` com 30+ padrões específicos | 81,5% |
| v3 | Aprofunda padrões de problema de acesso ("não estou conseguindo conectar", "como faço para acessar"), email institucional com hyphen, dívida, tratamento/trancamento, "ser aluno na uniube" | **93,5%** |

## 7. Memória de cálculo dos números reportados

Para projetar **números reais** a partir de uma amostra validada manualmente, aplicamos:

```
real_correto = clf_correto * (1 - taxa_falso_correto) + clf_errado * taxa_falso_errado
real_errado  = total_confirmed - real_correto
```

Onde:
- `clf_correto` / `clf_errado` = números do classificador atual
- `taxa_falso_correto` = falsos CORRETO / total CORRETO na amostra (overestimação)
- `taxa_falso_errado` = falsos ERRADO / total ERRADO na amostra (subestimação)

**Exemplo (Tickets v3):**
- clf_correto = 2.351, clf_errado = 1.060
- amostra: fp = 7/86 = 8,1%, fn = 10/113 = 8,8%
- real_correto = 2.351 × 0.919 + 1.060 × 0.088 = 2.161 + 93 = ~2.254 (66,1%)
- real_errado = 3.411 - 2.254 = ~1.157 (33,9%)

## 8. Resultados finais

### 8.1 SAE (v4 — atual)
- Total conversas: **6.637** (excluindo 07/04)
- Acionado: **4.717** (71%)
- Injetado: **2.518** · Enviado: **144**
- ✅ Correto: **730** (15,5%)
- ❌ Falso positivo: **3.987** (84,5%)
- **Acurácia do classificador: 95,0%** (190/200)

### 8.2 Tickets (v4 — atual)
- Total conversas: **6.637**
- Acionado: **3.406** (51%)
- ✅ Correto: **2.424** (71,1%)
- ❌ Falso positivo: **982** (28,9%)
- **Acurácia do classificador: 95,0%** (189/199)

### 8.3 Uberlândia (v1 — novo)
- Total conversas: **6.637**
- Acionado: **512** (7,7%)
- ✅ Correto: **69** (13,5%)
- ❌ Falso positivo: **443** (86,5%)
- Classificador: regex simples `\buberl[aâã]ndia\b` no texto do usuário
- **Sem validação manual ainda**

⚠️ **Uberlândia tem o pior desempenho de acionamento** — 86% de falsos positivos. A IA está disparando a automação em conversas que nunca mencionam Uberlândia.

## 9. Melhoria iterativa até 95%

### 9.1 Tickets: 91,5% → 95% (v3 → v4)

**Problema identificado:** cada sub-código (O242, O744, E461, W253) só reconhecia CORRETO se o usuário mencionasse o tema específico daquele código. Quando a IA disparava o código errado (ex.: O242 para uma conversa sobre acesso), o classificador marcava como ERRADO.

**Solução:** **Todos os códigos viram umbrella** — basta bater em qualquer um dos 5 critérios (medicina/valores/pós/email/acesso) para contar como CORRETO, independente do sub-código disparado.

**Ajustes adicionais nos regexes:**
- `RE_MEDICINA` — exclui "medicina. Veterinária" (com ponto)
- `RE_VALORES` — adiciona "quanto está", "quanto vou pagar"
- `RE_EMAIL` — adiciona "deu erro email", "email não existe"
- `RE_ACESSO` — adiciona "esperando token", "vestibular online não está abrindo", "documentos PDF não está enviando", "não estou conseguindo finalizar/enviar/ver/achar"

**Resultado:**
- False ERRADO caiu de 8,8% → 1,9%
- False CORRETO estável em ~8%
- Lógica mais alinhada com "a conversa justifica abrir QUALQUER ticket?" ao invés de "o sub-código exato bate?"

### 9.2 SAE: 93,5% → 95% (v3 → v4)

**Problema identificado:** conflito entre regras. Exemplo: "Já sou aluna da UNIUBE pedagogia... sou formada em licenciatura em biologia" — batia em RE_UNIUBE_EXPLICITO (aluna Uniube) E em RE_OUTRA_INSTIT (formada em outra coisa). A ordem de teste decidia — OUTRA era testada primeiro, ERRADO errado.

**Solução:** **Prioridade explícita no classificador.**

```python
def classify(user_text, ia_text):
    # P1: menção explícita aluno Uniube vence tudo
    if RE_UNIUBE_EXPLICITO.search(user_text):
        return "CORRETO", "aluno Uniube explicito"
    # P2: ex-aluno querendo nova graduação = prospectivo
    if RE_EX_SEGUNDA.search(user_text):
        return "ERRADO", "ex-aluno quer nova graduacao"
    # P3: explícita não aluno
    if RE_NAO_ALUNO.search(user_text):
        return "ERRADO", "explicita nao ser aluno"
    # P4: outra instituição
    if RE_OUTRA_INSTIT.search(user_text):
        return "ERRADO", "aluno de outra instituicao"
    # P5+: aluno tema, sou aluno forte, prospectivo
    ...
```

**Novos regexes:**
- `RE_UNIUBE_EXPLICITO` — "sou aluno da Uniube", "estudo na Uniube", "aluno da Uniube"
- `RE_EX_SEGUNDA` — "ex aluno + segunda graduação/nova graduação/qual valor"

**Resultado:** 93,5% → 95%, 5 false CORRETO e 5 false ERRADO (balanceado).

## 10. Feature: Sub-códigos e Mensagem-gatilho

### 10.1 Sub-automações acionadas (chart)
Cada automação tem 1+ códigos possíveis. O dashboard agora mostra:
- Barras empilhadas (correto/falso positivo) por sub-código
- Formato: "Nome da automação (CÓDIGO)"

### 10.2 Mensagem gatilho (trigger_msg)
Identifica **exatamente qual mensagem do usuário** fez a IA disparar a automação.

**Como é calculado:**
- Cada row na raw CSV = 1 request/turno
- Quando `decisionChain-<fluxo>` retorna código válido, salvamos a **última mensagem do usuário daquele request** (truncada em 500 chars)
- Salvo na coluna `trigger_msg` do `*_avaliacoes.csv`

**Uso:** Na tabela drill-down, nova coluna "Mensagem gatilho" ao lado de "Mensagens do usuário". Facilita entender por que a IA tomou aquela decisão.

## 11. Arquivos do projeto (atualizados)

| Arquivo | Função |
|---|---|
| `dashboard.py` | App Streamlit |
| `process_sae.py` | Pipeline SAE (95% accuracy) |
| `process_tickets.py` | Pipeline Tickets (95% accuracy) |
| `process_uberlandia.py` | Pipeline Uberlândia (sem validação manual) |
| `extract_sae_sample.py` | Sampler para validação SAE |
| `extract_full_convs.py` | Sampler para validação Tickets |
| `analises/01_sae_avaliacoes.csv` | SAE: verdict + codigos + trigger_msg |
| `analises/01_sae_metadata.json` | SAE: funil + datas |
| `analises/02_tickets_avaliacoes.csv` | Tickets: verdict + codigos + trigger_msg |
| `analises/02_tickets_metadata.json` | Tickets: funil + datas |
| `analises/03_uberlandia_avaliacoes.csv` | Uberlândia: verdict + codigos + trigger_msg |
| `analises/03_uberlandia_metadata.json` | Uberlândia: funil + datas |
| `analises/manual_review_sae.csv` | 200 amostras SAE revisadas |
| `analises/manual_review.csv` | 199 amostras Tickets revisadas |
| `analises/01_analise_sae.md` | Doc inicial SAE |
| `METODOLOGIA.md` | Este arquivo |

## 9. Insights descobertos durante a análise

### 9.1 Mudança de prompt SAE em 02/04
Comparando 01/04 vs 02/04+:
- **01/04:** "demonstrar que é aluno **OU** estiver tratando de assuntos acadêmicos"
- **02/04+:** "demonstrar que é aluno **E** estiver tratando de assuntos acadêmicos"

A troca de OU→E **não reduziu falsos positivos** — pelo contrário, em 03/04 a taxa de erro subiu para ~95% nos acionamentos confirmados. O modelo passou a interpretar "pretendo ser aluno" como satisfazendo ambas as condições.

### 9.2 Mudança de comportamento em 11/03
A taxa de acionamento SAE caiu de ~84% (01-10/03) para ~62% (11-31/03). Causa não confirmada — provavelmente outro ajuste de prompt.

### 9.3 Cobertura do prompt SAE atual
A descrição do critério não distingue claramente "aluno ativo" de "candidato/prospectivo". Sugestão: incluir explicitamente "**aluno ATIVO já matriculado, NÃO prospectivos/vestibulandos**".

## 10. Limitações conhecidas

1. **Regex tem teto:** ~93-95% de acurácia. Para 95%+ confiável seria preciso LLM por conversa.
2. **Amostra de validação fixa:** 200 conversas (random_state=42) — pode haver bias se a distribuição muda.
3. **Mensagens da IA não usadas no classificador:** evita falsos positivos por menção de keywords nas respostas.
4. **Contexto truncado na revisão manual:** primeiras 15 mensagens do usuário e 5 mensagens da IA (250-300 chars cada).
5. **Áudios/imagens:** o classificador não consegue analisar conteúdo multimodal — alguns acionamentos via áudio podem ficar como ERRADO sem evidência.

## 11. Arquivos do projeto

| Arquivo | Função |
|---|---|
| `dashboard.py` | App Streamlit |
| `process_sae.py` | Pipeline de extração + classificação SAE |
| `process_tickets.py` | Pipeline de extração + classificação Tickets |
| `extract_sae_sample.py` | Sampler para validação manual SAE |
| `extract_full_convs.py` | Sampler para validação manual Tickets |
| `analises/01_sae_avaliacoes.csv` | Veredictos por conversa SAE |
| `analises/01_sae_metadata.json` | Funil + datas + funil diário SAE |
| `analises/02_tickets_avaliacoes.csv` | Veredictos por conversa Tickets |
| `analises/02_tickets_metadata.json` | Funil + datas + funil diário Tickets |
| `analises/manual_review_sae.csv` | 200 amostras SAE com julgamento humano |
| `analises/manual_review.csv` | 199 amostras Tickets com julgamento humano |
| `analises/sample_sae_compact.jsonl` | Conversas SAE com contexto completo (compactadas) |
| `analises/sample_compact.jsonl` | Conversas Tickets com contexto completo |
| `analises/01_analise_sae.md` | Documentação inicial da análise SAE |
| `METODOLOGIA.md` | Este arquivo |
