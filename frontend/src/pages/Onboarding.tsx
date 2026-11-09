import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { MapPin } from 'lucide-react'
import { toast } from 'sonner'
import { DEFAULT_LOCATION, useLocationStore } from '@/store/locationStore'

export function Onboarding() {
  const navigate = useNavigate()
  const setLocation = useLocationStore((s) => s.setLocation)
  const [locating, setLocating] = useState(false)

  const goHome = () => navigate('/home')

  const handleLocation = () => {
    if (!navigator.geolocation) {
      toast.success('Usando Osasco, SP como localização padrão')
      goHome()
      return
    }

    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocation({
          lat: position.coords.latitude,
          lon: position.coords.longitude,
          label: 'Minha localização',
        })
        setLocating(false)
        toast.success('Localização detectada')
        goHome()
      },
      () => {
        setLocating(false)
        setLocation(DEFAULT_LOCATION)
        toast.success('Usando Osasco, SP como localização padrão')
        goHome()
      },
      { enableHighAccuracy: false, timeout: 5000, maximumAge: 600000 }
    )
  }

  const handleManualAddress = () => {
    setLocation(DEFAULT_LOCATION)
    goHome()
  }

  return (
    <div className="h-full flex flex-col items-center justify-center p-8 bg-white sm:max-w-md sm:mx-auto">
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
        type="button"
        onClick={handleLocation}
        disabled={locating}
        className="w-full bg-primary text-white rounded-2xl py-3.5 font-semibold flex items-center justify-center gap-2 hover:bg-primary-dark disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
      >
        <MapPin size={18} />{' '}
        {locating ? 'Detectando localização...' : 'Usar minha localização'}
      </button>
      <button
        type="button"
        onClick={handleManualAddress}
        className="mt-3 text-sm text-ink-soft underline rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        Digitar endereço manualmente
      </button>
    </div>
  )
}
