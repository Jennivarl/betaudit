import { useState, useEffect, useRef, useCallback } from 'react'
import betAuditLogo from './imports/image.png'
import { verifyMarket, ApiError, type VerifyResponse } from './api'

// ─── constants ────────────────────────────────────────────────────────────────
const CYAN = '#66cccc'
const CYAN_GLOW = 'rgba(102,204,204,0.7)'
const CYAN_DIM = 'rgba(102,204,204,0.15)'
const CYAN_BORDER = 'rgba(102,204,204,0.3)'
const GLASS = 'rgba(6,20,20,0.6)'
const AMBER = '#f5a623'
const CRIMSON = '#ff3a3a'

// Real destinations (no dead links).
const REPO_URL = 'https://github.com/Jennivarl/betaudit'
const DOCS_URL = '/docs/'
const API_DOCS_URL = '/api-docs'
const EXAMPLE_MARKET = 'https://polymarket.com/market/new-rhianna-album-before-gta-vi-926'

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

// ─── Logo ─────────────────────────────────────────────────────────────────────
function ShieldLogo({ size = 44 }: { size?: number }) {
  return (
    <img
      src={betAuditLogo}
      alt="BetAudit — AI trading shield logo"
      style={{
        width: size,
        height: size,
        objectFit: 'contain',
        filter: `drop-shadow(0 0 8px ${CYAN_GLOW})`,
        borderRadius: 4,
      }}
    />
  )
}

// ─── Heartbeat ────────────────────────────────────────────────────────────────
function Heartbeat() {
  const heights = [4, 4, 6, 4, 14, 20, 8, 4, 10, 6, 4, 4, 5, 4, 4, 6, 4, 4]
  return (
    <div className="heartbeat-bar">
      {heights.map((h, i) => (
        <span
          key={i}
          style={{
            height: h,
            animationDelay: `${i * 0.15}s`,
            animationDuration: `${2 + (i % 3) * 0.5}s`,
          }}
        />
      ))}
    </div>
  )
}

// ─── Nav ──────────────────────────────────────────────────────────────────────
function Nav() {
  return (
    <header
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 100,
        background: 'rgba(0,0,0,0.85)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        borderBottom: `1px solid ${CYAN_BORDER}`,
        padding: '0 32px',
        height: 64,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}
    >
      {/* Logo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <ShieldLogo size={48} />
        <div>
          <div
            style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontWeight: 700,
              fontSize: 18,
              color: CYAN,
              textShadow: `0 0 10px ${CYAN_GLOW}`,
              letterSpacing: '0.05em',
            }}
          >
            BetAudit
          </div>
          <div
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 9,
              color: 'rgba(102,204,204,0.5)',
              letterSpacing: '0.15em',
            }}
          >
            SIM_LAYER.v1
          </div>
        </div>
      </div>

      {/* Nav links — all real destinations */}
      <nav style={{ display: 'flex', alignItems: 'center', gap: 28 }}>
        {[
          { label: 'docs', href: DOCS_URL, external: false },
          { label: 'api', href: API_DOCS_URL, external: false },
          { label: 'github', href: REPO_URL, external: true },
        ].map((l) => (
          <a
            key={l.label}
            href={l.href}
            className="nav-link"
            {...(l.external ? { target: '_blank', rel: 'noreferrer' } : {})}
          >
            [ {l.label} ]
          </a>
        ))}
      </nav>

      {/* Status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: CYAN,
            boxShadow: `0 0 8px ${CYAN_GLOW}`,
            animation: 'glowPulse 2s ease-in-out infinite',
          }}
        />
        <span
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 11,
            color: 'rgba(102,204,204,0.6)',
            letterSpacing: '0.1em',
          }}
        >
          LIVE
        </span>
        <Heartbeat />
      </div>
    </header>
  )
}

// ─── Timeline SVG ─────────────────────────────────────────────────────────────
function TimelineViz() {
  return (
    <div
      style={{
        width: '100%',
        maxWidth: 720,
        margin: '0 auto',
        perspective: '800px',
      }}
    >
      <div style={{ transform: 'rotateX(18deg) rotateY(-4deg)', transformStyle: 'preserve-3d' }}>
        <svg viewBox="0 0 720 260" width="100%" style={{ overflow: 'visible' }}>
          <defs>
            <filter id="cyanGlow">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            <filter id="amberGlow">
              <feGaussianBlur stdDeviation="2" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            <marker id="cyanArrow" markerWidth="6" markerHeight="6" refX="6" refY="3" orient="auto">
              <path d="M0,0 L6,3 L0,6 Z" fill={CYAN} />
            </marker>
          </defs>

          {/* Main oracle path */}
          <path
            d="M 60 130 L 200 130 L 300 130 L 480 130 L 660 130"
            stroke={CYAN}
            strokeWidth="2.5"
            fill="none"
            filter="url(#cyanGlow)"
            markerEnd="url(#cyanArrow)"
            style={{
              strokeDasharray: 600,
              animation: 'pathDraw 2s ease-out forwards',
            }}
          />

          {/* Timeline nodes on main path */}
          {[60, 200, 300, 480, 660].map((x, i) => (
            <g key={x}>
              <circle cx={x} cy={130} r={i === 2 ? 10 : 6} fill="#000" stroke={CYAN} strokeWidth="1.5"
                filter="url(#cyanGlow)" />
              <circle cx={x} cy={130} r={i === 2 ? 4 : 2.5} fill={CYAN} />
            </g>
          ))}

          {/* Node labels */}
          {[
            { x: 60, label: 'MARKET_OPEN', y: 110 },
            { x: 200, label: 'ANCHOR_EVENT', y: 110 },
            { x: 300, label: 'ORACLE_CHECK', y: 110 },
            { x: 480, label: 'SETTLE_CALL', y: 110 },
            { x: 660, label: 'RESOLVED', y: 110 },
          ].map(({ x, label, y }) => (
            <text key={x} x={x} y={y} textAnchor="middle" fill={CYAN}
              fontSize="8" fontFamily="JetBrains Mono" opacity="0.7">{label}</text>
          ))}

          {/* Risk path 1 — amber — "Deadline Trap" */}
          <path
            d="M 300 130 C 350 130 370 70 420 55 L 540 40"
            stroke="#f5a623"
            strokeWidth="1.5"
            strokeDasharray="6 4"
            fill="none"
            opacity="0.7"
            filter="url(#amberGlow)"
          />
          <text x="490" y="36" fill="#f5a623" fontSize="9" fontFamily="JetBrains Mono" opacity="0.8">
            ⚠ DEADLINE_TRAP
          </text>

          {/* Risk path 2 — crimson — "Ambiguous Qualifier" */}
          <path
            d="M 300 130 C 360 130 380 190 430 210 L 560 220"
            stroke="#ff3a3a"
            strokeWidth="1.5"
            strokeDasharray="6 4"
            fill="none"
            opacity="0.6"
            filter="url(#amberGlow)"
          />
          <text x="490" y="235" fill="#ff3a3a" fontSize="9" fontFamily="JetBrains Mono" opacity="0.8">
            ✕ AMBIGUOUS_QUALIFIER
          </text>

          {/* Risk path 3 — amber — "Oracle Delay" */}
          <path
            d="M 480 130 C 520 130 540 90 570 80 L 640 72"
            stroke="#f5a623"
            strokeWidth="1"
            strokeDasharray="4 6"
            fill="none"
            opacity="0.5"
          />
          <text x="580" y="68" fill="#f5a623" fontSize="8" fontFamily="JetBrains Mono" opacity="0.6">
            ORACLE_DELAY
          </text>

          {/* LIVE indicator */}
          <circle cx={300} cy={130} r={20} fill="none" stroke={CYAN} strokeWidth="0.5" opacity="0.3"
            style={{ animation: 'sonarPing 2s ease-out infinite' }} />
          <circle cx={300} cy={130} r={30} fill="none" stroke={CYAN} strokeWidth="0.5" opacity="0.2"
            style={{ animation: 'sonarPing 2s ease-out infinite', animationDelay: '0.5s' }} />
        </svg>
      </div>
    </div>
  )
}

