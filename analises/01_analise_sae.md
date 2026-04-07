# Análise #01 — Automação SAE

**Data da análise:** 2026-04-07  
**Base:** `relatorio_automacoes_uniube_agregado_01.03_202603311646.csv`  
**Fluxos:** `fluxos_unifenascap_uniube_e_uberlandia_202604011311.xlsx`

---

## Contexto

A automação SAE (Serviço de Apoio ao Estudante) deve ser acionada quando o usuário demonstra claramente que é aluno da instituição ou trata de assuntos acadêmicos de aluno ativo (ex: disciplinas, TCC, estágio, rematrícula).

O canal analisado é de **captação** (futuros alunos), portanto o SAE deveria ser acionado raramente.

### Códigos do SAE
- `D71` — SAE (principal)
- `N43` — SAE 2 (secundário)

### Conteúdo injetado quando acionado
> "Entre em contato diretamente com o SAE para receber orientações completas. Utilize um dos canais disponíveis: WhatsApp da Mentoria 0800 940 2444 (gratuito e aceita ligações de celular) ou 34 3319 8798."

---

## Funil de Acionamento

| Etapa | Conversas | % do total | % da etapa anterior |
|-------|----------:|----------:|--------------------:|
| Total na base | 1.583 | 100,0% | — |
| 1. SAE acionado (chain + validation) | 1.325 | 83,7% | — |
| 2. SAE injetado no contexto da IA | 1.328 | 83,9% | 100,2% |
| 3. **IA enviou instrução SAE ao usuário** | **20** | **1,3%** | **1,5%** |

### Detalhamento do SAE acionado
| Código | Descrição | Conversas |
|--------|-----------|----------:|
| D71 | SAE (principal) | 1.047 (só D71) |
| N43 | SAE 2 | 41 (só N43) |
| D71 + N43 | Ambos | 237 |
| **Total** | **SAE acionado** | **1.325** |

---

## Achados

1. **83,7% das conversas tiveram o SAE acionado** — taxa muito elevada para um bot de captação, onde o público-alvo são futuros alunos, não alunos ativos.

2. **Quando acionado, o SAE é sempre injetado no contexto da IA** (0 casos de acionamento sem injeção).

3. **A IA enviou a instrução ao usuário em apenas 20 conversas (1,5% dos acionamentos)** — em 1.308 conversas o SAE foi acionado e injetado, mas a IA não chegou a mencionar o SAE ao usuário.

---

## Avaliação de Qualidade dos Acionamentos

Todas as 1.325 conversas com SAE confirmado foram analisadas individualmente.

**Metodologia:** leitura das mensagens do usuário + resposta da IA; classificação baseada em sinais explícitos (declaração de ser aluno, ações acadêmicas exclusivas de aluno ativo) ou ausência deles (canal de captação → default prospectivo).

| Veredicto | Conversas | % |
|-----------|----------:|--:|
| ✅ **CORRETO** — usuário era aluno, SAE justificado | 297 | 22,4% |
| ❌ **ERRADO** — usuário era prospectivo, SAE não deveria acionar | 1.028 | 77,6% |
| **Total avaliado** | **1.325** | **100%** |

### Principais sinais dos casos CORRETO
| Sinal | Ocorrências |
|-------|------------:|
| Declarou ser aluno ("sou aluno/a") | 131 |
| IA confirmou que era aluno | 54 |
| Assunto de disciplinas | 23 |
| Solicitação de histórico | 22 |
| Declarou ser ex-aluno | 17 |
| Acesso ao AVA | 8 |
| Cancelamento de matrícula | 8 |
| Quer trancar curso | 7 |

### Principais motivos dos casos ERRADO
| Motivo | Ocorrências |
|--------|------------:|
| "Pretendo ser aluno" (explícito) | 464 |
| Sem sinais de aluno — default prospectivo | 360 |
| Menciona vestibular | 66 |
| Quer se tornar aluno | 33 |
| Pergunta mensalidade/valor | 48 |
| Menciona ENEM | 14 |

### Conclusão
**77,6% dos acionamentos do SAE são falsos positivos.** A automação está sendo disparada para usuários que claramente são candidatos (futuros alunos), não alunos ativos. O custo é baixo pois a IA raramente transmite a instrução ao usuário (apenas 20 conversas), mas o acionamento desnecessário polui o contexto da IA e pode causar respostas equivocadas.

---

## Arquivos gerados

- `01_sae_avaliacoes.csv` — veredicto individual por conversa (conversation_id, verdict, motivo, user_msgs)
