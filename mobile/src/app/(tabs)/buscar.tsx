import React from 'react'
import { View, Text, TextInput, ScrollView, TouchableOpacity, Image, FlatList, StatusBar } from 'react-native'
import { Link, useRouter } from 'expo-router'
import { SearchX } from 'lucide-react-native'
import { useColorScheme } from 'react-native'
import { formatBRL } from '@/lib/format'
import { useCatalogStore } from '@/store/catalogStore'
import { filterRestaurants } from '@/lib/search'

export default function Buscar() {
  const colorScheme = useColorScheme()
  const isDark = colorScheme === 'dark'
  const { restaurants: catalogRestaurants, load, loading } = useCatalogStore()
  const router = useRouter()
  const [query, setQuery] = React.useState('')

  React.useEffect(() => {
    load()
  }, [load])

  const recentSearches = ['pizza', 'japonês', 'açaí', 'hambúrguer']
  const searched = filterRestaurants(catalogRestaurants, query)

  return (
    <View style={{ flex: 1, backgroundColor: isDark ? '#1a1a1a' : '#F7F7F7' }}>
      <View style={{ padding: 16, paddingTop: 50 }}>
        <View style={{ flexDirection: 'row', gap: 8, marginBottom: 20 }}>
          <TouchableOpacity onPress={() => router.back()} style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: '#F7F7F7', justifyContent: 'center', alignItems: 'center' }}>
            <SearchX size={20} color='#EA1D2C' />
          </TouchableOpacity>
          <TextInput
            placeholder="Buscar restaurantes..."
            value={query}
            onChangeText={setQuery}
            autoFocus
            style={{
              flex: 1,
              height: 48,
              backgroundColor: isDark ? '#2a2a2a' : '#fff',
              borderRadius: 12,
              paddingHorizontal: 16,
              color: isDark ? '#fff' : '#3F3E3E',
              fontSize: 14,
            }}
          />
        </View>

        {!query && (
          <View style={{ marginBottom: 20 }}>
            <Text style={{ fontSize: 14, fontWeight: '600', color: '#3F3E3E', marginBottom: 8 }}>Buscas recentes</Text>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
              {recentSearches.map((s: string) => (
                <TouchableOpacity
                  key={s}
                  onPress={() => setQuery(s)}
                  style={{ paddingHorizontal: 12, paddingVertical: 8, backgroundColor: '#fff', borderRadius: 20, borderWidth: 1, borderColor: '#E5E7EB' }}
                >
                  <Text style={{ fontSize: 13, color: '#3F3E3E' }}>{s}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        )}

        <View style={{ paddingHorizontal: 16 }}>
          {loading ? (
            <View style={{ paddingVertical: 40 }}>
              <Text style={{ color: '#717171' }}>Carregando…</Text>
            </View>
          ) : searched.length === 0 ? (
            <View style={{ paddingVertical: 40, alignItems: 'center' }}>
              <SearchX size={48} color='#EA1D2C' style={{ marginBottom: 12 }} />
              <Text style={{ fontSize: 16, fontWeight: '600', color: '#3F3E3E' }}>Nenhum restaurante encontrado</Text>
              <Text style={{ fontSize: 12, color: '#717171', marginTop: 4 }}>Tente outro termo ou revise a ortografia.</Text>
            </View>
          ) : (
            <FlatList
              data={searched}
              keyExtractor={(item: any) => item.id}
              renderItem={({ item }: { item: any }) => (
                <Link href={`/restaurante/${item.id}`}>
                  <View style={{ flexDirection: 'row', backgroundColor: '#fff', borderRadius: 16, overflow: 'hidden', marginBottom: 12, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 8, elevation: 4 }}>
                    <View style={{ width: 70, height: 70, backgroundColor: '#E5E7EB' }}>
                      <Image source={{ uri: item.image }} style={{ width: '100%', height: '100%' }} />
                    </View>
                    <View style={{ padding: 12, flex: 1 }}>
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
            />
          )}
        </View>
      </View>
    </View>
  )
}