// ─── Hero ─────────────────────────────────────────────────────────────────────
function Hero({ onRunSim }: { onRunSim: () => void }) {
  const [text, setText] = useState('')
  const full = '> INITIALIZING_SIMULATION_LAYER [BETAUDIT.v1]'

  useEffect(() => {
    let i = 0
    const interval = setInterval(() => {
      i++
      setText(full.slice(0, i))
      if (i >= full.length) clearInterval(interval)
    }, 38)
    return () => clearInterval(interval)
  }, [])

  return (
    <section
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        paddingTop: 64,
        padding: '100px 32px 80px',
        position: 'relative',
        zIndex: 1,
      }}
    >
      {/* Status badge */}
      <div
        style={{
          marginBottom: 32,
          padding: '6px 16px',
          border: `1px solid ${CYAN_BORDER}`,
          borderRadius: 2,
          background: CYAN_DIM,
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 11,
          color: 'rgba(102,204,204,0.7)',
          letterSpacing: '0.15em',
        }}
      >
        OKX_AI_MARKETPLACE :: A2MCP_ENABLED :: SIM_NODE_ACTIVE
      </div>

      {/* Main headline */}
      <h1
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 'clamp(16px, 2.8vw, 32px)',
          color: CYAN,
          textShadow: `0 0 10px ${CYAN_GLOW}, 0 0 40px rgba(102,204,204,0.3)`,
          letterSpacing: '0.05em',
          marginBottom: 8,
          minHeight: '1.4em',
        }}
      >
        {text}
        <span className="cursor-blink" style={{ color: CYAN }}>_</span>
      </h1>

      <p
        style={{
          fontFamily: "'Space Grotesk', sans-serif",
          fontSize: 'clamp(14px, 1.8vw, 20px)',
          color: 'rgba(102,204,204,0.5)',
          marginBottom: 56,
          maxWidth: 600,
          textAlign: 'center',
          lineHeight: 1.6,
        }}
      >
        AI-native pre-trade simulation terminal. Stress-test resolution paths before committing capital.
      </p>

      {/* Timeline viz */}
      <div
        style={{
          width: '100%',
          maxWidth: 760,
          marginBottom: 52,
          padding: 24,
          borderRadius: 4,
          position: 'relative',
          overflow: 'hidden',
        }}
        className="glass-panel"
      >
        <div className="scan-line" />
        <div
          style={{
            position: 'absolute',
            top: 8,
            left: 12,
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 9,
            color: 'rgba(102,204,204,0.4)',
            letterSpacing: '0.15em',
          }}
        >
          TIMELINE_VIZ :: ORACLE_PATH_ANALYSIS
        </div>
        <div style={{ marginTop: 16 }}>
          <TimelineViz />
        </div>

        {/* Legend */}
        <div style={{ display: 'flex', gap: 24, marginTop: 8, justifyContent: 'center' }}>
          {[
            { color: CYAN, label: 'ORACLE_PATH' },
            { color: '#f5a623', label: 'DEADLINE_RISK' },
            { color: '#ff3a3a', label: 'ABORT_RISK' },
          ].map(({ color, label }) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ width: 20, height: 2, background: color, boxShadow: `0 0 4px ${color}` }} />
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: 'rgba(102,204,204,0.5)' }}>
                {label}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* CTA */}
      <button
        className="cyan-btn"
        onClick={onRunSim}
        style={{
          padding: '18px 48px',
          fontSize: 15,
          letterSpacing: '0.12em',
          borderRadius: 2,
          fontWeight: 600,
          animation: 'glowPulse 3s ease-in-out infinite',
        }}
      >
        [ RUN_ACTIVE_MARKET_SIMULATION ]
      </button>

      {/* Sub-label */}
      <div
        style={{
          marginTop: 16,
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 10,
          color: 'rgba(102,204,204,0.35)',
          letterSpacing: '0.1em',
        }}
      >
        powered by UMA_ORACLE :: POLYMARKET_DATA :: OKX_A2MCP
      </div>
    </section>
  )
}

