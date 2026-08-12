// Configure Tailwind before it loads
window.tailwind = window.tailwind || {};
window.tailwind.config = {
  theme: {
    extend: {
      colors: {
        slate: {
          950: 'var(--slate-950)',
          900: 'var(--slate-900)',
          800: 'var(--slate-800)',
          700: 'var(--slate-700)',
          600: 'var(--slate-600)',
          500: 'var(--slate-500)',
          400: 'var(--slate-400)',
          300: 'var(--slate-300)',
          100: 'var(--slate-100)',
        },
        indigo: {
          950: 'var(--indigo-950)',
          900: 'var(--indigo-900)',
          800: 'var(--indigo-800)',
          700: 'var(--indigo-700)',
          600: 'var(--indigo-600)',
          400: 'var(--indigo-400)',
          300: 'var(--indigo-300)',
        }
      }
    }
  }
};

(function() {
  // 1. Determine Initial Theme
  const storedTheme = localStorage.getItem('theme');
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  const initialTheme = storedTheme || (prefersDark ? 'dark' : 'dark'); // Default to dark as requested by original design
  
  if (initialTheme === 'dark') {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }

  // 2. Add Stylesheet dynamically to prevent flash of light/dark content
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = '/static/theme.css';
  document.head.appendChild(link);

  // Helper to toggle theme
  window.toggleTheme = function() {
    const isDark = document.documentElement.classList.contains('dark');
    if (isDark) {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    } else {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    }
    updateTogglerButton();
  };

  function updateTogglerButton() {
    const isDark = document.documentElement.classList.contains('dark');
    const togglerButtons = document.querySelectorAll('.theme-toggle-btn');
    togglerButtons.forEach(btn => {
      btn.innerHTML = isDark ? '☀️ <span class="hidden sm:inline">Light Mode</span>' : '🌙 <span class="hidden sm:inline">Dark Mode</span>';
    });
  }

  // 3. Inject Button on DOM Load
  document.addEventListener('DOMContentLoaded', () => {
    // Find where to append the theme switcher
    const logoutBtn = document.querySelector('a[href*="logout"]');
    const header = document.querySelector('header .max-w-7xl') || document.querySelector('header div');
    
    // Create the premium theme toggle button
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'theme-toggle-btn flex items-center gap-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700/60 px-4 py-2 rounded-xl text-xs font-bold tracking-wide active:scale-95 transition-transform cursor-pointer shadow-sm';
    btn.onclick = window.toggleTheme;
    
    if (logoutBtn && logoutBtn.parentNode) {
      // If we have a logout button in the header, insert toggle right before it
      logoutBtn.parentNode.insertBefore(btn, logoutBtn);
      // Add a small spacer
      const spacer = document.createElement('div');
      spacer.className = 'w-2';
      logoutBtn.parentNode.insertBefore(spacer, logoutBtn);
    } else if (header) {
      // If header exists but no logout button
      header.appendChild(btn);
    } else {
      // Floating button in top-right for pages without header (login, signup)
      btn.className = 'theme-toggle-btn flex items-center gap-1.5 bg-slate-800/80 backdrop-blur-md hover:bg-slate-700/90 text-slate-300 hover:text-white border border-slate-700/60 px-4 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest active:scale-95 transition-transform cursor-pointer shadow-lg';
      
      let controls = document.getElementById('ahb-fixed-controls');
      if (!controls) {
        controls = document.createElement('div');
        controls.id = 'ahb-fixed-controls';
        controls.style.cssText = 'position:fixed;top:16px;right:16px;z-index:99999;display:flex;align-items:center;gap:8px;';
        document.body.appendChild(controls);
      }
      controls.appendChild(btn);
    }
    
    updateTogglerButton();
  });
})();
