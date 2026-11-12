# Especificação de métricas e avaliação — FoodFlow v2

Este documento transforma a revisão metodológica em especificação de
implementação. Ele descreve **o que é medido**, **com qual fórmula**, **quais
limitações existem** e **como validar** cada número. Nenhuma métrica aqui é
ajustada para melhorar resultado: quando o dado não permite concluir, o
relatório deve dizer isso explicitamente.

> Estado: implementado para ranking, qualidade preditiva, coorte válida do A/B,
> inferência por usuário, comparação com o modelo em produção, ILD, novidade,
> Brier, Log Loss, PR AUC, curva de calibração, avaliação rolling-window,
> sensibilidade a negativos observados/não observados e política temporal
> explícita. Atributos atuais do restaurante continuam com risco de vazamento
> quando não há snapshots históricos; `--strict-temporal` remove esses atributos.

---

## 1. Semântica do alvo e política de negativos

### 1.1 O alvo é compra, não clique

O rótulo positivo do treino é `purchased` (antigo `clicked`). Ele significa
**pedido observado no contexto**, com relevância binária:

$$
y_{u,r,t} =
\begin{cases}
1 & \text{se o usuário } u \text{ pediu no restaurante } r \text{ no contexto } t\\
0 & \text{caso contrário}
\end{cases}
$$

O modelo **não** é um estimador de clique. Para modelar interesse/clique seria
necessário um alvo próprio e uma janela de atribuição de exposição. A separação
entre “modelo de interesse” e “modelo de conversão” permanece como evolução
pendente.

### 1.2 Negativos observados × não observados

Ausência de pedido não é rejeição. O dataset distingue:

| Situação | Definição | Peso no treino |
|---|---|---|
| Positivo | `purchased = 1` | `1.0` |
| Negativo observado | `purchased = 0` e houve interação registrada antes de `until` | `1.0` |
| Negativo não observado | `purchased = 0` e nenhuma interação registrada | `UNOBSERVED_NEGATIVE_WEIGHT = 0.1` |

O peso é usado **somente no treino** (`sample_weight`). As métricas de ranking
continuam usando o catálogo inteiro e o rótulo binário; o relatório registra
`observed_negatives`, `unobserved_negatives` e `negative_policy`.

Como o catálogo inteiro é a avaliação principal, negativos não observados ainda
entram como não relevantes. Para não esconder esse efeito, o relatório inclui
`ranking_sensitivity` com dois pools diagnósticos:

- `negativos_observados`: positivos + negativos com exposição observada;
- `negativos_nao_observados`: positivos + negativos sem exposição.

Cada pool só é calculado se houver ao menos um negativo do tipo; caso contrário
é marcado `available = false` para evitar métrica trivial. A análise de
sensibilidade **não substitui** a avaliação principal: restringir candidatos
muda o objetivo da métrica.

Limitação explícita: o peso `0.1` é uma escolha de engenharia, não um valor
estimado por dados. Ele deve ser validado com dados de exposição reais.

---

## 2. Dimensão 1 — Qualidade do ranking

### 2.1 Contexto de avaliação

Um contexto é a ocasião de pedido:

```
contexto = (user_id, data local, turno)
```

O instante `until` é o primeiro pedido da ocasião. Features usam apenas pedidos
e interações **anteriores** a `until`. Os candidatos são todos os restaurantes
do catálogo, iguais para LightGBM, popularidade e aleatório.

As métricas são calculadas **por contexto** e agregadas por macro-média:

$$
M_{\text{macro}} = \frac{1}{N}\sum_{i=1}^{N} M_i
$$

Contextos sem item relevante entram com valor `0` (não são ignorados).
Contextos sem candidatos são contados e excluídos (não há ranking para avaliar).

### 2.2 Precision@K

$$
P@K = \frac{\text{nº de itens relevantes no Top K}}{\min(K, n_{\text{candidatos}})}
$$

O denominador usa `min(K, n_candidatos)` para não penalizar contextos com menos
de K candidatos.

### 2.3 Recall@K

$$
R@K = \frac{\text{nº de itens relevantes no Top K}}{\text{nº total de itens relevantes no contexto}}
$$

Se o contexto não tem item relevante, `R@K = 0`.

### 2.4 NDCG@K (relevância binária)

