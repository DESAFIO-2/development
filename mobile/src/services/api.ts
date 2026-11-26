/**
 * Cliente HTTP tipado do SUS Cidadão (Expo / React Native) conectado à API FastAPI oficial (`backend/`).
 *
 * Contratos espelhados estritamente de `backend/app/api/`:
 * - `GET  /health`
 * - `GET  /api/v1/medications/autocomplete`
 * - `POST /api/v1/prescriptions/audit`
 * - `POST /api/v1/agents/orchestrate`
 * - `POST /api/v1/agents/multimodal`
 * - `GET  /api/v1/pharmacies/nearby`
 * - `GET  /api/v1/ceaf-stock`
 */

import { Platform } from 'react-native';

export type CoverageRoute =
  | 'FARMACIA_POPULAR'
  | 'UBS_REME_DF'
  | 'FARMACIA_ALTO_CUSTO'
  | 'SISREG_EXAME_CONSULTA'
  | 'HOSPITALAR'
  | 'NAO_PADRONIZADO';

export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
}

export interface AutocompleteMedicationItem {
  dcb_principio_ativo: string;
  concentracao: string;
  forma_farmaceutica: string;
  via_retirada: CoverageRoute;
  dispensacao_gratuita_prevista: boolean;
  exige_lme: boolean;
  texto_exibicao: string;
}

export interface AutocompleteResponse {
  consulta: string;
  total_encontrados: number;
  resultados: AutocompleteMedicationItem[];
}

export interface MedicationItemInput {
  nome_digitado: string;
  principio_ativo_dcb?: string | null;
  concentracao?: string | null;
  forma_farmaceutica?: string | null;
  posologia?: string | null;
  quantidade_prescrita?: string | null;
}

export interface PrescriptionAuditRequestDTO {
  itens: MedicationItemInput[];
  data_emissao?: string; // AAAA-MM-DD (hoje ou anterior)
  regiao_administrativa?: string;
  tipo_prescritor?: string;
  pergunta_adicional?: string | null;
}

export interface ItemRoteiroDTO {
  medicamento: string;
  principio_ativo_dcb: string;
  via_retirada: CoverageRoute;
  local_sugerido: string;
  o_que_levar: string[];
  dias_validade_receita: number | null;
  data_limite_validade: string | null;
  dias_restantes: number | null;
  alerta_vencimento_proximo: boolean;
  citacao_normativa: string;
}

export interface PrescriptionAuditResponseDTO {
  sucesso: boolean;
  regiao_administrativa: string;
  itens: ItemRoteiroDTO[];
  resumo_acolhedor: string;
  aviso_preservacao_ato_medico: string;
}

export interface AgentRequestDTO {
  itens?: MedicationItemInput[];
  data_emissao?: string; // AAAA-MM-DD
  regiao_administrativa?: string;
  tipo_prescritor?: string;
  pergunta_adicional?: string | null;
}

export interface ItemRoteiroCidadao {
  medicamento_ou_exame: string;
  principio_ativo_dcb: string;
  via_retirada: CoverageRoute;
  local_sugerido: string;
  o_que_levar: string[];
  dias_validade_receita: number | null;
  data_limite_validade: string | null;
  dias_restantes: number | null;
  alerta_vencimento_proximo: boolean;
  citacao_normativa: string;
}

export interface CitizenGuidanceCard {
  sucesso: boolean;
  regiao_administrativa: string;
  itens_auditados: ItemRoteiroCidadao[];
  resumo_acolhedor: string;
  aviso_preservacao_ato_medico: string;
  solicitou_automedicacao: boolean;
}

export interface RetrievalHitDTO {
  chunk_id: string;
  score: number;
  source_id: string;
  document_title: string;
  section: string;
  page_number: number;
  route_category: string;
  text: string;
  matched_dcb?: string | null;
  retriever_name: string;
}

export interface GenerationMetadata {
  status:
    | 'DETERMINISTICO'
    | 'GERADO'
    | 'FALHA_PROVEDOR'
    | 'SAIDA_REJEITADA'
    | 'CONTEXTO_REJEITADO'
    | 'ABSTENCAO'
    | 'BLOQUEADO';
  provider: string | null;
  model: string | null;
  latency_ms: number;
  error_code: string | null;
  fallback_used: boolean;
  prompt_version: string | null;
  context_chunk_ids: string[];
  context_truncated: boolean;
}

export interface AgentTrace {
  agent: string;
  elapsed_ms: number;
  status: string;
}

