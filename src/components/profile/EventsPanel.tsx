import { Trash2 } from 'lucide-react'
import { useEventsStore } from '@/store/eventsStore'
import type { EventPayload, EventType } from '@/store/eventsStore'

const labels: Record<EventType, string> = {
  restaurant_card_clicked: 'Card clicado',
  restaurant_opened: 'Restaurante aberto',
  add_to_cart: 'Item adicionado',
  order_completed: 'Pedido concluído',
  preferences_updated: 'Preferências atualizadas',
  search_performed: 'Busca realizada',
}

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

  return (
    <section className="bg-white rounded-2xl p-4 border border-gray-100">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="font-semibold text-ink">Eventos do recomendador</h2>
          <p className="text-xs text-ink-soft mt-0.5">
            Mock local de POST /events · {events.length}{' '}
            {events.length === 1 ? 'evento' : 'eventos'}
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

      {events.length === 0 ? (
        <p className="mt-4 text-sm text-ink-soft">
          Nenhum evento coletado ainda. Abra um restaurante, adicione um item ou finalize
          um pedido.
        </p>
      ) : (
        <ul className="mt-3 space-y-2">
          {events.slice(0, 10).map((event) => (
            <li key={event.id} className="text-xs bg-surface-muted rounded-xl px-3 py-2">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-ink">{labels[event.type]}</span>
                <span className="text-ink-soft shrink-0">
                  {timeFormatter.format(new Date(event.createdAt))}
                </span>
              </div>
              <p className="text-ink-soft mt-0.5 truncate">{formatPayload(event.payload)}</p>
            </li>
          ))}
        </ul>
      )}

      {events.length > 10 && (
        <p className="mt-2 text-xs text-ink-soft">
          Mostrando os 10 mais recentes de {events.length}.
        </p>
      )}
    </section>
  )
}