$$
DCG@K = \sum_{i=1}^{K} \frac{rel_i}{\log_2(i+1)}, \qquad
NDCG@K = \frac{DCG@K}{IDCG@K}
$$

`IDCG@K` é o DCG do ranking ideal (relevâncias ordenadas de forma decrescente).
Se `IDCG = 0`, `NDCG@K = 0`.

Empates de score são desempatados por `restaurant_id`, de forma determinística.

**Evolução especificada (não implementada):** NDCG com ganho graduado, usando
eventos da mesma janela de atribuição:

| Evento | Ganho sugerido |
|---|---|
| Sem exposição observada | desconhecido (não usar como 0) |
| Impressão sem clique | 0 |
| Visualização de detalhes | 1 |
| Clique | 2 |
| Favorito | 3 |
| Compra | 5 |

Os pesos são uma proposta inicial, não validados empiricamente. Não se deve
misturar eventos de contextos diferentes nem tratar ausência de exposição como
zero.

### 2.5 MAP@K

$$
AP@K = \frac{1}{\min(R, K)}\sum_{i=1}^{K} P(i)\cdot rel_i
$$

onde `R` é o número de itens relevantes no contexto e `P(i)` é a precisão nas
primeiras `i` posições. `MAP@K` é a média macro de `AP@K` entre contextos.

### 2.6 Cobertura

Duas métricas separadas:

$$
\text{catalog\_coverage} = \frac{|\text{restaurantes recomendados no Top K}|}{|\text{catálogo}|}
$$

$$
\text{user\_coverage} = \frac{|\text{usuários que receberam recomendação}|}{|\text{usuários avaliados}|}
$$

`coverage` permanece como alias histórico de `catalog_coverage` no contrato do
painel.

### 2.7 Intra-List Diversity (ILD@K)

$$
ILD@K = \frac{2}{K(K-1)}\sum_{i<j}\bigl(1 - sim(i,j)\bigr)
$$

A similaridade implementada é Jaccard entre conjuntos de categorias + cozinha:

$$
sim(i,j) = \frac{|A_i \cap A_j|}{|A_i \cup A_j|}
$$

Sem atributos disponíveis, `ild_at_k = None`.

### 2.8 Novidade (Novelty@K)

$$
Novelty(r) = -\log_2\left(\frac{pop(r)}{N}\right), \qquad
Novelty@K = \frac{1}{K}\sum_{r \in TopK} Novelty(r)
$$

`pop(r)` é a contagem de pedidos do restaurante no contexto de referência e `N`
o total de pedidos. O piso de `1` evita `log(0)`. Sem contagens de
popularidade, `novelty_at_k = None`.

### 2.9 Intervalos de confiança por usuário

As métricas offline são reportadas com IC 95% por **bootstrap agrupado por
usuário**:

1. reamostrar usuários com reposição;
2. recalcular a métrica macro preservando todos os contextos do usuário;
3. repetir `BOOTSTRAP_RESAMPLES = 1000` vezes;
4. usar os percentis 2,5% e 97,5%.

Reamostrar linhas individuais quebraria a dependência entre contextos do mesmo
usuário. O relatório inclui `confidence_intervals` com `unit = "user"`.

---

## 3. Dimensão 2 — Qualidade preditiva

Cada métrica tem disponibilidade própria:

| Métrica | Requisito |
|---|---|
| ROC AUC | `>= 20` amostras, `>= 5` positivos e `>= 5` negativos |
| PR AUC | pelo menos um positivo e um negativo |
| Brier Score | rótulos e probabilidades válidos (qualquer composição de classes) |
| Log Loss | rótulos e probabilidades válidos (qualquer composição de classes) |
| Calibração/ECE | rótulos e probabilidades válidos (qualquer composição de classes) |

Quando uma métrica não pode ser calculada, ela é `None` e o motivo aparece em
`roc_auc_note`, `pr_auc_note` ou `predictive_notes`. Brier, Log Loss e
calibração **não** ficam condicionados à ROC AUC.

### 3.1 ROC AUC

$$
AUC = P\bigl(s(x^+) > s(x^-)\bigr)
$$

Mede separação, não calibração.

### 3.2 PR AUC

`average_precision_score` (área sob a curva precisão-recall). É mais informativa
que ROC AUC sob desbalanceamento forte.