// ─── Sonar Widget ─────────────────────────────────────────────────────────────
function SonarWidget({
  title,
  label,
  color = CYAN,
  children,
}: {
  title: string
  label: string
  color?: string
  children: React.ReactNode
}) {
  return (
    <div
      className="glass-panel"
      style={{
        borderRadius: 4,
        padding: 28,
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div className="scan-line" />
      <div
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 9,
          color: `${color}80`,
          letterSpacing: '0.2em',
        }}
      >
        {label}
      </div>
      <div style={{ display: 'flex', justifyContent: 'center' }}>{children}</div>
      <div
        style={{
          fontFamily: "'Space Grotesk', sans-serif",
          fontSize: 15,
          fontWeight: 600,
          color,
          textShadow: `0 0 10px ${color}80`,
          textAlign: 'center',
        }}
      >
        {title}
      </div>
    </div>
  )
}

// ─── Timeline Sonar ───────────────────────────────────────────────────────────
function TimelineSonar() {
  const blips = [
    { angle: 45, r: 60, color: '#f5a623' },
    { angle: 120, r: 80, color: CYAN },
    { angle: 200, r: 50, color: '#ff3a3a' },
    { angle: 290, r: 70, color: CYAN },
  ]
  const cx = 90, cy = 90, r = 80

  return (
    <svg width={180} height={180} viewBox="0 0 180 180">
      {/* rings */}
      {[80, 60, 40, 20].map((radius) => (
        <circle key={radius} cx={cx} cy={cy} r={radius} stroke={CYAN} strokeWidth="0.5" fill="none" opacity="0.2" />
      ))}
      {/* crosshairs */}
      <line x1={cx} y1={cy - r} x2={cx} y2={cy + r} stroke={CYAN} strokeWidth="0.5" opacity="0.2" />
      <line x1={cx - r} y1={cy} x2={cx + r} y2={cy} stroke={CYAN} strokeWidth="0.5" opacity="0.2" />

      {/* sweep gradient */}
      <defs>
        <radialGradient id="sweepGrad" cx="0%" cy="0%" r="100%">
          <stop offset="0%" stopColor={CYAN} stopOpacity="0.3" />
          <stop offset="100%" stopColor={CYAN} stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* sweep arm */}
      <g style={{ transformOrigin: `${cx}px ${cy}px`, animation: 'sonarSweep 3s linear infinite' }}>
        <line x1={cx} y1={cy} x2={cx} y2={cy - r} stroke={CYAN} strokeWidth="1.5" opacity="0.8"
          style={{ filter: `drop-shadow(0 0 4px ${CYAN_GLOW})` }} />
        <path
          d={`M${cx},${cy} L${cx},${cy - r} A${r},${r} 0 0,1 ${cx + r * Math.sin(Math.PI / 6)},${cy - r * Math.cos(Math.PI / 6)} Z`}
          fill={CYAN}
          opacity="0.05"
        />
      </g>

      {/* blips */}
      {blips.map((b, i) => {
        const rad = (b.angle * Math.PI) / 180
        const bx = cx + b.r * Math.sin(rad)
        const by = cy - b.r * Math.cos(rad)
        return (
          <circle key={i} cx={bx} cy={by} r={3} fill={b.color}
            style={{ filter: `drop-shadow(0 0 4px ${b.color})`, animation: `sonarPing 2s ease-out infinite`, animationDelay: `${i * 0.5}s` }} />
        )
      })}

      {/* center */}
      <circle cx={cx} cy={cy} r={4} fill={CYAN} style={{ filter: `drop-shadow(0 0 6px ${CYAN_GLOW})` }} />
    </svg>
  )
}

