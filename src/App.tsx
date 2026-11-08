import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'sonner'
import { MobileFrame } from '@/components/layout/MobileFrame'
import { BottomNav } from '@/components/layout/BottomNav'
import { Onboarding } from '@/pages/Onboarding'
import { Home } from '@/pages/Home'
import { Search } from '@/pages/Search'
import { RestaurantDetail } from '@/pages/RestaurantDetail'
import { Cart } from '@/pages/Cart'
import { Orders } from '@/pages/Orders'
import { Profile } from '@/pages/Profile'
import { Favorites } from '@/pages/Favorites'
import { OrderDetail } from '@/pages/OrderDetail'

function WithNav({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 overflow-hidden">{children}</div>
      <BottomNav />
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <MobileFrame>
        <Toaster position="top-center" richColors />
        <main className="h-full">
          <Routes>
            <Route path="/" element={<Onboarding />} />
            <Route
              path="/home"
              element={
                <WithNav>
                  <Home />
                </WithNav>
              }
            />
            <Route
              path="/buscar"
              element={
                <WithNav>
                  <Search />
                </WithNav>
              }
            />
            <Route path="/restaurante/:id" element={<RestaurantDetail />} />
            <Route path="/sacola" element={<Cart />} />
            <Route path="/favoritos" element={<Favorites />} />
            <Route
              path="/pedidos"
              element={
                <WithNav>
                  <Orders />
                </WithNav>
              }
            />
            <Route path="/pedidos/:id" element={<OrderDetail />} />
            <Route
              path="/perfil"
              element={
                <WithNav>
                  <Profile />
                </WithNav>
              }
            />
            <Route path="*" element={<Navigate to="/home" replace />} />
          </Routes>
        </main>
      </MobileFrame>
    </BrowserRouter>
  )
}
