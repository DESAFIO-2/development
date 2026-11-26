import { useRef, useState } from 'react';
import { KeyboardAvoidingView, Linking, Platform, Pressable, ScrollView, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { AppHeader } from '@/components/layout/app-header';
import { Icon } from '@/components/ui/icon';
import { Button, IconButton, Image, LinearGradient, Pill, PulseDot } from '@/components/ui/primitives';
import { Txt } from '@/components/ui/txt';
import { useApp } from '@/state/app-state';
import { shadow } from '@/theme/shadows';
import { colors } from '@/theme/tokens';
import { abrirRota } from '@/utils/maps';

const MAPA_FARMACIA =
  'https://lh3.googleusercontent.com/aida-public/AB6AXuBj77SEsZZN6pIDS-RRpA7nbxop_EjuIKyptgHD3a0igQpKhlRV4wGmd_M6Ta4rhh4n4CTy2XpUCXzevUcrun6Mpr7pbF1zl4p70LNJUaU3gwe2wwqY6bt2cSrItd5ytrH_wjM8PdqqNlrB_ul7d9Ndqd2bFzn9CLlVAtw2xgTdi4zJIMvLdXkDGLBBhAUScLsYLbezzekwwsQS8mx1Hdx2F-LtctYYM8vSpTRjvRU';

const SUGESTOES = [
  { icon: 'event_available', texto: 'Minha receita da Losartana vence quando?' },
  { icon: 'vaccines', texto: 'Como tomar a Insulina NPH hoje?' },
  { icon: 'calendar_month', texto: 'Agendar consulta na UBS 1 Asa Sul' },
  { icon: 'favorite', texto: 'Orientações sobre pressão alta' },
];

type Msg =
  | { id: string; de: 'zelo' | 'eu'; texto: string; hora: string; rodape?: string }
  | { id: string; de: 'zelo'; tipo: 'lembrete' | 'farmacia' | 'seguranca'; hora: string };

const INICIAIS: Msg[] = [
  { id: 'm1', de: 'zelo', hora: '11:52', texto: '' }, // saudação (montada com o nome do usuário)
  { id: 'm2', de: 'zelo', tipo: 'lembrete', hora: '11:53' },
  { id: 'm3', de: 'eu', hora: '11:54', texto: 'Zelo, onde posso pegar a Losartana da minha receita aqui perto da Asa Sul?' },
  { id: 'm4', de: 'zelo', tipo: 'farmacia', hora: '11:55' },
  {
    id: 'm5',
    de: 'eu',
    hora: '11:57',
    texto: 'Zelo, tô com uma dor muito forte no estômago e queimação. Posso tomar 2 comprimidos de Ibuprofeno 600mg junto com a Metformina pra passar logo?',
  },
  { id: 'm6', de: 'zelo', tipo: 'seguranca', hora: '11:58' },
];

function horaAgora() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

/** Respostas de demonstração até a IA real ser integrada. */
function respostaDemo(pergunta: string) {
  const p = pergunta.toLowerCase();
  if (p.includes('receita') || p.includes('vence'))
    return 'Sua receita da Losartana 50mg vale até 13/11, ou seja, vence em 7 dias. Quer que eu peça a renovação na UBS 1 da Asa Sul?';
  if (p.includes('insulina'))
    return 'Hoje sua dose de Insulina NPH é de 18 UI às 22:00. Lembre de tirar a caneta da geladeira uns minutos antes e trocar o local da aplicação. Se tiver dúvida na técnica, a enfermagem da UBS pode te ajudar.';
  if (p.includes('consulta') || p.includes('agendar'))
    return 'Você já tem consulta de Clínica Geral na quinta (14/11) às 14:20 com o Dr. Roberto Mendes. Quer que eu procure outro horário?';
  if (p.includes('pressão'))
    return 'Para ajudar a controlar a pressão: tome a Losartana todo dia no mesmo horário, diminua o sal, caminhe se o médico liberar e meça a pressão na UBS. Se sentir dor no peito ou falta de ar, ligue 192.';
  return 'Entendi! Ainda estou aprendendo e por enquanto essa é uma resposta de demonstração. Para dúvidas sobre o seu tratamento, fale com a equipe da sua UBS ou ligue no Disque Saúde 136.';
}

function AvatarZelo({ icon = 'spa', bg = 'bg-primary' }: { icon?: string; bg?: string }) {
  return (
    <View className={`mt-0.5 h-8 w-8 items-center justify-center rounded-full ${bg}`} style={shadow.sm}>
      <Icon name={icon} size={16} color="on-primary" />
    </View>
  );
}

function BolhaZelo({ children, hora, rodape = 'SUS Digital', destaque }: { children: React.ReactNode; hora: string; rodape?: string; destaque?: boolean }) {
  return (
    <View className="relative overflow-hidden rounded-2xl rounded-tl-sm bg-surface-container-lowest p-4" style={destaque ? shadow.md : shadow.sm}>
      {children}
      <Txt v="label-sm" w="medium" className="mt-2 text-right text-on-surface-variant">
        {hora} • {rodape}
      </Txt>
    </View>
  );
}

function BolhaEu({ texto, hora }: { texto: string; hora: string }) {
  return (
    <View className="ml-auto max-w-[88%] flex-row items-end gap-2">
      <View className="shrink rounded-2xl rounded-br-sm bg-primary p-3.5" style={shadow.sm}>
        <Txt v="body-md" className="text-on-primary">
          {texto}
        </Txt>
        <Txt v="label-sm" w="medium" className="mt-1 text-right text-primary-fixed-dim">
          {hora} • Enviado
        </Txt>
      </View>
      <View className="h-8 w-8 items-center justify-center rounded-full bg-primary-fixed" style={shadow.sm}>
        <Icon name="person" size={18} color="on-primary-fixed" />
      </View>
    </View>
  );
}

function Faixa({ cores }: { cores: [string, string, string] }) {
  return <LinearGradient colors={cores} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} className="absolute inset-x-0 top-0 h-1" />;
}

