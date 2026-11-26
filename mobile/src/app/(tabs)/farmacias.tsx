import { useState } from 'react';
import { Linking, Pressable, TextInput, View } from 'react-native';

import { Screen } from '@/components/layout/screen';
import { Icon } from '@/components/ui/icon';
import { Button, Image, LinearGradient, Pill, PulseDot } from '@/components/ui/primitives';
import { Txt } from '@/components/ui/txt';
import { farmacias, type Farmacia } from '@/data/mock';
import { accentBorder, shadow } from '@/theme/shadows';
import { colors } from '@/theme/tokens';
import { abrirRota } from '@/utils/maps';

const MAPA_URL =
  'https://lh3.googleusercontent.com/aida/AEtjO1ULJJwzv2tpPZQ0TOKrsIwn1oa_dpomJ6wFKuu9HSALzRn5-1DrQhj322P3oDs1WQ8U3G_12st2T5OQ_ahIdvbMjuFaMTv3pC6PHTjzE7gE264rz40cM_w1pgx51T2YrpCOV-dlIWLY_bvFLi35uAX9n-dyiJC60QxiY_UCgi8UuJmeXTNvZZK_McndGVKYOR-vHsFMrnqogEabcT3gJyC-DyImXbDnsMqA6euNml_i';

const LOCAIS = [
  { id: 'gps', label: 'Localização Atual', icon: 'my_location' },
  { id: 'casa', label: 'Minha Casa', icon: 'home' },
  { id: 'trabalho', label: 'Trabalho', icon: 'business' },
];

const DOCUMENTOS = [
  { icon: 'assignment_turned_in', titulo: 'Receita médica válida (SUS ou particular)', texto: 'Emitida há no máximo 180 dias' },
  { icon: 'badge', titulo: 'Documento com foto e CPF (RG, CNH)', texto: 'Físico ou digital oficial' },
  { icon: 'credit_card', titulo: 'Cartão Nacional de Saúde (CNS)', texto: 'Disponível também no app SUS Digital' },
];

function FarmaciaCard({ f, destaque }: { f: Farmacia; destaque?: boolean }) {
  return (
    <View
      className="gap-3 overflow-hidden rounded-xl bg-surface-container-lowest p-4"
      style={[destaque ? shadow.lg : shadow.sm, accentBorder(destaque ? 0.3 : 0.22)]}>
      <View className="flex-row items-start justify-between gap-2">
        <View className="flex-1">
          <View className="flex-row flex-wrap items-center gap-2">
            <Txt v="title-md" w="bold" className="text-primary">
              {f.nome}
            </Txt>
            <Pill label={f.selo} tone={f.seloTone} />
          </View>
          <Txt v="body-sm" className="text-on-surface-variant" numberOfLines={1}>
            {f.endereco}
          </Txt>
        </View>
        <View className="items-end">
          <Txt v="title-md" className="text-primary">
            {f.distancia}
          </Txt>
          <Txt v="label-sm" w="medium" className={destaque ? 'text-secondary' : 'text-on-surface-variant'}>
            {f.tempo}
          </Txt>
        </View>
      </View>

      <View
        className={`flex-row items-center gap-2 rounded-lg px-2.5 py-1.5 ${
          f.estoque.alerta ? 'bg-error-container/40' : 'bg-surface-container-low'
        }`}>
        <Icon name={f.estoque.icone} size={18} color={f.estoque.alerta ? 'error' : 'secondary'} />
        <Txt v="label-sm" w="medium" className="flex-1 text-on-surface" numberOfLines={2}>
          {f.estoque.texto}
          {f.estoque.destaque && (
            <Txt v="label-sm" w="bold" className={f.estoque.alerta ? 'text-error' : 'text-secondary'}>
              {f.estoque.destaque}
            </Txt>
          )}
          {f.estoque.alerta ? ' no lote' : ''}
        </Txt>
      </View>

      <View className="flex-row gap-2">
        <Button label="Como Chegar" icon="directions" className="flex-1" onPress={() => abrirRota(f.endereco)} />
        <Button
          label="Ligar"
          icon="call"
          variant="surface"
          className="flex-1"
          onPress={() => Linking.openURL(`tel:${f.telefone}`)}
        />
      </View>
    </View>
  );
}

