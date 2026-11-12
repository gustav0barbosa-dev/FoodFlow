import { useEffect, useState } from 'react'
import { getTrainingMetrics, type ApiTrainingMetrics } from '@/lib/api'

function metric(value: number | null | undefined) {
  return value == null ? '—' : value.toFixed(4)
}

function ratio(value: number | null | undefined) {
  return value == null ? '—' : `${(value * 100).toFixed(1)}%`
}

function shortHash(value: string | undefined) {
  return value ? value.slice(0, 12) : '—'
}

function dateTime(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString('pt-BR') : '—'
}

const DECISION_LABELS: Record<string, string> = {
  bootstrap: 'Promovido (sem modelo anterior)',
  promoted: 'Promovido',
  kept_previous: 'Modelo anterior mantido',
  rejected_quality: 'Rejeitado por qualidade',
  insufficient_evidence: 'Evidência insuficiente',
}

export function TrainingMetricsPanel() {
  const [report, setReport] = useState<ApiTrainingMetrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    getTrainingMetrics()
      .then((data) => {
        if (active) setReport(data)
      })
      .catch(() => {
        if (active) setError('Não foi possível carregar as métricas de treino.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const ndcgInterval =
    report?.metrics?.ranking.confidence_intervals?.ndcg_at_k ?? null
  const mapInterval =
    report?.metrics?.ranking.confidence_intervals?.map_at_k ?? null

  return (
    <section className="bg-white rounded-2xl p-4 border border-gray-100">
      <h2 className="font-semibold text-ink mb-1">Qualidade do modelo</h2>
      <p className="text-xs text-ink-soft mb-3">
        Métricas do último treino offline do LightGBM: split temporal por
        contexto, baselines com os mesmos candidatos e decisão de
        promoção/rollback.
      </p>

      {loading && <p className="text-xs text-ink-soft">Carregando…</p>}
      {error && (
        <p className="text-xs text-amber-700" role="status">
          {error}
        </p>
      )}

      {report && !report.available && (
        <p className="text-xs text-ink-soft" role="status">
          {report.message ?? 'Nenhum relatório de treino disponível.'}
        </p>
      )}

      {report?.available && (
        <div className="space-y-3 text-xs">
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="bg-surface-muted rounded-xl p-3 border border-gray-100">
              <p className="text-[10px] text-ink-soft">Versão do modelo</p>
              <p className="text-ink font-medium break-all">
                {report.model_version ?? '—'}
              </p>
              <p className="mt-1 text-[10px] text-ink-soft">
                Treinado em {dateTime(report.trained_at)} · fonte:{' '}
                {report.source ?? '—'}
              </p>
            </div>
            <div className="bg-surface-muted rounded-xl p-3 border border-gray-100">
              <p className="text-[10px] text-ink-soft">Dataset</p>
              <p className="text-ink font-medium">
                hash {shortHash(report.dataset?.hash)}
              </p>
              <p className="mt-1 text-[10px] text-ink-soft">
                {report.dataset?.samples ?? 0} amostras ·{' '}
                {report.dataset?.contexts ?? 0} contextos ·{' '}
                {report.dataset?.users ?? 0} usuários ·{' '}
                {report.dataset?.restaurants ?? 0} restaurantes
              </p>
              <p className="mt-0.5 text-[10px] text-ink-soft">
                {report.dataset?.positives ?? 0} positivos ·{' '}
                {report.dataset?.negatives ?? 0} negativos
                {report.dataset?.unobserved_negatives != null && (
                  <>
                    {' '}
                    (não observados:{' '}
                    {report.dataset.unobserved_negatives}, peso reduzido)
                  </>
                )}
              </p>
              {report.label_semantics && (
                <p className="mt-0.5 text-[10px] text-ink-soft">
                  Alvo: {report.target ?? 'purchased'} —{' '}
                  {report.label_semantics}
                </p>
              )}
            </div>
          </div>

          <div className="grid gap-2 sm:grid-cols-2">
            <div className="bg-surface-muted rounded-xl p-3 border border-gray-100">
              <p className="text-[10px] text-ink-soft">Split</p>
              <p className="text-ink font-medium">
                {report.split?.strategy === 'temporal'
                  ? 'Temporal por contexto'
                  : 'Temporal insuficiente (não é evidência)'}
              </p>
              <p className="mt-1 text-[10px] text-ink-soft">
                treino {report.split?.contexts?.train ?? 0} · validação{' '}
                {report.split?.contexts?.validation ?? 0} · teste{' '}
                {report.split?.contexts?.test ?? 0} contextos
              </p>
              <p className="mt-0.5 text-[10px] text-ink-soft">
                Teste: {dateTime(report.split?.test?.period?.start)} –{' '}
                {dateTime(report.split?.test?.period?.end)}
              </p>
            </div>
            <div className="bg-surface-muted rounded-xl p-3 border border-gray-100">
              <p className="text-[10px] text-ink-soft">Decisão de promoção</p>
              <p className="text-ink font-medium">
                {report.promotion
                  ? DECISION_LABELS[report.promotion.decision] ??
                    report.promotion.decision
                  : '—'}
              </p>
              <p className="mt-1 text-[10px] text-ink-soft">
                {report.promotion?.reason ?? '—'}
              </p>
              {report.promotion?.previous_model_version && (
                <p className="mt-0.5 text-[10px] text-ink-soft">
                  Versão anterior preservada:{' '}
                  {report.promotion.previous_model_version}
                </p>
              )}
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-[11px]">
              <thead>
                <tr className="text-ink-soft">
                  <th className="py-1 pr-2 font-medium">Estratégia</th>
                  <th className="py-1 pr-2 font-medium">P@K</th>
                  <th className="py-1 pr-2 font-medium">R@K</th>
                  <th className="py-1 pr-2 font-medium">NDCG@K</th>
                  <th className="py-1 pr-2 font-medium">MAP@K</th>
                  <th className="py-1 pr-2 font-medium">ILD@K</th>
                  <th className="py-1 pr-2 font-medium">Novidade@K</th>
                  <th className="py-1 pr-2 font-medium">Cob. catálogo</th>
                  <th className="py-1 font-medium">Cob. usuários</th>
                </tr>
              </thead>
              <tbody className="text-ink">
                <tr>
                  <td className="py-1 pr-2 font-medium">LightGBM</td>
                  <td className="py-1 pr-2">
                    {metric(report.metrics?.ranking.precision_at_k)}
                  </td>
                  <td className="py-1 pr-2">
                    {metric(report.metrics?.ranking.recall_at_k)}
                  </td>
                  <td className="py-1 pr-2">
                    {metric(report.metrics?.ranking.ndcg_at_k)}
                  </td>
                  <td className="py-1 pr-2">
                    {metric(report.metrics?.ranking.map_at_k)}
                  </td>
                  <td className="py-1 pr-2">
                    {metric(report.metrics?.ranking.ild_at_k)}
                  </td>
                  <td className="py-1 pr-2">
                    {metric(report.metrics?.ranking.novelty_at_k)}
                  </td>
                  <td className="py-1 pr-2">
                    {ratio(report.metrics?.ranking.catalog_coverage)}
                  </td>
                  <td className="py-1">
                    {ratio(report.metrics?.ranking.user_coverage)}
                  </td>
                </tr>
                {report.production?.available &&
                  report.production.ranking && (
                    <tr className="text-ink">
                      <td className="py-1 pr-2 font-medium">
                        Produção
                        {report.production.model_version
                          ? ` (${report.production.model_version})`
                          : ''}
                      </td>
                      <td className="py-1 pr-2">
                        {metric(report.production.ranking.precision_at_k)}
                      </td>
                      <td className="py-1 pr-2">
                        {metric(report.production.ranking.recall_at_k)}
                      </td>
                      <td className="py-1 pr-2">
                        {metric(report.production.ranking.ndcg_at_k)}
                      </td>
                      <td className="py-1 pr-2">
                        {metric(report.production.ranking.map_at_k)}
                      </td>
                      <td className="py-1 pr-2">
                        {metric(report.production.ranking.ild_at_k)}
                      </td>
                      <td className="py-1 pr-2">
                        {metric(report.production.ranking.novelty_at_k)}
                      </td>
                      <td className="py-1 pr-2">
                        {ratio(report.production.ranking.catalog_coverage)}
                      </td>
                      <td className="py-1">
                        {ratio(report.production.ranking.user_coverage)}
                      </td>
                    </tr>
                  )}
                {Object.entries(report.baselines ?? {}).map(([name, values]) => (
                  <tr key={name} className="text-ink-soft">
                    <td className="py-1 pr-2 capitalize">{name}</td>
                    <td className="py-1 pr-2">{metric(values.precision_at_k)}</td>
                    <td className="py-1 pr-2">{metric(values.recall_at_k)}</td>
                    <td className="py-1 pr-2">{metric(values.ndcg_at_k)}</td>
                    <td className="py-1 pr-2">{metric(values.map_at_k)}</td>
                    <td className="py-1 pr-2">{metric(values.ild_at_k)}</td>
                    <td className="py-1 pr-2">{metric(values.novelty_at_k)}</td>
                    <td className="py-1 pr-2">
                      {ratio(values.catalog_coverage)}
                    </td>
                    <td className="py-1">{ratio(values.user_coverage)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="text-[10px] text-ink-soft">
            ROC AUC ({report.metrics?.evaluation_split ?? 'teste'}):{' '}
            {metric(report.metrics?.roc_auc)} · PR AUC:{' '}
            {metric(report.metrics?.pr_auc)} · Brier:{' '}
            {metric(report.metrics?.brier_score)} · Log Loss:{' '}
            {metric(report.metrics?.log_loss)}
            {report.metrics?.roc_auc_note
              ? ` — ${report.metrics.roc_auc_note}`
              : ''}{' '}
            · K = {report.metrics?.ranking.k ?? '—'} · fase:{' '}
            {report.phase ?? '—'}
          </p>

          {ndcgInterval && (
            <p className="text-[10px] text-ink-soft">
              IC 95% bootstrap por usuário — NDCG@K: {metric(ndcgInterval.low)} –{' '}
              {metric(ndcgInterval.high)} · MAP@K:{' '}
              {mapInterval
                ? `${metric(mapInterval.low)} – ${metric(mapInterval.high)}`
                : '—'}
            </p>
          )}

          {report.metrics?.calibration && (
            <p className="text-[10px] text-ink-soft">
              Calibração (
              {report.metrics.calibration.bins.length} bins ·{' '}
              {report.metrics.calibration.samples} amostras): ECE{' '}
              {metric(report.metrics.calibration.expected_calibration_error)} ·
              erro máximo{' '}
              {metric(report.metrics.calibration.max_calibration_error)}
              {report.metrics.pr_auc_note
                ? ` · ${report.metrics.pr_auc_note}`
                : ''}
            </p>
          )}

          <div className="rounded-xl border border-gray-100 p-3">
            <h3 className="text-xs font-semibold text-ink mb-1">
              Validação temporal
            </h3>
            <p className="text-[11px] text-ink-soft">
              Modo:{' '}
              {report.temporal_mode === 'strict'
                ? 'estrito — atributos atuais do restaurante excluídos'
                : 'atributos atuais do restaurante incluídos'}
              .
            </p>
            {report.feature_temporal_policy && (
              <>
                <p className="mt-1 text-[10px] text-amber-700">
                  {report.feature_temporal_policy.risk}
                </p>
                <p className="mt-0.5 text-[10px] text-ink-soft">
                  Mitigação: {report.feature_temporal_policy.mitigation}
                </p>
                {report.feature_temporal_policy
                  .current_state_restaurant_features.length > 0 && (
                  <p className="mt-0.5 text-[10px] text-ink-soft">
                    Features de estado atual:{' '}
                    {report.feature_temporal_policy.current_state_restaurant_features.join(
                      ', '
                    )}
                  </p>
                )}
              </>
            )}
          </div>

          {report.metrics?.ranking_sensitivity && (
            <div className="rounded-xl border border-gray-100 p-3">
              <h3 className="text-xs font-semibold text-ink mb-1">
                Sensibilidade a negativos observados/não observados
              </h3>
              <p className="text-[10px] text-ink-soft mb-2">
                {report.metrics.ranking_sensitivity.note}
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                {Object.entries(report.metrics.ranking_sensitivity.pools).map(
                  ([pool, values]) => (
                    <div
                      key={pool}
                      className="bg-surface-muted rounded-xl p-2 border border-gray-100"
                    >
                      <p className="text-[11px] font-medium text-ink capitalize">
                        {pool.replace(/_/g, ' ')}
                      </p>
                      {values.available && values.metrics.model ? (
                        <>
                          <p className="mt-1 text-[10px] text-ink-soft">
                            P@K {metric(values.metrics.model.precision_at_k)} ·
                            NDCG@K {metric(values.metrics.model.ndcg_at_k)} ·
                            MAP@K {metric(values.metrics.model.map_at_k)}
                          </p>
                          <p className="text-[10px] text-ink-soft">
                            {values.positives} positivos · {values.negatives}{' '}
                            negativos
                          </p>
                        </>
                      ) : (
                        <p className="mt-1 text-[10px] text-amber-700">
                          {values.reason ?? 'Indisponível.'}
                        </p>
                      )}
                    </div>
                  )
                )}
              </div>
            </div>
          )}

          {report.rolling_window && (
            <div className="rounded-xl border border-gray-100 p-3">
              <h3 className="text-xs font-semibold text-ink mb-1">
                Janelas temporais (walk-forward)
              </h3>
              {report.rolling_window.available ? (
                <>
                  <p className="text-[10px] text-ink-soft mb-2">
                    {report.rolling_window.windows ?? 0} janelas expansíveis.
                    A média entre janelas não substitui a pior janela; janelas
                    instáveis bloqueiam promoção.
                  </p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-[11px]">
                      <thead>
                        <tr className="text-ink-soft">
                          <th className="py-1 pr-2 font-medium">Janela</th>
                          <th className="py-1 pr-2 font-medium">Treino</th>
                          <th className="py-1 pr-2 font-medium">Teste</th>
                          <th className="py-1 pr-2 font-medium">NDCG@K</th>
                          <th className="py-1 pr-2 font-medium">MAP@K</th>
                          <th className="py-1 font-medium">ROC AUC</th>
                        </tr>
                      </thead>
                      <tbody className="text-ink">
                        {(report.rolling_window.folds ?? []).map((fold) => (
                          <tr
                            key={fold.fold}
                            className="border-t border-gray-100"
                          >
                            <td className="py-1 pr-2">{fold.fold}</td>
                            <td className="py-1 pr-2">
                              {fold.train_contexts}
                            </td>
                            <td className="py-1 pr-2">{fold.test_contexts}</td>
                            <td className="py-1 pr-2">
                              {fold.available
                                ? metric(fold.ranking?.ndcg_at_k)
                                : '—'}
                            </td>
                            <td className="py-1 pr-2">
                              {fold.available
                                ? metric(fold.ranking?.map_at_k)
                                : '—'}
                            </td>
                            <td className="py-1">
                              {fold.available
                                ? metric(fold.predictive?.roc_auc)
                                : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {report.rolling_window.summary?.lightgbm && (
                    <p className="mt-1 text-[10px] text-ink-soft">
                      NDCG@K entre janelas:{' '}
                      {metric(
                        report.rolling_window.summary.lightgbm.ndcg_at_k?.mean
                      )}{' '}
                      ±{' '}
                      {metric(
                        report.rolling_window.summary.lightgbm.ndcg_at_k?.std
                      )}{' '}
                      (min{' '}
                      {metric(
                        report.rolling_window.summary.lightgbm.ndcg_at_k?.min
                      )}
                      , max{' '}
                      {metric(
                        report.rolling_window.summary.lightgbm.ndcg_at_k?.max
                      )}
                      )
                    </p>
                  )}
                </>
              ) : (
                <p className="text-[10px] text-amber-700">
                  {report.rolling_window.reason ??
                    'Avaliação por janelas indisponível.'}
                </p>
              )}
            </div>
          )}

          {report.production && !report.production.available && (
            <p className="rounded-xl bg-amber-50 px-3 py-2 text-[11px] text-amber-800">
              Modelo em produção não comparável no mesmo teste:{' '}
              {report.production.reason ?? 'motivo não informado'}. A promoção
              fica bloqueada sem essa comparação.
            </p>
          )}

          <div className="grid grid-cols-2 gap-2 text-[10px] sm:grid-cols-4">
            <div className="bg-surface-muted rounded-xl p-2 border border-gray-100">
              <p className="text-ink-soft">Contextos avaliados</p>
              <p className="text-ink font-semibold">
                {report.metrics?.ranking.contexts ?? 0}/
                {report.metrics?.ranking.contexts_total ?? 0}
              </p>
            </div>
            <div className="bg-surface-muted rounded-xl p-2 border border-gray-100">
              <p className="text-ink-soft">Sem relevância</p>
              <p className="text-ink font-semibold">
                {report.metrics?.ranking.contexts_without_relevance ?? 0}
              </p>
            </div>
            <div className="bg-surface-muted rounded-xl p-2 border border-gray-100">
              <p className="text-ink-soft">Qualidade</p>
              <p className="text-ink font-semibold">
                {report.quality?.ok ? 'Aprovada' : 'Reprovada'}
              </p>
            </div>
            <div className="bg-surface-muted rounded-xl p-2 border border-gray-100">
              <p className="text-ink-soft">Pronto p/ promoção</p>
              <p className="text-ink font-semibold">
                {report.quality?.promotion_ready ? 'Sim' : 'Não'}
              </p>
            </div>
          </div>

          {report.quality?.limitations && report.quality.limitations.length > 0 && (
            <div className="rounded-xl bg-amber-50 px-3 py-2 text-[11px] text-amber-800">
              <p className="font-semibold mb-1">Limitações</p>
              <ul className="list-disc pl-4 space-y-0.5">
                {report.quality.limitations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