export default function Zelo() {
  const insets = useSafeAreaInsets();
  const { usuario, doses, registrarDose, adiarDose } = useApp();
  const [msgs, setMsgs] = useState<Msg[]>(INICIAIS);
  const [texto, setTexto] = useState('');
  const [ouvindo, setOuvindo] = useState(false);
  const [voz, setVoz] = useState(false);
  const scroll = useRef<React.ComponentRef<typeof ScrollView>>(null);

  const espacoTabBar = 64 + Math.max(insets.bottom, 12) + 8;
  const tomada = doses.metformina === 'tomada';
  const adiada = doses.metformina === 'adiada';

  function enviar(t = texto) {
    const pergunta = t.trim();
    if (!pergunta) return;
    setTexto('');
    setMsgs((m) => [...m, { id: `u${Date.now()}`, de: 'eu', texto: pergunta, hora: horaAgora() }]);
    setTimeout(() => {
      setMsgs((m) => [...m, { id: `z${Date.now()}`, de: 'zelo', texto: respostaDemo(pergunta), hora: horaAgora() }]);
      scroll.current?.scrollToEnd({ animated: true });
    }, 900);
    setTimeout(() => scroll.current?.scrollToEnd({ animated: true }), 50);
  }

  function renderMsg(m: Msg) {
    if (m.de === 'eu' && 'texto' in m) return <BolhaEu key={m.id} texto={m.texto} hora={m.hora} />;

    if ('tipo' in m && m.tipo === 'lembrete') {
      return (
        <View key={m.id} className="max-w-[96%] flex-row items-start gap-2.5">
          <AvatarZelo icon="alarm" bg="bg-primary-container" />
          <View className="flex-1 overflow-hidden rounded-2xl rounded-tl-sm bg-surface-container-lowest p-4" style={shadow.md}>
            <Faixa cores={[colors.primary, colors['primary-container'], colors.secondary]} />
            <View className="mb-2 flex-row items-center justify-between pt-1">
              <View className="flex-row items-center gap-1.5">
                <Icon name="pill" size={18} color="secondary" />
                <Txt v="label-sm" upper className="text-secondary">
                  Lembrete de remédio
                </Txt>
              </View>
              <Pill label={tomada ? 'Tomado' : 'Em 38 min'} tone="success" />
            </View>
            <Txt v="title-md" className="text-primary">
              Metformina 850mg
            </Txt>
            <Txt v="body-sm" className="text-on-surface-variant">
              Horário: <Txt v="body-sm" w="semibold">12:30</Txt> (após o almoço, com um copo cheio de água).
            </Txt>
            <Txt v="body-sm" className="text-on-surface-variant">
              Quer que eu marque como tomado ou prefere adiar o aviso?
            </Txt>
            {tomada ? (
              <View className="mt-3 flex-row items-center gap-1.5 rounded-lg bg-secondary-container/50 p-2">
                <Icon name="task_alt" size={16} color="on-secondary-container" />
                <Txt v="label-sm" className="text-on-secondary-container">
                  Registrado no seu Diário SUS!
                </Txt>
              </View>
            ) : (
              <View className="mt-3 flex-row gap-2">
                <Button
                  label="Já tomei"
                  icon="check_circle"
                  variant="success"
                  className="flex-1 rounded-xl"
                  onPress={() => registrarDose('metformina', 'Metformina 850mg')}
                />
                <Button
                  label={adiada ? 'Adiado' : 'Adiar 15 min'}
                  icon="snooze"
                  variant="surface"
                  className="flex-1 rounded-xl"
                  disabled={adiada}
                  onPress={() => adiarDose('metformina')}
                />
              </View>
            )}
          </View>
        </View>
      );
    }

    if ('tipo' in m && m.tipo === 'farmacia') {
      return (
        <View key={m.id} className="max-w-[96%] flex-row items-start gap-2.5">
          <AvatarZelo />
          <View className="flex-1">
            <BolhaZelo hora={m.hora} rodape="Estoque verificado">
              <Txt v="body-md" className="text-on-surface">
                Encontrei <Txt v="body-md" w="semibold" className="text-primary">3 farmácias credenciadas</Txt> pelo{' '}
                <Txt v="body-md" w="semibold" className="text-secondary">Farmácia Popular</Txt> bem pertinho de você!
              </Txt>
              <Txt v="body-md" className="mt-1.5 text-on-surface">
                A mais próxima com estoque é a <Txt v="body-md" w="semibold">Drogaria São Paulo</Txt>, na CLS 106. Seu
                remédio sai 100% gratuito com a receita e o Cartão SUS.
              </Txt>
              <View className="mt-3 gap-2.5 rounded-xl bg-surface-container-low p-3">
                <View className="flex-row items-start justify-between gap-2">
                  <View className="flex-1 flex-row items-start gap-2">
                    <View className="h-9 w-9 items-center justify-center rounded-lg bg-surface-container-highest">
                      <Icon name="store" size={20} />
                    </View>
                    <View className="flex-1">
                      <Txt v="title-md" className="text-primary" numberOfLines={1}>
                        Drogaria São Paulo
                      </Txt>
                      <Txt v="body-sm" className="text-on-surface-variant" numberOfLines={1}>
                        CLS 106 Bloco A Loja 12 • Asa Sul
                      </Txt>
                    </View>
                  </View>
                  <Pill label="180m" className="bg-surface-container-highest" />
                </View>
                <View className="h-24 justify-end overflow-hidden rounded-lg bg-surface-container p-2">
                  <Image source={{ uri: MAPA_FARMACIA }} contentFit="cover" className="absolute inset-0" />
                  <LinearGradient
                    colors={['transparent', 'rgba(0, 37, 77, 0.2)', 'rgba(0, 37, 77, 0.8)']}
                    className="absolute inset-0"
                  />
                  <View className="flex-row items-center justify-between">
                    <View className="flex-row items-center gap-1">
                      <Icon name="navigation" size={14} color="on-primary" />
                      <Txt v="label-sm" className="text-on-primary">
                        3 min a pé
                      </Txt>
                    </View>
                    <View className="rounded-full bg-secondary px-2 py-0.5">
                      <Txt v="label-sm" className="text-on-secondary">
                        Aberto até 22:00
                      </Txt>
                    </View>
                  </View>
                </View>
                <View className="flex-row gap-2">
                  <Button
                    label="Ver rota no mapa"
                    icon="directions"
                    size="sm"
                    className="flex-1"
                    onPress={() => abrirRota('CLS 106 Bloco A Asa Sul')}
                  />
                  <IconButton icon="share" label="Compartilhar" size={36} iconSize={16} className="rounded-lg bg-surface-container" />
                </View>
              </View>
            </BolhaZelo>
          </View>
        </View>
      );
    }

    if ('tipo' in m && m.tipo === 'seguranca') {
      return (
        <View key={m.id} className="max-w-[96%] flex-row items-start gap-2.5">
          <AvatarZelo />
          <View className="flex-1 overflow-hidden rounded-2xl rounded-tl-sm bg-surface-container-lowest p-4" style={shadow.md}>
            <Faixa cores={[colors['on-tertiary-container'], colors.primary, colors.secondary]} />
            <View className="mb-2.5 flex-row items-center justify-between gap-2 pt-1">
              <View className="flex-1 flex-row items-center gap-1.5">
                <Icon name="warning" size={18} color="error" />
                <Txt v="label-sm" upper className="flex-1 text-error">
                  Alerta de segurança
                </Txt>
              </View>
              <Pill label="Cuidado" className="bg-error-container" />
            </View>
            <Txt v="body-md" className="text-on-surface">
              <Txt v="body-md" w="semibold" className="text-primary">{usuario?.nome}</Txt>, por favor{' '}
              <Txt v="body-md" w="semibold" className="text-error">não tome essa dose por conta própria!</Txt>
            </Txt>
            <Txt v="body-md" className="mt-2 text-on-surface">
              Eu sou uma assistente virtual e <Txt v="body-md" w="semibold" className="text-primary">não sou médica</Txt>.
              Não posso orientar mudança de dose nem automedicação, ainda mais misturando anti-inflamatório forte com
              seus remédios de uso contínuo, o que pode piorar a dor no estômago.
            </Txt>
            <Txt v="body-md" className="mt-2 text-on-surface">
              Para sua segurança, procure o posto de saúde mais próximo agora:
            </Txt>
            <View className="mt-3 gap-2.5 rounded-xl border border-primary-fixed-dim/60 bg-surface-container-low p-3">
              <View className="flex-row items-start justify-between gap-2">
                <View className="flex-1 flex-row items-start gap-2">
                  <View className="h-9 w-9 items-center justify-center rounded-lg bg-surface-container-highest">
                    <Icon name="local_hospital" size={20} />
                  </View>
                  <View className="flex-1">
                    <Txt v="title-md" className="text-primary">
                      UBS 1 da Asa Sul
                    </Txt>
                    <Txt v="body-sm" className="text-on-surface-variant">
                      Sua unidade de referência
                    </Txt>
                    <Txt v="label-sm" w="medium" className="text-on-surface-variant">
                      SGAS 612 • Aberto até 18:00
                    </Txt>
                  </View>
                </View>
                <Pill label="Aberto" tone="success" />
              </View>
              <View className="flex-row gap-2">
                <Button label="Como chegar" icon="near_me" size="sm" className="flex-1" onPress={() => abrirRota('SGAS 612 Asa Sul UBS 1')} />
                <Button label="Ligar" icon="call" size="sm" variant="surface" onPress={() => Linking.openURL('tel:6133461234')} />
              </View>
              <Pressable onPress={() => Linking.openURL('tel:192')} className="flex-row items-center gap-1 px-1">
                <Icon name="emergency" size={14} color="error" />
                <Txt v="label-sm" w="medium" className="text-error">
                  Se a dor for muito forte, ligue 192 (SAMU).
                </Txt>
              </Pressable>
            </View>
            <Txt v="label-sm" w="medium" className="mt-2 text-right text-on-surface-variant">
              {m.hora} • Protocolo de segurança
            </Txt>
          </View>
        </View>
      );
    }

    if ('texto' in m) {
      const saudacao = m.id === 'm1';
      return (
        <View key={m.id} className="max-w-[94%] flex-row items-start gap-2.5">
          <AvatarZelo />
          <View className="flex-1">
            <BolhaZelo hora={m.hora}>
              {saudacao ? (
                <Txt v="body-md" className="text-on-surface">
                  Olá, <Txt v="body-md" w="semibold" className="text-primary">{usuario?.nome}</Txt>! Sou a{' '}
                  <Txt v="body-md" w="semibold" className="text-primary">Zelo</Txt>, sua companheira de saúde. Como
                  posso te ajudar hoje com seus remédios, receitas ou consultas na{' '}
                  <Txt v="body-md" w="semibold" className="text-primary">{usuario?.ubs}</Txt>?
                </Txt>
              ) : (
                <Txt v="body-md" className="text-on-surface">
                  {m.texto}
                </Txt>
              )}
            </BolhaZelo>
          </View>
        </View>
      );
    }
    return null;
  }

  return (
    <View className="flex-1 bg-canvas">
      <AppHeader />
      <KeyboardAvoidingView className="flex-1" behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView
          ref={scroll}
          className="flex-1"
          contentContainerClassName="gap-4 px-4 pt-3"
          contentContainerStyle={{ paddingBottom: 16 }}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}>
          {/* Barra de emergência */}
          <View className="flex-row items-center justify-between gap-2 rounded-xl bg-surface-container-low px-3 py-2" style={shadow.sm}>
            <View className="flex-1 flex-row items-center gap-1.5">
              <Icon name="health_and_safety" size={18} />
              <Txt v="label-sm" upper className="flex-1 text-primary" numberOfLines={1}>
                Apoio imediato
              </Txt>
            </View>
            <Pressable
              onPress={() => Linking.openURL('tel:136')}
              className="flex-row items-center gap-1 rounded-full bg-surface-container-highest px-2.5 py-1 active:opacity-70">
              <Icon name="phone_in_talk" size={14} />
              <Txt v="label-sm" className="text-primary">
                Disque 136
              </Txt>
            </Pressable>
            <Pressable
              onPress={() => Linking.openURL('tel:192')}
              className="flex-row items-center gap-1 rounded-full bg-error-container px-2.5 py-1 active:opacity-70">
              <Icon name="ambulance" size={14} color="on-error-container" />
              <Txt v="label-sm" className="text-on-error-container">
                192 SAMU
              </Txt>
            </Pressable>
          </View>

          {/* Cartão da Zelo */}
          <View className="overflow-hidden rounded-2xl bg-surface-container-lowest p-4" style={shadow.md}>
            <View className="flex-row items-center justify-between gap-3">
              <View className="flex-1 flex-row items-center gap-3">
                <View className="h-12 w-12 items-center justify-center rounded-full bg-primary-container" style={{ borderWidth: 3, borderColor: 'rgba(167, 200, 255, 0.6)' }}>
                  <Icon name="spa" size={26} color="on-primary" />
                  <View className="absolute -bottom-0.5 -right-0.5 h-3.5 w-3.5 rounded-full border-2 border-surface-container-lowest bg-secondary" />
                </View>
                <View className="flex-1">
                  <View className="flex-row items-center gap-1.5">
                    <Txt v="title-md" className="text-primary">
                      Zelo
                    </Txt>
                    <Pill label="SUS DF" className="bg-primary/10" />
                  </View>
                  <Txt v="body-sm" className="text-on-surface-variant" numberOfLines={1}>
                    Assistente de saúde
                  </Txt>
                  <View className="flex-row items-center gap-1">
                    <PulseDot />
                    <Txt v="label-sm" w="medium" className="text-secondary">
                      Disponível 24h
                    </Txt>
                  </View>
                </View>
              </View>
              <IconButton
                icon={voz ? 'graphic_eq' : 'volume_up'}
                label="Ouvir respostas em voz alta"
                color={voz ? 'on-secondary-container' : 'primary'}
                className={voz ? 'bg-secondary-container' : 'bg-surface-container'}
                onPress={() => setVoz((v) => !v)}
              />
            </View>
            <View className="mt-3 flex-row items-center justify-between rounded-xl bg-surface-container-low/70 px-3 py-2">
              <View className="flex-1 flex-row items-center gap-2">
                <Icon name="graphic_eq" size={16} color="secondary" />
                <Txt v="label-sm" w="medium" className="flex-1 text-on-surface-variant">
                  Pronta para ouvir seu áudio ou ler sua receita
                </Txt>
              </View>
            </View>
          </View>

          {msgs.map(renderMsg)}

          {/* Sugestões */}
          <View className="gap-1.5 pt-1">
            <Txt v="label-sm" upper className="px-1 text-on-surface-variant">
              Perguntas rápidas
            </Txt>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerClassName="gap-2 py-1">
              {SUGESTOES.map((s) => (
                <Pressable
                  key={s.texto}
                  onPress={() => enviar(s.texto)}
                  className="flex-row items-center gap-1.5 rounded-full bg-surface-container-lowest px-3.5 py-2 active:bg-surface-container-high"
                  style={shadow.sm}>
                  <Icon name={s.icon} size={16} color="secondary" />
                  <Txt v="label-md" className="text-primary">
                    {s.texto}
                  </Txt>
                </Pressable>
              ))}
            </ScrollView>
          </View>
        </ScrollView>

        {/* Barra de texto e voz */}
        <View className="px-4 pb-2 pt-1" style={{ marginBottom: espacoTabBar }}>
          <View className="gap-2 rounded-2xl bg-surface-container-lowest p-2.5" style={shadow.lg}>
            {ouvindo && (
              <View className="flex-row items-center justify-between rounded-xl bg-primary-container p-3">
                <View className="flex-1 flex-row items-center gap-2.5">
                  <PulseDot color="bg-error" size={12} />
                  <Txt v="body-sm" className="text-on-primary">
                    Ouvindo você... fale naturalmente
                  </Txt>
                </View>
                <Pressable onPress={() => setOuvindo(false)} hitSlop={8}>
                  <Txt v="label-sm" className="text-on-primary underline">
                    Cancelar
                  </Txt>
                </Pressable>
              </View>
            )}
            <View className="flex-row items-center gap-2">
              <IconButton icon="document_scanner" label="Enviar foto de receita ou exame" />
              <TextInput
                value={texto}
                onChangeText={setTexto}
                onSubmitEditing={() => enviar()}
                returnKeyType="send"
                accessibilityLabel="Escreva sua dúvida"
                placeholder="Escreva sua dúvida..."
                placeholderTextColor={colors['on-surface-variant']}
                className="h-11 flex-1 rounded-xl bg-surface-container-low px-3.5 font-sans text-body-md text-on-surface"
              />
              <IconButton
                icon="mic"
                label="Falar com a Zelo"
                size={44}
                iconSize={22}
                color="on-primary"
                className="rounded-xl bg-primary"
                onPress={() => setOuvindo((o) => !o)}
              />
              <IconButton
                icon="send"
                label="Enviar mensagem"
                size={44}
                color="on-secondary"
                className="rounded-xl bg-secondary"
                onPress={() => enviar()}
              />
            </View>
            <View className="flex-row items-center gap-1 px-1">
              <Icon name="verified_user" size={13} color="secondary" />
              <Txt v="label-sm" w="medium" className="text-on-surface-variant">
                Conversa protegida pela LGPD
              </Txt>
            </View>
          </View>
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}
