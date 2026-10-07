import type {
  CatalogFilters,
  CatalogListing,
  Conversation,
  PageResult,
  ProductCardData,
  ProductDetail,
  ShoppingContext,
  User,
} from '../types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// The session lives in an httpOnly cookie, sent automatically on these same-origin requests.
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init.headers },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    const detail = body?.detail
    const message = Array.isArray(detail)
      ? detail.map((d: { msg: string }) => d.msg.replace(/^Value error, /, '')).join('. ')
      : (detail ?? res.statusText)
    throw new ApiError(res.status, message)
  }
  return (res.status === 204 ? undefined : await res.json()) as T
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export const api = {
  listProducts: (filters: CatalogFilters = {}) => {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(filters)) {
      if (value === undefined || value === null || value === '') continue
      params.set(key, Array.isArray(value) ? value.join(',') : String(value))
    }
    const qs = params.toString()
    return request<CatalogListing>(`/api/products${qs ? `?${qs}` : ''}`)
  },
  getProduct: (productId: string) => request<ProductDetail>(`/api/products/${encodeURIComponent(productId)}`),

  signup: (body: { first_name: string; last_name: string; email: string; password: string; confirm_password: string }) =>
    post<User>('/api/auth/signup', body),
  login: (body: { email: string; password: string }) => post<User>('/api/auth/login', body),
  logout: () => post<void>('/api/auth/logout'),
  me: () => request<User>('/api/auth/me'),

  chat: (body: {
    message: string
    history: { role: 'user' | 'assistant'; content: string }[]
    current_product_id: string | null
    conversation_id: string
    context: ShoppingContext | null
  }) =>
    post<{
      reply: string
      products: ProductCardData[]
      page: PageResult | null
      context: ShoppingContext
      suggestions: string[]
      conversation_id: string
      saved: boolean
    }>('/api/chat', body),
  chatHistory: () => request<Conversation[]>('/api/chat/history'),
}
