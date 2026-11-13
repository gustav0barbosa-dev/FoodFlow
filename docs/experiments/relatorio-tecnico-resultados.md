# Relatório técnico — Resultados dos experimentos do FoodFlow

**Projeto:** FoodFlow — sistema inteligente de recomendação de restaurantes  
**Data de elaboração:** 13/11/2026  
**Escopo:** pipeline de recomendação, treinamento do modelo LightGBM, simulações sintéticas (`exp1`, `exp1-unseen`) e avaliação de desempenho.  
**Status dos dados:** as métricas de simulação são calculadas sobre dados sintéticos e representam o comportamento do recomendador frente às regras do simulador, não o desempenho com usuários reais.

---

## 1. Introdução

O FoodFlow é um sistema de recomendação de restaurantes que combina catálogo geoespacial, histórico de pedidos e interações do usuário, Machine Learning (LightGBM) e estratégias de baseline (popularidade e distância). O objetivo da recomendação é ordenar restaurantes candidatos de forma a maximizar a probabilidade de compra observada em um contexto específico de usuário, data local e turno.

Os experimentos documentados neste relatório têm como objetivo:

- avaliar o treinamento supervisionado do modelo LightGBM com split temporal;
- comparar o modelo com baselines (popularidade e aleatório) e com o modelo em produção;
- avaliar três estratégias de recomendação em simulação (`baseline`, `distance`, `personalized`);
- analisar comportamento em usuários conhecidos e não vistos (cold start relativo);
- identificar limitações metodológicas e riscos de interpretação.

Este documento não afirma validação em produção. Os resultados de simulação são sintéticos e as conclusões de treinamento dependem do volume e da qualidade dos dados disponíveis.

---

## 2. Arquitetura e tecnologias

### 2.1 Arquitetura geral

- **Backend:** FastAPI (`backend/app/main.py`), com rotas modulares em `backend/app/api/`.
- **Banco de dados:** PostgreSQL com PostGIS (geoespacial), acessado via SQLAlchemy async.
- **Cache/métricas operacionais:** Redis (`backend/app/cache/redis_client.py`).
- **Frontend:** React/Vite (não detalhado neste relatório).
- **Machine Learning:** LightGBM (`backend/app/ml/train.py`, `backend/app/ml/recommender.py`).
- **Integrações externas:** OpenStreetMap/Overpass (`backend/app/integrations/overpass_client.py`), Street View (dependente de chave).

### 2.2 Componentes relevantes

| Componente | Arquivo principal |
|---|---|
| Treinamento e avaliação | `backend/app/ml/train.py` |
| Feature engineering | `backend/app/ml/features.py` |
| Serving do modelo | `backend/app/ml/recommender.py` |
| Experimento A/B | `backend/app/services/experiment.py` |
| Recomendações (API) | `backend/app/api/recommendations.py` |
| Ingestão OSM | `backend/app/services/osm_ingestion.py` |
| Simulação | `backend/scripts/simulate.py` |

---

## 3. Metodologia experimental

### 3.1 Origem dos dados

- **Treinamento:** dados do PostgreSQL (pedidos, usuários, restaurantes, interações), carregados por `load_training_data()` em `backend/app/ml/train.py`.
- **Simulação:** dados sintéticos gerados por `backend/scripts/simulate.py` (backfill/live), executados em banco separado.

### 3.2 Construção das amostras (treino)

- **Contexto** = `(usuário, data local, turno)` de uma ocasião de pedido.
- `until` = primeiro pedido da ocasião.
- Features usam apenas pedidos/interações com `created_at < until`.
- Candidatos = catálogo inteiro; ausência de pedido é negativo implícito.
- Alvo = `purchased` (compra observada), não clique.
- Negativos observados (peso 1.0) vs não observados (peso 0.1), apenas no treino.

### 3.3 Engenharia de atributos

- Features de usuário: histórico por turno, contagens de interações, afinidade por restaurante/categoria/cozinha, gasto.
- Features de restaurante: rating, contagem de avaliações, frete, tempo médio de entrega (estado atual — risco de vazamento temporal).
- One-hot do turno solicitado.

### 3.4 Divisão temporal

- Split por contexto: 60% treino, 20% validação, 20% teste, sem compartilhar contextos.
- Popularidade baseline incremental até `until`; aleatório determinístico por SHA-256.

### 3.5 Configuração dos experimentos

- Experimento A/B com três grupos: `baseline`, `personalized`, `distance`.
- Unidade experimental = usuário, atribuição persistente e versionada.
- Modo `demo` excluído das métricas oficiais.

---