### 3.3 Brier Score

$$
BS = \frac{1}{N}\sum_{i=1}^{N}(p_i - y_i)^2
$$

Quanto menor, melhor. Mede o erro quadrático da probabilidade.

### 3.4 Log Loss

$$
LL = -\frac{1}{N}\sum_{i=1}^{N}\bigl[y_i\log(p_i) + (1-y_i)\log(1-p_i)\bigr]
$$

Probabilidades são limitadas a `[1e-6, 1-1e-6]` para evitar log de zero.

### 3.5 Curva de calibração e ECE

As probabilidades são agrupadas em 10 bins de largura fixa. Para cada bin:

$$
\text{erro}_{\text{bin}} =
\bigl|\overline{p}_{\text{bin}} - \text{taxa observada}_{\text{bin}}\bigr|
$$

$$
ECE = \sum_{\text{bins}} \frac{n_{\text{bin}}}{N}\,\text{erro}_{\text{bin}}
$$

O relatório também expõe `max_calibration_error`. A curva é diagnóstica: não
substitui Brier/Log Loss e não autoriza promoção sozinha. O contrato inclui
`calibration.bins` com contagem, probabilidade média e taxa observada por bin.

---

## 4. Dimensão 3 — Desempenho experimental A/B

### 4.1 Unidade e atribuição

- Unidade experimental: **usuário**.
- Grupo derivado por SHA-256 de `experiment_version:user_id`.
- Atribuição persistida em `experiment_assignments` com versão e data.
- Eventos `experiment_mode = 'demo'` são excluídos de todas as métricas
  oficiais e reportados separadamente em `demo_events`.

### 4.2 Taxas descritivas

$$
CTR = \frac{\text{cliques}}{\text{impressões}}, \qquad
CVR = \frac{\text{compras}}{\text{impressões}}
$$

$$
DetailRate = \frac{\text{VIEW\_DETAILS}}{\text{impressões}}, \qquad
FavoriteRate = \frac{\text{FAVORITE}}{\text{impressões}}
$$

`VIEW` legado é contado separadamente e não infla `detail_rate`.

### 4.3 Coorte válida e contaminação

Há duas visões:

- **bruta** (`groups`): todos os eventos oficiais, para auditoria;
- **válida** (`valid_groups`): exclui usuários contaminados, usada para leitura
  e inferência.

Contaminação é detectada quando:

1. o mesmo usuário aparece em mais de um grupo nos eventos oficiais; ou
2. o grupo do evento diverge da atribuição persistente para a versão atual.

$$
\text{contamination\_rate} =
\frac{\text{usuários contaminados}}{\text{usuários experimentais únicos}}
$$

### 4.4 Inferência por usuário

Para cada grupo:

$$
CTR_u = \frac{\text{cliques do usuário } u}{\text{impressões do usuário } u}, \qquad
CVR_u = \frac{\text{compras do usuário } u}{\text{impressões do usuário } u}
$$

A comparação principal usa a **média por usuário** e bootstrap agrupado:

1. reamostrar usuários de cada grupo com reposição;
2. calcular a diferença das médias;
3. repetir `BOOTSTRAP_RESAMPLES = 1000` vezes;
4. IC 95% pelos percentis 2,5% e 97,5%;
5. construir uma **distribuição nula explícita** sob H0: centralizar as duas
   amostras na média conjunta e reamostrar os grupos; o p-valor bilateral é a
   proporção de diferenças nulas com magnitude maior ou igual à observada
   (com correção de continuidade);
6. reportar o método como `bootstrap_null_distribution_by_user`.

A **evidência principal é o IC 95% da diferença**. Um resultado só é marcado
como significante quando `p < alpha_corrigido` **e** o IC da diferença exclui
zero. O p-valor não é a proporção de diferenças positivas da distribuição
observada; ele vem da distribuição nula construída sob H0.

Quando há menos de dois usuários válidos por grupo, o bootstrap não é
identificável. Nesse caso, o relatório usa explicitamente o teste z por
impressão como **fallback**, sem IC bootstrap, com a limitação registrada em
`method` (`z_test_by_impression_fallback`).

### 4.5 Múltiplas comparações e exigência de baseline

