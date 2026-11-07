import { useNavigate } from 'react-router-dom'
import { MapPin } from 'lucide-react'
import { toast } from 'sonner'

export function Onboarding() {
  const navigate = useNavigate()

  const handleLocation = () => {
    // TODO: usar navigator.geolocation
    toast.success('Localização detectada: Osasco, SP')
    setTimeout(() => navigate('/home'), 600)
  }

  return (
    <div className="h-full flex flex-col items-center justify-center p-8 bg-white">
      <div className="w-20 h-20 rounded-3xl bg-primary flex items-center justify-center text-white text-3xl font-bold mb-6">
        🍴
      </div>
      <h1 className="font-display text-2xl font-bold text-ink text-center mb-2">
        FoodFlow
      </h1>
      <p className="text-center text-ink-soft mb-2">
        Descubra restaurantes perto de você
      </p>
      <p className="text-center text-sm text-ink-soft mb-8">
        Ative sua localização para ver os melhores restaurantes da sua região.
      </p>

      <button
        onClick={handleLocation}
        className="w-full bg-primary text-white rounded-2xl py-3.5 font-semibold flex items-center justify-center gap-2"
      >
        <MapPin size={18} /> Usar minha localização
      </button>
      <button className="mt-3 text-sm text-ink-soft underline">
        Digitar endereço manualmente
      </button>
    </div>
  )
}