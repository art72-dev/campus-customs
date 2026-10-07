import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../AuthContext'
import type { ChatMessage, Conversation, PageResult, ShoppingContext } from '../types'
import { formatPrice } from './ProductCard'

const GREETING: ChatMessage = {
  role: 'assistant',
  content:
    "Hello, and welcome to Campus Customs! I'm Audrey. Ask me about prices, sizes in stock, or let me help you find the perfect piece.",
  products: [],
}
const HISTORY_TURNS_SENT = 20
const STARTERS = ['Show me navy hoodies', 'Gifts for my dad under $60', 'What brands do you carry?']

function newConversationId(): string {
  return crypto.randomUUID().replace(/-/g, '')
}

// Audrey sometimes uses **bold** for key facts (prices, counts); render it instead of showing asterisks.
function renderText(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') && part.length > 4 ? <strong key={i}>{part.slice(2, -2)}</strong> : part,
  )
}

function formatWhen(iso: string): string {
  const d = new Date(iso.replace(' ', 'T') + 'Z')
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

export default function ChatWidget() {
  const { user } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const currentProductId = location.pathname.match(/^\/products\/([^/]+)$/)?.[1] ?? null

  const [open, setOpen] = useState(false)
  const [view, setView] = useState<'chat' | 'history'>('chat')
  const [messages, setMessages] = useState<ChatMessage[]>([GREETING])
  const [conversationId, setConversationId] = useState(newConversationId)
  const [context, setContext] = useState<ShoppingContext | null>(null)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [failed, setFailed] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  function startNewChat() {
    setMessages([GREETING])
    setConversationId(newConversationId())
    setContext(null)
    setError(null)
    setFailed(null)
    setView('chat')
  }

  function openConversation(c: Conversation) {
    setMessages(c.messages)
    setConversationId(c.conversation_id)
    // Pick up the shopping context where that chat left off.
    setContext([...c.messages].reverse().find((m) => m.context)?.context ?? null)
    setView('chat')
  }

  // Logged in: reopen the most recent saved chat. Guest (or logout): start fresh, nothing saved.
  useEffect(() => {
    setView('chat')
    if (!user) {
      setConversations([])
      startNewChat()
      return
    }
    api
      .chatHistory()
      .then((saved) => {
        setConversations(saved)
        if (saved.length) openConversation(saved[0])
        else startNewChat()
      })
      .catch(() => startNewChat())
  }, [user])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, sending, open, view])

  function showHistory() {
    setView('history')
    api.chatHistory().then(setConversations).catch((e: Error) => setError(e.message))
  }

  // The agent's page update drives the main page; the chat panel stays open on top.
  function showOnPage(page: PageResult) {
    if (page.action === 'open_product') {
      navigate(`/products/${page.product_ids[0]}`)
      return
    }
    const params = new URLSearchParams({ q: page.title })
    if (page.action === 'show_results') params.set('ids', page.product_ids.join(','))
    if (page.keywords.length) params.set('kw', page.keywords.join(','))
    for (const key of ['sort', 'category', 'color', 'brand', 'max_price', 'size'] as const) {
      const value = page[key]
      if (value !== null && value !== undefined && value !== '') params.set(key, String(value))
    }
    navigate(`/products${params.size ? `?${params}` : ''}`)
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    void send(input)
  }

  async function send(raw: string, retry = false) {
    const text = raw.trim()
    if (!text || sending) return
    const history = (retry ? messages.slice(0, -1) : messages)
      .filter((m) => m !== GREETING)
      .slice(-HISTORY_TURNS_SENT)
      .map(({ role, content }) => ({ role, content }))
    setInput('')
    setError(null)
    setFailed(null)
    if (!retry) setMessages((prev) => [...prev, { role: 'user', content: text, products: [] }])
    setSending(true)
    try {
      const res = await api.chat({
        message: text,
        history,
        current_product_id: currentProductId,
        conversation_id: conversationId,
        context,
      })
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: res.reply,
          products: res.products,
          page: res.page,
          context: res.context,
          suggestions: res.suggestions,
        },
      ])
      setContext(res.context)
      if (res.page) showOnPage(res.page)
    } catch (err) {
      setError((err as Error).message)
      setFailed(text)
    } finally {
      setSending(false)
    }
  }

  return (
    <>
      {open && (
        <div className="chat-panel" role="dialog" aria-label="Chat with Audrey">
          <div className="chat-header">
            <div>
              <div className="chat-title">Audrey · Campus Customs</div>
              <div className="chat-subtitle">
                {user ? `Chatting as ${user.first_name ?? user.email}` : 'Guest chat · not saved'}
              </div>
            </div>
            <div className="chat-header-actions">
              <button className="chat-link" onClick={startNewChat} disabled={sending}>
                New chat
              </button>
              {user && (
                <button className="chat-link" onClick={view === 'history' ? () => setView('chat') : showHistory}>
                  {view === 'history' ? 'Back' : 'History'}
                </button>
              )}
              <button className="chat-close" onClick={() => setOpen(false)} aria-label="Close chat">
                ×
              </button>
            </div>
          </div>

          {view === 'history' ? (
            <div className="chat-messages chat-history-list">
              {conversations.length === 0 && <div className="chat-empty">No saved chats yet.</div>}
              {conversations.map((c) => (
                <button
                  key={c.conversation_id}
                  className={`chat-history-item${c.conversation_id === conversationId ? ' active' : ''}`}
                  onClick={() => openConversation(c)}
                >
                  <span className="chat-history-title">{c.title}</span>
                  <span className="chat-history-meta">
                    {formatWhen(c.last_message_at)} · {c.messages.filter((m) => m.role === 'user').length} questions
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <div className="chat-messages" ref={scrollRef}>
              {messages.map((m, i) => (
                <div key={i} className={`chat-msg ${m.role === 'user' ? 'user' : 'bot'}`}>
                  <div className="chat-text">{renderText(m.content)}</div>
                  {m.page && m.page.action !== 'open_product' && (
                    <button className="chat-page-link" onClick={() => showOnPage(m.page!)}>
                      {m.page.action === 'show_results'
                        ? `View ${m.page.product_ids.length} results: ${m.page.title} →`
                        : `View on the page: ${m.page.title} →`}
                    </button>
                  )}
                  {m.products.length > 0 && (
                    <div className="chat-cards">
                      {m.products.map((p) => (
                        <Link key={p.product_id} to={`/products/${p.product_id}`} className="chat-card">
                          <img src={p.image_url} alt={p.name} />
                          <div>
                            <div className="chat-card-name">{p.name}</div>
                            <div className="chat-card-price">{formatPrice(p.price)}</div>
                            <div className="chat-card-sizes">
                              {p.in_stock_sizes.length ? `In stock: ${p.in_stock_sizes.join(', ')}` : 'Sold out'}
                            </div>
                          </div>
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              {!sending && !failed && (() => {
                const last = messages[messages.length - 1]
                const chips = messages.length === 1 && last === GREETING ? STARTERS : last?.role === 'assistant' ? (last.suggestions ?? []) : []
                return chips.length > 0 ? (
                  <div className="chat-suggestions">
                    {chips.map((q) => (
                      <button key={q} className="chat-suggestion" onClick={() => send(q)}>
                        {q}
                      </button>
                    ))}
                  </div>
                ) : null
              })()}
              {sending && (
                <div className="chat-msg bot thinking" aria-label="Audrey is typing">
                  <span className="dot" />
                  <span className="dot" />
                  <span className="dot" />
                </div>
              )}
            </div>
          )}

          {error && (
            <div className="chat-error">
              {error}
              {failed && (
                <button className="chat-link" onClick={() => send(failed, true)}>
                  Try again
                </button>
              )}
            </div>
          )}

          {view === 'chat' && (
            <>
              {!user && (
                <div className="chat-guest-note">
                  <Link to="/login">Log in</Link> or <Link to="/signup">create an account</Link> to save your chats.
                </div>
              )}
              <form className="chat-input" onSubmit={onSubmit}>
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={currentProductId ? 'Ask about this item…' : 'Ask Audrey anything about the merch…'}
                  maxLength={1000}
                  disabled={sending}
                />
                <button type="submit" className="btn btn-primary" disabled={sending || !input.trim()}>
                  Send
                </button>
              </form>
            </>
          )}
        </div>
      )}
      <button className="chat-fab" onClick={() => setOpen((o) => !o)} aria-label={open ? 'Close chat' : 'Open chat'}>
        {open ? '×' : 'Chat'}
      </button>
    </>
  )
}
