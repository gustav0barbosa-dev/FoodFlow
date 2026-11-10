const settingsItems = ['Notificações', 'Endereços', 'Pagamento']

export function SettingsList() {
  return (
    <section className="bg-white rounded-2xl border border-gray-100 divide-y divide-gray-100">
      {settingsItems.map((item) => (
        <button
          key={item}
          type="button"
          className="w-full text-left px-4 py-3 text-sm text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          {item}
        </button>
      ))}
    </section>
  )
}