export default function Farmacias() {
  const [busca, setBusca] = useState('Losartana Potássica 50mg');
  const [local, setLocal] = useState('gps');

  return (
    <Screen>
      {/* Status de sincronização */}
      <View className="flex-row items-center justify-between rounded-xl bg-surface-container-high/80 p-3" style={shadow.sm}>
        <View className="flex-1 flex-row items-center gap-2.5">
          <View className="h-7 w-7 items-center justify-center rounded-lg bg-primary-container">
            <Icon name="verified_user" size={18} color="primary-fixed" />
          </View>
          <View className="flex-1">
            <Txt v="label-sm" className="text-primary" numberOfLines={1}>
              Programa Farmácia Popular do Brasil
            </Txt>
            <View className="flex-row items-center gap-1">
              <PulseDot />
              <Txt v="label-sm" w="medium" className="text-secondary">
                Estoque oficial sincronizado
              </Txt>
            </View>
          </View>
        </View>
        <View className="rounded-full bg-surface-container-lowest px-2 py-0.5">
          <Txt v="label-sm" w="medium" className="text-on-surface-variant">
            Hoje 10:42
          </Txt>
        </View>
      </View>

      {/* Busca + local */}
      <View className="gap-2.5">
        <View className="h-14 flex-row items-center rounded-xl bg-surface-container-lowest pl-3.5 pr-2.5" style={shadow.sm}>
          <Icon name="search" size={20} color="on-tertiary-container" />
          <TextInput
            accessibilityLabel="Buscar medicamento"
            value={busca}
            onChangeText={setBusca}
            placeholder="Buscar remédio na Farmácia Popular"
            placeholderTextColor={colors['on-surface-variant']}
            className="h-full flex-1 px-2.5 font-sans text-body-md text-primary"
          />
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Buscar por voz"
            className="h-9 w-9 items-center justify-center rounded-lg bg-surface-container active:opacity-70">
            <Icon name="mic" size={19} />
          </Pressable>
        </View>
        <View className="flex-row gap-1 rounded-xl bg-surface-container-low p-1">
          {LOCAIS.map((l) => {
            const ativo = l.id === local;
            return (
              <Pressable
                key={l.id}
                accessibilityRole="tab"
                accessibilityState={{ selected: ativo }}
                onPress={() => setLocal(l.id)}
                className={`flex-1 flex-row items-center justify-center gap-1.5 rounded-lg px-2 py-2 ${
                  ativo ? 'bg-surface-container-lowest' : ''
                }`}
                style={ativo ? shadow.sm : undefined}>
                <Icon name={l.icon} size={16} color={ativo ? 'secondary' : 'on-surface-variant'} />
                <Txt v="label-sm" className={ativo ? 'text-primary' : 'text-on-surface-variant'} numberOfLines={1}>
                  {l.label}
                </Txt>
              </Pressable>
            );
          })}
        </View>
      </View>

      {/* Mapa */}
      <View className="h-44 overflow-hidden rounded-xl bg-surface-container" style={[shadow.md, accentBorder(0.3)]}>
        <Image
          source={{ uri: MAPA_URL }}
          contentFit="cover"
          accessibilityLabel="Mapa de Brasília, Asa Sul"
          className="absolute inset-0"
        />
        <LinearGradient
          colors={['transparent', 'rgba(0, 37, 77, 0.2)', 'rgba(0, 37, 77, 0.8)']}
          className="absolute inset-0"
        />
        <View className="absolute inset-x-3 bottom-3 flex-row items-center justify-between rounded-lg bg-surface-container-lowest/90 p-2.5">
          <View className="flex-1 flex-row items-center gap-2">
            <PulseDot size={10} />
            <Txt v="label-sm" w="medium" className="flex-1 text-primary" numberOfLines={1}>
              Asa Sul • Plano Piloto
            </Txt>
          </View>
          <Txt v="label-sm" w="medium" className="text-secondary">
            3 farmácias a menos de 10 min
          </Txt>
        </View>
      </View>

      {/* Lista */}
      <View className="flex-row items-center justify-between">
        <View className="flex-1">
          <Txt v="headline-sm" className="text-primary">
            Farmácias Credenciadas
          </Txt>
          <Txt v="label-sm" w="medium" className="text-on-surface-variant">
            Farmácia Popular & SUS gratuito
          </Txt>
        </View>
        <Pill label="100% Gratuito" tone="success" upper />
      </View>
      <View className="gap-3.5">
        {farmacias.map((f, i) => (
          <FarmaciaCard key={f.id} f={f} destaque={i === 0} />
        ))}
      </View>

      {/* O que levar */}
      <View className="gap-3 rounded-xl bg-surface-container-high p-4" style={[shadow.sm, accentBorder(0.3)]}>
        <View className="flex-row items-center gap-2">
          <View className="h-8 w-8 items-center justify-center rounded-lg bg-primary">
            <Icon name="badge" size={18} color="primary-fixed" />
          </View>
          <View className="flex-1">
            <Txt v="title-md" w="bold" className="text-primary">
              O que levar para retirar de graça
            </Txt>
            <Txt v="label-sm" w="medium" className="text-on-surface-variant">
              Documentos obrigatórios na farmácia
            </Txt>
          </View>
        </View>
        {DOCUMENTOS.map((d) => (
          <View key={d.titulo} className="flex-row items-center gap-2.5 rounded-lg bg-surface-container-lowest p-2.5">
            <Icon name={d.icon} size={20} color="secondary" />
            <View className="flex-1">
              <Txt v="label-lg" className="text-primary">
                {d.titulo}
              </Txt>
              <Txt v="body-sm" className="text-on-surface-variant">
                {d.texto}
              </Txt>
            </View>
          </View>
        ))}
      </View>

      {/* Disque Saúde */}
      <View
        className="flex-row items-center justify-between rounded-xl bg-primary p-4"
        style={[shadow.lg, { borderWidth: 1, borderColor: 'rgba(167, 200, 255, 0.35)' }]}>
        <View className="flex-1 flex-row items-center gap-3">
          <View className="h-10 w-10 items-center justify-center rounded-full bg-primary-container">
            <Icon name="support_agent" size={22} color="secondary-fixed" />
          </View>
          <View className="flex-1">
            <Txt v="title-md" w="bold" className="text-on-primary">
              Disque Saúde 136
            </Txt>
            <Txt v="body-sm" className="text-primary-fixed">
              Canal oficial SUS • 24h
            </Txt>
          </View>
        </View>
        <Button label="Ligar" icon="call" variant="success" size="sm" onPress={() => Linking.openURL('tel:136')} />
      </View>
    </Screen>
  );
}
