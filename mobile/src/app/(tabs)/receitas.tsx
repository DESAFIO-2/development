import { useState } from 'react';
import { Modal, Pressable, View } from 'react-native';

import { Screen } from '@/components/layout/screen';
import { Icon } from '@/components/ui/icon';
import { Button, Card, LinearGradient, Pill } from '@/components/ui/primitives';
import { Txt } from '@/components/ui/txt';
import { receitas, type Receita } from '@/data/mock';
import { useApp } from '@/state/app-state';
import { accentBorder, shadow } from '@/theme/shadows';
import { colors } from '@/theme/tokens';

type Filtro = 'ativas' | 'vencendo' | 'historico';

const STATUS = {
  ativa: { label: 'Válida', tone: 'success' as const, barra: 'bg-secondary' },
  vencendo: { label: 'Vence em breve', tone: 'warning' as const, barra: 'bg-on-tertiary-container' },
  vencida: { label: 'Vencida', tone: 'neutral' as const, barra: 'bg-outline' },
};

/** Desenho de QR code ilustrativo (o código real virá do backend). */
function QrIlustrativo({ seed }: { seed: string }) {
  const n = 21;
  let h = 0;
  for (const c of seed) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  const cells: boolean[] = [];
  for (let i = 0; i < n * n; i++) {
    h = (h * 1103515245 + 12345) >>> 0;
    cells.push(((h >> 16) & 1) === 1);
  }
  const finder = (r: number, c: number) => {
    const inBox = (r0: number, c0: number) => r >= r0 && r < r0 + 7 && c >= c0 && c < c0 + 7;
    const box = inBox(0, 0) ? [0, 0] : inBox(0, n - 7) ? [0, n - 7] : inBox(n - 7, 0) ? [n - 7, 0] : null;
    if (!box) return null;
    const rr = r - box[0];
    const cc = c - box[1];
    return rr === 0 || rr === 6 || cc === 0 || cc === 6 || (rr >= 2 && rr <= 4 && cc >= 2 && cc <= 4);
  };
  return (
    <View className="rounded-xl bg-surface-container-lowest p-3" style={{ width: 21 * 9 + 24 }}>
      {Array.from({ length: n }).map((_, r) => (
        <View key={r} className="flex-row">
          {Array.from({ length: n }).map((__, c) => {
            const f = finder(r, c);
            const on = f ?? cells[r * n + c];
            return <View key={c} style={{ width: 9, height: 9, backgroundColor: on ? colors.primary : 'transparent' }} />;
          })}
        </View>
      ))}
    </View>
  );
}

function ReceitaCard({ r, onMostrar, onRenovar }: { r: Receita; onMostrar: () => void; onRenovar: () => void }) {
  const st = STATUS[r.status];
  const pct = Math.max(0, Math.min(1, r.diasRestantes / r.diasTotais));
  const vencida = r.status === 'vencida';
  return (
    <View
      className={`gap-3 overflow-hidden rounded-xl bg-surface-container-lowest p-4 ${vencida ? 'opacity-70' : ''}`}
      style={[r.status === 'vencendo' ? shadow.lg : shadow.sm, accentBorder(r.status === 'vencendo' ? 0.3 : 0.2)]}>
      {r.status === 'vencendo' && (
        <LinearGradient
          colors={[colors.tertiary, colors['tertiary-fixed-dim'], colors.tertiary]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 0 }}
          className="absolute inset-x-0 top-0 h-1"
        />
      )}
      <View className="flex-row items-start justify-between gap-2">
        <View className="flex-1 flex-row items-start gap-3">
          <View className="h-11 w-11 items-center justify-center rounded-xl bg-surface-container-high">
            <Icon name="prescriptions" size={22} />
          </View>
          <View className="flex-1">
            <Txt v="title-md" className="text-primary">
              {r.medicamento}
            </Txt>
            <Txt v="body-sm" className="text-on-surface-variant">
              {r.posologia}
            </Txt>
          </View>
        </View>
        <Pill label={st.label} tone={st.tone} upper />
      </View>

      <View className="flex-row items-center gap-2 rounded-lg bg-surface-container-low px-3 py-2">
        <Icon name="stethoscope" size={16} color="secondary" />
        <Txt v="label-sm" w="medium" className="flex-1 text-on-surface" numberOfLines={1}>
          {r.medico} • {r.crm}
        </Txt>
        <Txt v="label-sm" w="medium" className="text-on-surface-variant">
          {r.tipo}
        </Txt>
      </View>

      <View className="gap-1.5">
        <View className="flex-row items-center justify-between">
          <Txt v="label-sm" w="medium" className="text-on-surface-variant">
            Emitida {r.emitida}
          </Txt>
          <Txt
            v="label-sm"
            className={r.status === 'vencendo' ? 'text-on-tertiary-container' : vencida ? 'text-on-surface-variant' : 'text-secondary'}>
            {vencida ? `Venceu em ${r.validade}` : `Válida até ${r.validade} • ${r.diasRestantes} dias`}
          </Txt>
        </View>
        <View className="h-1.5 w-full overflow-hidden rounded-full bg-surface-container-highest">
          <View className={`h-1.5 rounded-full ${st.barra}`} style={{ width: `${pct * 100}%` }} />
        </View>
      </View>

      {!vencida && (
        <View className="flex-row gap-2">
          <Button label="Mostrar na farmácia" icon="qr_code" className="flex-1" onPress={onMostrar} />
          {r.status === 'vencendo' && (
            <Button label="Renovar" icon="sync_saved_loc" variant="surface" onPress={onRenovar} />
          )}
        </View>
      )}
    </View>
  );
}

