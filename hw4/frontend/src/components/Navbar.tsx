import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../AuthContext'

export default function Navbar() {
  const { user, loading, logout } = useAuth()
  const navigate = useNavigate()

  return (
    <header className="navbar">
      <Link to="/" className="brand">
        Campus<span className="brand-accent">Customs</span>
      </Link>
      <nav className="nav-links">
        <NavLink to="/" end>
          Home
        </NavLink>
        <NavLink to="/about">About Us</NavLink>
        <NavLink to="/products">Products</NavLink>
        {loading ? null : user ? (
          <>
            <span className="nav-user">Hey, {user.first_name}!</span>
            <button
              className="btn btn-ghost"
              onClick={async () => {
                await logout()
                navigate('/')
              }}
            >
              Log out
            </button>
          </>
        ) : (
          <>
            <NavLink to="/login">Log in</NavLink>
            <Link to="/signup" className="btn btn-primary">
              Create account
            </Link>
          </>
        )}
      </nav>
    </header>
  )
}
