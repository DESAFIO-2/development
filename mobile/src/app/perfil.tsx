import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, Switch, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { BackHeader } from '@/components/layout/app-header';
import { Icon } from '@/components/ui/icon';
import { Button, Card, LinearGradient } from '@/components/ui/primitives';
import { Txt } from '@/components/ui/txt';
import { useApp } from '@/state/app-state';
import { shadow } from '@/theme/shadows';
import { colors } from '@/theme/tokens';

function Linha({ icon, label, valor }: { icon: string; label: string; valor?: string }) {
  return (
    <View className="flex-row items-center gap-3 py-2.5">
      <Icon name={icon} size={20} color="on-surface-variant" />
      <View className="flex-1">
        <Txt v="label-sm" w="medium" className="text-on-surface-variant">
          {label}
        </Txt>
        <Txt v="body-md" className="text-primary">
          {valor || '—'}
        </Txt>
      </View>
    </View>
  );
}

function Preferencia({ icon, label, value, onChange }: { icon: string; label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <View className="flex-row items-center gap-3 py-2">
      <Icon name={icon} size={20} />
      <Txt v="label-lg" className="flex-1 text-on-surface">
        {label}
      </Txt>
      <Switch
        value={value}
        onValueChange={onChange}
        accessibilityLabel={label}
        trackColor={{ false: colors['surface-container-highest'], true: colors.primary }}
        thumbColor={colors['surface-container-lowest']}
      />
    </View>
  );
}

export default function Perfil() {
  const insets = useSafeAreaInsets();
  const { usuario, sair } = useApp();
  const [prefs, setPrefs] = useState({ alarmes: true, pulseira: true, textoGrande: false, voz: true });
  const toggle = (k: keyof typeof prefs) => (v: boolean) => setPrefs((p) => ({ ...p, [k]: v }));

  return (
    <View className="flex-1 bg-canvas">
      <BackHeader title="Meu Perfil" />
      <ScrollView contentContainerClassName="gap-4 px-4 pt-4" contentContainerStyle={{ paddingBottom: insets.bottom + 24 }}>
        <LinearGradient
          colors={[colors.primary, colors['primary-container'], colors.primary]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          className="flex-row items-center gap-4 overflow-hidden rounded-2xl p-5"
          style={shadow.xl}>
          <View className="h-16 w-16 items-center justify-center rounded-full bg-primary-fixed">
            <Txt v="headline-md" className="text-primary">
              {usuario?.nome.charAt(0)}
            </Txt>
          </View>
          <View className="flex-1">
            <Txt v="title-lg" className="text-on-primary">
              {usuario?.nomeCompleto}
            </Txt>
            <Txt v="body-sm" className="text-primary-fixed">
              CNS {usuario?.cns}
            </Txt>
            <View className="mt-1 flex-row items-center gap-1">
              <Icon name="location_on" size={14} color="secondary-fixed" />
              <Txt v="label-sm" className="text-surface-bright">
                {usuario?.ubs}
              </Txt>
            </View>
          </View>
        </LinearGradient>

        <Card className="px-4 py-2">
          <Linha icon="badge" label="CPF" valor={usuario?.cpf} />
          <Linha icon="cake" label="Data de nascimento" valor={usuario?.nascimento} />
          <Linha icon="smartphone" label="Celular" valor={usuario?.celular} />
          <Linha icon="mail" label="E-mail" valor={usuario?.email} />
        </Card>

        <Card className="px-4 py-2">
          <Txt v="label-md" upper className="pt-2 text-on-surface-variant">
            Preferências
          </Txt>
          <Preferencia icon="volume_up" label="Alarme sonoro dos remédios" value={prefs.alarmes} onChange={toggle('alarmes')} />
          <Preferencia icon="watch" label="Alertas na pulseira" value={prefs.pulseira} onChange={toggle('pulseira')} />
          <Preferencia icon="record_voice_over" label="Zelo responde por voz" value={prefs.voz} onChange={toggle('voz')} />
          <Preferencia icon="text_increase" label="Letras maiores" value={prefs.textoGrande} onChange={toggle('textoGrande')} />
        </Card>

        <Pressable
          onPress={() => router.push('/alerta-pulseira')}
          className="flex-row items-center gap-3 rounded-xl bg-surface-container p-4 active:opacity-80">
          <Icon name="watch" size={22} />
          <Txt v="label-lg" className="flex-1 text-primary">
            Configurar pulseira ou relógio
          </Txt>
          <Icon name="chevron_right" size={22} color="on-surface-variant" />
        </Pressable>

        <Button label="Sair da conta" icon="logout" variant="white" iconColor="error" style={shadow.sm} onPress={sair} />
        <Txt v="label-sm" w="medium" className="text-center text-on-surface-variant">
          SUS Digital • versão 1.0.0
        </Txt>
      </ScrollView>
    </View>
  );
}
