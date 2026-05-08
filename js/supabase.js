// ════════════════════════════════════════
//  Supabase 設定
// ════════════════════════════════════════
const SUPABASE_URL  = 'https://kldumnxdlgovaxtiszyn.supabase.co';
const SUPABASE_ANON = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtsZHVtbnhkbGdvdmF4dGlzenluIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzgxMjIyNDgsImV4cCI6MjA5MzY5ODI0OH0.P_anfYpSV2tgCPIQ7uZDVBjUFY3UhfEXk9u3XjlzBHI';
const DEFAULT_AI_KEY = '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';

const { createClient } = supabase;
const sb = createClient(SUPABASE_URL, SUPABASE_ANON);

// ── 會員方案權限對照表 ──────────────────
// plan 欄位值：free / tw / us / all / admin
const PLAN_ACCESS = {
  free:  { tw: false, us: false, label: '免費',     badge: 'plan-free' },
  tw:    { tw: true,  us: false, label: '台股會員',  badge: 'plan-tw'   },
  us:    { tw: false, us: true,  label: '美股會員',  badge: 'plan-us'   },
  all:   { tw: true,  us: true,  label: '全市場',   badge: 'plan-all'  },
  admin: { tw: true,  us: true,  label: '管理員',   badge: 'plan-admin'},
};

function canAccess(plan, market) {
  return PLAN_ACCESS[plan]?.[market] ?? false;
}
function planLabel(plan) {
  return PLAN_ACCESS[plan]?.label ?? plan;
}
function planBadge(plan) {
  return PLAN_ACCESS[plan]?.badge ?? 'plan-free';
}

// ── 基本 auth ───────────────────────────
async function getUser() {
  const { data: { user } } = await sb.auth.getUser();
  return user;
}
async function getProfile(userId) {
  const { data } = await sb.from('profiles').select('*').eq('id', userId).single();
  return data;
}
async function requireAuth() {
  const user = await getUser();
  if (!user) { window.location.href = 'login.html'; return null; }
  return user;
}
async function signOut() {
  await sb.auth.signOut();
  window.location.href = 'login.html';
}

// ── 點數 ────────────────────────────────
async function getPoints(userId) {
  const { data } = await sb.from('points').select('balance').eq('user_id', userId).single();
  return data?.balance || 0;
}
async function deductPoint(userId, description = 'AI 股票健診') {
  const balance = await getPoints(userId);
  if (balance < 1) return false;
  const { error } = await sb.from('points').update({ balance: balance - 1 }).eq('user_id', userId);
  if (error) return false;
  await sb.from('point_logs').insert({ user_id: userId, amount: -1, description, created_at: new Date().toISOString() });
  return true;
}
async function addPoints(userId, amount, description = '管理員儲值') {
  const current = await getPoints(userId);
  const { error } = await sb.from('points').upsert({ user_id: userId, balance: current + parseInt(amount) }, { onConflict: 'user_id' });
  if (error) return false;
  await sb.from('point_logs').insert({ user_id: userId, amount: +amount, description, created_at: new Date().toISOString() });
  return true;
}

// ── AI Key ──────────────────────────────
function getAIKey() {
  return localStorage.getItem('ai_key') || DEFAULT_AI_KEY || '';
}

// ── 共用 Toast ──────────────────────────
function showToast(msg, type = '') {
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.className = 'show ' + type;
  setTimeout(() => t.className = '', 2800);
}

// ── AI 呼叫（支援 Groq 和 Anthropic）──────
// Groq key 以 gsk_ 開頭，Anthropic 以 sk-ant- 開頭
async function callAI(prompt, maxTokens = 1000) {
  const key = getAIKey();
  if (!key) throw new Error('請先設定 AI Key');

  const isGroq = key.startsWith('gsk_');

  if (isGroq) {
    // Groq API
    const res = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + key
      },
      body: JSON.stringify({
        model: 'llama-3.3-70b-versatile',
        max_tokens: maxTokens,
        messages: [{ role: 'user', content: prompt }]
      })
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error.message);
    return data.choices[0].message.content;

  } else {
    // Anthropic API
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': key,
        'anthropic-version': '2023-06-01'
      },
      body: JSON.stringify({
        model: 'claude-sonnet-4-20250514',
        max_tokens: maxTokens,
        messages: [{ role: 'user', content: prompt }]
      })
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error.message);
    return data.content.map(b => b.text || '').join('');
  }
}
