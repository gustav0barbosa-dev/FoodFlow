import React from 'react'
import { View, Text, TouchableOpacity, Image } from 'react-native'
import { Link, useRouter } from 'expo-router'
import { ChevronLeft, Heart } from 'lucide-react-native'
import { useColorScheme } from 'react-native'
import { formatBRL } from '@/lib/format'
import { useRoute } from 'expo-router'
import { restaurants } from '@/data/mockData'

export default function RestauranteDetalhe() {
  const colorScheme = useColorScheme()
  const isDark = colorScheme === 'dark'
  const router = useRouter()
  const route = useRoute()
  const { id } = route.params as { id: string }

  const restaurant = restaurants.find((r: any) => r.id === id)

  if (!restaurant) {
    return (
      <View
        style={{
          flex: 1,
          backgroundColor: '#fff',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 32,
        }}
      >
        <Text style={{ fontSize: 16, color: '#717171' }}>
          Restaurante não encontrado
        </Text>
        <TouchableOpacity
          onPress={() => router.back()}
          style={{
            marginTop: 16,
            paddingHorizontal: 16,
            paddingVertical: 8,
            backgroundColor: '#EA1D2C',
            borderRadius: 12,
          }}
        >
          <Text style={{ color: '#fff', fontWeight: '600' }}>Voltar</Text>
        </TouchableOpacity>
      </View>
    )
  }

  return (
    <View style={{ flex: 1, backgroundColor: '#fff' }}>
      <View
        style={{ width: '100%', height: 200, backgroundColor: '#E5E7EB' }}
      >
        <Image
          source={{ uri: restaurant.image }}
          style={{ width: '100%', height: '100%' }}
        />
      </View>
      <TouchableOpacity
        onPress={() => router.back()}
        style={{
          position: 'absolute',
          top: 50,
          left: 16,
          width: 44,
          height: 44,
          borderRadius: 22,
          backgroundColor: 'rgba(255,255,255,0.9)',
          justifyContent: 'center',
          alignItems: 'center',
        }}
      >
        <ChevronLeft size={20} color='#3F3E3E' />
      </TouchableOpacity>
      <TouchableOpacity
        style={{
          position: 'absolute',
          top: 50,
          right: 16,
          width: 44,
          height: 44,
          borderRadius: 22,
          backgroundColor: 'rgba(255,255,255,0.9)',
          justifyContent: 'center',
          alignItems: 'center',
        }}
      >
        <Heart size={20} color='#EA1D2C' />
      </TouchableOpacity>

      <View style={{ padding: 16 }}>
        <Text style={{ fontSize: 22, fontWeight: 'bold', color: '#3F3E3E' }}>
          {restaurant.name}
        </Text>
        <Text
          style={{ fontSize: 14, color: '#717171', marginTop: 4 }}
        >
          {restaurant.category}
        </Text>
        <View
          style={{
            flexDirection: 'row',
            gap: 8,
            marginTop: 12,
          }}
        >
          {restaurant.dietaryTags.map((tag: string) => (
            <View
              key={tag}
              style={{
                backgroundColor: '#ECFDF5',
                borderRadius: 20,
                paddingHorizontal: 10,
                paddingVertical: 4,
              }}
            >
              <Text style={{ fontSize: 11, color: '#15803d', fontWeight: '600' }}>
                {tag}
              </Text>
            </View>
          ))}
        </View>

        <View
          style={{
            flexDirection: 'row',
            backgroundColor: '#F7F7F7',
            borderRadius: 16,
            padding: 16,
            marginTop: 16,
            gap: 16,
          }}
        >
          <View>
            <Text style={{ fontSize: 12, color: '#717171' }}>Nota</Text>
            <View
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                gap: 4,
                marginTop: 4,
              }}
            >
              <Text style={{ fontSize: 20, fontWeight: 'bold', color: '#3F3E3E' }}>
                {restaurant.rating}
              </Text>
              <Text style={{ fontSize: 12, color: '#717171' }}>
                {restaurant.reviewCount} avaliações
              </Text>
            </View>
          </View>
          <View style={{ width: 1, height: 40, backgroundColor: '#E5E7EB' }} />
          <View>
            <Text style={{ fontSize: 12, color: '#717171' }}>Entrega</Text>
            <Text
              style={{
                fontSize: 14,
                fontWeight: '600',
                color: '#3F3E3E',
                marginTop: 4,
              }}
            >
              {restaurant.deliveryFee === 0
                ? 'Grátis'
                : formatBRL(restaurant.deliveryFee)}
            </Text>
          </View>
          <View style={{ width: 1, height: 40, backgroundColor: '#E5E7EB' }} />
          <View>
            <Text style={{ fontSize: 12, color: '#717171' }}>Tempo</Text>
            <Text
              style={{
                fontSize: 14,
                fontWeight: '600',
                color: '#3F3E3E',
                marginTop: 4,
              }}
            >
              {restaurant.deliveryTimeMin}-{restaurant.deliveryTimeMax} min
            </Text>
          </View>
        </View>

        <View style={{ marginTop: 16 }}>
          <Text style={{ fontSize: 14, fontWeight: '600', color: '#3F3E3E' }}>
            Horário de funcionamento
          </Text>
          <Text style={{ fontSize: 14, color: '#3F3E3E', marginTop: 4 }}>
            {restaurant.hours}
          </Text>
        </View>

        <View style={{ marginTop: 16 }}>
          <Text style={{ fontSize: 14, fontWeight: '600', color: '#3F3E3E' }}>
            Endereço
          </Text>
          <Text style={{ fontSize: 14, color: '#3F3E3E', marginTop: 4 }}>
            {restaurant.address}
          </Text>
        </View>

        <View style={{ marginTop: 16 }}>
          <Text style={{ fontSize: 14, fontWeight: '600', color: '#3F3E3E' }}>
            Formas de pagamento
          </Text>
          <View
            style={{
              flexDirection: 'row',
              gap: 8,
              marginTop: 8,
            }}
          >
            {restaurant.paymentMethods.map((method: string) => (
              <View
                key={method}
                style={{
                  backgroundColor: '#F7F7F7',
                  borderRadius: 12,
                  paddingHorizontal: 12,
                  paddingVertical: 8,
                }}
              >
                <Text style={{ fontSize: 12, color: '#3F3E3E' }}>
                  {method}
                </Text>
              </View>
            ))}
          </View>
        </View>
      </View>
    </View>
  )
}