## 4. Treinamento do modelo

### 4.1 Algoritmo

- **LightGBM** (`LGBMClassifier`), com parâmetros em `MODEL_PARAMS` (`backend/app/ml/train.py`).
- `is_unbalance=True`, `random_state=42`.

### 4.2 Processo

- Construção de contextos e frame de treino.
- Split temporal.
- Treino com early stopping na validação.
- Avaliação de ranking (Precision/Recall/NDCG/MAP@K) e métricas preditivas.
- Comparação com modelo em produção nos mesmos contextos.
- Decisão de promoção/rollback.

### 4.3 Dataset atual (fonte: `backend/models/training_metrics.json`)

| Item | Valor |
|---|---:|
| Amostras | 216.000 |
| Usuários | 271 |
| Contextos | 1.125 |
| Restaurantes | 192 |
| Positivos | 1.180 |
| Negativos | 214.820 |
| Negativos observados | 33.241 |
| Negativos não observados | 181.579 |
| Features | 53 |
| Período | 2026-10-14 a 2026-11-13 |

Split temporal:

| Conjunto | Amostras | Contextos | Usuários | Positivos |
|---|---:|---:|---:|---:|
| Treino | 129.600 | 675 | 225 | 709 |
| Validação | 43.200 | 225 | 156 | 237 |
| Teste | 43.200 | 225 | 157 | 234 |

---

## 5. Métricas de avaliação

### 5.1 Classificação/calibração

- **ROC-AUC**: capacidade de ordenação (requer duas classes).
- **PR-AUC**: área sob precisão-recall.
- **Brier Score**: erro quadrático médio das probabilidades.
- **Log Loss**: log-verossimilhança negativa.
- **ECE**: Expected Calibration Error (10 bins).

### 5.2 Ranking

- **Precision@K**, **Recall@K**, **NDCG@K**, **MAP@K** (macro-média por contexto).
- **ILD@K**: diversidade intra-lista (Jaccard).
- **Novelty@K**: novidade baseada em popularidade.
- **Catalog Coverage**: restaurantes distintos recomendados / catálogo.
- **User Coverage**: usuários com recomendação / total.

### 5.3 Simulação/comportamento

- **CTR**: cliques / impressões.
- **Compras por sessão**: compras / sessões (ou por impressão, conforme relatório).
- **Recall ideal**: hits no top-10 ideal.
- **Oracle Coverage**: compras esperadas da lista servida / top-10 ideal.

---

## 6. Resultados do treinamento

### 6.1 Métricas no conjunto de teste (fonte: `training_metrics.json`)

| Métrica | Valor |
|---|---:|
| ROC-AUC | 0,9520 |
| PR-AUC | 0,7778 |
| Brier Score | 0,0051 |
| Log Loss | 0,0416 |
| ECE | 0,0290 |
| Precision@5 | 0,1947 |
| Recall@5 | 0,9489 |
| NDCG@5 | 0,9178 |
| MAP@5 | 0,9024 |
| ILD@5 | 0,6032 |
| Novelty@5 | 7,6296 |
| Catalog Coverage | 0,7500 |

IC 95% bootstrap por usuário (NDCG@5): [0,8896; 0,9459].

### 6.2 Comparação com baselines e produção

| Estratégia | Precision@5 | Recall@5 | NDCG@5 | MAP@5 |
|---|---:|---:|---:|---:|
| LightGBM (candidato) | 0,1947 | 0,9489 | 0,9178 | 0,9024 |
| Popularidade | 0,0240 | 0,1178 | 0,0866 | 0,0756 |
| Aleatório | 0,0107 | 0,0533 | 0,0312 | 0,0240 |
| Produção (anterior) | 0,2018 | 0,9844 | 0,9380 | 0,9172 |

- Diferença vs produção: ΔNDCG = -0,0202; ΔMAP = -0,0148.
- Decisão de promoção: **`kept_previous`** (candidato não superou o modelo em produção com margem mínima).

### 6.3 Calibração

- Método selecionado: **isotonic**.
- Brier após calibração: 0,0016 (vs 0,0051 bruto).
- ECE após calibração: 0,0003.

### 6.4 Análise

Pontos positivos:
- Alta capacidade de ordenação (ROC-AUC 0,952; NDCG@5 0,918).
- Boa cobertura do catálogo (0,75).

Problemas:
- Calibração bruta inadequada em faixas intermediárias (0,1–0,2: previsto 0,1268 vs observado 0,1802).
- Candidato não superou produção; promoção bloqueada.
- Atributos de restaurante em estado atual (risco de vazamento temporal).

---

