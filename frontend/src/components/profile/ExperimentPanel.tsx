import { useEffect, useState } from 'react'
import { getABTestResults, type ApiExperimentResults } from '@/lib/api'
import { type ABGroup, type ExperimentMode } from '@/lib/config'

const GROUP_ORDER = ['baseline', 'personalized', 'distance'] as const

const GROUP_LABELS: Record<string, string> = {
  baseline: 'Baseline (popularidade)',
  personalized: 'Personalizado (ML)',
  distance: 'Por distância',
}

const GROUP_OPTIONS: Array<{ value: ABGroup; label: string }> = [
  { value: '', label: 'Padrão (backend)' },
  { value: 'baseline', label: 'Baseline' },
  { value: 'personalized', label: 'Personalizado' },
  { value: 'distance', label: 'Por distância' },
]

const PHASE_STYLES: Record<
  string,
  { label: string; className: string }
> = {
  collecting: {
    label: 'Coletando',
    className: 'bg-amber-50 text-amber-800',
  },
  insufficient_data: {
    label: 'Dados insuficientes',
    className: 'bg-amber-50 text-amber-800',
  },
  ready: {
    label: 'Pronto para leitura descritiva (sem significância)',
    className: 'bg-blue-50 text-blue-800',
  },
  statistical_analysis: {
    label: 'Análise estatística disponível',
    className: 'bg-green-50 text-green-800',
  },
}

function percent(value: number | null | undefined) {
  return value == null ? '—' : `${(value * 100).toFixed(1)}%`
}

function interval(
  value: { low: number; high: number } | null | undefined
) {
  return value ? `${percent(value.low)}–${percent(value.high)}` : '—'
}

function pValue(value: number | null | undefined) {
  if (value == null) return '—'
  return value < 0.0001 ? '< 0,0001' : value.toFixed(4)
}

