import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { formatPrice } from '../components/ProductCard'
import type { ProductDetail } from '../types'

export default function ProductDetailPage() {
  const { productId } = useParams<{ productId: string }>()
  const [product, setProduct] = useState<ProductDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [size, setSize] = useState<string | null>(null)

  useEffect(() => {
    if (!productId) return
    setProduct(null)
    setError(null)
    setSize(null)
    window.scrollTo({ top: 0 })
    api.getProduct(productId).then(setProduct).catch((e: Error) => setError(e.message))
  }, [productId])

  if (error) {
    return (
      <div className="page">
        <div className="error-box">{error}</div>
        <Link to="/products">← Back to products</Link>
      </div>
    )
  }
  if (!product) return <div className="page muted">Loading…</div>

  const chosen = product.sizes.find((s) => s.size === size)

  return (
    <div className="page">
      <Link to="/products" className="back-link">
        ← Back to products
      </Link>
      <div className="detail">
        <div className="detail-image">
          <img src={product.image_url} alt={product.name} />
        </div>
        <div className="detail-info">
          <div className="detail-type">{product.garment_type}</div>
          <h1>{product.name}</h1>
          <div className="detail-price">{formatPrice(product.price)}</div>
          <p className="detail-desc">{product.description}</p>

          <div className="detail-section">
            <div className="label">Colors</div>
            <div className="chips">
              {product.colors.map((c) => (
                <span key={c} className="chip">
                  {c}
                </span>
              ))}
            </div>
          </div>

          <div className="detail-section">
            <div className="label">Size</div>
            <div className="size-grid">
              {product.sizes.map((s) => (
                <button
                  key={s.size}
                  className={`size-btn${size === s.size ? ' active' : ''}`}
                  disabled={s.quantity === 0}
                  onClick={() => setSize(s.size)}
                  title={s.quantity === 0 ? 'Sold out' : `${s.quantity} in stock`}
                >
                  {s.size}
                </button>
              ))}
            </div>
            <div className="stock-note">
              {chosen
                ? `${chosen.quantity} left in ${chosen.size}`
                : `${product.total_stock} in stock across all sizes. Crossed-out sizes are sold out.`}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
