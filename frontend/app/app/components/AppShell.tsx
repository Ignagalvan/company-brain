'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useState } from 'react'

// ─── Icons ────────────────────────────────────────────────────────────────────

function IconMenu() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="12" x2="21" y2="12" />
      <line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  )
}

function IconX() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}

function IconChat({ active }: { active: boolean }) {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={active ? '2.2' : '1.8'} strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  )
}

function IconGaps({ active }: { active: boolean }) {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={active ? '2.2' : '1.8'} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  )
}

function IconFile() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  )
}

function IconAnalytics() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  )
}

function IconSettings() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14" />
    </svg>
  )
}

// ─── Nav config ───────────────────────────────────────────────────────────────

const NAV_ITEMS = [
  { href: '/app', label: 'Chat', icon: IconChat, exact: true },
  { href: '/dashboard/improvement', label: 'Knowledge Gaps', icon: IconGaps, exact: false },
  { href: '/documents', label: 'Documents', icon: IconFile, exact: false },
  { href: '/optimize', label: 'Optimize', icon: IconAnalytics, exact: false },
] as const

const COMING_SOON = [
  { label: 'Configuración', icon: IconSettings },
]

// ─── Sub-components ───────────────────────────────────────────────────────────

function NavList({
  isActive,
  onNavigate,
}: {
  isActive: (item: typeof NAV_ITEMS[number]) => boolean
  onNavigate?: () => void
}) {
  return (
    <div className="space-y-0.5">
      {NAV_ITEMS.map(item => {
        const active = isActive(item)
        const Icon = item.icon
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            className={[
              'flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-[15px] font-medium transition-colors',
              active
                ? 'bg-slate-100 text-slate-900'
                : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800',
            ].join(' ')}
          >
            <span className={active ? 'text-slate-800' : 'text-slate-400'}>
              <Icon active={active} />
            </span>
            {item.label}
          </Link>
        )
      })}
    </div>
  )
}

// ─── AppShell ─────────────────────────────────────────────────────────────────

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  function isActive(item: typeof NAV_ITEMS[number]) {
    return item.exact ? pathname === item.href : pathname.startsWith(item.href)
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden bg-slate-50">

      {/* Mobile top bar */}
      <header className="md:hidden shrink-0 h-14 bg-white border-b border-slate-100 flex items-center px-4 gap-3 z-30 relative">
        <button
          onClick={() => setMobileMenuOpen(v => !v)}
          className="w-9 h-9 flex items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 active:bg-slate-200 transition-colors"
          aria-label="Abrir menú"
        >
          {mobileMenuOpen ? <IconX /> : <IconMenu />}
        </button>
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-slate-900 flex items-center justify-center shrink-0">
            <span className="text-white text-[10px] font-bold leading-none">CB</span>
          </div>
          <span className="text-sm font-semibold text-slate-900">Company Brain</span>
        </div>
      </header>

      {/* Mobile nav overlay */}
      {mobileMenuOpen && (
        <>
          <div
            className="md:hidden fixed inset-0 top-14 z-20 bg-black/20"
            onClick={() => setMobileMenuOpen(false)}
          />
          <nav className="md:hidden fixed left-0 top-14 bottom-0 w-56 z-30 bg-white border-r border-slate-100 flex flex-col py-4 px-3 shadow-xl">
            <NavList isActive={isActive} onNavigate={() => setMobileMenuOpen(false)} />
          </nav>
        </>
      )}

      {/* Desktop layout */}
      <div className="flex-1 flex overflow-hidden">

        {/* Desktop left nav */}
        <nav className="hidden md:flex shrink-0 w-52 bg-white border-r border-slate-100 flex-col py-5 px-3">

          {/* Brand */}
          <div className="px-3 mb-6">
            <Link href="/app" className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-slate-900 flex items-center justify-center shrink-0">
                <span className="text-white text-[11px] font-bold leading-none">CB</span>
              </div>
              <span className="text-sm font-semibold text-slate-900 tracking-tight">Company Brain</span>
            </Link>
          </div>

          {/* Main nav */}
          <NavList isActive={isActive} />

          {/* Coming soon */}
          <div className="mt-auto border-t border-slate-100 pt-4 space-y-0.5">
            {COMING_SOON.map(item => {
              const Icon = item.icon
              return (
                <div
                  key={item.label}
                  className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg opacity-40 cursor-not-allowed select-none"
                >
                  <span className="text-slate-400">
                    <Icon />
                  </span>
                  <span className="text-sm text-slate-500 flex-1">{item.label}</span>
                  <span className="text-[10px] font-medium text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
                    Soon
                  </span>
                </div>
              )
            })}
          </div>
        </nav>

        {/* Page content */}
        <div className="flex-1 flex overflow-hidden">
          {children}
        </div>

      </div>
    </div>
  )
}
