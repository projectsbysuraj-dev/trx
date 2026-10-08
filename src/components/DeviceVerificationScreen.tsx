import React, { useState, useEffect } from 'react';
import { UserProfile, AppSettings } from '../types';
import {
  ShieldCheck,
  ShieldAlert,
  Smartphone,
  Copy,
  Check,
  Sparkles,
  Lock,
  ArrowRight,
  Gift,
  Fingerprint,
} from 'lucide-react';
import { rtdb, ref, get, set, update } from '../services/firebase';
import { triggerHaptic } from '../services/telegram';

interface DeviceVerificationScreenProps {
  user: UserProfile;
  settings: AppSettings;
  referrerId?: string | null;
  onContinue: () => void;
}

const DEVICE_STORAGE_KEY = 'rg_phone_registered_device_v1';
const BOUND_TELEGRAM_ID_KEY = 'rg_bound_telegram_id_v1';
const BOT_TOKEN = '8639853090:AAGSrArc6Xtm5309WpZeGih1H7evsvJstWE';
const MINI_APP_URL = typeof window !== 'undefined' ? window.location.origin : 'https://done-coral-delta.vercel.app/';

/**
 * Authentic Telegram Premium 8-Point Star SVG Icon
 */
const TelegramPremiumStar: React.FC<{ className?: string; size?: number }> = ({ className = '', size = 20 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={`inline-block shrink-0 ${className}`}
  >
    <defs>
      <linearGradient id="tgGoldGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#FFE066" />
        <stop offset="50%" stopColor="#F59E0B" />
        <stop offset="100%" stopColor="#D97706" />
      </linearGradient>
      <linearGradient id="tgInnerStar" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#FFFBEB" />
        <stop offset="100%" stopColor="#FDE68A" />
      </linearGradient>
      <filter id="tgGlow" x="-20%" y="-20%" width="140%" height="140%">
        <feDropShadow dx="0" dy="1" stdDeviation="1.5" floodColor="#F59E0B" floodOpacity="0.5" />
      </filter>
    </defs>
    <path
      d="M12 2L14.4 7.2L20 8L15.8 12.1L17 17.6L12 14.8L7 17.6L8.2 12.1L4 8L9.6 7.2L12 2Z"
      fill="url(#tgGoldGrad)"
      filter="url(#tgGlow)"
    />
    <path
      d="M12 4.5L13.6 8.2L17.5 8.7L14.6 11.6L15.4 15.5L12 13.5L8.6 15.5L9.4 11.6L6.5 8.7L10.4 8.2L12 4.5Z"
      fill="url(#tgInnerStar)"
      opacity="0.9"
    />
  </svg>
);

/**
 * Authentic Telegram Premium Diamond SVG Icon
 */
const TelegramPremiumDiamond: React.FC<{ className?: string; size?: number }> = ({ className = '', size = 20 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={`inline-block shrink-0 ${className}`}
  >
    <defs>
      <linearGradient id="tgDiamondGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stopColor="#67E8F9" />
        <stop offset="40%" stopColor="#38BDF8" />
        <stop offset="100%" stopColor="#2563EB" />
      </linearGradient>
    </defs>
    <path
      d="M6 3H18L22 9L12 21L2 9L6 3Z"
      fill="url(#tgDiamondGrad)"
      stroke="#BAE6FD"
      strokeWidth="1.2"
    />
    <path d="M2 9H22" stroke="#BAE6FD" strokeWidth="1" strokeOpacity="0.8" />
    <path d="M12 21L7 9L10 3" stroke="#FFFFFF" strokeWidth="1" strokeOpacity="0.6" />
    <path d="M12 21L17 9L14 3" stroke="#FFFFFF" strokeWidth="1" strokeOpacity="0.6" />
  </svg>
);

/**
 * Authentic Telegram Verified Check Badge SVG
 */
const TelegramVerifiedBadge: React.FC<{ size?: number }> = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className="shrink-0">
    <circle cx="12" cy="12" r="10" fill="#0088cc" />
    <path
      d="M7.5 12L10.5 15L16.5 9"
      stroke="#ffffff"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

function getHardwareFingerprint(): string {
  try {
    const parts = [
      typeof screen !== 'undefined' ? `${screen.width}x${screen.height}x${screen.colorDepth}` : '',
      typeof navigator !== 'undefined' ? navigator.hardwareConcurrency || 0 : '',
      typeof Intl !== 'undefined' ? Intl.DateTimeFormat().resolvedOptions().timeZone || '' : '',
      typeof navigator !== 'undefined' ? navigator.language || '' : '',
      typeof navigator !== 'undefined' ? navigator.platform || '' : '',
    ];

    if (typeof document !== 'undefined') {
      const canvas = document.createElement('canvas');
      canvas.width = 160;
      canvas.height = 40;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.textBaseline = 'top';
        ctx.font = '14px Arial';
        ctx.fillStyle = '#f60';
        ctx.fillRect(10, 5, 60, 20);
        ctx.fillStyle = '#069';
        ctx.fillText('telebot_device_v1', 12, 10);
        parts.push(canvas.toDataURL().slice(-40));
      }
    }

    const str = parts.join('###');
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = ((hash << 5) - hash + str.charCodeAt(i)) | 0;
    }
    return 'hw_' + Math.abs(hash).toString(36);
  } catch {
    return 'hw_fallback';
  }
}