export interface AgentResponse {
  card: CitizenGuidanceCard;
  resposta_adicional: string | null;
  primary_route: string;
  evidencias: RetrievalHitDTO[];
  citacoes: string[];
  generation: GenerationMetadata;
  agent_trace: AgentTrace[];
  scientific_status: 'NAO_AVALIADO';
}

export type CanalMultimodal = 'texto' | 'pdf' | 'voz';
export type StatusResolucaoItem =
  | 'EXATO_CATALOGO'
  | 'SUGESTAO_ORTOGRAFICA'
  | 'AMBIGUO_REQUER_CONFIRMACAO'
  | 'NAO_IDENTIFICADO';

export interface ExtractedFileReport {
  canal: 'pdf' | 'voz';
  aceito: boolean;
  motivos_rejeicao: string[];
  alertas: string[];
  paginas: number | null;
  duracao_segundos: number | null;
  caracteres_extraidos: number;
  pii_tipos_mascarados: string[];
  extrator_usado: string;
  latencia_ms: number;
}

export interface ExtractedCandidateItem {
  texto_origem: string;
  dcb_sugerido: string | null;
  concentracao_sugerida: string | null;
  forma_sugerida: string | null;
  origem_canal: CanalMultimodal;
  status_resolucao: StatusResolucaoItem;
  opcoes_autocomplete: string[];
}

export interface MultimodalResponse {
  sucesso: boolean;
  modalidades_recebidas: CanalMultimodal[];
  requer_confirmacao_usuario: boolean;
  candidatos_extraidos: ExtractedCandidateItem[];
  relatorios_entrada: ExtractedFileReport[];
  resultado_agentes: AgentResponse | null;
  motivo_falha_ou_bloqueio: string | null;
  mensagem_orientacao: string | null;
}

export interface NativeFileUpload {
  uri: string;
  name: string;
  type: string;
}

export interface MultimodalFormInput {
  pdfBlob?: Blob | null;
  pdfFile?: NativeFileUpload | null;
  audioBlob?: Blob | null;
  audioFile?: NativeFileUpload | null;
  itens?: MedicationItemInput[];
  pergunta_adicional?: string | null;
  regiao_administrativa?: string;
  data_emissao?: string; // AAAA-MM-DD
  tipo_prescritor?: string;
  confirmado_pelo_usuario?: boolean;
}

export interface PharmacyLocationDTO {
  cnes: string;
  name: string;
  address: string;
  neighborhood_or_ra: string;
  pharmacy_type: string;
  latitude: number | null;
  longitude: number | null;
  google_maps_url: string;
  covered_ras?: string[] | null;
  distance_km?: number | null;
}

export interface NearbyPharmaciesResponseDTO {
  ra: string;
  total: number;
  update_schedule: string | null;
  items: PharmacyLocationDTO[];
}

export interface CeafStockItemDTO {
  cod_produto: string;
  desc_produto: string;
  unidade: string;
  disp_estoque: string;
  origem_abastecimento: string;
  psicotropico: string;
  ultima_atualizacao: string;
}

export interface CeafStockResponseDTO {
  query: string;
  unidade: string;
  updated_at: string | null;
  stale_warning: boolean;
  stale_after_hours: number;
  cobertura_escopo: 'CEAF_ALTO_CUSTO';
  cobertura_ubs_disponivel: boolean;
  aviso_cobertura: string;
  total: number;
  items: CeafStockItemDTO[];
}

export function getDefaultApiBaseUrl(): string {
  const envUrl = process.env.EXPO_PUBLIC_API_URL?.trim();
  if (envUrl) return envUrl.replace(/\/+$/, '');
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    const rawHost = window.location.hostname || '127.0.0.1';
    const host = rawHost === 'localhost' ? '127.0.0.1' : rawHost;
    return `http://${host}:8000`;
  }
  return 'http://127.0.0.1:8000';
}

