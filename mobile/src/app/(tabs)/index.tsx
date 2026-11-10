import React from 'react'
import { View, Text, TextInput, TouchableOpacity, Image, ActivityIndicator, FlatList, StatusBar } from 'react-native'
import { Link, useRouter } from 'expo-router'
import { ShoppingCart, MapPin } from 'lucide-react-native'
import { useColorScheme } from 'react-native'
import { formatBRL } from '@/lib/format'
import { useCartStore } from '@/store/cartStore'
import { useLocationStore } from '@/store/locationStore'
import { useCatalogStore } from '@/store/catalogStore'
import { filterRestaurants } from '@/lib/search'

export default function Home() {
  const colorScheme = useColorScheme()
  const isDark = colorScheme === 'dark'
  const cartCount = useCartStore((s) => s.count())
  const { restaurants: catalogRestaurants, recommended, load, loading } = useCatalogStore()
  const locationLabel = useLocationStore((s) => s.label)
  const router = useRouter()
  const [query, setQuery] = React.useState('')
  const [loadedCount, setLoadedCount] = React.useState(3)
  const [filter, setFilter] = React.useState('Todos')
  const [category, setCategory] = React.useState<string | null>(null)

  React.useEffect(() => {
    load()
  }, [load])

  const searched = filterRestaurants(catalogRestaurants, query)
  const filtered = searched.filter(
    (r: any) => filter === 'Todos' || r.tags.some((t: string) => t.toLowerCase().includes(filter.toLowerCase()))
  )

  const nearby = filtered.filter(
    (r: any) => !category || r.category === category
  )

  // O feed personalizado vem de GET /recommendations. Se a API não retornar
  // recomendações, mantém o fallback para os itens marcados no catálogo/mock.
  const recommendedAll = recommended.length
    ? recommended
    : filtered.filter((r: any) => r.isRecommended)
  const recommendedList = recommendedAll.slice(0, loadedCount)

  return (
    <View style={{ flex: 1, backgroundColor: isDark ? '#1a1a1a' : '#F7F7F7' }}>
      <StatusBar barStyle={isDark ? 'dark-content' : 'light-content'} />
      <View style={{ padding: 16, paddingTop: 50 }}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <View>
            <Text style={{ fontSize: 14, color: '#717171', marginBottom: 4 }}>Olá, Ana Souza 👋</Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
              <MapPin size={14} color='#EA1D2C' />
              <Text style={{ fontSize: 16, fontWeight: '600', color: '#3F3E3E' }}>{locationLabel}</Text>
            </View>
          </View>
          <TouchableOpacity
            style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: '#F7F7F7', justifyContent: 'center', alignItems: 'center' }}
            onPress={() => router.push('/sacola')}
          >
            <ShoppingCart size={22} color='#3F3E3E' />
            {cartCount > 0 && (
              <View style={{ position: 'absolute', top: 6, right: 6, width: 18, height: 18, borderRadius: 9, backgroundColor: '#EA1D2C', justifyContent: 'center', alignItems: 'center' }}>
                <Text style={{ fontSize: 10, color: '#fff', fontWeight: 'bold' }}>{cartCount > 99 ? '99+' : cartCount}</Text>
              </View>
            )}
          </TouchableOpacity>
        </View>

        <View style={{ flexDirection: 'row', gap: 8, marginBottom: 16 }}>
          <TextInput
            placeholder="Buscar restaurantes..."
            value={query}
            onChangeText={setQuery}
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
          <TouchableOpacity style={{ width: 44, height: 44, borderRadius: 12, backgroundColor: '#EA1D2C', justifyContent: 'center', alignItems: 'center' }}>
            <MapPin size={20} color='#fff' />
          </TouchableOpacity>
        </View>

        <View style={{ marginBottom: 16 }}>
          <Text style={{ fontSize: 20, fontWeight: 'bold', color: '#3F3E3E', marginBottom: 8 }}>Recomendados para você</Text>
          <Text style={{ fontSize: 12, color: '#717171', marginBottom: 12 }}>Baseado no seu histórico e horário</Text>

          {loading ? (
            <View style={{ height: 200, justifyContent: 'center', alignItems: 'center' }}>
              <ActivityIndicator size="large" color="#EA1D2C" />
            </View>
          ) : (
            <View style={{ height: 260 }}>
              <FlatList
                data={recommendedList}
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={{ paddingLeft: 0 }}
                keyExtractor={(item: any) => item.id}
                renderItem={({ item }: { item: any }) => (
                  <Link href={`/restaurante/${item.id}`}>
                    <View style={{ width: 180, marginRight: 12 }}>
                      <View style={{ width: 180, height: 120, borderRadius: 16, overflow: 'hidden', backgroundColor: '#E5E7EB' }}>
                        <Image source={{ uri: item.image }} style={{ width: '100%', height: '100%' }} />
                      </View>
                      <View style={{ paddingTop: 8 }}>
                        <Text style={{ fontSize: 16, fontWeight: '600', color: '#3F3E3E' }}>{item.name}</Text>
                        <Text style={{ fontSize: 12, color: '#717171', marginTop: 2 }}>{item.category}</Text>
                      </View>
                    </View>
                  </Link>
                )}
              />
            </View>
          )}
          {recommendedAll.length > loadedCount && (
            <TouchableOpacity
              onPress={() => setLoadedCount((c: number) => c + 3)}
              style={{ alignSelf: 'center', marginTop: 8, paddingHorizontal: 16, paddingVertical: 10, backgroundColor: '#fff', borderRadius: 12, borderWidth: 1, borderColor: '#E5E7EB' }}
            >
              <Text style={{ fontSize: 14, color: '#EA1D2C', fontWeight: '600' }}>Carregar mais</Text>
            </TouchableOpacity>
          )}
        </View>

        <View style={{ marginTop: 16 }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <Text style={{ fontSize: 20, fontWeight: 'bold', color: '#3F3E3E' }}>Perto de você</Text>
          </View>

          {loading ? (
            <View style={{ height: 400, justifyContent: 'center', alignItems: 'center' }}>
              <ActivityIndicator size="large" color="#EA1D2C" />
            </View>
          ) : nearby.length === 0 ? (
            <View style={{ justifyContent: 'center', alignItems: 'center', paddingVertical: 40 }}>
              <Text style={{ color: '#717171' }}>Nenhum restaurante encontrado</Text>
            </View>
          ) : (
            <FlatList
              data={nearby.slice(0, loadedCount)}
              keyExtractor={(item: any) => item.id}
              renderItem={({ item }: { item: any }) => (
                <Link href={`/restaurante/${item.id}`}>
                  <View style={{ flexDirection: 'row', backgroundColor: '#fff', borderRadius: 16, overflow: 'hidden', marginBottom: 12, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 8, elevation: 4 }}>
                    <View style={{ width: 90, height: 90, backgroundColor: '#E5E7EB' }}>
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
