// Minimal client for the BetAudit / Resolution Layer backend.
//
// Same-origin by default: in dev the Vite proxy forwards /admin + /verify to
// the FastAPI backend; in prod FastAPI serves this bundle and the API from one
// origin. Override with VITE_API_BASE if you host them apart.

const API_BASE: string = (import.meta.env.VITE_API_BASE as string) || ''

export type ParsedContractData = {
  oracle_type: string
  challenge_window_hours: number | null
  source_of_truth_specified: string | null
  current_oracle_state: string
}

export type RuleMismatch = {
  clause: string
  trader_thesis: string
  conflict_reason: string
}

export type VerifyResponse = {
  market_id: string
  resolution_risk_score: number
  action: 'PROCEED' | 'CAUTION' | 'ABORT_TRADE'
  parsed_contract_data: ParsedContractData
  rule_mismatches_detected: RuleMismatch[]
  platform: string
  queried_side: string | null
  confidence: number
  summary: string
  request_id: string
}

export class ApiError extends Error {
  code: string
  constructor(message: string, code = 'ERROR') {
    super(message)
    this.code = code
  }
}

// A dev/demo API key, minted once via the (locally open) admin route and cached
// in memory. For a locked-down prod deploy, swap this for a real key flow.
let cachedKey: string | null = null
let keyPromise: Promise<string> | null = null

async function mintKey(): Promise<string> {
  // Public, IP-throttled demo-key route, so admin can stay locked in prod.
  const res = await fetch(`${API_BASE}/demo/key`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
  })
  if (!res.ok) {
    throw new ApiError(`Could not mint demo key (HTTP ${res.status}).`, 'KEY_MINT_FAILED')
  }
  const data = await res.json()
  return data.api_key as string
}

export async function ensureKey(): Promise<string> {
  if (cachedKey) return cachedKey
  if (!keyPromise) {
    keyPromise = mintKey().then((k) => {
      cachedKey = k
      return k
    })
  }
  return keyPromise
}

export async function verifyMarket(
  marketUrl: string,
  queriedSide = 'YES',
): Promise<VerifyResponse> {
  const key = await ensureKey()
  const res = await fetch(`${API_BASE}/verify-resolution-rules`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'X-API-Key': key },
    body: JSON.stringify({ market_url: marketUrl, queried_side: queriedSide }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const msg = (data && (data.message || data.detail)) || `Request failed (HTTP ${res.status}).`
    const code = (data && data.error_code) || `HTTP_${res.status}`
    throw new ApiError(msg, code)
  }
  return data as VerifyResponse
}