function resolveUrl(path: string, baseUrl?: string): string {
  const cleanBase = (baseUrl?.trim() || getDefaultApiBaseUrl()).replace(/\/+$/, '');
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${cleanBase}${cleanPath}`;
}

function extractErrorMessage(body: unknown, fallback: string): string {
  if (!body || typeof body !== 'object') return fallback;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const messages = detail
      .map((item) =>
        item && typeof item === 'object' && 'msg' in item ? String((item as { msg: unknown }).msg) : ''
      )
      .filter(Boolean);
    if (messages.length > 0) return messages.join('; ');
  }
  return fallback;
}

async function requestJson<T>(
  path: string,
  init?: RequestInit,
  baseUrl?: string,
  timeoutMs = 20000
): Promise<T> {
  const url = resolveUrl(path, baseUrl);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      ...init,
      signal: controller.signal,
    });
    if (!res.ok) {
      let message = `Erro HTTP ${res.status}`;
      try {
        message = extractErrorMessage(await res.json(), message);
      } catch {
        // Ignora corpo não-JSON em erro HTTP.
      }
      throw new Error(message);
    }
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') {
      throw new Error(`Tempo esgotado ao aguardar o servidor (${url}).`);
    }
    if (err instanceof TypeError) {
      throw new Error(
        `API inacessível em ${url}. Inicie o backend com "make run-api" ou configure EXPO_PUBLIC_API_URL.`
      );
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export async function checkHealth(baseUrl?: string): Promise<HealthResponse> {
  return requestJson<HealthResponse>('/health', { method: 'GET' }, baseUrl, 5000);
}

export async function autocompleteMedications(
  q: string,
  limite = 10,
  baseUrl?: string
): Promise<AutocompleteResponse> {
  const qs = new URLSearchParams({ q, limite: String(limite) });
  return requestJson<AutocompleteResponse>(
    `/api/v1/medications/autocomplete?${qs.toString()}`,
    { method: 'GET' },
    baseUrl
  );
}

export async function auditPrescription(
  payload: PrescriptionAuditRequestDTO,
  baseUrl?: string
): Promise<PrescriptionAuditResponseDTO> {
  return requestJson<PrescriptionAuditResponseDTO>(
    '/api/v1/prescriptions/audit',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    baseUrl
  );
}

export async function orchestrateAgents(
  payload: AgentRequestDTO,
  baseUrl?: string
): Promise<AgentResponse> {
  return requestJson<AgentResponse>(
    '/api/v1/agents/orchestrate',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    baseUrl,
    30000
  );
}

export async function orchestrateMultimodal(
  params: MultimodalFormInput,
  baseUrl?: string
): Promise<MultimodalResponse> {
  const form = new FormData();
  if (params.pdfBlob) {
    form.append('pdf_file', params.pdfBlob, 'receita.pdf');
  } else if (params.pdfFile) {
    form.append('pdf_file', params.pdfFile as unknown as Blob);
  }
  if (params.audioBlob) {
    form.append('audio_file', params.audioBlob, 'duvida.wav');
  } else if (params.audioFile) {
    form.append('audio_file', params.audioFile as unknown as Blob);
  }
  if (params.itens && params.itens.length > 0) {
    form.append('itens_json', JSON.stringify(params.itens));
  }
  if (params.pergunta_adicional?.trim()) {
    form.append('pergunta_adicional', params.pergunta_adicional.trim());
  }
  if (params.regiao_administrativa?.trim()) {
    form.append('regiao_administrativa', params.regiao_administrativa.trim());
  }
  if (params.data_emissao?.trim()) {
    form.append('data_emissao', params.data_emissao.trim());
  }
  if (params.tipo_prescritor?.trim()) {
    form.append('tipo_prescritor', params.tipo_prescritor.trim());
  }
  form.append('confirmado_pelo_usuario', params.confirmado_pelo_usuario ? 'true' : 'false');

  return requestJson<MultimodalResponse>(
    '/api/v1/agents/multimodal',
    {
      method: 'POST',
      body: form,
    },
    baseUrl,
    45000
  );
}

export async function fetchNearbyPharmacies(
  params: { ra?: string; q?: string; lat?: number; lng?: number; limite?: number },
  baseUrl?: string
): Promise<NearbyPharmaciesResponseDTO> {
  const qs = new URLSearchParams();
  if (params.ra) qs.set('ra', params.ra);
  if (params.q) qs.set('q', params.q);
  if (params.lat !== undefined && params.lng !== undefined) {
    qs.set('lat', String(params.lat));
    qs.set('lng', String(params.lng));
  }
  qs.set('limite', String(params.limite ?? 8));
  return requestJson<NearbyPharmaciesResponseDTO>(
    `/api/v1/pharmacies/nearby?${qs.toString()}`,
    { method: 'GET' },
    baseUrl
  );
}

export async function fetchCeafStock(
  params: { q?: string; unidade?: string; limite?: number },
  baseUrl?: string
): Promise<CeafStockResponseDTO> {
  const qs = new URLSearchParams();
  if (params.q) qs.set('q', params.q);
  if (params.unidade) qs.set('unidade', params.unidade);
  qs.set('limite', String(params.limite ?? 15));
  return requestJson<CeafStockResponseDTO>(
    `/api/v1/ceaf-stock?${qs.toString()}`,
    { method: 'GET' },
    baseUrl
  );
}
