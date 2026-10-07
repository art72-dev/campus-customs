import { Link } from 'react-router-dom'
import Bulldog from '../components/Bulldog'

const SERVICES = [
  { title: 'Screen printing', body: 'Big runs, bold colors, crisp prints. Team orders and event drops are our thing.' },
  { title: 'Embroidery', body: 'Stitched crests and left-chest logos for that elevated, old-money-but-make-it-campus look.' },
  { title: 'Graphic design', body: "Got a vibe but no design? Our team turns your idea into merch you'll actually wear." },
  { title: 'Event merch', body: 'Reunions, clubs, conferences, game day: we handle it start to finish.' },
]

export default function AboutPage() {
  return (
    <div className="page about">
      <section className="hero hero-with-mascot">
        <div>
          <div className="eyebrow">About Us</div>
          <h1>
            A New Haven family business, <span className="accent">still going strong.</span>
          </h1>
          <p>
            Campus Customs has been posted up on Broadway, right across from Yale, since the '70s. What started as a
            little memorabilia shop is now a full-on merch powerhouse, and it's still run by the same family.
          </p>
        </div>
        <Bulldog size={200} tilt={8} label="Bulldog mascot tilting its head" />
      </section>

      <section className="about-grid">
        <div className="about-block">
          <h2>The story</h2>
          <p>
            Brothers Joel and Jeremy Cobden run the shop today, keeping their dad's whole philosophy alive: treat
            every customer like a regular, and do business the right way. No shortcuts, no sketchy stuff, just good gear
            and good people.
          </p>
          <p>
            Over the decades we've gone from selling Yale souvenirs to printing, stitching and designing merch for
            students, families, alumni, teams and events, all in our own production space.
          </p>
        </div>
        <div className="about-block highlight">
          <h2>Come through</h2>
          <p>
            <strong>57 Broadway, New Haven, CT</strong>
            <br />
            Right across from campus. Pull up between classes, on move-in weekend, or when you're back for reunions.
          </p>
          <Link to="/products" className="btn btn-primary">
            Shop online
          </Link>
        </div>
      </section>

      <section className="section">
        <h2>What we do</h2>
        <div className="perks">
          {SERVICES.map((s) => (
            <div key={s.title} className="perk">
              <h3>{s.title}</h3>
              <p>{s.body}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
