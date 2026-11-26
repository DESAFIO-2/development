import * as Haptics from 'expo-haptics';
import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import { Platform, View } from 'react-native';
import Animated, { FadeInDown, FadeOutDown } from 'react-native-reanimated';

import { Icon } from '@/components/ui/icon';
import { Txt } from '@/components/ui/txt';
import { usuario as usuarioMock } from '@/data/mock';
import { shadow } from '@/theme/shadows';

type Usuario = typeof usuarioMock;
type DoseState = 'tomada' | 'adiada' | undefined;

type AppState = {
  usuario: Usuario | null;
  entrar: (cpf: string, senha: string) => boolean;
  cadastrar: (dados: Partial<Usuario>) => void;
  sair: () => void;
  doses: Record<string, DoseState>;
  horaTomada: Record<string, string>;
  registrarDose: (medId: string, nome?: string) => void;
  adiarDose: (medId: string) => void;
  toast: (mensagem: string, icone?: string) => void;
};

const Ctx = createContext<AppState | null>(null);

function agora() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function vibrar() {
  if (Platform.OS !== 'web') Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
}

export function AppStateProvider({ children }: { children: React.ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  // A Losartana já vem tomada às 08:05, como na tela de referência.
  const [doses, setDoses] = useState<Record<string, DoseState>>({ losartana: 'tomada' });
  const [horaTomada, setHoraTomada] = useState<Record<string, string>>({ losartana: '08:05' });
  const [toastMsg, setToastMsg] = useState<{ id: number; texto: string; icone: string } | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const toast = useCallback((texto: string, icone = 'check_circle') => {
    if (timer.current) clearTimeout(timer.current);
    setToastMsg({ id: Date.now(), texto, icone });
    timer.current = setTimeout(() => setToastMsg(null), 2800);
  }, []);

  const value = useMemo<AppState>(
    () => ({
      usuario,
      // Login fictício: qualquer CPF com 11 dígitos e senha com 4+ caracteres.
      entrar: (cpf, senha) => {
        if (cpf.replace(/\D/g, '').length !== 11 || senha.length < 4) return false;
        setUsuario(usuarioMock);
        return true;
      },
      cadastrar: (dados) => {
        const nomeCompleto = dados.nomeCompleto?.trim() || usuarioMock.nomeCompleto;
        setUsuario({
          ...usuarioMock,
          ...dados,
          nomeCompleto,
          nome: nomeCompleto.split(' ').slice(0, 2).join(' '),
        });
      },
      sair: () => setUsuario(null),
      doses,
      horaTomada,
      registrarDose: (medId, nome) => {
        setDoses((d) => ({ ...d, [medId]: 'tomada' }));
        setHoraTomada((h) => ({ ...h, [medId]: agora() }));
        vibrar();
        toast(`Dose de ${nome ?? medId} registrada no seu prontuário.`);
      },
      adiarDose: (medId) => {
        setDoses((d) => ({ ...d, [medId]: 'adiada' }));
        toast('Lembrete adiado por 15 minutos.', 'snooze');
      },
      toast,
    }),
    [usuario, doses, horaTomada, toast],
  );

  return (
    <Ctx.Provider value={value}>
      {children}
      {toastMsg && (
        <Animated.View
          key={toastMsg.id}
          entering={FadeInDown}
          exiting={FadeOutDown}
          pointerEvents="none"
          className="absolute inset-x-6 bottom-28 items-center">
          <View
            className="flex-row items-center gap-2 rounded-full bg-inverse-surface px-4 py-2.5"
            style={shadow.xl}>
            <Icon name={toastMsg.icone} size={18} color="secondary-fixed" />
            <Txt v="label-md" className="shrink text-inverse-on-surface">
              {toastMsg.texto}
            </Txt>
          </View>
        </Animated.View>
      )}
    </Ctx.Provider>
  );
}

export function useApp() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useApp precisa estar dentro de <AppStateProvider>');
  return ctx;
}
