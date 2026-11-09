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
        // Mobile: absolute sobreposto ao conteúdo no fundo da tela.
        'absolute bottom-0 left-0 right-0 h-16 bg-white border-t border-gray-200 flex items-center justify-around z-20',
        // Tablet/Desktop: não sobrepõe, fica no fluxo com largura limitada e espaçamento.
        'sm:static sm:block sm:w-auto sm:h-auto sm:bg-transparent sm:border-0 sm:z-auto sm:mx-auto sm:mt-6 sm:mb-4'
      )}
    >
      {tabs.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            cn(
              'flex flex-col items-center gap-1 text-xs font-medium rounded-lg px-2 py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary',
              isActive ? 'text-primary' : 'text-ink-soft',
              // Tablet/Desktop: target maior e fundo sutil.
              'sm:px-3 sm:py-1.5 sm:bg-white/50 sm:rounded-xl sm:border sm:border-gray-100 sm:shadow-sm sm:hover:bg-white'
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
