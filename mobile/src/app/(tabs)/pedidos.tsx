import React from 'react'
import { View, Text, TouchableOpacity, ScrollView } from 'react-native'
import { Link } from 'expo-router'
import { Receipt } from 'lucide-react-native'
import { useColorScheme } from 'react-native'
import { formatBRL } from '@/lib/format'
import { useOrdersStore } from '@/store/ordersStore'

export default function Pedidos() {
  const colorScheme = useColorScheme()
  const isDark = colorScheme === 'dark'
  const orders = useOrdersStore((s: any) => s.orders)

  return (
    <View style={{ flex: 1, backgroundColor: isDark ? '#1a1a1a' : '#F7F7F7' }}>
      <View style={{ padding: 16, paddingTop: 50 }}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <Text style={{ fontSize: 20, fontWeight: 'bold', color: '#3F3E3E' }}>Pedidos</Text>
        </View>

        {orders.length === 0 ? (
          <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 32 }}>
            <Receipt size={64} color='#EA1D2C' style={{ marginBottom: 16 }} />
            <Text style={{ fontSize: 16, fontWeight: '600', color: '#3F3E3E' }}>Nenhum pedido ainda</Text>
            <Text style={{ fontSize: 12, color: '#717171', marginTop: 4, textAlign: 'center' }}>Faça seu primeiro pedido e acompanhe aqui.</Text>
          </View>
        ) : (
          <ScrollView>
            {orders.map((order: any) => (
              <View key={order.id} style={{ backgroundColor: '#fff', borderRadius: 16, marginBottom: 12, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1, shadowRadius: 8, elevation: 4 }}>
                <View style={{ padding: 16, borderBottomWidth: 1, borderBottomColor: '#E5E7EB', flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                  <View>
                    <Text style={{ fontSize: 16, fontWeight: '600', color: '#3F3E3E' }}>{order.restaurantNames[0]}</Text>
                    <Text style={{ fontSize: 12, color: '#717171' }}>{order.itemCount} itens</Text>
                  </View>
                  <View style={{ flexDirection: 'row', gap: 6 }}>
                    <Text style={{ fontSize: 12, fontWeight: '600', color: order.status === 'Entregue' ? '#22C55E' : '#EA1D2C' }}>{order.status}</Text>
                  </View>
                </View>
                <View style={{ padding: 16 }}>
                  {order.items.map((item: any) => (
                    <View key={item.id} style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 }}>
                      <Text style={{ fontSize: 14, color: '#3F3E3E' }}>{item.quantity}x {item.name}</Text>
                      <Text style={{ fontSize: 14, color: '#3F3E3E', fontWeight: '600' }}>{formatBRL(item.price * item.quantity)}</Text>
                    </View>
                  ))}
                  <View style={{ flexDirection: 'row', justifyContent: 'space-between', borderTopWidth: 1, borderTopColor: '#E5E7EB', paddingTop: 8, marginTop: 8 }}>
                    <Text style={{ fontSize: 14, color: '#717171' }}>Total</Text>
                    <Text style={{ fontSize: 16, fontWeight: 'bold', color: '#EA1D2C' }}>{formatBRL(order.total)}</Text>
                  </View>
                </View>
              </View>
            ))}
          </ScrollView>
        )}
      </View>
    </View>
  )
}
