import { useState } from 'react'
import { Trash2 } from 'lucide-react'
import { useEventsStore } from '@/store/eventsStore'
import type { EventPayload, EventType } from '@/store/eventsStore'
import {
  EVENT_LABELS,
  EVENT_PERIODS,
  EVENT_TYPES,
  countEventsByType,
  filterEvents,
  type EventPeriod,
} from '@/lib/events'
import { cn } from '@/lib/utils'

const timeFormatter = new Intl.DateTimeFormat('pt-BR', {
  day: '2-digit',
  month: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
})

function formatPayload(payload: EventPayload) {
  return Object.entries(payload)
    .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : value}`)
    .join(' · ')
}

export function EventsPanel() {
  const events = useEventsStore((s) => s.events)
  const clearEvents = useEventsStore((s) => s.clearEvents)
  const [type, setType] = useState<EventType | 'all'>('all')
  const [period, setPeriod] = useState<EventPeriod>('all')

  const filtered = filterEvents(events, { type, period })
  const summary = countEventsByType(filterEvents(events, { type: 'all', period }))
  const hasFilters = type !== 'all' || period !== 'all'

  return (
    <section className="bg-white rounded-2xl p-4 border border-gray-100">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="font-semibold text-ink">Eventos do recomendador</h2>
          <p className="text-xs text-ink-soft mt-0.5">
            Mock local de POST /events ·{' '}
            {filtered.length === events.length
              ? `${events.length} ${events.length === 1 ? 'evento' : 'eventos'}`
              : `${filtered.length} de ${events.length} eventos`}
          </p>
        </div>
        {events.length > 0 && (
          <button
            type="button"
            onClick={clearEvents}
            className="p-2 rounded-lg text-ink-soft hover:text-primary hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            aria-label="Limpar eventos coletados"
          >
            <Trash2 size={16} />
          </button>
        )}
      </div>

      {events.length > 0 && (
        <div className="mt-3 space-y-2">
          <div>
            <label htmlFor="event-type-filter" className="sr-only">
              Filtrar por tipo de evento
            </label>
            <select
              id="event-type-filter"
              value={type}
              onChange={(event) => setType(event.target.value as EventType | 'all')}
              className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-xs text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              <option value="all">Todos os tipos</option>
              {EVENT_TYPES.map((eventType) => (
                <option key={eventType} value={eventType}>
                  {EVENT_LABELS[eventType]}
                </option>
              ))}
            </select>
          </div>

          <div
            className="flex flex-wrap gap-1.5"
            role="group"
            aria-label="Filtrar por período"
          >
            {EVENT_PERIODS.map((option) => {
              const active = period === option.value
              return (
                <button
                  key={option.value}
                  type="button"
                  aria-pressed={active}
                  onClick={() => setPeriod(option.value)}
                  className={cn(
                    'text-xs font-medium px-2.5 py-1 rounded-full border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary',
                    active
                      ? 'bg-primary-dark text-white border-primary-dark'
                      : 'bg-white text-ink-soft border-gray-200 hover:bg-surface-muted'
                  )}
                >
                  {option.label}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {summary.length > 0 && (
        <ul aria-label="Contagem por tipo" className="mt-3 flex flex-wrap gap-1.5">
          {summary.map((item) => (
            <li
              key={item.type}
              className="text-[11px] bg-surface-muted text-ink-soft rounded-full px-2 py-1"
            >
              {EVENT_LABELS[item.type]} · {item.count}
            </li>
          ))}
        </ul>
      )}

      {filtered.length === 0 ? (
        <>
          <p className="mt-4 text-sm text-ink-soft">
            {events.length === 0
              ? 'Nenhum evento coletado ainda. Abra um restaurante, adicione um item ou finalize um pedido.'
              : 'Nenhum evento corresponde aos filtros selecionados.'}
          </p>
          {events.length > 0 && hasFilters && (
            <button
              type="button"
              onClick={() => {
                setType('all')
                setPeriod('all')
              }}
              className="mt-2 text-xs font-medium text-primary px-2 py-1 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              Limpar filtros
            </button>
          )}
        </>
      ) : (
        <>
          <ul aria-label="Eventos recentes" className="mt-3 space-y-2">
            {filtered.slice(0, 10).map((event) => (
              <li
                key={event.id}
                className="text-xs bg-surface-muted rounded-xl px-3 py-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-ink">{EVENT_LABELS[event.type]}</span>
                  <span className="text-ink-soft shrink-0">
                    {timeFormatter.format(new Date(event.createdAt))}
                  </span>
                </div>
                <p className="text-ink-soft mt-0.5 truncate">{formatPayload(event.payload)}</p>
              </li>
            ))}
          </ul>

          {filtered.length > 10 && (
            <p className="mt-2 text-xs text-ink-soft">
              Mostrando os 10 mais recentes de {filtered.length}.
            </p>
          )}
        </>
      )}
    </section>
  )
}
