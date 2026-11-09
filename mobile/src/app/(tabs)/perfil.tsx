import React from 'react'
import { View, Text, TouchableOpacity, ScrollView } from 'react-native'
import { Link } from 'expo-router'
import { Heart, ShieldCheck } from 'lucide-react-native'
import { useColorScheme } from 'react-native'
import { currentUser } from '@/data/mockData'
import { useFavoritesStore } from '@/store/favoritesStore'
import { useCatalogStore } from '@/store/catalogStore'

export default function Perfil() {
  const colorScheme = useColorScheme()
  const isDark = colorScheme === 'dark'
  const favoriteCount = useFavoritesStore((s: any) => s.favoriteIds.length)
  const { restaurants } = useCatalogStore()
  const favorites = restaurants.filter((r: any) => favoriteCount > 0 ? useFavoritesStore.getState().favoriteIds.includes(r.id) : false)

  return (
    <View style={{ flex: 1, backgroundColor: isDark ? '#1a1a1a' : '#F7F7F7' }}>
      <View style={{ padding: 16, paddingTop: 50 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 24 }}>
          <View style={{ width: 56, height: 56, borderRadius: 28, backgroundColor: '#EA1D2C', justifyContent: 'center', alignItems: 'center' }}>
            <Text style={{ fontSize: 24, color: '#fff' }}>{currentUser.name[0]}</Text>
          </View>
          <View>
            <Text style={{ fontSize: 20, fontWeight: 'bold', color: '#3F3E3E' }}>{currentUser.name}</Text>
            <Text style={{ fontSize: 12, color: '#717171' }}>{currentUser.email}</Text>
          </View>
        </View>

        <TouchableOpacity
          onPress={() => {}}
          style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#fff', borderRadius: 16, padding: 16, marginBottom: 12, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 8, elevation: 4 }}
        >
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <Heart size={18} color='#EA1D2C' />
            <Text style={{ fontSize: 16, fontWeight: '600', color: '#3F3E3E' }}>Favoritos</Text>
          </View>
          <Text style={{ fontSize: 12, color: '#717171', fontWeight: '600' }}>{favoriteCount}</Text>
        </TouchableOpacity>

        <View style={{ backgroundColor: '#fff', borderRadius: 16, padding: 16, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 8, elevation: 4 }}>
          <Text style={{ fontSize: 14, fontWeight: '600', color: '#3F3E3E', marginBottom: 8 }}>Suas preferências de recomendação</Text>
          <Text style={{ fontSize: 12, color: '#717171', marginBottom: 16 }}>Essas preferências ajudam a personalizar suas recomendações.</Text>
          <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
            {['Vegano', 'Vegetariano', 'Sem glúten', 'Sem lactose'].map((pref: string) => (
              <TouchableOpacity key={pref} style={{ paddingHorizontal: 10, paddingVertical: 6, backgroundColor: '#F7F7F7', borderRadius: 20 }}>
                <Text style={{ fontSize: 12, color: '#3F3E3E' }}>{pref}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        <TouchableOpacity
          onPress={() => {}}
          style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#fff', borderRadius: 16, padding: 16, marginBottom: 12, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 8, elevation: 4 }}
        >
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <ShieldCheck size={18} color='#EA1D2C' />
            <Text style={{ fontSize: 16, fontWeight: '600', color: '#3F3E3E' }}>Configurações</Text>
          </View>
        </TouchableOpacity>
      </View>
    </View>
  )
}
