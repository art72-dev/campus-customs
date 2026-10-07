import { Link } from 'react-router-dom'
import type { CatalogItem } from '../types'

export function formatPrice(price: number): string {
  return `$${price.toFixed(2)}`
}

export default function ProductCard({ product }: { product: CatalogItem }) {
  const soldOut = product.stock_status === 'sold_out'
  return (
    <Link to={`/products/${product.product_id}`} className="product-card">
      <div className="product-image-wrap">
        <img src={product.image_url} alt={product.name} loading="lazy" />
        {soldOut && <span className="badge badge-out">Sold out</span>}
      </div>
      <div className="product-info">
        <div className="product-meta-line">
          {product.brand === 'Campus Customs design' ? 'Campus Customs' : product.brand} · {product.color_family}
        </div>
        <div className="product-name">{product.name}</div>
        <p className="product-desc">{product.description}</p>
        <div className="product-price">{formatPrice(product.price)}</div>
      </div>
    </Link>
  )
}
