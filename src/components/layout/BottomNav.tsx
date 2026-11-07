import { Home, Search, ReceiptText, User } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { useCartStore } from '@/store/cartStore'
import { cn } from '@/lib/utils'

const tabs = [
  { to: '/home', label: 'Início', icon: Home },
  { to: '/buscar', label: 'Buscar', icon: Search },
  { to: '/pedidos', label: 'Pedidos', icon: ReceiptText },
  { to: '/perfil', label: 'Perfil', icon: User },
]

export function BottomNav() {
  const count = useCartStore((s) => s.count())

  return (
    <nav className="absolute bottom-0 left-0 right-0 h-16 bg-white border-t border-gray-200 flex items-center justify-around">
      {tabs.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            cn(
              'flex flex-col items-center gap-1 text-xs font-medium',
              isActive ? 'text-primary' : 'text-ink-soft'
            )
          }
        >
          <div className="relative">
            <Icon size={22} />
            {to === '/pedidos' && count > 0 && (
              <span className="absolute -top-1 -right-2 bg-primary text-white text-[10px] rounded-full w-4 h-4 flex items-center justify-center">
                {count}
              </span>
            )}
          </div>
          {label}
        </NavLink>
      ))}
    </nav>
  )
}