// ─── Semantic Parser ──────────────────────────────────────────────────────────
function SemanticParser() {
  const words = [
    { text: 'EOD', risk: 82, x: 50, y: 30, size: 16 },
    { text: 'merger', risk: 45, x: 110, y: 55, size: 12 },
    { text: 'prior to', risk: 71, x: 25, y: 80, size: 13 },
    { text: 'settled', risk: 30, x: 90, y: 105, size: 11 },
    { text: 'subject to', risk: 88, x: 45, y: 130, size: 14 },
    { text: 'announced', risk: 55, x: 105, y: 145, size: 12 },
    { text: 'deadline', risk: 91, x: 20, y: 155, size: 15 },
    { text: 'or earlier', risk: 76, x: 75, y: 25, size: 11 },
  ]
  const riskColor = (r: number) =>
    r > 75 ? '#ff3a3a' : r > 50 ? '#f5a623' : CYAN

  return (
    <div style={{ position: 'relative', width: 180, height: 180 }}>
      {words.map((w, i) => (
        <div
          key={i}
          style={{
            position: 'absolute',
            left: w.x,
            top: w.y,
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: w.size,
            color: riskColor(w.risk),
            textShadow: `0 0 8px ${riskColor(w.risk)}80`,
            animation: `wordFloat ${1.5 + i * 0.4}s ease-in-out infinite`,
            animationDelay: `${i * 0.3}s`,
            fontWeight: w.risk > 70 ? 700 : 400,
          }}
        >
          {w.text}
          <sup style={{ fontSize: 7, opacity: 0.6 }}>{w.risk}</sup>
        </div>
      ))}
    </div>
  )
}

// ─── Cross-Chain Bridge ───────────────────────────────────────────────────────
function CrossChainBridge() {
  return (
    <svg width={200} height={180} viewBox="0 0 200 180">
      <defs>
        <linearGradient id="streamGrad1" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor={CYAN} stopOpacity="0.8" />
          <stop offset="100%" stopColor={CYAN} stopOpacity="0.1" />
        </linearGradient>
        <linearGradient id="streamGrad2" x1="100%" y1="0%" x2="0%" y2="0%">
          <stop offset="0%" stopColor="#f5a623" stopOpacity="0.8" />
          <stop offset="100%" stopColor="#f5a623" stopOpacity="0.1" />
        </linearGradient>
      </defs>

      {/* Binding-rules stream */}
      <text x="10" y="45" fill={CYAN} fontSize="8" fontFamily="JetBrains Mono" opacity="0.7">RULES</text>
      <rect x="10" y="52" width="75" height="18" rx="2" fill="none" stroke={CYAN} strokeWidth="0.8" opacity="0.4" />
      <rect x="10" y="52" width="75" height="18" rx="2" fill="url(#streamGrad1)" opacity="0.15" />
      {[0, 1, 2].map((i) => (
        <rect key={i} x={14 + i * 22} y="57" width={14} height="8" rx="1" fill={CYAN} opacity="0.4"
          style={{ animation: `streamParticle 2s linear infinite`, animationDelay: `${i * 0.6}s` }} />
      ))}

      {/* Headline-thesis stream */}
      <text x="115" y="45" fill="#f5a623" fontSize="8" fontFamily="JetBrains Mono" opacity="0.7">THESIS</text>
      <rect x="115" y="52" width="75" height="18" rx="2" fill="none" stroke="#f5a623" strokeWidth="0.8" opacity="0.4" />
      <rect x="115" y="52" width="75" height="18" rx="2" fill="url(#streamGrad2)" opacity="0.15" />
      {[0, 1, 2].map((i) => (
        <rect key={i} x={119 + i * 22} y="57" width={14} height="8" rx="1" fill="#f5a623" opacity="0.4"
          style={{ animation: `streamParticle 2.5s linear infinite`, animationDelay: `${i * 0.7}s` }} />
      ))}

      {/* Gap marker */}
      <rect x="88" y="44" width="24" height="34" rx="2"
        fill="rgba(255,58,58,0.08)" stroke="#ff3a3a" strokeWidth="1" strokeDasharray="3 2" />
      <text x="100" y="65" fill="#ff3a3a" fontSize="7" fontFamily="JetBrains Mono" textAnchor="middle" opacity="0.9">GAP</text>

      {/* Risk label */}
      <text x="100" y="110" fill="#ff3a3a" fontSize="8" fontFamily="JetBrains Mono" textAnchor="middle">
        RESOLUTION_RISK
      </text>
      <line x1="60" y1="80" x2="100" y2="100" stroke="#ff3a3a" strokeWidth="0.8" strokeDasharray="3 2" opacity="0.6" />
      <line x1="140" y1="80" x2="100" y2="100" stroke="#ff3a3a" strokeWidth="0.8" strokeDasharray="3 2" opacity="0.6" />

      {/* Bottom stream arrows */}
      <text x="10" y="140" fill={CYAN} fontSize="7" fontFamily="JetBrains Mono" opacity="0.5">RESOLUTION_TEXT</text>
      <text x="128" y="140" fill="#f5a623" fontSize="7" fontFamily="JetBrains Mono" opacity="0.5">HEADLINE</text>

      <path d="M40 125 L40 130 L100 130 L100 125" stroke={CYAN} strokeWidth="0.8" fill="none" opacity="0.4" />
      <path d="M160 125 L160 130 L100 130" stroke="#f5a623" strokeWidth="0.8" fill="none" opacity="0.4" />
    </svg>
  )
}

