import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import ProductCard from '../components/ProductCard'
import type { CatalogListing, SortOption } from '../types'

const SORT_LABELS: Record<SortOption, string> = {
  featured: 'Featured',
  price_low: 'Price: low to high',
  price_high: 'Price: high to low',
  name: 'Name: A to Z',
  color: 'Color',
  brand: 'Brand',
  category: 'Category',
}
const PRICE_CAPS = [35, 50, 60, 75, 100]
const SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL']
const SWATCHES: Record<string, string> = {
  Navy: '#1f2f55',
  Gray: '#a4a9b1',
  'White & cream': '#f4efe3',
  Coral: '#e58e78',
  'Not listed': 'repeating-linear-gradient(45deg,#ddd 0 3px,#fff 3px 6px)',
}
// Filters live in the URL so the chat, back/forward and refresh all work.
const FILTER_KEYS = ['sort', 'category', 'color', 'brand', 'max_price', 'size'] as const

export default function ProductsPage() {
  const [params, setParams] = useSearchParams()
  const [listing, setListing] = useState<CatalogListing | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Chat search adds q (title), ids (results) and kw (keywords picked from the message).
  const chatTitle = params.get('q')
  const idsParam = params.get('ids')
  const chatIds = useMemo(() => idsParam?.split(',').filter(Boolean) ?? null, [idsParam])
  const keywords = params.get('kw')?.split(',').filter(Boolean) ?? []
  const sort = (params.get('sort') as SortOption | null) ?? 'featured'
  const category = params.get('category')
  const color = params.get('color')
  const brand = params.get('brand')
  const maxPrice = params.get('max_price')
  const size = params.get('size')
  const activeFilters = [category, color, brand, maxPrice, size].filter(Boolean).length
  // Results the chat put on the page: a search (ids) or a browse (filters + Audrey's title).
  const fromChat = Boolean(chatIds || chatTitle)
  const filterTitle = category || color || brand
    ? [color, category ?? 'merch'].filter(Boolean).join(' ') + (brand ? ` by ${brand}` : '')
    : null

  useEffect(() => {
    setLoading(true)
    setError(null)
    api
      .listProducts({
        sort,
        category: category ?? undefined,
        color: color ?? undefined,
        brand: brand ?? undefined,
        max_price: maxPrice ? Number(maxPrice) : undefined,
        size: size ?? undefined,
        ids: chatIds ?? undefined,
      })
      .then(setListing)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [sort, category, color, brand, maxPrice, size, chatIds])

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [idsParam])

  // A browse page's chat title no longer fits once the shopper changes the filters themselves.
  function withoutStaleChatTitle(next: URLSearchParams) {
    if (!next.get('ids')) {
      next.delete('q')
      next.delete('kw')
    }
    return next
  }

  function setParam(key: (typeof FILTER_KEYS)[number], value: string | null) {
    const next = withoutStaleChatTitle(new URLSearchParams(params))
    if (value === null || value === '' || (key === 'sort' && value === 'featured')) next.delete(key)
    else next.set(key, value)
    setParams(next, { replace: true })
  }

  function toggle(key: 'category' | 'color' | 'brand' | 'size', value: string) {
    setParam(key, params.get(key) === value ? null : value)
  }

  function clearFilters() {
    const next = withoutStaleChatTitle(new URLSearchParams(params))
    for (const key of FILTER_KEYS) if (key !== 'sort') next.delete(key)
    setParams(next, { replace: true })
  }

  const products = listing?.products ?? []

  return (
    <div className="page catalog-page">
      <aside className="catalog-sidebar" aria-label="Sort and filter">
        <div className="filter-group">
          <label className="filter-label" htmlFor="sort-select">
            Sort by
          </label>
          <select id="sort-select" value={sort} onChange={(e) => setParam('sort', e.target.value)}>
            {(Object.keys(SORT_LABELS) as SortOption[]).map((key) => (
              <option key={key} value={key}>
                {key === 'featured' && chatIds ? 'Best match' : SORT_LABELS[key]}
              </option>
            ))}
          </select>
        </div>

        {listing &&
          (
            [
              ['category', 'Category', category],
              ['color', 'Color', color],
              ['brand', 'Brand', brand],
            ] as const
          ).map(([key, label, active]) => (
            <div className="filter-group" key={key}>
              <div className="filter-label">{label}</div>
              <ul className="facet-list">
                {listing.facets[key].map((f) => (
                  <li key={f.value}>
                    <button
                      className={`facet${active === f.value ? ' active' : ''}`}
                      onClick={() => toggle(key, f.value)}
                      aria-pressed={active === f.value}
                    >
                      {key === 'color' && <span className="swatch" style={{ background: SWATCHES[f.value] ?? '#ccc' }} />}
                      <span className="facet-name">{f.value}</span>
                      <span className="facet-count">{f.count}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}

        <div className="filter-group">
          <label className="filter-label" htmlFor="price-select">
            Price
          </label>
          <select id="price-select" value={maxPrice ?? ''} onChange={(e) => setParam('max_price', e.target.value)}>
            <option value="">Any price</option>
            {PRICE_CAPS.map((cap) => (
              <option key={cap} value={cap}>
                Under ${cap}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <div className="filter-label">In stock in size</div>
          <div className="size-chips">
            {SIZES.map((s) => (
              <button
                key={s}
                className={`size-chip${size === s ? ' active' : ''}`}
                onClick={() => toggle('size', s)}
                aria-pressed={size === s}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {activeFilters > 0 && (
          <button className="btn btn-ghost btn-block" onClick={clearFilters}>
            Clear filters ({activeFilters})
          </button>
        )}
      </aside>

      <section className="catalog-main">
        {fromChat ? (
          <div className="page-head chat-search-head" key={params.get('q') ?? idsParam}>
            <div className="eyebrow">Chat search · picked by Audrey</div>
            <h1>{chatTitle || 'Your results'}</h1>
            {keywords.length > 0 && (
              <div className="chips">
                {keywords.map((k) => (
                  <span key={k} className="chip">
                    {k}
                  </span>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="page-head">
            {filterTitle ? (
              <h1>{filterTitle}</h1>
            ) : (
              <h1>
                All the <span className="accent">merch</span>
              </h1>
            )}
          </div>
        )}
        <div className="result-bar">
          <span className="muted">
            {loading || !listing
              ? 'Loading…'
              : `${listing.total} ${listing.total === 1 ? 'product' : 'products'}${size ? ` in stock in ${size}` : ''} · sorted by ${(chatIds && sort === 'featured' ? 'best match' : SORT_LABELS[sort]).toLowerCase()}`}
          </span>
          {(fromChat || activeFilters > 0) && <Link to="/products">Show all products</Link>}
        </div>
        {error && <div className="error-box">Couldn't load products: {error}</div>}
        {!loading && listing && products.length === 0 && (
          <div className="empty-state">
            Nothing matches those filters.{' '}
            <button className="link-button" onClick={clearFilters}>
              Clear filters
            </button>
          </div>
        )}
        <div className="product-grid">
          {products.map((p) => (
            <ProductCard key={p.product_id} product={p} />
          ))}
        </div>
      </section>
    </div>
  )
}