A inferência é sempre contra o grupo `baseline`. **Sem baseline com impressões e
usuários mínimos na coorte válida, a análise estatística permanece
indisponível**, mesmo que dois grupos variantes tenham volume. O relatório
expõe `baseline_ready` e `comparison_groups` (apenas grupos com impressões);
`ready_comparison_groups` lista o subconjunto que atinge o volume mínimo e
entra efetivamente nas comparações.

Comparações planejadas: 2 métricas (`ctr`, `conversion_rate`) × cada grupo
pronto (`personalized`, `distance`) contra `baseline`. Com os dois grupos,
`m = 4`.

$$
\alpha_{\text{corrigido}} = \frac{\alpha}{m}, \qquad
m = 2 \times |ready\_comparison\_groups|
$$

Significância só é declarada quando `p < alpha_corrigido` **e** o IC 95% da
diferença exclui zero.

### 4.6 Lift

$$
\text{Lift} = \frac{\text{taxa}_{\text{variante}} - \text{taxa}_{\text{baseline}}}
{\text{taxa}_{\text{baseline}}} \times 100\%
$$

O relatório apresenta também a diferença absoluta em pontos percentuais, porque
o lift relativo pode parecer grande quando a taxa inicial é pequena.

### 4.7 Dimensionamento da amostra

Aproximação para duas proporções independentes:

$$
n \approx
\frac{2(z_{1-\alpha/2} + z_{1-\beta})^2 \bar p(1-\bar p)}
{(p_1 - p_0)^2}, \qquad
\bar p = \frac{p_0 + p_1}{2}
$$

O plano usa a taxa do baseline da coorte válida, efeito relativo mínimo de 20%,
poder de 80% e `alpha` corrigido por Bonferroni. O resultado é um **piso**: a
unidade real é o usuário e a variância agrupada pode ser maior.

### 4.8 Fases do painel

| Fase | Significado |
|---|---|
| `COLLECTING` | não há impressões oficiais na coorte válida |
| `INSUFFICIENT_DATA` | há dados, mas abaixo do mínimo descritivo |
| `READY` | volume mínimo descritivo; **não é significância** |
| `STATISTICAL_ANALYSIS` | volume mínimo para inferência; testes são executados |

`READY` nunca deve ser apresentado como “resultado comprovado”.

---

## 5. Dimensão 4 — Saúde e confiabilidade dos dados

O relatório expõe:

- usuários únicos e usuários por grupo;
- contextos únicos (treino, validação, teste);
- impressões brutas e impressões da coorte válida;
- eventos sem atribuição (`untagged_events`);
- eventos de demonstração (`demo_events`);
- percentual de usuários contaminados;
- proporção de negativos observados e não observados;
- distribuição de eventos por grupo;
- período coberto (`periods`, `dataset.period`).

**Pendente:** idade e cobertura das features (`feature_age`, `feature_coverage`).
A especificação é calcular, por contexto, o tempo desde o último evento usado
por feature e a fração de features não nulas; reportar média, mediana e pior
caso. Ainda não implementado.

---

## 6. Comparação com o modelo em produção

O candidato é comparado com:

1. baseline de popularidade;
2. baseline aleatório determinístico;
3. **modelo atualmente em produção**, avaliado nos mesmos contextos, com os
   mesmos candidatos e com as features disponíveis naquele instante.

$$
\Delta NDCG@K = NDCG_{\text{novo}} - NDCG_{\text{produção}}
$$

$$
\Delta MAP@K = MAP_{\text{novo}} - MAP_{\text{produção}}
$$

Política de promoção:

- rejeitar se a qualidade mínima falhar;
- exigir contextos de teste suficientes;
- exigir superar `max(melhor baseline, produção)` por margem mínima
  `MIN_PROMOTION_IMPROVEMENT = 0.01` em NDCG@K **ou** MAP@K;
- rejeitar se houver degradação acima de
  `MAX_PROMOTION_DEGRADATION = 0.01` na outra métrica;
- se o modelo em produção não puder ser avaliado, a decisão é
  `insufficient_evidence` (não promover).

**Seed nunca substitui produção.** Um treino `--source seed` pode gerar
candidato e relatório para inspeção, mas a decisão é `kept_previous` quando já
existe modelo em produção. A promoção exige `--source db`.

---