// ─── Stress Test Section ──────────────────────────────────────────────────────
function StressTests() {
  return (
    <section
      style={{
        padding: '80px 32px',
        maxWidth: 1100,
        margin: '0 auto',
        position: 'relative',
        zIndex: 1,
      }}
    >
      <div style={{ textAlign: 'center', marginBottom: 48 }}>
        <div
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 11,
            color: 'rgba(102,204,204,0.5)',
            letterSpacing: '0.2em',
            marginBottom: 12,
          }}
        >
          // HOW_IT_WORKS
        </div>
        <h2
          style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 'clamp(24px, 3vw, 36px)',
            fontWeight: 700,
            color: CYAN,
            textShadow: `0 0 20px ${CYAN_GLOW}`,
          }}
        >
          How BetAudit Audits a Market
        </h2>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: 24,
        }}
      >
        <SonarWidget title="1 · Read the real rules" label="STEP_01 :: POLYMARKET_GAMMA">
          <TimelineSonar />
        </SonarWidget>

        <SonarWidget title="2 · Audit the clauses" label="STEP_02 :: LLM_GROUNDED" color="#f5a623">
          <SemanticParser />
        </SonarWidget>

        <SonarWidget title="3 · Score the gap" label="STEP_03 :: RULES_VS_THESIS" color={CYAN}>
          <CrossChainBridge />
        </SonarWidget>
      </div>

      {/* Descriptions — accurate to what the engine actually does */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: 24,
          marginTop: 16,
        }}
      >
        {[
          {
            label: "Pulls the market's real resolution criteria, oracle type, challenge window, and live oracle state straight from Polymarket's Gamma API.",
            color: CYAN,
          },
          {
            label: 'An LLM reads the exact resolution text and surfaces concrete mismatches between the binding rules and a naive headline thesis.',
            color: '#f5a623',
          },
          {
            label: 'Returns a 0–100 resolution risk score and a PROCEED / CAUTION / ABORT_TRADE verdict — the gap between what the rules require and the headline read.',
            color: CYAN,
          },
        ].map(({ label, color }, i) => (
          <p
            key={i}
            style={{
              fontFamily: "'Space Grotesk', sans-serif",
              fontSize: 13,
              color: `${color}80`,
              lineHeight: 1.6,
              textAlign: 'center',
            }}
          >
            {label}
          </p>
        ))}
      </div>
    </section>
  )
}

// ─── Terminal Console ─────────────────────────────────────────────────────────
type LogLine = { prefix: string; text: string; color: string }

type Verdict =
  | { kind: 'safe' | 'caution' | 'abort'; score: number; confidence: number; summary: string }
  | { kind: 'error'; message: string; code: string }
  | null

// Map the backend action to the on-screen verdict.
function verdictFrom(res: VerifyResponse): Exclude<Verdict, null> {
  const kind = res.action === 'ABORT_TRADE' ? 'abort' : res.action === 'CAUTION' ? 'caution' : 'safe'
  return { kind, score: res.resolution_risk_score, confidence: res.confidence, summary: res.summary }
}

function shortUrl(u: string): string {
  return u.length > 52 ? u.slice(0, 49) + '...' : u
}

