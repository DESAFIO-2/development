/**
 * Guarda da sessão no aparelho.
 *
 * - Refresh token e perfil local vão para o expo-secure-store: Keychain no iOS e
 *   Keystore (AES) no Android, com acesso só com o aparelho desbloqueado e sem
 *   ir para backup/iCloud (WHEN_UNLOCKED_THIS_DEVICE_ONLY).
 * - O access token nunca é gravado: fica só na memória do app.
 * - Nada disso vai para AsyncStorage, localStorage ou log.
 * - Na web não existe armazenamento seguro equivalente: a sessão fica só em
 *   memória e some ao recarregar a página (de propósito).
 */

import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

const CHAVE_REFRESH = 'remedia.refresh';
const CHAVE_PERFIL = 'remedia.perfil';

const OPCOES: SecureStore.SecureStoreOptions = {
  keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
};

const memoriaWeb = new Map<string, string>();
const seguro = Platform.OS !== 'web';

async function gravar(chave: string, valor: string): Promise<void> {
  if (seguro) await SecureStore.setItemAsync(chave, valor, OPCOES);
  else memoriaWeb.set(chave, valor);
}

async function ler(chave: string): Promise<string | null> {
  if (seguro) return SecureStore.getItemAsync(chave, OPCOES);
  return memoriaWeb.get(chave) ?? null;
}

async function apagar(chave: string): Promise<void> {
  if (seguro) await SecureStore.deleteItemAsync(chave, OPCOES);
  else memoriaWeb.delete(chave);
}

export const sessao = {
  salvarRefresh: (token: string) => gravar(CHAVE_REFRESH, token),
  lerRefresh: () => ler(CHAVE_REFRESH),

  async salvarPerfil<T>(perfil: T): Promise<void> {
    await gravar(CHAVE_PERFIL, JSON.stringify(perfil));
  },
  async lerPerfil<T>(): Promise<T | null> {
    const bruto = await ler(CHAVE_PERFIL);
    if (!bruto) return null;
    try {
      return JSON.parse(bruto) as T;
    } catch {
      await apagar(CHAVE_PERFIL);
      return null;
    }
  },

  /** Sair: apaga a sessão. O perfil local some junto (aparelho compartilhado). */
  async limpar(): Promise<void> {
    await Promise.all([apagar(CHAVE_REFRESH), apagar(CHAVE_PERFIL)]);
  },
};