## 7. Avaliação temporal com múltiplas janelas (implementada)

O split principal continua sendo temporal único: treino → validação → teste.
Como a quantidade de contextos importa mais do que a quantidade de linhas
(570 linhas podem ser apenas 30 contextos e 4 usuários), a avaliação
walk-forward é opcional via `--rolling-window`.

Implementação:

1. ordenar contextos por `until`;
2. dividir os contextos em `windows + 1` blocos;
3. em cada fold, treinar nos contextos anteriores, validar no bloco
   imediatamente anterior ao teste e testar no bloco seguinte;
4. reportar métricas por janela, além de média, desvio, mínimo e máximo entre
   janelas;
5. reportar métricas preditivas por janela quando disponíveis;
6. não escolher hiperparâmetros na janela de teste;
7. registrar no relatório `folds`, `summary`, `windows` e o motivo quando a
   avaliação não é possível.

Requisitos: pelo menos 2 janelas e `(windows + 1) * 2` contextos. Caso
contrário, `available = false` com motivo explícito.

Critério de leitura: se o modelo só supera o baseline em uma janela, o resultado
é **instável** e não autoriza promoção. A decisão final deve considerar a média
e a pior janela, não apenas a melhor.

---

## 7.1 Política de vazamento temporal dos atributos do restaurante

O histórico do usuário é estritamente anterior a `until`, mas quatro atributos
do restaurante são lidos do estado atual da tabela:

- `restaurant_rating`;
- `restaurant_review_count`;
- `restaurant_delivery_fee`;
- `restaurant_delivery_time_avg`.

Se esses valores mudaram depois do contexto avaliado, o modelo pode ver
informação que não existia na época. O relatório expõe
`feature_temporal_policy` com o risco e a mitigação. O modo
`--strict-temporal` remove essas features do treino e da avaliação; o modo
padrão as mantém e registra a limitação em `quality.limitations`.

A solução definitiva é persistir snapshots históricos por versão/data do
restaurante. Enquanto eles não existirem, nenhuma conclusão deve tratar os
atributos atuais como se fossem históricos.

---

## 8. Critérios de validação

### 8.1 Ranking

- ranking perfeito → `P@K = 1`, `R@K = 1`, `NDCG@K = 1`, `MAP@K = 1`;
- contexto sem relevância → todas as métricas `0` e contado em
  `contexts_without_relevance`;
- contexto sem candidatos → excluído e contado em `contexts_without_candidates`;
- menos de K candidatos → denominador `min(K, n)`;
- empates → desempate determinístico por `restaurant_id`;
- ILD de itens com atributos disjuntos → `1.0`; idênticos → `0.0`;
- novidade com item mais popular → menor valor; item raro → maior valor;
- IC bootstrap reprodutível com a mesma semente.

### 8.2 Qualidade preditiva

- probabilidades perfeitas → Brier e Log Loss próximos de zero;
- uma única classe → ROC AUC e PR AUC `None`; Brier, Log Loss e calibração
  continuam disponíveis;
- menos de 20 amostras → ROC AUC `None` com motivo;
- PR AUC exige pelo menos um positivo e um negativo;
- calibração reporta ECE e erro máximo por bin.

### 8.3 A/B

- atribuição estável e sensível à versão;
- três grupos cobertos;
- `READY` não declara significância;
- `baseline_ready` exige impressões e usuários mínimos no baseline;
- `comparison_groups` lista apenas grupos comparáveis com impressões;
- sem baseline, a análise estatística fica indisponível com motivo explícito;
- Bonferroni usa o total de comparações planejadas;
- usuários contaminados excluídos da coorte válida;
- bootstrap por usuário usado quando há dados por usuário;
- p-valor vem de distribuição nula construída sob H0;
- evidência principal é o IC 95% da diferença; significância exige IC
  excluindo zero e p < alpha corrigido;
- fallback z por impressão só quando o bootstrap não é identificável;
- eventos demo nunca entram no denominador oficial;
- taxa de contaminação reportada.

### 8.4 Integração

- endpoint `/api/v1/experiment/ab-test` devolve `valid_groups`, `valid_cohort`,
  `contamination_rate`, `baseline_ready`, `comparison_groups`,
  `statistical_analysis` e `plan`;
