import { useState, useEffect, useCallback } from 'react';
import {
  AppSettings,
  ThemeSettings,
  UserProfile,
} from './types';
import {
  getCurrentUser,
  getStoredSettings,
  getStoredTheme,
  subscribeRealtime,
  recordPendingReferral,
  syncUserWithRemote,
  saveSingleUser,
} from './services/store';
import { initTelegramApp, getTelegramReferralParam } from './services/telegram';
import { Header } from './components/Header';
import { BottomNav, TabType } from './components/BottomNav';
import { HomeScreen } from './components/HomeScreen';
import { InviteScreen } from './components/InviteScreen';
import { WalletScreen } from './components/WalletScreen';
import { AdminPortal } from './components/AdminPortal';
import { DeviceVerificationScreen } from './components/DeviceVerificationScreen';

function checkIsAdminRoute(): boolean {
  if (typeof window === 'undefined') return false;
  const path = window.location.pathname.toLowerCase();
  const hash = window.location.hash.toLowerCase();
  const search = new URLSearchParams(window.location.search);
  return (
    path === '/admin' ||
    path.startsWith('/admin') ||
    hash === '#/admin' ||
    hash.startsWith('#/admin') ||
    hash === '#admin' ||
    search.get('admin') === 'true' ||
    search.get('tab') === 'admin'
  );
}

export default function App() {
  const [isAdminRoute, setIsAdminRoute] = useState<boolean>(checkIsAdminRoute());
  const [activeTab, setActiveTab] = useState<TabType>('home');
  const [user, setUser] = useState<UserProfile>(getCurrentUser());
  const [settings, setSettings] = useState<AppSettings>(getStoredSettings());
  const [theme, setTheme] = useState<ThemeSettings>(getStoredTheme());
  const [isDarkMode, setIsDarkMode] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return localStorage.getItem('rg_dark_mode_v1') === 'true';
  });

  const handleToggleDarkMode = useCallback(() => {
    setIsDarkMode((prev) => {
      const next = !prev;
      if (typeof window !== 'undefined') {
        localStorage.setItem('rg_dark_mode_v1', String(next));
      }
      return next;
    });
  }, []);
  const [showVerification, setShowVerification] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    const search = new URLSearchParams(window.location.search);
    const hash = window.location.hash;
    const isVerifyParam = search.get('verify') === 'true' || hash.includes('verify=true');
    const boundId = localStorage.getItem('rg_bound_telegram_id_v1');
    const currentUser = getCurrentUser();
    // Show if explicit ?verify=true or if multi-account switch detected
    if (isVerifyParam) return true;
    if (boundId && boundId !== String(currentUser.id)) return true;
    return false;
  });

  const handleNavigateToUserApp = useCallback(() => {
    if (typeof window !== 'undefined') {
      window.history.pushState({}, '', '/');
    }
    setIsAdminRoute(false);
  }, []);

  const handleNavigateToAdmin = useCallback(() => {
    if (typeof window !== 'undefined') {
      window.history.pushState({}, '', '#admin');
    }
    setIsAdminRoute(true);
  }, []);

  useEffect(() => {
    initTelegramApp();
    // Synchronize user immediately after Telegram WebApp initialization
    const initialUser = getCurrentUser();
    setUser(initialUser);

    const checkAndProcessReferral = (u: UserProfile) => {
      try {
        const refParam = getTelegramReferralParam();
        if (refParam) {
          recordPendingReferral(refParam, u.id);
        }
      } catch (e) {
        console.warn('Referral check notice:', e);
      }
    };

    // Run referral check immediately
    checkAndProcessReferral(initialUser);
    saveSingleUser(initialUser);

    // Re-check after Telegram WebApp finishes injecting (250ms)
    const tgTimer = setTimeout(() => {
      const freshUser = getCurrentUser();
      setUser(freshUser);
      saveSingleUser(freshUser);
      checkAndProcessReferral(freshUser);
      syncUserWithRemote(freshUser.id).then((fresh) => {
        if (fresh) setUser(fresh);
      });
    }, 250);

    // Initial remote profile sync
    syncUserWithRemote(initialUser.id).then((fresh) => {
      if (fresh) setUser(fresh);
    });

    // Auto-sync user balance & spins every 3.5 seconds
    const userSyncInterval = setInterval(() => {
      const current = getCurrentUser();
      syncUserWithRemote(current.id).then((fresh) => {
        if (fresh) setUser(fresh);
      });
    }, 3500);

    // 2. Listen to route / URL changes (popstate & hashchange)
    const handleUrlChange = () => {
      setIsAdminRoute(checkIsAdminRoute());
    };
    window.addEventListener('popstate', handleUrlChange);
    window.addEventListener('hashchange', handleUrlChange);

    // 3. Subscribe to real-time events across all tabs, storage, and Firebase
    const unsubscribe = subscribeRealtime(() => {
      setUser(getCurrentUser());
      setSettings(getStoredSettings());
      setTheme(getStoredTheme());
    });

    return () => {
      clearTimeout(tgTimer);
      clearInterval(userSyncInterval);
      window.removeEventListener('popstate', handleUrlChange);
      window.removeEventListener('hashchange', handleUrlChange);
      unsubscribe();
    };
  }, []);

  // -------------------------------------------------------------
  // Device Verification Screen (Matching Screenshot 3 & Anti-Switch Lock)
  // -------------------------------------------------------------
  if (showVerification) {
    return (
      <DeviceVerificationScreen
        user={user}
        settings={settings}
        referrerId={getTelegramReferralParam()}
        onContinue={() => setShowVerification(false)}
      />
    );
  }

  // -------------------------------------------------------------
  // Dedicated Admin Portal at /admin
  // -------------------------------------------------------------
  if (isAdminRoute) {
    return (
      <AdminPortal
        settings={settings}
        theme={theme}
        onNavigateToUserApp={handleNavigateToUserApp}
      />
    );
  }

  // -------------------------------------------------------------
  // User Panel: Clean Telegram Mini App (0 Admin traces)
  // -------------------------------------------------------------
  return (
    <div
      className={`min-h-screen w-full flex flex-col items-center justify-start transition-colors duration-500 overflow-x-hidden ${
        isDarkMode
          ? 'dark-mode bg-gradient-to-b from-[#090d16] via-[#0f172a] to-[#090d16] text-slate-100'
          : 'bg-gradient-to-b from-[#fbfbfa] via-[#f8f9fa] to-[#f1f3f6] text-slate-800'
      }`}
    >
      {/* Mobile Telegram App View Container */}
      <div className="w-full max-w-md min-h-screen flex flex-col px-3 sm:px-4 pt-2 pb-16 relative">
        {/* Header */}
        <Header
          user={user}
          settings={settings}
          theme={theme}
          activeTab={activeTab}
          onNavigate={(tab) => setActiveTab(tab)}
        />

        {/* Tab Views */}
        <main className="flex-1 w-full mt-2">
          {activeTab === 'home' && (
            <HomeScreen
              user={user}
              settings={settings}
              onNavigate={(tab) => setActiveTab(tab)}
              isDarkMode={isDarkMode}
              onToggleDarkMode={handleToggleDarkMode}
            />
          )}

          {activeTab === 'invite' && (
            <InviteScreen user={user} settings={settings} />
          )}

          {activeTab === 'wallet' && (
            <WalletScreen
              user={user}
              settings={settings}
              onNavigate={(tab) => setActiveTab(tab)}
            />
          )}
        </main>

        {/* Floating Bottom Navigation */}
        <BottomNav
          activeTab={activeTab}
          onTabChange={(tab) => setActiveTab(tab)}
        />
      </div>
    </div>
  );
}