export default function Receitas() {
  const { toast } = useApp();
  const [filtro, setFiltro] = useState<Filtro>('ativas');
  const [aberta, setAberta] = useState<Receita | null>(null);

  const lista = receitas.filter((r) =>
    filtro === 'ativas' ? r.status !== 'vencida' : filtro === 'vencendo' ? r.status === 'vencendo' : r.status === 'vencida',
  );
  const qtd = {
    ativas: receitas.filter((r) => r.status !== 'vencida').length,
    vencendo: receitas.filter((r) => r.status === 'vencendo').length,
    historico: receitas.filter((r) => r.status === 'vencida').length,
  };

  const FILTROS: { id: Filtro; label: string }[] = [
    { id: 'ativas', label: `Válidas (${qtd.ativas})` },
    { id: 'vencendo', label: `Vencendo (${qtd.vencendo})` },
    { id: 'historico', label: `Histórico (${qtd.historico})` },
  ];

  return (
    <Screen>
      {/* Título */}
      <View className="gap-2">
        <Pill label="Receitas digitais • SUS" upper className="bg-surface-container-high" />
        <Txt v="headline-lg-mobile" className="text-primary">
          Minhas Receitas
        </Txt>
        <Txt v="body-sm" className="text-on-surface-variant">
          Todas as suas receitas em um só lugar. Mostre o código na farmácia para retirar seu remédio de graça.
        </Txt>
      </View>

      {/* Resumo */}
      <View className="flex-row gap-2.5">
        <Card className="flex-1 gap-1 p-3">
          <View className="flex-row items-center justify-between">
            <Icon name="task_alt" size={18} color="secondary" />
            <Txt v="headline-sm" className="text-primary">
              {String(qtd.ativas).padStart(2, '0')}
            </Txt>
          </View>
          <Txt v="label-sm" w="medium" className="text-on-surface-variant">
            Receitas válidas
          </Txt>
        </Card>
        <View className="flex-1 gap-1 rounded-xl bg-tertiary-fixed/50 p-3" style={shadow.sm}>
          <View className="flex-row items-center justify-between">
            <Icon name="schedule" size={18} color="on-tertiary-container" />
            <Txt v="headline-sm" className="text-on-tertiary-container">
              {String(qtd.vencendo).padStart(2, '0')}
            </Txt>
          </View>
          <Txt v="label-sm" w="medium" className="text-tertiary-container">
            Vencem em 7 dias
          </Txt>
        </View>
        <Card className="flex-1 gap-1 p-3">
          <View className="flex-row items-center justify-between">
            <Icon name="history" size={18} color="on-surface-variant" />
            <Txt v="headline-sm" className="text-primary">
              {String(qtd.historico).padStart(2, '0')}
            </Txt>
          </View>
          <Txt v="label-sm" w="medium" className="text-on-surface-variant">
            No histórico
          </Txt>
        </Card>
      </View>

      {/* Adicionar */}
      <Pressable
        accessibilityRole="button"
        onPress={() => toast('Aponte a câmera para a receita em papel para digitalizar.', 'document_scanner')}
        className="flex-row items-center gap-3 rounded-xl border-2 border-dashed border-primary-fixed-dim bg-surface-container-low p-4 active:opacity-80">
        <View className="h-11 w-11 items-center justify-center rounded-xl bg-primary">
          <Icon name="document_scanner" size={22} color="tertiary-fixed" />
        </View>
        <View className="flex-1">
          <Txt v="title-md" className="text-primary">
            Adicionar receita em papel
          </Txt>
          <Txt v="body-sm" className="text-on-surface-variant">
            Tire uma foto e a gente organiza pra você
          </Txt>
        </View>
        <Icon name="photo_camera" size={22} />
      </Pressable>

      {/* Filtros */}
      <View className="flex-row flex-wrap gap-2">
        {FILTROS.map((f) => {
          const ativo = filtro === f.id;
          return (
            <Pressable
              key={f.id}
              accessibilityRole="tab"
              accessibilityState={{ selected: ativo }}
              onPress={() => setFiltro(f.id)}
              className={`rounded-full px-4 py-2 ${ativo ? 'bg-primary' : 'bg-surface-container-high'}`}>
              <Txt v="label-md" className={ativo ? 'text-on-primary' : 'text-on-surface-variant'}>
                {f.label}
              </Txt>
            </Pressable>
          );
        })}
      </View>

      <View className="gap-3.5">
        {lista.map((r) => (
          <ReceitaCard
            key={r.id}
            r={r}
            onMostrar={() => setAberta(r)}
            onRenovar={() => toast('Pedido de renovação enviado para a UBS 1 - Asa Sul.', 'task_alt')}
          />
        ))}
        {lista.length === 0 && (
          <Card className="items-center gap-2 py-8">
            <Icon name="inbox" size={32} color="outline" />
            <Txt v="body-md" className="text-on-surface-variant">
              Nenhuma receita aqui.
            </Txt>
          </Card>
        )}
      </View>

      {/* Guia de validade */}
      <View className="gap-2.5 rounded-xl bg-surface-container-high p-4" style={[shadow.sm, accentBorder()]}>
        <View className="flex-row items-center gap-2">
          <View className="h-7 w-7 items-center justify-center rounded-full bg-primary">
            <Icon name="info" size={16} color="primary-fixed" />
          </View>
          <Txt v="title-md" serif className="flex-1 text-primary">
            Quanto tempo vale uma receita?
          </Txt>
        </View>
        {[
          ['Uso contínuo (pressão, diabetes)', 'Até 180 dias na Farmácia Popular'],
          ['Antibióticos', '10 dias a partir da emissão'],
          ['Controle especial', 'Em geral 30 dias a partir da emissão'],
        ].map(([t, d]) => (
          <View key={t} className="flex-row items-center gap-2.5 rounded-lg bg-surface-container-lowest p-2.5">
            <Icon name="schedule" size={18} color="secondary" />
            <View className="flex-1">
              <Txt v="label-lg" className="text-primary">
                {t}
              </Txt>
              <Txt v="body-sm" className="text-on-surface-variant">
                {d}
              </Txt>
            </View>
          </View>
        ))}
        <Txt v="label-sm" w="medium" className="text-on-surface-variant">
          Na dúvida, confirme com o farmacêutico ou com a sua UBS.
        </Txt>
      </View>

      {/* Modal do código */}
      <Modal visible={!!aberta} transparent animationType="fade" onRequestClose={() => setAberta(null)}>
        <Pressable className="flex-1 items-center justify-center bg-primary/70 px-6" onPress={() => setAberta(null)}>
          <Pressable className="w-full max-w-sm items-center gap-4 rounded-2xl bg-surface-container-lowest p-6" style={shadow.xl}>
            <View className="items-center gap-1">
              <Txt v="label-sm" upper className="text-on-surface-variant">
                Receita digital SUS
              </Txt>
              <Txt v="title-lg" className="text-center text-primary">
                {aberta?.medicamento}
              </Txt>
            </View>
            {aberta && <QrIlustrativo seed={aberta.codigo} />}
            <View className="items-center">
              <Txt v="label-md" className="tracking-widest text-primary">
                {aberta?.codigo}
              </Txt>
              <Txt v="body-sm" className="text-center text-on-surface-variant">
                Mostre este código ao farmacêutico junto com seu documento com foto.
              </Txt>
            </View>
            <Button label="Fechar" variant="surface" className="w-full" onPress={() => setAberta(null)} />
          </Pressable>
        </Pressable>
      </Modal>
    </Screen>
  );
}