- endpoint `/api/v1/ml/metrics` devolve `schema_version = 3`, alvo `purchased`,
  métricas preditivas, calibração, ILD/novidade, `ranking_sensitivity`,
  `temporal_mode`, `feature_temporal_policy`, `rolling_window`, `production` e
  comparação;
- frontend renderiza as duas visões sem quebrar quando campos novos estão
  ausentes.

---

## 9. Arquivos e testes

| Arquivo | Papel |
|---|---|
| `backend/app/ml/train.py` | alvo `purchased`, pesos de negativos, ranking, ILD, novidade, bootstrap, métricas preditivas, calibração, sensibilidade, política temporal, rolling-window, produção e promoção |
| `backend/app/ml/features.py` | features compartilhadas e política de atributos de estado atual do restaurante |
| `backend/app/ml/lora_evaluation.py` | adaptação ao alvo `purchased` e às features canônicas |
| `backend/app/services/experiment.py` | coorte válida, contaminação, exigência de baseline, bootstrap nulo, Bonferroni, plano de amostra |
| `backend/app/api/experiment.py` | endpoint A/B |
| `backend/tests/test_ranking_metrics.py` | fórmulas, casos extremos, empates e cobertura |
| `backend/tests/test_training.py` | pesos, métricas preditivas, calibração, sensibilidade, rolling-window, política temporal, bootstrap, ILD/novidade, produção e seed |
| `backend/tests/test_experiment.py` | fases, ICs, Bonferroni, coorte válida, exigência de baseline, bootstrap nulo e plano |
| `frontend/src/lib/api.ts` | contrato TypeScript v3 |
| `frontend/src/components/profile/ExperimentPanel.tsx` | painel A/B com coorte válida, baseline, IC como evidência principal e plano |
| `frontend/src/components/profile/TrainingMetricsPanel.tsx` | painel de treino com métricas preditivas, calibração, sensibilidade, política temporal e rolling-window |

Testes executados nesta versão:

- backend: `pytest` completo;
- frontend: `npm run test`, `npm run lint`, `npm run build`.

Os números reais de cada execução devem ser consultados no relatório
`backend/models/training_metrics.json` e no endpoint `/api/v1/ml/metrics`; eles
não são copiados para este documento para evitar resultados desatualizados.

---

## 10. Resultados atuais e limitações

### 10.1 Seed (não é evidência de produção)

A execução `--source seed` usa 4 usuários, 12 restaurantes e 30 contextos (360
amostras, 30 positivos). Ela serve para exercitar o pipeline, não para concluir
superioridade. No seed não há interações registradas, então todos os 330
negativos são “não observados” e recebem peso `0.1`.

Resultados da última execução de seed com `--strict-temporal --rolling-window`
(schema 3; 6 contextos de teste):

| Estratégia | P@5 | R@5 | NDCG@5 | MAP@5 | ILD@5 | Novidade@5 |
|---|---|---|---|---|---|---|
| LightGBM | 0,0333 | 0,1667 | 0,1667 | 0,1667 | 0,8667 | 3,6067 |
| Popularidade | 0,1000 | 0,5000 | 0,4051 | 0,3750 | 0,8667 | 3,0846 |
| Aleatório | 0,1333 | 0,6667 | 0,2798 | 0,1583 | 0,9500 | 3,5927 |
| Produção (modelo anterior) | 0,0667 | 0,3333 | 0,1478 | 0,0889 | 0,9833 | 3,5740 |

Métricas preditivas do LightGBM no teste de seed: ROC AUC `0,3636`, PR AUC
`0,1151`, Brier `0,2453`, Log Loss `0,6836`, ECE `0,4088` (erro máximo
`0,4088`). IC 95% bootstrap por usuário para NDCG@5: `[0,0000; 0,4286]` —
largura que mostra a instabilidade com 4 usuários.

A análise de sensibilidade só pôde avaliar o pool de negativos não observados
(não há negativos observados no seed); NDCG@5 nesse pool foi `0,1667`.

A avaliação walk-forward gerou 3 janelas. NDCG@5 do LightGBM entre janelas:
média `0,2410`, desvio `0,0930`, mínimo `0,1429`, máximo `0,3659`. A
popularidade teve média `0,2648` e o aleatório `0,2596`; a instabilidade e a
ausência de vantagem impedem qualquer conclusão de superioridade.

