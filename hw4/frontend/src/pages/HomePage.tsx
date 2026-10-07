import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import Bulldog from '../components/Bulldog'
import ProductCard from '../components/ProductCard'
import type { CatalogItem } from '../types'

const FEATURED_IDS = [
  'district-vit-hoodie-vintage-bulldog',
  '2025-yale-vs-harvard-t-shirt',
  'yale-mom-hoodie',
  'champion-reverse-weave-crewneck',
]

const PERKS = [
  {
    title: 'Family-run, fr',
    body: "Not a faceless megastore. We're a New Haven family business that's been repping Yale for decades.",
  },
  {
    title: 'Made in-house',
    body: 'Screen printing, embroidery and design all happen under one roof, so your fit comes out clean every time.',
  },
  {
    title: 'Custom drops',
    body: 'Club, team, reunion or event? We design and print merch that actually slaps, in any quantity.',
  },
]

export default function HomePage() {
  const [featured, setFeatured] = useState<CatalogItem[]>([])

  useEffect(() => {
    api
      .listProducts({ ids: FEATURED_IDS })
      .then((listing) => setFeatured(listing.products))
      .catch(() => setFeatured([]))
  }, [])

  return (
    <div className="page">
      <section className="hero hero-with-mascot">
        <div>
          <div className="eyebrow">Right across from Yale · New Haven, CT</div>
          <h1>
            Your Yale fit <span className="accent">starts here.</span>
          </h1>
          <p>
            Hoodies, crewnecks, tees and quarter-zips that hit different. Whether you're a first-year, a proud parent or
            an alum who still bleeds blue, we've got the drip.
          </p>
          <div className="hero-actions">
            <Link to="/products" className="btn btn-primary">
              Shop the merch
            </Link>
            <Link to="/about" className="btn btn-ghost">
              Our story
            </Link>
          </div>
        </div>
        <Bulldog size={230} cap tilt={-4} label="Bulldog mascot in a Yale cap" />
      </section>

      <section className="perks">
        {PERKS.map((perk) => (
          <div key={perk.title} className="perk">
            <h3>{perk.title}</h3>
            <p>{perk.body}</p>
          </div>
        ))}
      </section>

      {featured.length > 0 && (
        <section className="section">
          <div className="section-head">
            <h2>Certified bangers</h2>
            <Link to="/products">See everything →</Link>
          </div>
          <div className="product-grid">
            {featured.map((p) => (
              <ProductCard key={p.product_id} product={p} />
            ))}
          </div>
        </section>
      )}

      <section className="cta">
        <h2>Main character energy, Yale edition.</h2>
        <p>Residential colleges, varsity sports, grad schools, Yale Mom and Dad gear: find the piece that's lowkey you.</p>
        <Link to="/products" className="btn btn-primary">
          Browse all products
        </Link>
      </section>
    </div>
  )
}
