import React from 'react'
import { View, Text, TouchableOpacity } from 'react-native'
import { MapPin } from 'lucide-react-native'
import { Link, useRouter } from 'expo-router'
import { useColorScheme } from 'react-native'
import { useLocationStore } from '@/store/locationStore'
import { DEFAULT_LOCATION } from '@/store/locationStore'

export default function Onboarding() {
  const colorScheme = useColorScheme()
  const isDark = colorScheme === 'dark'
  const router = useRouter()
  const setLocation = useLocationStore((s: any) => s.setLocation)

  const handleLocation = async () => {
    try {
      const { status } = await (await import('expo-location')).requestForegroundPermissionsAsync()
      if (status !== 'granted') {
        setLocation(DEFAULT_LOCATION)
        router.push('/(tabs)/index')
        return
      }
      const location = await (await import('expo-location')).getCurrentPositionAsync()
      setLocation({
        lat: location.coords.latitude,
        lon: location.coords.longitude,
        label: 'Minha localização',
      })
      router.push('/(tabs)/index')
    } catch {
      setLocation(DEFAULT_LOCATION)
      router.push('/(tabs)/index')
    }
  }

  return (
    <View style={{ flex: 1, backgroundColor: '#fff', alignItems: 'center', justifyContent: 'center', padding: 32 }}>
      <View style={{ width: 80, height: 80, borderRadius: 40, backgroundColor: '#EA1D2C', justifyContent: 'center', alignItems: 'center', marginBottom: 32 }}>
        <Text style={{ fontSize: 40 }}>🍴</Text>
      </View>
      <Text style={{ fontSize: 28, fontWeight: 'bold', color: '#3F3E3E', textAlign: 'center', marginBottom: 8 }}>FoodFlow</Text>
      <Text style={{ fontSize: 16, color: '#717171', textAlign: 'center', marginBottom: 8 }}>Descubra restaurantes perto de você</Text>
      <Text style={{ fontSize: 14, color: '#717171', textAlign: 'center', marginBottom: 32 }}>Ative sua localização para ver os melhores restaurantes da sua região.</Text>

      <TouchableOpacity onPress={handleLocation} style={{ width: '100%', backgroundColor: '#EA1D2C', borderRadius: 16, paddingVertical: 18, alignItems: 'center', marginBottom: 16 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
          <MapPin size={18} color='#fff' />
          <Text style={{ color: '#fff', fontSize: 16, fontWeight: '600' }}>Usar minha localização</Text>
        </View>
      </TouchableOpacity>
      <TouchableOpacity onPress={() => { setLocation(DEFAULT_LOCATION); router.push('/(tabs)/index') }} style={{ paddingVertical: 12 }}>
        <Text style={{ fontSize: 14, color: '#717171', textDecorationLine: 'underline' }}>Digitar endereço manualmente</Text>
      </TouchableOpacity>
    </View>
  )
}