Decisão: `kept_previous`. O seed não substitui o modelo em produção.

### 10.2 Banco real (última execução disponível)

A última execução com `--source db` tinha 19 restaurantes, 4 usuários, 30
contextos, 570 amostras e 30 positivos. O LightGBM ficou abaixo da
popularidade:

| Estratégia | P@5 | R@5 | NDCG@5 | MAP@5 |
|---|---|---|---|---|
| LightGBM | 0,0667 | 0,3333 | 0,2311 | 0,2000 |
| Popularidade | 0,1000 | 0,5000 | 0,4051 | 0,3750 |
| Aleatório | 0,0667 | 0,3333 | 0,1769 | 0,1250 |

$$
\Delta NDCG@5 = 0,2311 - 0,4051 = -0,1740
\qquad (-42,95\%)
$$

Conclusão permitida: **naquele conjunto**, o LightGBM não demonstrou vantagem
sobre a popularidade. Não é correto afirmar que a popularidade é universalmente
superior.

### 10.3 A/B real

A última leitura oficial tinha 57 impressões, 1 usuário único e 1 usuário
contaminado. Não há base para declarar vencedor. A coorte válida exclui o
usuário contaminado; com isso, a inferência fica ainda mais limitada.

### 10.4 Limitações abertas

- poucos usuários e contextos;
- ausência de dados de exposição para separar negativo observado de não
  observado no seed;
- comparação com produção depende de features compatíveis;
- Street View depende de chave/quota externa;
- Overpass pública é intermitente;
- atributos do restaurante (rating, avaliações, frete, tempo de entrega) não têm
  snapshots históricos; `--strict-temporal` é mitigação, não solução;
- modelo de clique e modelo de conversão separados ainda não implementados;
- NDCG com ganho exponencial ainda não implementado (a versão atual usa ganho
  linear);
- `feature_age`/`feature_coverage` ainda não implementados;
- rolling-window usa apenas métricas agregadas por janela, sem IC bootstrap
  dentro de cada janela.

---

## 11. Pendências classificadas

### Implementado nesta versão

1. alvo renomeado para `purchased` com semântica documentada;
2. negativos observados × não observados com peso distinto;
3. coorte válida do A/B e taxa de contaminação;
4. inferência por usuário com bootstrap agrupado e fallback explícito;
5. dimensionamento de amostra com alpha corrigido;
6. comparação do candidato com o modelo em produção no mesmo teste;
7. ILD@K e Novelty@K;
8. PR AUC, Brier Score e Log Loss;
9. IC bootstrap por usuário nas métricas offline;
10. seed nunca substitui produção;
11. exigência explícita de baseline com volume para liberar inferência;
12. p-valor bootstrap por distribuição nula construída sob H0;
13. IC 95% da diferença como evidência principal;
14. análise de sensibilidade a negativos observados/não observados;
15. disponibilidade independente de ROC AUC, PR AUC, Brier, Log Loss e
    calibração;
16. curva de calibração com ECE e erro máximo;
17. avaliação rolling-window walk-forward;
18. política temporal explícita para atributos do restaurante e modo
    `--strict-temporal`.

### Pendente (próxima versão)

1. snapshots históricos dos atributos do restaurante;
2. NDCG com ganho exponencial/graduado;
3. modelo de interesse/clique separado do modelo de compra;
4. `feature_age` e `feature_coverage`;
5. IC bootstrap por usuário dentro de cada janela rolling-window;
6. teste de hipótese com erro-padrão robusto agrupado como alternativa ao
   bootstrap.

### Bloqueado por dados/infra

1. significância real do A/B (volume e janela limpa);
2. métricas de produção com dados suficientes;
3. Street View real (chave/quota);
4. Overpass estável;
5. banco PostgreSQL local disponível para reexecutar `--source db`.

---

## 12. Regra final

Nenhum número deste relatório autoriza afirmar que uma estratégia é melhor sem:

- coorte válida;
- tamanho de amostra compatível com o efeito que se quer detectar;
- intervalo de confiança;
- correção para múltiplas comparações;
- comparação com o modelo em produção;
- registro das limitações.

Quando esses critérios não forem atendidos, a resposta correta é
**“evidência insuficiente”**.