function ConsoleSection({ onSimRun }: { onSimRun?: boolean }) {
  const [input, setInput] = useState('')
  const [logs, setLogs] = useState<LogLine[]>([])
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<Verdict>(null)
  const logRef = useRef<HTMLDivElement>(null)
  const runningRef = useRef(false)

  const push = (prefix: string, text: string, color: string) =>
    setLogs((prev) => [...prev, { prefix, text, color }])

  const runSim = useCallback(async () => {
    if (runningRef.current) return
    const url = input.trim()
    runningRef.current = true
    setRunning(true)
    setResult(null)
    setLogs([])

    if (!url) {
      push('[SYS]', 'Paste a Polymarket market URL to run a live simulation.', AMBER)
      runningRef.current = false
      setRunning(false)
      return
    }

    push('[SYS]', 'Establishing secure channel to OKX_A2MCP...', CYAN)
    await sleep(450)
    push('[SIM]', `Submitting ${shortUrl(url)} to Resolution Layer...`, CYAN)
    await sleep(400)
    push('[SIM]', 'Resolving market via Polymarket Gamma + reading real rules...', CYAN)

    try {
      const res = await verifyMarket(url, 'YES')
      const pc = res.parsed_contract_data

      await sleep(300)
      push(
        '[PARSE]',
        `oracle=${pc.oracle_type} :: window=${pc.challenge_window_hours ?? '?'}h :: state=${pc.current_oracle_state}`,
        CYAN,
      )
      if (pc.source_of_truth_specified) {
        await sleep(300)
        push('[PARSE]', `binding source_of_truth = '${pc.source_of_truth_specified}'`, AMBER)
      }
      for (const m of res.rule_mismatches_detected) {
        await sleep(280)
        push('[RISK]', `mismatch: ${m.conflict_reason}`, CRIMSON)
      }
      await sleep(300)
      const scoreColor = res.resolution_risk_score >= 70 ? CRIMSON : res.resolution_risk_score >= 35 ? AMBER : CYAN
      push(
        '[RISK]',
        `resolution_risk_score = ${res.resolution_risk_score} :: confidence = ${res.confidence.toFixed(2)}`,
        scoreColor,
      )
      await sleep(300)
      push('[SIM]', `verdict: ${res.action} :: ${res.summary}`, scoreColor)
      setResult(verdictFrom(res))
    } catch (err) {
      const message = err instanceof ApiError ? err.message : `Network error: ${String(err)}`
      const code = err instanceof ApiError ? err.code : 'NETWORK'
      await sleep(200)
      push('[ERR]', `${code} — ${message}`, CRIMSON)
      setResult({ kind: 'error', message, code })
    } finally {
      runningRef.current = false
      setRunning(false)
    }
  }, [input])

  useEffect(() => {
    if (onSimRun) runSim()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onSimRun])

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [logs])

  return (
    <section
      id="console"
      style={{
        padding: '80px 32px',
        maxWidth: 900,
        margin: '0 auto',
        position: 'relative',
        zIndex: 1,
      }}
    >
      <div style={{ textAlign: 'center', marginBottom: 40 }}>
        <div
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 11,
            color: 'rgba(102,204,204,0.5)',
            letterSpacing: '0.2em',
            marginBottom: 12,
          }}
        >
          // LIVE_CLERK_SANDBOX
        </div>
        <h2
          style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 'clamp(24px, 3vw, 36px)',
            fontWeight: 700,
            color: CYAN,
            textShadow: `0 0 20px ${CYAN_GLOW}`,
          }}
        >
          Simulation Terminal
        </h2>
      </div>

      <div
        className="glass-panel"
        style={{
          borderRadius: 4,
          overflow: 'hidden',
        }}
      >
        {/* Terminal header */}
        <div
          style={{
            padding: '10px 16px',
            borderBottom: `1px solid ${CYAN_BORDER}`,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          {['#ff3a3a', '#f5a623', CYAN].map((c) => (
            <div key={c} style={{ width: 8, height: 8, borderRadius: '50%', background: c, opacity: 0.7 }} />
          ))}
          <span
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 11,
              color: 'rgba(102,204,204,0.4)',
              marginLeft: 8,
              letterSpacing: '0.1em',
            }}
          >
            BetAudit :: verify_resolution_rules :: LIVE
          </span>
        </div>

        {/* Log output */}
        <div
          ref={logRef}
          style={{
            height: 280,
            overflowY: 'auto',
            padding: '16px 20px',
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 12,
            lineHeight: 1.8,
          }}
        >
          {logs.length === 0 && !running && (
            <div style={{ color: 'rgba(102,204,204,0.45)' }}>
              <div style={{ fontStyle: 'italic', color: 'rgba(102,204,204,0.3)' }}>
                // Paste a Polymarket market URL below to run a live audit.
              </div>
              <div style={{ marginTop: 10 }}>
                <span style={{ opacity: 0.5 }}>try an example → </span>
                <button
                  onClick={() => setInput(EXAMPLE_MARKET)}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: CYAN,
                    cursor: 'pointer',
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 12,
                    textShadow: `0 0 8px ${CYAN_GLOW}`,
                    padding: 0,
                    textDecoration: 'underline',
                  }}
                >
                  new-rhianna-album-before-gta-vi
                </button>
              </div>
            </div>
          )}
          {logs.map((log, i) => (
            <div
              key={i}
              style={{
                color: log.color,
                textShadow: `0 0 6px ${log.color}60`,
                animation: 'fadeInUp 0.3s ease-out forwards',
              }}
            >
              <span style={{ opacity: 0.5 }}>{log.prefix}</span>{' '}
              <span>{log.text}</span>
            </div>
          ))}
          {running && (
            <div style={{ color: CYAN, opacity: 0.5 }}>
              <span className="cursor-blink">▋</span>
            </div>
          )}
        </div>

        {/* Input */}
        <div
          style={{
            borderTop: `1px solid ${CYAN_BORDER}`,
            padding: '12px 20px',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
          }}
        >
          <span
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 13,
              color: CYAN,
              textShadow: `0 0 8px ${CYAN_GLOW}`,
              flexShrink: 0,
            }}
          >
            BetAudit&gt;
          </span>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && runSim()}
            placeholder="Paste a Polymarket market URL and press Enter"
            disabled={running}
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 13,
              color: CYAN,
              caretColor: CYAN,
            }}
          />
          <button
            className="cyan-btn"
            onClick={runSim}
            disabled={running}
            style={{
              padding: '6px 16px',
              fontSize: 11,
              letterSpacing: '0.1em',
              opacity: running ? 0.4 : 1,
            }}
          >
            {running ? '[ RUNNING... ]' : '[ SUBMIT ]'}
          </button>
        </div>
      </div>

      {/* Result Badge */}
      {result && (() => {
        const color =
          result.kind === 'safe' ? CYAN : result.kind === 'caution' ? AMBER : CRIMSON
        const rgb =
          result.kind === 'safe' ? '102,204,204' : result.kind === 'caution' ? '245,166,35' : '255,58,58'
        const label =
          result.kind === 'safe'
            ? 'SAFE_TO_BET'
            : result.kind === 'caution'
              ? 'CAUTION_ADVISED'
              : result.kind === 'abort'
                ? 'ABORT_BET'
                : 'SIM_ERROR'
        const sub =
          result.kind === 'error'
            ? result.message
            : `confidence: ${(result.confidence * 100).toFixed(0)}% :: risk_score: ${result.score}`
        return (
          <div
            style={{
              marginTop: 40,
              display: 'flex',
              justifyContent: 'center',
              animation: 'badgeFloat 3s ease-in-out infinite, fadeInUp 0.5s ease-out',
            }}
          >
            <div
              style={{
                padding: '24px 56px',
                borderRadius: 4,
                maxWidth: 560,
                border: `2px solid ${color}`,
                background: `rgba(${rgb},0.08)`,
                boxShadow: `0 0 40px rgba(${rgb},0.4), 0 0 80px rgba(${rgb},0.15)`,
                textAlign: 'center',
                transform: 'perspective(400px) rotateX(8deg)',
              }}
            >
              <div
                style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 9,
                  letterSpacing: '0.3em',
                  color: `rgba(${rgb},0.6)`,
                  marginBottom: 8,
                }}
              >
                SIMULATION_RESULT
              </div>
              <div
                style={{
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: 28,
                  fontWeight: 700,
                  color,
                  textShadow: `0 0 20px rgba(${rgb},0.9), 0 0 60px rgba(${rgb},0.4)`,
                  letterSpacing: '0.1em',
                }}
              >
                {label}
              </div>
              <div
                style={{
                  marginTop: 8,
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 10,
                  color: `rgba(${rgb},0.6)`,
                  lineHeight: 1.5,
                }}
              >
                {sub}
              </div>
            </div>
          </div>
        )
      })()}
    </section>
  )
}

