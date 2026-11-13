# Simulação de usuários e cardápios sintéticos

Ferramentas para destravar o fluxo de pedido (cardápio) e gerar dados de teste
para o recomendador **sem APIs pagas**. Tudo é **sintético**.

> **Regra de ouro:** rode em um banco separado (`DATABASE_URL=.../foodflow_sim`).
> O treino (`python -m app.ml.train --source db`) lê *todas* as linhas do banco,
> então dados simulados contaminariam um treino com usuários reais.

## Segurança operacional

Os comandos que escrevem (`enrich_restaurants.py`,
`generate_synthetic_restaurants.py` e `simulate.py backfill|live|cleanup`)
seguem o mesmo contrato:

- exibem o banco de destino antes de qualquer operação;
- `--dry-run` mostra o que mudaria e **não grava** (não exige `--yes`);
- sem `--yes` o script aborta;
- bancos de produção (ambiente `production`/`prod` ou nome com `prod`) são
  bloqueados;
- hosts remotos exigem `--allow-remote-db` explícito.

O bloqueio é conservador de propósito: dados sintéticos nunca devem chegar a um
banco com usuários reais.

## Por que cardápio sintético

Nem o Street View nem o OSM trazem cardápio. Os itens criados aqui têm
`source='synthetic'` (exemplo plausível por tipo de cozinha, determinístico por
restaurante). Um cardápio real (cadastro pelo dono, parceria) deve usar outro
`source`. Raspar cardápios de apps de delivery viola os termos de uso: evite.

O frontend lê o cardápio por `GET /api/v1/restaurants/{id}/menu` e marca
visualmente itens sintéticos ("Exemplo") para não confundi-los com dados reais.

## Fluxo

```bash
cd backend
python scripts/init_db.py                          # aplica até a migração 0006

# 1. Restaurantes: reais (OSM) e/ou sintéticos como plano B
python scripts/ingest_osm.py --south -23.55 --west -46.82 --north -23.51 --east -46.77
python scripts/generate_synthetic_restaurants.py --count 150 --dry-run
python scripts/generate_synthetic_restaurants.py --count 150 --yes

# 2. Cardápio (e frete/prazo no lugar dos valores neutros do OSM)
python scripts/enrich_restaurants.py --fill-delivery --dry-run
python scripts/enrich_restaurants.py --fill-delivery --yes

# 3. Histórico retroativo (política de log: distância / popularidade / aleatória)
python scripts/simulate.py backfill --users 300 --days 21 --run-id exp1 --dry-run
python scripts/simulate.py backfill --users 300 --days 21 --run-id exp1 --yes

# 4. Treina o modelo com esse histórico
python -m app.ml.train --source db

# 5. Agentes usando a API de verdade (A/B baseline | personalized | distance)
uvicorn app.main:app &
python scripts/simulate.py live --run-id exp1 --rounds 5 --dry-run
python scripts/simulate.py live --run-id exp1 --rounds 5 --yes

# 6. Generalização: usuários inéditos (não vistos no treino)
python scripts/simulate.py live --run-id exp1-unseen --unseen-users --rounds 5 --yes

# 7. Relatório: ordenação, seleção e coortes
python scripts/simulate.py report --run-id exp1 --by-cohort --by-persona
python scripts/simulate.py report --run-id exp1-unseen --require-unseen

# 8. Limpeza auditável
python scripts/simulate.py cleanup --run-id exp1 --dry-run
python scripts/simulate.py cleanup --run-id exp1 --include-restaurants --yes
```

## Como os agentes decidem

Cada usuário tem uma persona (executivo de almoço, família de noite, fit,
noturno de lanche, exploradora, econômico) com variação individual. A
**utilidade latente** por restaurante soma afinidade por tipo de comida, bônus
de turno e qualidade, e subtrai preço, distância, frete e restrição alimentar
não atendida. Ela vira probabilidade de clique, favorito e compra. Só itens
*examinados* (viés de posição `1/(1+0.3·pos)`) podem ser clicados, e cada sessão
termina em no máximo um pedido. Avaliações refletem a qualidade latente do
restaurante, então `average_rating` vira um sinal real para o modelo.

