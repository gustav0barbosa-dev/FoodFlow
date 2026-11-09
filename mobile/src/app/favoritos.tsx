import React from 'react'
import { View, Text, TouchableOpacity, FlatList, Image } from 'react-native'
import { Link } from 'expo-router'
import { Heart } from 'lucide-react-native'
import { useColorScheme } from 'react-native'
import { formatBRL } from '@/lib/format'
import { useCatalogStore } from '@/store/catalogStore'
import { useFavoritesStore } from '@/store/favoritesStore'

export default function Favoritos() {
  const colorScheme = useColorScheme()
  const isDark = colorScheme === 'dark'
  const { restaurants } = useCatalogStore()
  const favoriteIds = useFavoritesStore((s: any) => s.favoriteIds)
  const favorites = restaurants.filter((r: any) => favoriteIds.includes(r.id))

  return (
    <View style={{ flex: 1, backgroundColor: isDark ? '#1a1a1a' : '#F7F7F7' }}>
      <View style={{ padding: 16, paddingTop: 50 }}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <Text style={{ fontSize: 20, fontWeight: 'bold', color: '#3F3E3E' }}>Favoritos</Text>
        </View>

        {favorites.length === 0 ? (
          <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 32 }}>
            <Heart size={64} color='#EA1D2C' style={{ marginBottom: 16 }} />
            <Text style={{ fontSize: 16, fontWeight: '600', color: '#3F3E3E' }}>Nenhum favorito ainda</Text>
            <Text style={{ fontSize: 12, color: '#717171', marginTop: 4, textAlign: 'center' }}>Toque no coração dos restaurantes que você gosta para encontrá-los aqui.</Text>
            <TouchableOpacity style={{ marginTop: 24, paddingHorizontal: 24, paddingVertical: 14, backgroundColor: '#EA1D2C', borderRadius: 14 }}>
              <Text style={{ color: '#fff', fontWeight: '600' }}>Explorar restaurantes</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <FlatList
            data={favorites}
            keyExtractor={(item: any) => item.id}
            renderItem={({ item }: { item: any }) => (
              <Link href={`/restaurante/${item.id}`}>
                <View style={{ backgroundColor: '#fff', borderRadius: 16, overflow: 'hidden', marginBottom: 12, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 8, elevation: 4 }}>
                  <View style={{ width: '100%', height: 120, backgroundColor: '#E5E7EB' }}>
                    <Image source={{ uri: item.image }} style={{ width: '100%', height: '100%' }} />
                  </View>
                  <View style={{ padding: 12 }}>
                    <Text style={{ fontSize: 16, fontWeight: '600', color: '#3F3E3E' }}>{item.name}</Text>
                    <Text style={{ fontSize: 12, color: '#717171', marginTop: 4 }}>{item.category}</Text>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 8 }}>
                      <Text style={{ fontSize: 12, color: '#717171' }}>{item.distanceKm.toFixed(1)} km</Text>
                      <Text style={{ fontSize: 12, color: '#717171' }}>{item.deliveryTimeMin}-{item.deliveryTimeMax} min</Text>
                    </View>
                  </View>
                </View>
              </Link>
            )}
            contentContainerStyle={{ paddingHorizontal: 16 }}
          />
        )}
      </View>
    </View>
  )
}