// ─── Node Graph ───────────────────────────────────────────────────────────────
function NodeGraph() {
  const orbitNodes = [
    { label: 'Polymarket', sublabel: 'MARKET_DATA', color: CYAN, delay: '0s' },
    { label: 'UMA Oracle', sublabel: 'SETTLEMENT', color: '#f5a623', delay: '-5s' },
    { label: 'OKX A2MCP', sublabel: 'A2MCP_PAY_CALL', color: CYAN, delay: '-10s' },
  ]

  return (
    <section
      style={{
        padding: '80px 32px',
        position: 'relative',
        zIndex: 1,
        textAlign: 'center',
      }}
    >
      <div
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 11,
          color: 'rgba(102,204,204,0.5)',
          letterSpacing: '0.2em',
          marginBottom: 12,
        }}
      >
        // MARKETPLACE_NODE_NETWORK
      </div>
      <h2
        style={{
          fontFamily: "'Space Grotesk', sans-serif",
          fontSize: 'clamp(24px, 3vw, 36px)',
          fontWeight: 700,
          color: CYAN,
          textShadow: `0 0 20px ${CYAN_GLOW}`,
          marginBottom: 60,
        }}
      >
        Protocol Integration Layer
      </h2>

      <div style={{ position: 'relative', width: 360, height: 360, margin: '0 auto' }}>
        {/* Orbit ring */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            borderRadius: '50%',
            border: `1px solid ${CYAN_BORDER}`,
            boxShadow: `0 0 20px rgba(102,204,204,0.05)`,
          }}
        />
        <div
          style={{
            position: 'absolute',
            inset: 40,
            borderRadius: '50%',
            border: `1px dashed rgba(102,204,204,0.1)`,
          }}
        />

        {/* Center node */}
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            width: 90,
            height: 90,
            borderRadius: '50%',
            background: GLASS,
            border: `2px solid ${CYAN}`,
            boxShadow: `0 0 30px rgba(102,204,204,0.5), 0 0 60px rgba(102,204,204,0.2)`,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 2,
            overflow: 'hidden',
          }}
        >
          <ShieldLogo size={82} />
        </div>

        {/* Orbiting nodes */}
        {orbitNodes.map((node, i) => (
          <div
            key={i}
            style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transformOrigin: '0 0',
              animation: `nodeOrbit${i + 1} 15s linear infinite`,
              animationDelay: node.delay,
            }}
          >
            <div
              style={{
                transform: 'translate(-50%, -50%)',
                width: 72,
                height: 72,
                borderRadius: '50%',
                background: GLASS,
                border: `1.5px solid ${node.color}60`,
                boxShadow: `0 0 16px ${node.color}40`,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'default',
              }}
            >
              <div
                style={{
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: 9,
                  fontWeight: 700,
                  color: node.color,
                  textShadow: `0 0 8px ${node.color}80`,
                }}
              >
                {node.label}
              </div>
              <div
                style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 6,
                  color: `${node.color}60`,
                  letterSpacing: '0.05em',
                }}
              >
                {node.sublabel}
              </div>
            </div>
          </div>
        ))}

        {/* Data pipe SVG behind nodes */}
        <svg
          style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 1 }}
          width="360"
          height="360"
          viewBox="0 0 360 360"
        >
          {[0, 120, 240].map((angle) => {
            const rad = (angle * Math.PI) / 180
            const x2 = 180 + 140 * Math.sin(rad)
            const y2 = 180 - 140 * Math.cos(rad)
            return (
              <line
                key={angle}
                x1="180" y1="180"
                x2={x2} y2={y2}
                stroke={CYAN}
                strokeWidth="1"
                strokeDasharray="6 4"
                opacity="0.25"
              />
            )
          })}
        </svg>
      </div>

      <p
        style={{
          marginTop: 40,
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 11,
          color: 'rgba(102,204,204,0.4)',
          letterSpacing: '0.1em',
        }}
      >
        A2MCP :: pay-per-call settlement :: fully autonomous agent compatible
      </p>
    </section>
  )
}

// ─── Footer ───────────────────────────────────────────────────────────────────
function Footer() {
  const links = [
    { label: '[ github ]', href: REPO_URL, external: true },
    { label: '[ docs ]', href: DOCS_URL, external: false },
    { label: '[ api ]', href: API_DOCS_URL, external: false },
    { label: '[ health ]', href: '/health', external: false },
  ]

  return (
    <footer
      style={{
        borderTop: `1px solid ${CYAN_BORDER}`,
        padding: '40px 32px',
        position: 'relative',
        zIndex: 1,
        background: 'rgba(0,0,0,0.6)',
      }}
    >
      <div
        style={{
          maxWidth: 900,
          margin: '0 auto',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 20,
        }}
      >
        <div
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 13,
            color: CYAN,
            textShadow: `0 0 8px ${CYAN_GLOW}`,
            letterSpacing: '0.05em',
          }}
        >
          // betaudit.onrender.com :: Pre-Trade Resolution Auditor
        </div>

        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', justifyContent: 'center' }}>
          {links.map(({ label, href, external }) => (
            <a
              key={label}
              href={href}
              className="nav-link"
              style={{ fontSize: 12 }}
              {...(external ? { target: '_blank', rel: 'noreferrer' } : {})}
            >
              {label}
            </a>
          ))}
        </div>

        <div
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 10,
            color: 'rgba(102,204,204,0.25)',
            letterSpacing: '0.1em',
          }}
        >
          © 2026 BetAudit :: MIT License :: OKX AI Marketplace · Agent #6141
        </div>
      </div>
    </footer>
  )
}