## 7. Resultados das simulações

### 7.1 Experimento `exp1-unseen` (fonte: `backend/sim_runs/exp1-unseen/report.md`)

| Estratégia | Usuários | Sessões | Impressões | Cliques | Compras | CTR | Compras/sessão | NDCG@10 | Recall ideal | Oracle coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 24 | 67 | 670 | 59 | 17 | 0,088 | 0,254 | 0,733 | 0,316 | 0,429 |
| Distance | 34 | 108 | 1080 | 131 | 37 | 0,121 | 0,343 | 0,693 | 0,319 | 0,381 |
| Personalized | 41 | 129 | 1290 | 150 | 56 | 0,116 | 0,434 | 0,786 | 0,403 | 0,533 |

IC 95% (compras/sessão): Baseline [0,151; 0,385], Distance [0,239; 0,457], Personalized [0,341; 0,535].

### 7.2 Comparação de estratégias

- **Personalized** apresentou melhor NDCG@10 (0,786), Recall ideal (0,403) e Oracle coverage (0,533), além de mais compras por sessão (0,434).
- **Distance** apresentou maior CTR (0,121) que Personalized (0,116).
- **Baseline** apresentou menor desempenho na maioria das métricas.

### 7.3 Análise

A personalização gera mais compras por sessão, mas não necessariamente mais cliques. Isso pode indicar que seleciona restaurantes com maior probabilidade de compra, ou diferenças na lógica do simulador. CTR e conversão não devem ser confundidos com qualidade de ranking.

---

## 8. Discussão dos resultados

- **Qual estratégia é melhor?** Depende da métrica. Personalized lidera em qualidade de ranking e compras; Distance lidera em CTR.
- **Consistência:** resultados coerentes entre métricas de ranking, mas CTR diverge.
- **Limitações:** dados sintéticos, volume pequeno de usuários/sessões, sem validação real.
- **Não há evidência suficiente** para declarar superioridade estatística.

---

## 9. Limitações e problemas identificados

### Confirmados

- Uso de dados sintéticos nas simulações.
- Possível vazamento temporal (atributos atuais do restaurante).
- Calibração bruta inadequada em faixas intermediárias.
- Candidato não superou produção.
- Volume insuficiente para significância estatística.

### Hipóteses a investigar

- Repetibilidade das simulações (seeds).
- Dependência excessiva de informações do perfil.
- Falta de snapshots históricos.
- Possível favorecimento artificial nas regras do simulador.

---

## 10. Trabalhos futuros

1. Validar treinamento com snapshots históricos.
2. Executar `--strict-temporal` e comparar métricas.
3. Repetir simulações com diferentes seeds.
4. Investigar calibração (Platt/Isotonic) — já implementada parcialmente.
5. Ampliar testes com usuários não vistos.
6. Validar com dados reais.
7. Melhorar cobertura do catálogo.
8. Avaliar desempenho em produção.

---

## 11. Conclusão

O FoodFlow possui pipeline funcional de treinamento, avaliação e simulação. Os resultados são promissores (personalização lidera em ranking/compras), mas não há evidência suficiente para validação em produção. As principais limitações são dados sintéticos, vazamento temporal potencial e volume insuficiente. Próximas etapas devem focar em auditoria do pipeline e validação real.

---

## 12. Reprodutibilidade

Comandos (fonte: scripts e `backend/README.md`):

```bash
# Treinamento
cd backend
python -m app.ml.train --source db
python -m app.ml.train --source db --strict-temporal
python -m app.ml.train --source seed --rolling-window

# Simulação
python scripts/simulate.py backfill --users 200 --days 21 --yes
python scripts/simulate.py live --run-id <id> --rounds 5 --yes
python scripts/simulate.py report --run-id <id>
python scripts/simulate.py cleanup --run-id <id> --yes

# Ingestão OSM
python scripts/ingest_osm.py --south -23.55 --west -46.82 --north -23.51 --east -46.77

# Testes
.venv\Scripts\python.exe -m pytest -q
```

---

## Fontes utilizadas

- `backend/models/training_metrics.json`
- `backend/sim_runs/exp1-unseen/report.md`
- `backend/sim_runs/exp1-unseen/report.csv`
- `docs/relatorio-final.md`
- `docs/arquitetura-tecnica.md`
- `backend/app/ml/train.py`
- `backend/scripts/simulate.py`

## Dados não encontrados / não confirmados

- Experimento `exp1` (conhecidos) completo não localizado em arquivos (apenas `exp1-unseen`).
- Resultados de calibração por persona detalhados não localizados.
- Dados de usuários reais não disponíveis.