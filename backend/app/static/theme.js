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
  link.href = 'theme.css';
  document.head.appendChild(link);

  // Helper to toggle theme
  window.toggleTheme = function() {
    const isDark = document.documentElement.classList.contains('dark');
    window.setTheme(isDark ? 'light' : 'dark');
  };

  window.setTheme = function(themeName) {
    if (themeName === 'light') {
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
      btn.innerHTML = isDark ? '☀️' : '🌙';
      btn.title = isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode';
    });

    const btnLight = document.getElementById('theme-btn-light');
    const btnDark = document.getElementById('theme-btn-dark');
    if (btnLight && btnDark) {
      if (isDark) {
        btnLight.classList.remove('active');
        btnDark.classList.add('active');
      } else {
        btnLight.classList.add('active');
        btnDark.classList.remove('active');
      }
    }
  }

  // 3. Inject Button on DOM Load
  document.addEventListener('DOMContentLoaded', () => {
    const navActions = document.querySelector('.nav-actions');
    
    // Create the premium theme toggle button
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'theme-toggle-btn';
    btn.onclick = window.toggleTheme;
    
    if (navActions) {
      navActions.appendChild(btn);
    } else {
      // Floating button in top-right for pages without header (login, signup)
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
