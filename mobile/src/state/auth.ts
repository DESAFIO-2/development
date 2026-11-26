/**
 * Sessão do usuário: login e cadastro na API, refresh rotativo, desbloqueio por
 * biometria e bloqueio por inatividade.
 *
 * Modelo de segurança:
 * - Access token (15 min) só na memória; refresh no SecureStore (sessao.ts).
 * - Ao abrir o app com sessão salva, ele NÃO entra sozinho: pede biometria do
 *   aparelho (ou a senha). Sem biometria cadastrada no aparelho, só a senha entra.
 * - Depois de 5 min em segundo plano, o app bloqueia e pede de novo.
 * - Sair revoga a sessão na API e apaga tudo do aparelho.
 * - Perfil (nome, celular, CNS...) fica só no aparelho, cifrado: a API guarda
 *   apenas o HMAC do CPF e o hash da senha.
 */

import * as LocalAuthentication from 'expo-local-authentication';
import { useCallback, useEffect, useRef, useState } from 'react';
import { AppState, Platform } from 'react-native';

import { usuario as usuarioMock } from '@/data/mock';
import {
  cadastrarConta,
  configurarAutenticacao,
  entrarConta,
  ErroApi,
  renovarSessao,
  sairConta,
  type TokensDTO,
} from '@/services/api';
import { sessao } from '@/services/sessao';

export type Usuario = typeof usuarioMock;
export type Resultado = { ok: true } | { ok: false; erro: string };

export const BLOQUEIO_INATIVIDADE_MS = 5 * 60 * 1000;

const soDigitos = (cpf: string) => cpf.replace(/\D/g, '');

function mensagemDeErro(err: unknown): string {
  if (err instanceof ErroApi) {
    if (err.status === 429) return 'Muitas tentativas. Aguarde um minuto e tente de novo.';
    return err.message;
  }
  if (err instanceof Error) return err.message;
  return 'Não foi possível concluir agora. Tente de novo.';
}

/** Perfil do aparelho só vale para o mesmo CPF (aparelho compartilhado). */
async function perfilDoCpf(cpf: string): Promise<Usuario | null> {
  const perfil = await sessao.lerPerfil<Usuario>();
  return perfil && soDigitos(perfil.cpf) === soDigitos(cpf) ? perfil : null;
}