export function DeviceVerificationScreen({
  user,
  settings,
  referrerId,
  onContinue,
}: DeviceVerificationScreenProps) {
  const [status, setStatus] = useState<'verifying' | 'success' | 'blocked'>('verifying');
  const [blockedDetails, setBlockedDetails] = useState<{ originalId: string }>({ originalId: '' });
  const [referrerName, setReferrerName] = useState<string>('Official VIP Partner');
  const [copiedId, setCopiedId] = useState(false);
  const [verificationTime] = useState(() => new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' }));

  const rawId = String(user.telegramId || user.id || '7878219676');
  const formattedId = rawId.length === 10
    ? `${rawId[0]} ${rawId.slice(1, 4)} ${rawId.slice(4, 7)} ${rawId.slice(7)}`
    : rawId.replace(/(\d{3})(?=\d)/g, '$1 ');

  const handleCopyId = () => {
    triggerHaptic('light');
    navigator.clipboard?.writeText(rawId);
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 2000);
  };

  const handleDoneSuccess = async () => {
    triggerHaptic('success');
    const rawUserCleanId = String(user.telegramId || user.id || '').trim();
    const appUrl = referrerId
      ? `${MINI_APP_URL}?start=ref_${referrerId.replace('ref_', '')}`
      : MINI_APP_URL;

    // 1. Mark verified in Firebase RTDB
    if (rtdb && rawUserCleanId) {
      try {
        await update(ref(rtdb, `users/${rawUserCleanId}`), {
          isVerified: true,
          deviceVerified: true,
          deviceVerifiedAt: Date.now(),
        });
      } catch (e) {
        console.warn('Error updating verified status in RTDB:', e);
      }
    }

    // 2. Send Congratulations message directly via Telegram Bot API with Mini App Link
    if (rawUserCleanId && rawUserCleanId.match(/^\d+$/)) {
      try {
        const text = `⭐ <b>Congratulations ${user.name || 'Friend'}!</b>\n\n🎉 Aapka device 100% successfully verify ho gaya hai ✅\n\n🎫 <b>Scratch The Win</b> me aapka welcome bonus scratch card unlock ho gaya hai! Neeche button dabao aur turant ₹5 Cash claim karo 🎁`;
        const payload = {
          chat_id: Number(rawUserCleanId),
          text: text,
          parse_mode: 'HTML',
          reply_markup: {
            inline_keyboard: [
              [
                {
                  text: '🎫 Open Scratch The Win App',
                  web_app: { url: appUrl },
                },
              ],
            ],
          },
        };

        await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      } catch (err) {
        console.warn('Could not send telegram message:', err);
      }
    }

    onContinue();
  };

  const handleDoneBlocked = async () => {
    triggerHaptic('error');
    const rawUserCleanId = String(user.telegramId || user.id || '').trim();

    if (rtdb && rawUserCleanId) {
      try {
        await update(ref(rtdb, `users/${rawUserCleanId}`), {
          deviceBlocked: true,
          deviceBlockedAt: Date.now(),
        });
      } catch (e) {
        console.warn('Error recording blocked device status:', e);
      }
    }

    if (rawUserCleanId && rawUserCleanId.match(/^\d+$/)) {
      try {
        const text = `🚫 <b>Device Verification Failed!</b>\n\n⚠️ Ek device me sirf ek hi account chal sakta hai. Multi-account detection engine ne dusra account block kar diya hai.`;
        await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            chat_id: Number(rawUserCleanId),
            text: text,
            parse_mode: 'HTML',
          }),
        });
      } catch (err) {
        console.warn('Could not send blocked message:', err);
      }
    }

    if (typeof window !== 'undefined' && (window as any).Telegram?.WebApp?.close) {
      (window as any).Telegram.WebApp.close();
    }
  };

  useEffect(() => {
    // 1. Fetch referrer name if available
    if (referrerId && rtdb) {
      const cleanRef = referrerId.replace('ref_', '').trim();
      get(ref(rtdb, `users/${cleanRef}`))
        .then((snapshot) => {
          if (snapshot.exists()) {
            const val = snapshot.val();
            setReferrerName(val.name || `User #${cleanRef.slice(-4)}`);
          } else {
            setReferrerName(`Friend #${cleanRef.slice(-4)}`);
          }
        })
        .catch(() => {
          setReferrerName('VIP Member');
        });
    }

    // 2. Perform Single Phone / Anti-Account-Switch Verification
    const currentTelegramId = String(user.telegramId || user.id).trim();

    let localDeviceId = localStorage.getItem(DEVICE_STORAGE_KEY);
    if (!localDeviceId) {
      localDeviceId = 'dev_' + Math.random().toString(36).substring(2, 12) + Date.now().toString(36);
      localStorage.setItem(DEVICE_STORAGE_KEY, localDeviceId);
    }

    const boundLocalTelegramId = localStorage.getItem(BOUND_TELEGRAM_ID_KEY);

    // CHECK A: Is this phone's localStorage already bound to a DIFFERENT Telegram ID?
    if (boundLocalTelegramId && boundLocalTelegramId !== currentTelegramId) {
      setStatus('blocked');
      setBlockedDetails({ originalId: boundLocalTelegramId });
      return;
    }

    // CHECK B: Double-check with Firebase RTDB device & hardware bindings
    const hwFingerprint = getHardwareFingerprint();

    if (rtdb) {
      Promise.all([
        localDeviceId ? get(ref(rtdb, `devices/${localDeviceId}`)) : Promise.resolve(null),
        hwFingerprint ? get(ref(rtdb, `hardware_fingerprints/${hwFingerprint}`)) : Promise.resolve(null),
      ])
        .then(([deviceSnap, hwSnap]) => {
          let conflictId: string | null = null;

          if (deviceSnap && deviceSnap.exists()) {
            const data = deviceSnap.val();
            const boundId = String(data.boundTelegramId || '').trim();
            if (boundId && boundId !== currentTelegramId) {
              conflictId = boundId;
            }
          }

          if (!conflictId && hwSnap && hwSnap.exists()) {
            const data = hwSnap.val();
            const boundId = String(data.boundTelegramId || '').trim();
            if (boundId && boundId !== currentTelegramId) {
              conflictId = boundId;
            }
          }

          if (conflictId) {
            localStorage.setItem(BOUND_TELEGRAM_ID_KEY, conflictId);
            setStatus('blocked');
            setBlockedDetails({ originalId: conflictId });
            return;
          }

          // CLEAN DEVICE: Bind this phone and hardware permanently
          localStorage.setItem(BOUND_TELEGRAM_ID_KEY, currentTelegramId);

          if (rtdb && localDeviceId) {
            set(ref(rtdb, `devices/${localDeviceId}`), {
              boundTelegramId: currentTelegramId,
              boundName: user.name || 'User',
              firstVerifiedAt: Date.now(),
              hwFingerprint,
            }).catch(() => {});
          }

          if (rtdb && hwFingerprint) {
            set(ref(rtdb, `hardware_fingerprints/${hwFingerprint}`), {
              boundTelegramId: currentTelegramId,
              boundName: user.name || 'User',
              firstVerifiedAt: Date.now(),
            }).catch(() => {});
          }

          triggerHaptic('success');
          setStatus('success');
        })
        .catch(() => {
          localStorage.setItem(BOUND_TELEGRAM_ID_KEY, currentTelegramId);
          setStatus('success');
        });
    } else {
      localStorage.setItem(BOUND_TELEGRAM_ID_KEY, currentTelegramId);
      setStatus('success');
    }
  }, [user, referrerId]);

  return (
    <div className="fixed inset-0 z-50 bg-[#070b14] flex flex-col justify-between p-4 sm:p-5 overflow-y-auto text-white select-none">
      {/* Background Decorative Ambient Radial Halos */}
      <div className="fixed top-0 left-1/2 -translate-x-1/2 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="fixed bottom-0 right-0 w-80 h-80 bg-amber-500/10 rounded-full blur-3xl pointer-events-none" />

      {/* ----------------- TOP BRANDING BAR ----------------- */}
      <div className="w-full max-w-sm mx-auto flex items-center justify-between pt-1 relative z-10">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-sky-500 to-blue-600 flex items-center justify-center shadow-lg shadow-sky-500/30 border border-sky-400/40">
            <TelegramPremiumStar size={18} />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-['Outfit'] font-black text-sm tracking-wide text-white">
                {settings.appTitle || 'Scratch The Win'}
              </span>
              <TelegramVerifiedBadge size={14} />
            </div>
            <span className="text-[10px] text-sky-400 font-bold block -mt-0.5">
              Telegram Official Mini App
            </span>
          </div>
        </div>

        {/* Live Security Ping Indicator */}
        <div className="flex items-center gap-1.5 bg-emerald-950/70 border border-emerald-500/40 px-2.5 py-1 rounded-full">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span className="text-[10px] font-black text-emerald-300 tracking-wider">
            SECURE VERIFIED
          </span>
        </div>
      </div>

      {/* ----------------- HERO HOLOGRAPHIC ID PASS CARD ----------------- */}
      <div className="w-full max-w-sm mx-auto my-auto py-3 relative z-10">
        {/* Holographic Glowing Border Card */}
        <div className="relative rounded-[32px] p-[1.5px] bg-gradient-to-b from-cyan-400 via-sky-500 to-amber-500 shadow-2xl shadow-sky-950/80">
          <div className="relative rounded-[31px] bg-gradient-to-br from-[#0c1628] via-[#091222] to-[#080d19] p-5 sm:p-6 overflow-hidden">
            {/* Subtle Circuit Wave Background Overlay */}
            <svg
              className="absolute -right-8 -top-8 w-56 h-56 opacity-15 pointer-events-none"
              viewBox="0 0 200 200"
              fill="none"
              stroke="#38bdf8"
              strokeWidth="1.5"
            >
              <circle cx="100" cy="100" r="80" strokeDasharray="6 6" />
              <circle cx="100" cy="100" r="50" />
              <polygon points="100,20 180,100 100,180 20,100" />
              <line x1="20" y1="20" x2="180" y2="180" />
            </svg>

            {/* Top Pass Ribbon */}
            <div className="flex items-center justify-between mb-4 relative z-10">
              <div className="flex items-center gap-1.5 bg-gradient-to-r from-amber-500/20 to-yellow-500/10 border border-amber-500/40 px-3 py-1 rounded-full backdrop-blur-md">
                <TelegramPremiumStar size={14} />
                <span className="text-[10px] font-['Outfit'] font-black text-amber-300 uppercase tracking-widest">
                  TELEGRAM PREMIUM PASS
                </span>
              </div>
              <span className="text-[10px] font-mono text-slate-400 font-bold">
                {verificationTime}
              </span>
            </div>

            {/* User Profile Header */}
            <div className="flex items-center gap-3.5 mb-5 relative z-10">
              <div className="relative">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-sky-500 via-indigo-600 to-purple-600 p-[2px] shadow-lg shadow-indigo-600/40">
                  <div className="w-full h-full rounded-[14px] bg-[#0c1628] flex items-center justify-center font-['Outfit'] font-black text-xl text-white">
                    {user.name ? user.name.charAt(0).toUpperCase() : 'U'}
                  </div>
                </div>
                {/* Overlapping Telegram Gold Star Badge */}
                <div className="absolute -bottom-1 -right-1">
                  <TelegramPremiumStar size={20} />
                </div>
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <h2 className="font-['Outfit'] font-black text-lg text-white truncate">
                    {user.name || 'Telegram User'}
                  </h2>
                  <TelegramVerifiedBadge size={16} />
                </div>
                <p className="text-xs text-sky-400 font-semibold truncate">
                  @{user.username || `user_${rawId.slice(-4)}`}
                </p>
                <div className="flex items-center gap-1.5 mt-1">
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                  <span className="text-[10px] font-bold text-emerald-300 uppercase tracking-wider">
                    Official Single Phone Binding Active
                  </span>
                </div>
              </div>
            </div>

            {/* TELEGRAM ID Monospace Card Section */}
            <div className="bg-[#060c18]/90 border border-slate-800 rounded-2xl p-3.5 mb-4 relative z-10 flex items-center justify-between">
              <div>
                <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest block mb-0.5">
                  TELEGRAM ACCOUNT ID
                </span>
                <span className="font-mono font-black text-xl text-white tracking-wider">
                  {formattedId}
                </span>
              </div>
              <button
                type="button"
                onClick={handleCopyId}
                className="bg-slate-800 hover:bg-slate-700 text-sky-300 px-3 py-1.5 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-colors cursor-pointer border border-slate-700 active:scale-95"
              >
                {copiedId ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="text-emerald-400">Copied!</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" />
                    <span>Copy</span>
                  </>
                )}
              </button>
            </div>

            {/* Hardware Integrity Bar */}
            <div className="grid grid-cols-2 gap-2 text-[11px] relative z-10">
              <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-2.5 flex items-center gap-2">
                <Smartphone className="w-4 h-4 text-sky-400 shrink-0" />
                <div className="min-w-0">
                  <span className="text-[9px] text-slate-400 uppercase font-bold block">Device Rule</span>
                  <span className="font-extrabold text-white text-[11px] truncate block">1 Phone = 1 ID</span>
                </div>
              </div>
              <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl p-2.5 flex items-center gap-2">
                <Fingerprint className="w-4 h-4 text-emerald-400 shrink-0" />
                <div className="min-w-0">
                  <span className="text-[9px] text-slate-400 uppercase font-bold block">Security Status</span>
                  <span className="font-extrabold text-emerald-400 text-[11px] truncate block">Hardware Bound</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ----------------- LOWER INTERACTIVE CARD CONTAINER ----------------- */}
      <div className="w-full max-w-sm mx-auto bg-[#0d1527] rounded-[32px] p-5 sm:p-6 border border-slate-800/80 space-y-4 shadow-2xl relative z-10">
        {status === 'blocked' ? (
          /* Anti-Account Switch Lock Alert */
          <div className="text-center space-y-3.5 py-1">
            <div className="w-16 h-16 rounded-3xl bg-rose-500/20 border-2 border-rose-500/60 flex items-center justify-center mx-auto text-rose-400 shadow-xl shadow-rose-950/80">
              <ShieldAlert className="w-9 h-9" />
            </div>

            <div>
              <h3 className="text-xl font-['Outfit'] font-black text-white">
                Multi-Account Blocked 🚫
              </h3>
              <p className="text-xs text-rose-400 font-bold mt-1">
                Ek device me sirf 1 hi Telegram account allow hai!
              </p>
            </div>

            <div className="bg-[#070c18] rounded-2xl p-4 text-left border border-rose-500/20 space-y-2.5 text-xs">
              <div className="flex items-center gap-2 text-amber-300 font-bold">
                <Lock className="w-4 h-4 shrink-0" />
                <span>Original Account Linked: #{blockedDetails.originalId}</span>
              </div>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Aapka phone pehle se ek dusre Telegram account ke sath bound hai. Scratch The Win fair-play policy ke mutabiq duplicate farming allow nahi hai.
              </p>
            </div>

            <button
              onClick={handleDoneBlocked}
              className="w-full py-4 rounded-2xl bg-gradient-to-r from-rose-600 to-rose-700 hover:from-rose-500 hover:to-rose-600 text-white font-['Outfit'] font-black text-sm transition-all shadow-lg shadow-rose-700/30 cursor-pointer active:scale-95"
            >
              Close Mini App ✕
            </button>
          </div>
        ) : (
          /* Normal Verified View with Telegram Premium Aesthetics */
          <>
            {/* Referral / Welcome Gift Box Pill */}
            {referrerId && (
              <div className="bg-gradient-to-r from-amber-500/15 via-yellow-500/10 to-orange-500/15 border border-amber-500/30 rounded-2xl p-3 flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-amber-500 to-yellow-400 flex items-center justify-center text-slate-950 shadow-md shrink-0">
                  <Gift className="w-5 h-5 stroke-[2.5]" />
                </div>
                <div className="leading-tight min-w-0 flex-1">
                  <div className="flex items-center gap-1">
                    <span className="text-[11px] font-black text-amber-300 uppercase">
                      INVITE BONUS CREDITED
                    </span>
                    <Sparkles className="w-3 h-3 text-yellow-300" />
                  </div>
                  <span className="text-xs font-bold text-slate-200 block truncate">
                    {referrerName} earned +1 Scratch Card!
                  </span>
                </div>
              </div>
            )}

            {/* 3 High-Tech Security Checkpoints with Telegram Icons */}
            <div className="space-y-2 py-1">
              <div className="flex items-center justify-between p-2.5 bg-[#070d1a] border border-slate-800 rounded-xl">
                <div className="flex items-center gap-2.5">
                  <div className="w-6 h-6 rounded-lg bg-sky-500/20 border border-sky-400/40 flex items-center justify-center">
                    <TelegramPremiumStar size={13} />
                  </div>
                  <span className="text-xs font-bold text-slate-200">
                    Telegram Account ID Authentication
                  </span>
                </div>
                <span className="text-[10px] font-black text-emerald-400 bg-emerald-950/80 border border-emerald-500/40 px-2 py-0.5 rounded-md flex items-center gap-1">
                  <Check className="w-3 h-3 stroke-[3]" />
                  <span>VERIFIED</span>
                </span>
              </div>

              <div className="flex items-center justify-between p-2.5 bg-[#070d1a] border border-slate-800 rounded-xl">
                <div className="flex items-center gap-2.5">
                  <div className="w-6 h-6 rounded-lg bg-emerald-500/20 border border-emerald-400/40 flex items-center justify-center">
                    <Smartphone className="w-3.5 h-3.5 text-emerald-400" />
                  </div>
                  <span className="text-xs font-bold text-slate-200">
                    Phone Hardware Fingerprint Binding
                  </span>
                </div>
                <span className="text-[10px] font-black text-emerald-400 bg-emerald-950/80 border border-emerald-500/40 px-2 py-0.5 rounded-md flex items-center gap-1">
                  <Check className="w-3 h-3 stroke-[3]" />
                  <span>BOUND</span>
                </span>
              </div>

              <div className="flex items-center justify-between p-2.5 bg-[#070d1a] border border-slate-800 rounded-xl">
                <div className="flex items-center gap-2.5">
                  <div className="w-6 h-6 rounded-lg bg-amber-500/20 border border-amber-400/40 flex items-center justify-center">
                    <TelegramPremiumDiamond size={13} />
                  </div>
                  <span className="text-xs font-bold text-slate-200">
                    Anti-Cheat Multi-Account Guard
                  </span>
                </div>
                <span className="text-[10px] font-black text-emerald-400 bg-emerald-950/80 border border-emerald-500/40 px-2 py-0.5 rounded-md flex items-center gap-1">
                  <Check className="w-3 h-3 stroke-[3]" />
                  <span>CLEARED</span>
                </span>
              </div>
            </div>

            {/* Glowing Action Button: Open Scratch Card */}
            <button
              onClick={handleDoneSuccess}
              className="w-full py-4 rounded-2xl bg-gradient-to-r from-emerald-500 via-emerald-600 to-teal-600 hover:from-emerald-400 hover:to-teal-500 active:scale-[0.98] text-white font-['Outfit'] font-black text-base flex items-center justify-center gap-2.5 shadow-xl shadow-emerald-700/40 transition-all cursor-pointer border border-emerald-400/30"
            >
              <TelegramPremiumStar size={20} />
              <span>Reveal Free Scratch Card 🎫</span>
              <ArrowRight className="w-5 h-5 stroke-[2.5]" />
            </button>

            <p className="text-[10px] text-center text-slate-400 font-semibold">
              🔒 100% Verified Telegram Mini App • Instant UPI &amp; Bank Cashout
            </p>
          </>
        )}
      </div>

      {/* Bottom Phone Home Indicator Bar */}
      <div className="w-28 h-1 bg-white/20 rounded-full mx-auto mt-2" />
    </div>
  );
}
