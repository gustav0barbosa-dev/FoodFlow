import { StatusBar } from 'react-native'
import { Tabs } from 'expo-router'
import { HomeIcon, SearchIcon, ReceiptIcon, UserIcon } from 'lucide-react-native'

const TabIcon = ({ name, focused }: { name: string; focused: boolean }) => {
  const icons: Record<string, React.ComponentType<{ size?: number; strokeWidth?: number; color?: string }>> = {
    HomeIcon,
    SearchIcon,
    ReceiptIcon,
    UserIcon,
  }
  const Icon = icons[name] || HomeIcon
  return <Icon size={22} strokeWidth={focused ? 2.5 : 1.5} color={focused ? '#EA1D2C' : '#717170'} />
}

export default function TabLayout() {
  return (
    <>
      <StatusBar barStyle="auto" />
      <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: '#EA1D2C',
        tabBarInactiveTintColor: '#717170',
        tabBarStyle: {
          borderTopWidth: 1,
          borderTopColor: '#E5E7EB',
          backgroundColor: '#fff',
          paddingBottom: 12,
          height: 90,
        },
        tabBarItemStyle: {
          flex: 1,
          justifyContent: 'center',
          alignItems: 'center',
        },
        tabBarLabelStyle: {
          fontSize: 10,
          marginTop: 4,
        },
        tabBarShowLabel: true,
      }}
    >
      <Tabs.Screen
        options={{
          title: 'Início',
          tabBarIcon: ({ focused }: { focused: boolean }) => (
            <TabIcon name="HomeIcon" focused={focused} />
          ),
        }}
      />
      <Tabs.Screen
        options={{
          title: 'Buscar',
          tabBarIcon: ({ focused }: { focused: boolean }) => (
            <TabIcon name="SearchIcon" focused={focused} />
          ),
        }}
      />
      <Tabs.Screen
        options={{
          title: 'Pedidos',
          tabBarIcon: ({ focused }: { focused: boolean }) => (
            <TabIcon name="ReceiptIcon" focused={focused} />
          ),
        }}
      />
      <Tabs.Screen
        options={{
          title: 'Perfil',
          tabBarIcon: ({ focused }: { focused: boolean }) => (
            <TabIcon name="UserIcon" focused={focused} />
          ),
        }}
      />
    </Tabs>
    </>
  )
}