Restrições alimentares são levadas a sério: se nenhum item do cardápio atende à
restrição do agente, a compra **não acontece** naquele restaurante. Não existe
fallback para o cardápio inteiro.

Calibração (compra por sessão, 600 usuários, 60 restaurantes): aleatória ≈ 20%,
distância ≈ 21%, ranking ideal ≈ 54%. Ajuste em `app/simulation/behavior.py`.

## Métricas: ordenação vs. seleção

`sim_runs/<run-id>/sessions.jsonl` (backfill) e `live_sessions.jsonl` (live)
guardam a verdade de cada sessão. O relatório traz duas perguntas diferentes:

- **`ordenacao servida` (NDCG@10)**: a API ordenou bem os restaurantes que
  mostrou? O ideal é calculado dentro da própria lista servida.
- **`recall do top-10 ideal`**: dos 10 melhores restaurantes do universo
  elegível, quantos entraram na lista servida?
- **`cobertura do oraculo`**: compras esperadas da lista servida ÷ compras
  esperadas do top-10 ideal, considerando **todos** os candidatos elegíveis
  (com viés de posição). `1.0` = seleção e ordenação perfeitas.

No modo `live`, o universo elegível (`nearby_candidates`, até 50 restaurantes
em 10 km) é calculado **antes** de chamar a API. Usar a própria resposta como
universo mediria apenas a ordenação e esconderia os bons restaurantes que
ficaram de fora da seleção.

ICs são calculados por bootstrap de **usuários**, não de sessões. O relatório
também aceita `--by-persona`, `--by-cohort` e `--by-period day|week|month`.

## Coortes: usuários conhecidos e inéditos

O backfill cria usuários com um `run_id`. O modo live, por padrão, reutiliza
esses usuários (coorte `known`), o que mede comportamento de retornantes.

Para generalização, use `--unseen-users`: o simulador cria uma coorte
`unseen` com IDs e personas diferentes (offset de índice e `user_seed`
separado), sem histórico no treino. O relatório `--require-unseen` falha se não
houver sessões dessa coorte, tornando a checagem obrigatória no fluxo oficial.

## Idempotência e rastreabilidade

- Restaurantes sintéticos recebem UUID determinístico por
  `(seed, centro, raio, índice)`: repetir a geração não duplica o catálogo.
- O backfill bloqueia a repetição de um `run_id` que já tenha eventos; use
  outro `run_id` ou limpe antes.
- Pedidos, avaliações e restaurantes sintéticos guardam `simulation_run_id`
  (e pedidos/avaliações também `simulation_mode`). Interações guardam
  `metadata.sim_run`/`metadata.sim_mode`.
- O `cleanup` grava um `cleanup-<timestamp>.json` em `sim_runs/<run-id>/` com
  banco, filtros, contagens e se foi `--dry-run`. `--include-restaurants`
  remove apenas restaurantes sintéticos do run que não tenham mais referências.

## O que estes números NÃO dizem

- Medem o recomendador contra **as regras deste simulador**, não contra pessoas
  reais. Um modelo que "vence" aqui aprendeu o simulador. Use para validar
  pipeline, A/B, métricas e regressões, e não cite como desempenho real.
- O histórico do backfill vem de políticas simples; o modelo é treinado nele.
  A coorte `known` mede retornantes; a coorte `unseen` é a que testa
  generalização.
- Em `live`, os timestamps das interações são reais; `--turno random` só muda
  o turno enviado ao `/recommendations`. Prefira `--turno auto`.
- Eventos de backfill são gravados com `experiment_mode='demo'` e ficam fora
  das métricas oficiais do A/B; os de `live` entram como experimento oficial.
- Atributos atuais do restaurante (nota, frete, tempo) ainda são usados como
  features. Isso é um risco de vazamento temporal; snapshots históricos são a
  solução definitiva.
