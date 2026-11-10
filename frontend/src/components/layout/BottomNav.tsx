import { Home, Search, ReceiptText, User } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'

const tabs = [
  { to: '/home', label: 'Início', icon: Home },
  { to: '/buscar', label: 'Buscar', icon: Search },
  { to: '/pedidos', label: 'Pedidos', icon: ReceiptText },
  { to: '/perfil', label: 'Perfil', icon: User },
]

export function BottomNav() {
  return (
    <nav
      className={cn(
        // Sempre uma linha horizontal fixa no rodapé da moldura.
        'z-20 flex h-16 shrink-0 items-center justify-around border-t border-gray-200 bg-white',
        // No desktop, centraliza os atalhos dentro da largura maior da moldura.
        'sm:justify-center sm:gap-4'
      )}
    >
      {tabs.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            cn(
              'flex flex-col items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary',
              isActive ? 'text-primary' : 'text-ink-soft',
              // Tablet/Desktop: alvo maior e fundo sutil.
              'sm:rounded-xl sm:border sm:border-gray-100 sm:bg-white/50 sm:px-4 sm:py-1.5 sm:shadow-sm sm:hover:bg-white'
            )
          }
        >
          <Icon size={22} />
          {label}
        </NavLink>
      ))}
    </nav>
  )
}
