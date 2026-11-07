const mockOrders = [
  { id: 'o1', name: 'Sabor da Vila', date: '12/10/2025', total: 48.9, status: 'Entregue' },
  { id: 'o2', name: 'Verde Vivo', date: '08/10/2025', total: 32.5, status: 'Entregue' },
]

export function Orders() {
  return (
    <div className="h-full overflow-y-auto pb-20 bg-surface-muted">
      <header className="sticky top-0 z-10 bg-white px-4 py-4 border-b border-gray-100">
        <h1 className="font-display font-bold text-lg text-ink">Pedidos</h1>
      </header>

      <div className="p-4 space-y-3">
        {mockOrders.map((o) => (
          <div key={o.id} className="bg-white rounded-2xl p-4 border border-gray-100">
            <div className="flex justify-between">
              <span className="font-medium text-ink">{o.name}</span>
              <span className="text-xs text-green-600 font-medium">{o.status}</span>
            </div>
            <p className="text-xs text-ink-soft mt-1">{o.date}</p>
            <div className="flex justify-between items-center mt-2">
              <span className="font-semibold text-primary">
                {o.total.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
              </span>
              <button className="text-sm text-primary font-medium">Pedir novamente</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}