export interface ProductSummary {
  product_id: string
  name: string
  garment_type: string
  description: string
  price: number
  image_url: string
}

export interface User {
  id: number
  first_name: string | null
  last_name: string | null
  email: string
}

export interface ProductCardData {
  product_id: string
  name: string
  price: number
  image_url: string
  garment_type: string
  in_stock_sizes: string[]
}

export type SortOption = 'featured' | 'price_low' | 'price_high' | 'name' | 'color' | 'brand' | 'category'

export interface CatalogItem {
  product_id: string
  name: string
  garment_type: string
  category: string
  brand: string
  color_family: string
  description: string
  price: number
  image_url: string
  in_stock_sizes: string[]
  stock_status: 'in_stock' | 'partly_sold_out' | 'sold_out'
}

export interface FacetCount {
  value: string
  count: number
}

export interface CatalogListing {
  sort: SortOption
  total: number
  in_stock: number
  products: CatalogItem[]
  facets: Record<'category' | 'color' | 'brand', FacetCount[]>
}

export interface CatalogFilters {
  sort?: SortOption
  category?: string
  color?: string
  brand?: string
  max_price?: number
  size?: string
  ids?: string[]
}

export interface PageResult {
  action: 'show_results' | 'open_product' | 'browse'
  title: string
  keywords: string[]
  product_ids: string[]
  sort: SortOption | null
  category: string | null
  color: string | null
  brand: string | null
  max_price: number | null
  size: string | null
}

export interface ShoppingContext {
  garment: string | null
  colors: string[]
  other_keywords: string[]
  size: string | null
  max_price: number | null
  product_ids: string[]
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  products: ProductCardData[]
  page?: PageResult | null
  context?: ShoppingContext | null
  suggestions?: string[]
  created_at?: string
}

export interface Conversation {
  conversation_id: string
  title: string
  started_at: string
  last_message_at: string
  messages: ChatMessage[]
}

export interface SizeStock {
  size: string
  quantity: number
}

export interface ProductDetail extends ProductSummary {
  colors: string[]
  sizes: SizeStock[]
  total_stock: number
}
