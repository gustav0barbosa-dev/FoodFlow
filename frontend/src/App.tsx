import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'sonner'
import { MobileFrame } from '@/components/layout/MobileFrame'
import { BottomNav } from '@/components/layout/BottomNav'
import { GuestRoute, PrivateRoute } from '@/components/auth/PrivateRoute'
import { AuthProvider } from '@/contexts/AuthProvider'
import { Onboarding } from '@/pages/Onboarding'
import { Home } from '@/pages/Home'
import { Search } from '@/pages/Search'
import { RestaurantDetail } from '@/pages/RestaurantDetail'
import { Cart } from '@/pages/Cart'
import { Orders } from '@/pages/Orders'
import { Profile } from '@/pages/Profile'
import { ProfileAddress } from '@/pages/ProfileAddress'
import { Register } from '@/pages/Register'
import { Favorites } from '@/pages/Favorites'
import { OrderDetail } from '@/pages/OrderDetail'
import { useOrderAutoAdvance } from '@/hooks/useOrderAutoAdvance'

function WithNav({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-hidden">{children}</div>
      <BottomNav />
    </div>
  )
}

function ProtectedWithNav({ children }: { children: React.ReactNode }) {
  return (
    <PrivateRoute>
      <WithNav>{children}</WithNav>
    </PrivateRoute>
  )
}

export default function App() {
  useOrderAutoAdvance()

  return (
    <AuthProvider>
      <BrowserRouter>
        <MobileFrame>
          <Toaster position="top-center" richColors />
          <main className="h-full">
            <Routes>
              <Route
                path="/"
                element={
                  <GuestRoute>
                    <Onboarding />
                  </GuestRoute>
                }
              />
              <Route
                path="/bem-vindo"
                element={
                  <GuestRoute>
                    <Onboarding />
                  </GuestRoute>
                }
              />
              <Route path="/cadastro" element={<Register />} />
              <Route
                path="/home"
                element={
                  <ProtectedWithNav>
                    <Home />
                  </ProtectedWithNav>
                }
              />
              <Route
                path="/buscar"
                element={
                  <ProtectedWithNav>
                    <Search />
                  </ProtectedWithNav>
                }
              />
              <Route
                path="/restaurante/:id"
                element={
                  <PrivateRoute>
                    <RestaurantDetail />
                  </PrivateRoute>
                }
              />
              <Route
                path="/sacola"
                element={
                  <PrivateRoute>
                    <Cart />
                  </PrivateRoute>
                }
              />
              <Route
                path="/favoritos"
                element={
                  <PrivateRoute>
                    <Favorites />
                  </PrivateRoute>
                }
              />
              <Route
                path="/pedidos"
                element={
                  <ProtectedWithNav>
                    <Orders />
                  </ProtectedWithNav>
                }
              />
              <Route
                path="/pedidos/:id"
                element={
                  <PrivateRoute>
                    <OrderDetail />
                  </PrivateRoute>
                }
              />
              <Route
                path="/perfil"
                element={
                  <ProtectedWithNav>
                    <Profile />
                  </ProtectedWithNav>
                }
              />
              <Route
                path="/perfil/endereco"
                element={
                  <PrivateRoute>
                    <ProfileAddress />
                  </PrivateRoute>
                }
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </MobileFrame>
      </BrowserRouter>
    </AuthProvider>
  )
}
