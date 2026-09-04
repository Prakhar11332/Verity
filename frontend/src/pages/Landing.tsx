import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';

export const Landing: React.FC = () => {
  useEffect(() => {
    // Document title
    document.title = 'Verity.ai — Autonomous Financial Reconciliation Infrastructure';

    const appears = document.querySelectorAll<HTMLElement>('.appear');
    const heroPhoto = document.querySelector<HTMLElement>('.hero-photo');
    const burger = document.getElementById('burger-btn');
    const nav = document.getElementById('site-nav');
    const backdrop = document.getElementById('menu-backdrop');

    if (window.location.search.includes('settled')) {
      appears.forEach((el) => el.classList.add('is-in'));
      if (heroPhoto) heroPhoto.classList.add('is-in');
      const star = document.querySelector('.badge-star');
      if (star) star.classList.add('is-in');
      const em = document.querySelector('h1 em');
      if (em) em.classList.add('is-in');
    }

    // 1. Each .appear -> own animationend -> add is-in (once: true)
    appears.forEach((el) => {
      el.addEventListener(
        'animationend',
        () => {
          el.classList.add('is-in');
        },
        { once: true }
      );
    });
    if (heroPhoto) {
      heroPhoto.addEventListener(
        'animationend',
        () => {
          heroPhoto.classList.add('is-in');
        },
        { once: true }
      );
    }

    // 2. If animations are not running after two rAFs, force .is-in on all .appear and .hero-photo
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        let isRunning = false;
        appears.forEach((el) => {
          if (typeof el.getAnimations === 'function') {
            const anims = el.getAnimations();
            if (anims.some((a) => a.playState === 'running' || a.playState === 'finished')) {
              isRunning = true;
            }
          }
        });
        if (!isRunning) {
          appears.forEach((el) => el.classList.add('is-in'));
          if (heroPhoto) heroPhoto.classList.add('is-in');
        }
      });
    });

    // 3. Burger toggles body.menu-open
    const onBurgerClick = () => {
      const isOpen = document.body.classList.toggle('menu-open');
      if (burger) {
        burger.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        burger.setAttribute('aria-label', isOpen ? 'Close menu' : 'Open menu');
      }
    };
    if (burger) {
      burger.addEventListener('click', onBurgerClick);
    }

    // 4. Nav links, backdrop and Escape close the menu
    const closeMenu = () => {
      if (document.body.classList.contains('menu-open')) {
        document.body.classList.remove('menu-open');
        if (burger) {
          burger.setAttribute('aria-expanded', 'false');
          burger.setAttribute('aria-label', 'Open menu');
        }
      }
    };

    if (backdrop) backdrop.addEventListener('click', closeMenu);
    if (nav) {
      nav.querySelectorAll('a').forEach((a) => a.addEventListener('click', closeMenu));
    }

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeMenu();
    };
    window.addEventListener('keydown', onKeyDown);

    // 5. Resize to (min-width: 901px) closes the menu
    const mql = window.matchMedia('(min-width: 901px)');
    const onMqlChange = (e: MediaQueryListEvent) => {
      if (e.matches) closeMenu();
    };
    mql.addEventListener('change', onMqlChange);

    return () => {
      document.body.classList.remove('menu-open');
      if (burger) burger.removeEventListener('click', onBurgerClick);
      if (backdrop) backdrop.removeEventListener('click', closeMenu);
      window.removeEventListener('keydown', onKeyDown);
      mql.removeEventListener('change', onMqlChange);
    };
  }, []);

  return (
    <div
      style={{
        background: '#000000',
        color: '#ffffff',
        minHeight: '100vh',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* 4. Grain at z-index: 100 */}
      <div className="grain"></div>

      {/* 2. Hero photo / background video */}
      <div className="hero-photo appear">
        <video
          className="hero-video"
          autoPlay
          loop
          muted
          playsInline
          src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260818_072341_50851634-bbc3-4c33-9acc-7647d4db44aa.mp4"
        />
      </div>

      {/* 3. Page Container */}
      <div className="page">
        <div className="menu-backdrop" id="menu-backdrop"></div>

        {/* Header */}
        <header className="header">
          {/* Left: Logo */}
          <Link to="/" className="logo appear appear--scale" aria-label="Verity" style={{ '--d': '0.08s' } as any}>
            <svg className="logo-mark" width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
              <g transform="rotate(-30 12 12)">
                <circle cx="7.3" cy="3.2" r="1.45" />
                <rect x="5.5" y="4.7" width="3.6" height="14.6" rx="1.8" />
                <rect x="14.9" y="4.7" width="3.6" height="14.6" rx="1.8" />
                <circle cx="16.7" cy="20.8" r="1.45" />
              </g>
            </svg>
            <span>
              Verity<span className="logo-suffix">.ai</span>
            </span>
          </Link>

          {/* Center: Nav (Primary Verity workflows) */}
          <nav id="site-nav" aria-label="Primary">
            <Link to="/reconciliation" className="nav-pill appear appear--scale" style={{ '--d': '0.16s' } as any}>
              Reconciliation
            </Link>
            <Link to="/exceptions" className="nav-pill appear appear--soft" style={{ '--d': '0.28s' } as any}>
              Exception Center
            </Link>
            <Link to="/pattern-insights" className="nav-pill appear appear--scale" style={{ '--d': '0.40s' } as any}>
              Pattern Insights
            </Link>
            <Link to="/audit-log" className="nav-pill appear appear--soft" style={{ '--d': '0.52s' } as any}>
              Audit Trail
            </Link>
          </nav>

          {/* Right: CTA + Burger */}
          <Link
            to="/overview"
            className="btn btn-solid header-cta appear appear--scale"
            style={{ '--d': '0.34s' } as any}
          >
            Launch Console
          </Link>

          <button
            className="burger appear appear--scale"
            id="burger-btn"
            aria-controls="site-nav"
            aria-expanded="false"
            aria-label="Open menu"
            style={{ '--d': '0.34s' } as any}
          >
            <span className="burger-bar"></span>
            <span className="burger-bar"></span>
            <span className="burger-bar"></span>
          </button>
        </header>

        {/* Main Hero */}
        <main className="hero" id="top">
          <div className="hero-copy">
            {/* Badge */}
            <div className="badge appear appear--pop" style={{ '--d': '0.22s' } as any}>
              <svg className="badge-star" width="18" height="20" viewBox="0 0 24 24" fill="#ffffff">
                <path d="M12 2.6C12.55 2.6 12.88 3.15 13.08 4.7c.62 4.7 1.52 5.6 6.22 6.22 1.55.2 2.1.53 2.1 1.08s-.55.88-2.1 1.08c-4.7.62-5.6 1.52-6.22 6.22-.2 1.55-.53 2.1-1.08 2.1s-.88-.55-1.08-2.1c-.62-4.7-1.52-5.6-6.22-6.22C3.15 12.88 2.6 12.55 2.6 12s.55-.88 2.1-1.08c4.7-.62 5.6-1.52 6.22-6.22C11.12 3.15 11.45 2.6 12 2.6Z" />
              </svg>
              <span>Autonomous Financial Reconciliation Engine</span>
            </div>

            {/* H1 */}
            <h1>
              <span className="headline-line">
                <span className="appear appear--mask" style={{ '--d': '0.42s', display: 'block' } as any}>
                  Reconcile <em>multi-source ledgers</em> in
                </span>
              </span>
              <span className="headline-line">
                <span className="appear appear--mask" style={{ '--d': '0.62s', display: 'block' } as any}>
                  milliseconds, not months.
                </span>
              </span>
            </h1>

            {/* Lede */}
            <p className="lede appear appear--soft" style={{ '--d': '0.82s' } as any}>
              Deterministic matching engines and adaptive AI agents that classify exceptions, prove root causes, and resolve discrepancies across four-way financial ledgers.
            </p>

            {/* Actions */}
            <div className="hero-actions">
              <Link to="/overview" className="btn btn-solid appear appear--btn" style={{ '--d': '0.96s' } as any}>
                Launch Console
              </Link>
              <Link to="/reconciliation" className="btn btn-hero-ghost appear appear--side" style={{ '--d': '1.10s' } as any}>
                Live Reconciliation
              </Link>
            </div>
          </div>
        </main>

        {/* Stats Footer */}
        <footer className="stats">
          {/* Stat 1 */}
          <div className="stat appear appear--stat" style={{ '--d': '1.12s' } as any}>
            <svg className="stat-icon" width="20" height="20" viewBox="0 0 24 24" fill="none">
              <defs>
                <linearGradient id="pillGrad1_verity" x1="3" y1="2" x2="14" y2="22" gradientUnits="userSpaceOnUse">
                  <stop offset="0%" stopColor="#ffffff" stopOpacity="0.38" />
                  <stop offset="100%" stopColor="#3a3a3a" stopOpacity="0.62" />
                </linearGradient>
                <linearGradient id="pillGrad2_verity" x1="3" y1="2" x2="14" y2="22" gradientUnits="userSpaceOnUse">
                  <stop offset="0%" stopColor="#3a3a3a" stopOpacity="0.38" />
                  <stop offset="100%" stopColor="#ffffff" stopOpacity="0.62" />
                </linearGradient>
              </defs>
              <rect x="3.4" y="2.6" width="7.2" height="18.8" rx="3.6" fill="url(#pillGrad1_verity)" />
              <rect x="13.4" y="2.6" width="7.2" height="18.8" rx="3.6" fill="url(#pillGrad2_verity)" />
              <rect x="9.2" y="10.9" width="5.6" height="2.2" rx="1.1" fill="#4a4a4a" />
            </svg>
            <span>4-way ledger synchronization</span>
          </div>

          {/* Stat 2 */}
          <div className="stat appear appear--stat" style={{ '--d': '1.28s' } as any}>
            <svg className="stat-icon" width="20" height="20" viewBox="0 0 24 24" fill="none">
              <rect x="2.4" y="2.4" width="19.2" height="19.2" rx="6.2" fill="#ffffff" />
              <path
                d="M12 7.1v7.4M8.15 12.35L12 16.2l3.85-3.85"
                stroke="#111111"
                strokeWidth="1.85"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <span>98% reduction in manual investigation</span>
          </div>

          {/* Stat 3 */}
          <div className="stat appear appear--stat" style={{ '--d': '1.44s' } as any}>
            <svg className="stat-icon-wide" width="38" height="21" viewBox="0 0 40 22" fill="none">
              <circle cx="10.2" cy="11" r="9.2" fill="#2b2b2b" />
              <ellipse cx="10.2" cy="12.1" rx="4.15" ry="3.7" fill="#f4f4f4" />
              <path d="M7 6L8.5 8.5M13.4 6L11.9 8.5" stroke="#2b2b2b" strokeWidth="1.2" strokeLinecap="round" />
              <circle cx="8.7" cy="11.8" r="0.7" fill="#1a1a1a" />
              <circle cx="11.7" cy="11.8" r="0.7" fill="#1a1a1a" />
              <circle cx="20.2" cy="11" r="9.2" fill="#ffffff" />
              <circle cx="17.8" cy="10" r="1.7" fill="#111111" />
              <circle cx="22.6" cy="10" r="1.7" fill="#111111" />
              <ellipse cx="20.2" cy="12.2" rx="1.2" ry="0.8" fill="#111111" />
              <path d="M18.4 14.2c.9.8 2.7.8 3.6 0" stroke="#111111" strokeWidth="1.2" strokeLinecap="round" />
              <circle cx="30.2" cy="11" r="9.2" fill="#f26b1d" />
              <text
                x="30.2"
                y="15.1"
                fontSize="12.5"
                fontFamily="'Inter', sans-serif"
                fontWeight="700"
                textAnchor="middle"
                fill="#ffffff"
              >
                e
              </text>
            </svg>
            <span>100% immutable audit logging</span>
          </div>
        </footer>
      </div>
    </div>
  );
};