export function useAutenticacao() {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [sessaoSalva, setSessaoSalva] = useState(false);
  const [biometriaDisponivel, setBiometriaDisponivel] = useState(false);
  const access = useRef<string | null>(null);
  const renovando = useRef<Promise<string | null> | null>(null);
  const emSegundoPlanoDesde = useRef<number | null>(null);

  const encerrarLocal = useCallback(async () => {
    access.current = null;
    await sessao.limpar();
    setSessaoSalva(false);
    setUsuario(null);
  }, []);

  const guardarTokens = useCallback(async (t: TokensDTO) => {
    access.current = t.access_token;
    await sessao.salvarRefresh(t.refresh_token);
    setSessaoSalva(true);
  }, []);

  /** Uma renovação por vez: chamadas paralelas esperam a mesma. */
  const renovar = useCallback((): Promise<string | null> => {
    if (renovando.current) return renovando.current;
    renovando.current = (async () => {
      try {
        const refresh = await sessao.lerRefresh();
        if (!refresh) return null;
        const t = await renovarSessao(refresh);
        await guardarTokens(t);
        return t.access_token;
      } catch (err) {
        // 401: sessão revogada/expirada no servidor. Rede fora: mantém a sessão salva.
        if (err instanceof ErroApi && err.status === 401) await encerrarLocal();
        return null;
      } finally {
        renovando.current = null;
      }
    })();
    return renovando.current;
  }, [encerrarLocal, guardarTokens]);

  useEffect(() => {
    configurarAutenticacao({ obterToken: () => access.current, renovar });
    return () => configurarAutenticacao(null);
  }, [renovar]);

  useEffect(() => {
    sessao.lerRefresh().then((r) => setSessaoSalva(Boolean(r)));
    if (Platform.OS === 'web') return;
    Promise.all([LocalAuthentication.hasHardwareAsync(), LocalAuthentication.isEnrolledAsync()]).then(
      ([hardware, cadastrada]) => setBiometriaDisponivel(hardware && cadastrada)
    );
  }, []);

  // Bloqueio por inatividade: tira o usuário da tela e descarta o access token.
  useEffect(() => {
    const sub = AppState.addEventListener('change', (estado) => {
      if (estado === 'background') {
        emSegundoPlanoDesde.current = Date.now();
        return;
      }
      if (estado === 'active' && emSegundoPlanoDesde.current !== null) {
        const fora = Date.now() - emSegundoPlanoDesde.current;
        emSegundoPlanoDesde.current = null;
        if (fora > BLOQUEIO_INATIVIDADE_MS) {
          access.current = null;
          setUsuario(null);
        }
      }
    });
    return () => sub.remove();
  }, []);

  const entrar = useCallback(
    async (cpf: string, senha: string): Promise<Resultado> => {
      try {
        const t = await entrarConta(cpf, senha);
        await guardarTokens(t);
        const perfil = (await perfilDoCpf(cpf)) ?? { ...usuarioMock, cpf };
        await sessao.salvarPerfil(perfil);
        setUsuario(perfil);
        return { ok: true };
      } catch (err) {
        return { ok: false, erro: mensagemDeErro(err) };
      }
    },
    [guardarTokens]
  );

  const cadastrar = useCallback(
    async (dados: Partial<Usuario> & { cpf: string }, senha: string): Promise<Resultado> => {
      try {
        const t = await cadastrarConta(dados.cpf, senha);
        await guardarTokens(t);
        const nomeCompleto = dados.nomeCompleto?.trim() || usuarioMock.nomeCompleto;
        const perfil: Usuario = {
          ...usuarioMock,
          ...dados,
          nomeCompleto,
          nome: nomeCompleto.split(' ').slice(0, 2).join(' '),
        };
        await sessao.salvarPerfil(perfil);
        setUsuario(perfil);
        return { ok: true };
      } catch (err) {
        return { ok: false, erro: mensagemDeErro(err) };
      }
    },
    [guardarTokens]
  );

  const desbloquearComBiometria = useCallback(async (): Promise<Resultado> => {
    if (!sessaoSalva) return { ok: false, erro: 'Entre com CPF e senha no primeiro acesso.' };
    if (!biometriaDisponivel) {
      return { ok: false, erro: 'Cadastre a digital ou o rosto no aparelho para usar a biometria.' };
    }
    const r = await LocalAuthentication.authenticateAsync({
      promptMessage: 'Desbloquear a RemedIA',
      cancelLabel: 'Usar senha',
      disableDeviceFallback: false,
    });
    if (!r.success) return { ok: false, erro: 'Biometria não confirmada.' };
    const token = await renovar();
    if (!token) return { ok: false, erro: 'Sessão expirada. Entre com CPF e senha.' };
    const perfil = await sessao.lerPerfil<Usuario>();
    if (!perfil) {
      await encerrarLocal();
      return { ok: false, erro: 'Entre com CPF e senha para continuar.' };
    }
    setUsuario(perfil);
    return { ok: true };
  }, [biometriaDisponivel, encerrarLocal, renovar, sessaoSalva]);

  const sair = useCallback(async () => {
    const refresh = await sessao.lerRefresh();
    if (refresh) {
      // Revoga no servidor; sem rede, a sessão expira sozinha e o aparelho já foi limpo.
      await sairConta(refresh).catch(() => undefined);
    }
    await encerrarLocal();
  }, [encerrarLocal]);

  return {
    usuario,
    sessaoSalva,
    biometriaDisponivel,
    entrar,
    cadastrar,
    desbloquearComBiometria,
    sair,
  };
}