// ─── Live Audit Feed ──────────────────────────────────────────────────────────
type FeedItem = {
  request_id: string
  market_url: string
  action: string
  resolution_risk_score: number
  oracle_state: string
  summary?: string
}

function LiveAuditFeed() {
  const [items, setItems] = useState<FeedItem[]>([])
  const [status, setStatus] = useState<'connecting' | 'live' | 'offline'>('connecting')

  useEffect(() => {
    let stopped = false
    let retry: number | undefined
    let ws: WebSocket | null = null

    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${location.host}/ws/audits`)
      ws.onopen = () => setStatus('live')
      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data)
          if (data.type === 'info') {
            setStatus('offline')
            return
          }
          setItems((prev) => [data as FeedItem, ...prev].slice(0, 8))
        } catch {
          /* ignore malformed frame */
        }
      }
      ws.onclose = () => {
        if (stopped) return
        setStatus('connecting')
        retry = window.setTimeout(connect, 2500)
      }
      ws.onerror = () => ws?.close()
    }
    connect()
    return () => {
      stopped = true
      if (retry) clearTimeout(retry)
      ws?.close()
    }
  }, [])

  const color = (a: string) => (a === 'ABORT_TRADE' ? CRIMSON : a === 'CAUTION' ? AMBER : CYAN)
  const label = (a: string) => (a === 'ABORT_TRADE' ? 'ABORT' : a === 'CAUTION' ? 'CAUTION' : 'PROCEED')
  const statusColor = status === 'live' ? CYAN : status === 'connecting' ? AMBER : 'rgba(102,204,204,0.4)'

  return (
    <section style={{ padding: '40px 32px 80px', maxWidth: 900, margin: '0 auto', position: 'relative', zIndex: 1 }}>
      <div style={{ textAlign: 'center', marginBottom: 28 }}>
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: 'rgba(102,204,204,0.5)', letterSpacing: '0.2em', marginBottom: 12 }}>
          // LIVE_AUDIT_STREAM
        </div>
        <h2 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 'clamp(20px, 2.4vw, 30px)', fontWeight: 700, color: CYAN, textShadow: `0 0 20px ${CYAN_GLOW}` }}>
          Global Simulation Feed
        </h2>
      </div>

      <div className="glass-panel" style={{ borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ padding: '10px 16px', borderBottom: `1px solid ${CYAN_BORDER}`, display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 7, height: 7, borderRadius: '50%', background: statusColor, boxShadow: `0 0 8px ${statusColor}`, animation: 'glowPulse 2s ease-in-out infinite' }} />
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: 'rgba(102,204,204,0.5)', letterSpacing: '0.1em' }}>
            pubsub:live_audits :: {status.toUpperCase()}
          </span>
        </div>

        <div style={{ padding: '12px 20px', minHeight: 180, fontFamily: "'JetBrains Mono', monospace", fontSize: 12, lineHeight: 2 }}>
          {items.length === 0 && (
            <div style={{ color: 'rgba(102,204,204,0.3)', fontStyle: 'italic' }}>
              {status === 'offline'
                ? '// live feed offline — Redis not configured on this instance'
                : '// waiting for agents to run simulations across the network...'}
            </div>
          )}
          {items.map((it, i) => (
            <div key={it.request_id + i} style={{ display: 'flex', gap: 12, alignItems: 'baseline', animation: 'fadeInUp 0.3s ease-out' }}>
              <span style={{ color: color(it.action), fontWeight: 700, minWidth: 66, textShadow: `0 0 8px ${color(it.action)}80` }}>
                {label(it.action)}
              </span>
              <span style={{ color: color(it.action), opacity: 0.8, minWidth: 34 }}>{it.resolution_risk_score}</span>
              <span style={{ color: 'rgba(102,204,204,0.45)', minWidth: 92 }}>{it.oracle_state}</span>
              <span style={{ color: 'rgba(102,204,204,0.6)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {shortUrl(it.market_url)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── App ──────────────────────────────────────────────────────────────────────
export default function App() {
  const [simTriggered, setSimTriggered] = useState(false)

  const handleRunSim = () => {
    setSimTriggered(true)
    document.getElementById('console')?.scrollIntoView({ behavior: 'smooth' })
    setTimeout(() => setSimTriggered(false), 100)
  }

  return (
    <div style={{ background: '#000', minHeight: '100vh', position: 'relative' }}>
      {/* Global grid overlay */}
      <div className="grid-overlay" />

      {/* Radial ambient glow */}
      <div
        style={{
          position: 'fixed',
          top: '30%',
          left: '50%',
          transform: 'translateX(-50%)',
          width: '60vw',
          height: '60vw',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(102,204,204,0.04) 0%, transparent 70%)',
          pointerEvents: 'none',
          zIndex: 0,
        }}
      />

      <Nav />

      <main>
        <Hero onRunSim={handleRunSim} />
        <StressTests />
        <ConsoleSection onSimRun={simTriggered} />
        <LiveAuditFeed />
        <NodeGraph />
      </main>

      <Footer />
    </div>
  )
}
