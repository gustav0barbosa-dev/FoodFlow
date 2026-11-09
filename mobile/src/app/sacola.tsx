import React from 'react'
import { View, Text, TouchableOpacity, ScrollView } from 'react-native'
import { ChevronLeft, ShoppingBag } from 'lucide-react-native'
import { useColorScheme } from 'react-native'
import { formatBRL } from '@/lib/format'
import { useCartStore } from '@/store/cartStore'
import { useOrdersStore } from '@/store/ordersStore'
import { useAddressStore } from '@/store/addressStore'

export default function Sacola() {
  const colorScheme = useColorScheme()
  const isDark = colorScheme === 'dark'
  const lines = useCartStore((s: any) => s.lines)
  const total = useCartStore((s: any) => s.total())
  const count = useCartStore((s: any) => s.count())
  const address = useAddressStore((s: any) => s.address)

  const groups: Record<
    string,
    {
      restaurantId: string
      restaurantName: string
      deliveryFee: number
      lines: any[]
    }
  > = {}
  lines.forEach((line: any) => {
    if (!groups[line.restaurantId]) {
      groups[line.restaurantId] = {
        restaurantId: line.restaurantId,
        restaurantName: line.restaurantName,
        deliveryFee: line.item.price * 0.1,
        lines: [],
      }
    }
    groups[line.restaurantId].lines.push(line)
  })

  const subtotal = lines.reduce(
    (sum: number, line: any) => sum + line.item.price * line.quantity,
    0
  )
  const deliveryFee = Object.values(groups).reduce(
    (sum: number, g: any) => sum + g.deliveryFee,
    0
  )
  const grandTotal = subtotal + deliveryFee

  if (lines.length === 0) {
    return (
      <View
        style={{
          flex: 1,
          backgroundColor: isDark ? '#1a1a1a' : '#F7F7F7',
          alignItems: 'center',
          justifyContent: 'center',
          paddingHorizontal: 32,
        }}
      >
        <ShoppingBag size={64} color='#EA1D2C' style={{ marginBottom: 16 }} />
        <Text
          style={{
            fontSize: 16,
            fontWeight: '600',
            color: '#3F3E3E',
          }}
        >
          Sua sacola está vazia
        </Text>
        <Text
          style={{
            fontSize: 12,
            color: '#717171',
            marginTop: 4,
          }}
        >
          Adicione itens de um restaurante para começar seu pedido.
        </Text>
        <TouchableOpacity
          style={{
            marginTop: 24,
            paddingHorizontal: 24,
            paddingVertical: 14,
            backgroundColor: '#EA1D2C',
            borderRadius: 14,
          }}
        >
          <Text style={{ color: '#fff', fontWeight: '600' }}>
            Explorar restaurantes
          </Text>
        </TouchableOpacity>
      </View>
    )
  }

  return (
    <View
      style={{
        flex: 1,
        backgroundColor: isDark ? '#1a1a1a' : '#F7F7F7',
      }}
    >
      <View style={{ padding: 16, paddingTop: 50 }}>
        <View
          style={{
            flexDirection: 'row',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 20,
          }}
        >
          <TouchableOpacity
            style={{
              width: 44,
              height: 44,
              borderRadius: 22,
              backgroundColor: '#F7F7F7',
              justifyContent: 'center',
              alignItems: 'center',
            }}
          >
            <ChevronLeft size={20} color='#3F3E3E' />
          </TouchableOpacity>
          <Text style={{ fontSize: 20, fontWeight: 'bold', color: '#3F3E3E' }}>
            Sacola
          </Text>
        </View>
        <Text style={{ fontSize: 14, color: '#717171' }}>
          {count} {count === 1 ? 'item' : 'itens'}
        </Text>
      </View>

      <ScrollView style={{ flex: 1 }}>
        {Object.values(groups).map((group: any) => (
          <View
            key={group.restaurantId}
            style={{
              backgroundColor: '#fff',
              borderRadius: 16,
              marginHorizontal: 16,
              marginBottom: 12,
              shadowColor: '#000',
              shadowOffset: { width: 0, height: 2 },
              shadowOpacity: 0.1,
              shadowRadius: 8,
              elevation: 4,
            }}
          >
            <View
              style={{
                padding: 16,
                borderBottomWidth: 1,
                borderBottomColor: '#E5E7EB',
                flexDirection: 'row',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <Text style={{ fontSize: 16, fontWeight: '600', color: '#3F3E3E' }}>
                {group.restaurantName}
              </Text>
              <Text style={{ fontSize: 12, color: '#717171' }}>
                {group.deliveryFee === 0
                  ? 'Frete grátis'
                  : `Entrega ${formatBRL(group.deliveryFee)}`}
              </Text>
            </View>
            {group.lines.map((line: any) => (
              <View
                key={line.item.id}
                style={{
                  paddingHorizontal: 16,
                  paddingVertical: 12,
                  borderBottomWidth: 1,
                  borderBottomColor: '#E5E7EB',
                  flexDirection: 'row',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <View>
                  <Text
                    style={{ fontSize: 15, color: '#3F3E3E', fontWeight: '500' }}
                  >
                    {line.item.name}
                  </Text>
                  <Text
                    style={{
                      fontSize: 12,
                      color: '#717171',
                      marginTop: 2,
                    }}
                  >
                    {line.item.description}
                  </Text>
                </View>
                <View
                  style={{
                    flexDirection: 'row',
                    alignItems: 'center',
                    gap: 8,
                  }}
                >
                  <TouchableOpacity
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: 16,
                      backgroundColor: '#F7F7F7',
                      justifyContent: 'center',
                      alignItems: 'center',
                    }}
                  >
                    <Text style={{ color: '#3F3E3E', fontWeight: 'bold' }}>
                      -
                    </Text>
                  </TouchableOpacity>
                  <Text
                    style={{ fontSize: 14, fontWeight: '600', color: '#3F3E3E' }}
                  >
                    {line.quantity}
                  </Text>
                  <TouchableOpacity
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: 16,
                      backgroundColor: '#F7F7F7',
                      justifyContent: 'center',
                      alignItems: 'center',
                    }}
                  >
                    <Text style={{ color: '#EA1D2C', fontWeight: 'bold' }}>
                      +
                    </Text>
                  </TouchableOpacity>
                </View>
              </View>
            ))}
          </View>
        ))}
      </ScrollView>

      <View
        style={{
          padding: 16,
          backgroundColor: '#fff',
          borderTopWidth: 1,
          borderTopColor: '#E5E7EB',
        }}
      >
        <View
          style={{
            flexDirection: 'row',
            justifyContent: 'space-between',
            marginBottom: 8,
          }}
        >
          <Text style={{ fontSize: 14, color: '#717171' }}>Subtotal</Text>
          <Text style={{ fontSize: 14, color: '#3F3E3E', fontWeight: '600' }}>
            {formatBRL(subtotal)}
          </Text>
        </View>
        <View
          style={{
            flexDirection: 'row',
            justifyContent: 'space-between',
            marginBottom: 8,
          }}
        >
          <Text style={{ fontSize: 14, color: '#717171' }}>
            Taxa de entrega
          </Text>
          <Text style={{ fontSize: 14, color: '#3F3E3E', fontWeight: '600' }}>
            {deliveryFee === 0 ? 'Grátis' : formatBRL(deliveryFee)}
          </Text>
        </View>
        <View
          style={{
            flexDirection: 'row',
            justifyContent: 'space-between',
            borderTopWidth: 1,
            borderTopColor: '#E5E7EB',
            paddingTop: 8,
            marginTop: 8,
          }}
        >
          <Text
            style={{ fontSize: 16, fontWeight: 'bold', color: '#3F3E3E' }}
          >
            Total
          </Text>
          <Text style={{ fontSize: 18, fontWeight: 'bold', color: '#EA1D2C' }}>
            {formatBRL(grandTotal)}
          </Text>
        </View>

        <TouchableOpacity
          style={{
            marginTop: 20,
            backgroundColor: '#EA1D2C',
            borderRadius: 16,
            paddingVertical: 16,
            alignItems: 'center',
          }}
        >
          <Text style={{ color: '#fff', fontSize: 16, fontWeight: 'bold' }}>
            Finalizar pedido · {formatBRL(grandTotal)}
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  )
}