export function ExperimentPanel({
  group,
  mode,
  onGroupChange,
  onModeChange,
}: {
  group: ABGroup
  mode: ExperimentMode
  onGroupChange: (group: ABGroup) => void
  onModeChange: (mode: ExperimentMode) => void
}) {
  const [results, setResults] = useState<ApiExperimentResults | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      setResults(await getABTestResults())
    } catch {
      setError('Não foi possível carregar as métricas do experimento.')
      setResults(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const phase = results ? PHASE_STYLES[results.phase] : undefined

  return (
    <section className="bg-white rounded-2xl p-4 border border-gray-100">
      <h2 className="font-semibold text-ink mb-1">
        Experimento A/B de recomendações
      </h2>
      <p className="text-xs text-ink-soft mb-3">
        Três estratégias estáveis: baseline (popularidade), personalizado
        (LightGBM + afinidade) e por distância. As taxas usam impressões
        oficiais no denominador e ignoram eventos de demonstração.
      </p>

      <div className="mb-3">
        <p className="text-[10px] uppercase tracking-wide text-ink-soft mb-1">
          Modo de uso
        </p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => onModeChange('experiment')}
            aria-pressed={mode === 'experiment'}
            className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
              mode === 'experiment'
                ? 'bg-primary border-primary text-white'
                : 'bg-white border-gray-200 text-ink-soft hover:bg-surface-muted'
            }`}
          >
            Experimento oficial
          </button>
          <button
            type="button"
            onClick={() => onModeChange('demo')}
            aria-pressed={mode === 'demo'}
            className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
              mode === 'demo'
                ? 'bg-amber-500 border-amber-500 text-white'
                : 'bg-white border-gray-200 text-ink-soft hover:bg-surface-muted'
            }`}
          >
            Demonstração
          </button>
        </div>
      </div>

      {mode === 'demo' ? (
        <div className="mb-3 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-800">
          No modo de demonstração você escolhe a estratégia manualmente. Os
          eventos são gravados como <code>demo</code> e excluídos das métricas
          oficiais do experimento.
          <div className="flex flex-wrap gap-2 mt-2">
            {GROUP_OPTIONS.map((option) => (
              <button
                key={option.value || 'default'}
                type="button"
                onClick={() => onGroupChange(option.value)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                  group === option.value
                    ? 'bg-amber-600 border-amber-600 text-white'
                    : 'bg-white border-amber-200 text-amber-800 hover:bg-amber-100'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <p className="mb-3 text-[11px] text-ink-soft">
          A estratégia é atribuída pelo backend por hash do usuário e persistida
          em <code>experiment_assignments</code>. A seleção manual fica
          desabilitada para não contaminar o experimento.
        </p>
      )}

      {loading && <p className="text-xs text-ink-soft">Carregando…</p>}
      {error && (
        <p className="text-xs text-amber-700" role="status">
          {error}
        </p>
      )}

      {results && (
        <div className="space-y-3">
          <div
            className={`rounded-xl px-3 py-2 text-xs ${
              phase?.className ?? 'bg-amber-50 text-amber-800'
            }`}
            role="status"
          >
            <p className="font-semibold">{phase?.label ?? results.phase}</p>
            <p className="mt-0.5">{results.message}</p>
          </div>

          {results.contamination_detected && (
            <p className="rounded-xl bg-red-50 px-3 py-2 text-xs text-red-800">
              Contaminação detectada em {results.contaminated_users} usuário(s)
              {results.contamination_rate != null
                ? ` (${percent(results.contamination_rate)} dos usuários)`
                : ''}
              . Eles foram <strong>excluídos da coorte válida</strong> usada na
              leitura e na inferência; as métricas brutas continuam abaixo
              apenas para auditoria.
            </p>
          )}

          <div className="grid grid-cols-2 gap-2 text-[11px] sm:grid-cols-4">
            <div className="bg-surface-muted rounded-xl p-2 border border-gray-100">
              <p className="text-ink-soft">Impressões brutas</p>
              <p className="text-ink font-semibold">
                {results.total_impressions}
              </p>
            </div>
            <div className="bg-surface-muted rounded-xl p-2 border border-gray-100">
              <p className="text-ink-soft">Impressões válidas</p>
              <p className="text-ink font-semibold">
                {results.valid_total_impressions ?? results.total_impressions}
              </p>
            </div>
            <div className="bg-surface-muted rounded-xl p-2 border border-gray-100">
              <p className="text-ink-soft">Usuários válidos</p>
              <p className="text-ink font-semibold">
                {results.valid_exposed_users ?? results.exposed_users}
              </p>
            </div>
            <div className="bg-surface-muted rounded-xl p-2 border border-gray-100">
              <p className="text-ink-soft">Eventos demo (excluídos)</p>
              <p className="text-ink font-semibold">{results.demo_events}</p>
            </div>
          </div>

          <p className="text-[10px] text-ink-soft">
            Versão do experimento: {results.experiment_version} · unidade
            experimental: {results.unit}
          </p>

          <div className="grid gap-2 sm:grid-cols-3">
            {GROUP_ORDER.map((key) => {
              const metrics =
                (results.valid_groups ?? results.groups)[key] ??
                results.groups[key]
              if (!metrics) return null
              const userCtr = metrics.user_confidence_intervals?.ctr
              const userConversion =
                metrics.user_confidence_intervals?.conversion_rate
              return (
                <div
                  key={key}
                  className="bg-surface-muted rounded-xl p-3 border border-gray-100"
                >
                  <p className="text-xs font-semibold text-ink">
                    {metrics.label || GROUP_LABELS[key]}
                  </p>
                  <dl className="mt-2 space-y-1 text-[11px] text-ink-soft">
                    <div className="flex justify-between gap-2">
                      <dt>Impressões</dt>
                      <dd className="text-ink font-medium">
                        {metrics.impressions}
                      </dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt>Usuários</dt>
                      <dd className="text-ink font-medium">{metrics.users}</dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt>CTR por impressão</dt>
                      <dd className="text-ink font-medium">
                        {percent(metrics.ctr)}
                      </dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt>CTR médio por usuário</dt>
                      <dd className="text-ink font-medium">
                        {percent(metrics.user_ctr)}
                      </dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt>IC bootstrap CTR</dt>
                      <dd className="text-ink font-medium">
                        {interval(userCtr)}
                      </dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt>Detalhes</dt>
                      <dd className="text-ink font-medium">
                        {percent(metrics.detail_rate)}
                      </dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt>Conversão por impressão</dt>
                      <dd className="text-ink font-medium">
                        {percent(metrics.conversion_rate)}
                      </dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt>Conversão por usuário</dt>
                      <dd className="text-ink font-medium">
                        {percent(metrics.conversion_per_user)}
                      </dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt>IC bootstrap conversão</dt>
                      <dd className="text-ink font-medium">
                        {interval(userConversion)}
                      </dd>
                    </div>
                    <div className="flex justify-between gap-2">
                      <dt>Favoritos</dt>
                      <dd className="text-ink font-medium">
                        {percent(metrics.favorite_rate)}
                      </dd>
                    </div>
                  </dl>
                  {!metrics.readable && (
                    <p className="mt-2 text-[10px] text-amber-700">
                      Amostra insuficiente para leitura descritiva.
                    </p>
                  )}
                </div>
              )
            })}
          </div>

          <p className="text-[10px] text-ink-soft">
            Os cartões usam a coorte válida. CTR e conversão por impressão são
            descritivos; a inferência usa a média por usuário e o bootstrap
            agrupado.
          </p>

          <div className="rounded-xl border border-gray-100 p-3">
            <h3 className="text-xs font-semibold text-ink mb-1">
              Comparação estatística
            </h3>
            {!results.statistical_analysis.available ? (
              <p className="text-[11px] text-ink-soft">
                {results.statistical_analysis.reason ??
                  'Análise estatística indisponível.'}
              </p>
            ) : (
              <>
                <p className="text-[11px] text-ink-soft mb-2">
                  {results.statistical_analysis.method}
                  {results.statistical_analysis.corrected_alpha != null && (
                    <>
                      {' '}
                      α corrigido:{' '}
                      {results.statistical_analysis.corrected_alpha.toFixed(4)}{' '}
                      ({results.statistical_analysis.planned_comparisons ?? 0}{' '}
                      comparações planejadas).
                    </>
                  )}
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-[11px]">
                    <thead>
                      <tr className="text-ink-soft">
                        <th className="py-1 pr-2 font-medium">Métrica</th>
                        <th className="py-1 pr-2 font-medium">Grupo</th>
                        <th className="py-1 pr-2 font-medium">Diferença</th>
                        <th className="py-1 pr-2 font-medium">Lift</th>
                        <th className="py-1 pr-2 font-medium">IC 95% diferença</th>
                        <th className="py-1 pr-2 font-medium">p-valor</th>
                        <th className="py-1 pr-2 font-medium">Método</th>
                        <th className="py-1 font-medium">Significante</th>
                      </tr>
                    </thead>
                    <tbody className="text-ink">
                      {(results.statistical_analysis.comparisons ?? []).map(
                        (item) => (
                          <tr
                            key={`${item.metric}-${item.group}`}
                            className="border-t border-gray-100"
                          >
                            <td className="py-1 pr-2">{item.metric}</td>
                            <td className="py-1 pr-2">{item.group}</td>
                            <td className="py-1 pr-2">
                              {percent(item.absolute_difference)}
                            </td>
                            <td className="py-1 pr-2">
                              {item.relative_lift == null
                                ? '—'
                                : percent(item.relative_lift)}
                            </td>
                            <td className="py-1 pr-2">
                              {interval(item.confidence_interval)}
                            </td>
                            <td className="py-1 pr-2">
                              {pValue(item.p_value)}
                            </td>
                            <td className="py-1 pr-2">
                              {item.method === 'bootstrap_by_user'
                                ? 'bootstrap/usuário'
                                : item.method ===
                                    'z_test_by_impression_fallback'
                                  ? 'z/impressão (fallback)'
                                  : (item.method ?? '—')}
                            </td>
                            <td className="py-1">
                              {item.significant ? 'Sim' : 'Não'}
                            </td>
                          </tr>
                        )
                      )}
                    </tbody>
                  </table>
                </div>
              </>
            )}
            <p className="mt-2 text-[11px] text-ink-soft">
              {results.comparison.winner_declared
                ? 'Há diferença estatisticamente significante após correção para múltiplas comparações.'
                : results.comparison.note}
            </p>
          </div>

          {results.plan && (
            <div className="rounded-xl border border-gray-100 p-3">
              <h3 className="text-xs font-semibold text-ink mb-1">
                Dimensionamento da amostra
              </h3>
              <p className="text-[11px] text-ink-soft mb-2">
                {results.plan.note} Poder desejado:{' '}
                {percent(results.plan.power)} · efeito mínimo:{' '}
                {percent(results.plan.minimum_detectable_effect_relative)} ·{' '}
                {results.plan.planned_comparisons} comparações planejadas.
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-[11px]">
                  <thead>
                    <tr className="text-ink-soft">
                      <th className="py-1 pr-2 font-medium">Métrica</th>
                      <th className="py-1 pr-2 font-medium">Baseline</th>
                      <th className="py-1 pr-2 font-medium">Esperado</th>
                      <th className="py-1 pr-2 font-medium">Usuários/grupo</th>
                      <th className="py-1 font-medium">Impressões/grupo</th>
                    </tr>
                  </thead>
                  <tbody className="text-ink">
                    {results.plan.plans.map((entry) => (
                      <tr
                        key={entry.metric}
                        className="border-t border-gray-100"
                      >
                        <td className="py-1 pr-2">{entry.metric}</td>
                        <td className="py-1 pr-2">
                          {percent(entry.baseline_rate)}
                        </td>
                        <td className="py-1 pr-2">
                          {percent(entry.expected_rate)}
                        </td>
                        <td className="py-1 pr-2">
                          {entry.required_users_per_group ?? '—'}
                        </td>
                        <td className="py-1">
                          {entry.required_impressions_per_group ?? '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {results.plan.plans.some((entry) => entry.reason) && (
                <p className="mt-2 text-[10px] text-amber-700">
                  {results.plan.plans
                    .filter((entry) => entry.reason)
                    .map((entry) => `${entry.metric}: ${entry.reason}`)
                    .join(' ')}
                </p>
              )}
            </div>
          )}

          {results.timeline.length > 0 && (
            <div className="rounded-xl border border-gray-100 p-3">
              <h3 className="text-xs font-semibold text-ink mb-1">
                Série diária (últimos dias)
              </h3>
              <ul className="space-y-1 text-[11px] text-ink-soft">
                {results.timeline.slice(-7).map((point) => (
                  <li key={point.date} className="flex justify-between gap-2">
                    <span>{point.date}</span>
                    <span>
                      {Object.entries(point.groups)
                        .map(
                          ([key, value]) =>
                            `${key}: ${value.impressions} imp / ${percent(
                              value.ctr
                            )} CTR`
                        )
                        .join(' · ')}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-ink-soft">
            <span>
              Fonte: {results.source} · unidade: {results.unit} · mínimo
              descritivo: {results.minimum_impressions_for_reading} impressões
            </span>
            <button
              type="button"
              onClick={() => void load()}
              className="text-primary underline hover:text-primary-dark"
            >
              Atualizar
            </button>
          </div>
          {results.request_counters && (
            <p className="text-[10px] text-ink-soft">
              Requisições (Redis, apenas diagnóstico; não são métricas
              oficiais): baseline {results.request_counters.baseline_requests},
              personalizado {results.request_counters.personalized_requests},
              distância {results.request_counters.distance_requests}
            </p>
          )}
        </div>
      )}
    </section>
  )
}
