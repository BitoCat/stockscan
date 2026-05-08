# 🚀 StockScan 部署完整指南

## 📁 檔案結構
```
stockscan/
├── index.html        ← 主頁（AI 健診）
├── login.html        ← 登入/註冊
├── watchlist.html    ← 觀察名單
├── news.html         ← 市場新聞
├── profile.html      ← 個人設定 + 管理員面板
├── css/
│   └── base.css      ← 共用樣式
└── js/
    └── supabase.js   ← 資料庫設定
```

---

## 第一步：建立 Supabase 專案（10 分鐘）

1. 前往 https://supabase.com → 「Start your project」→ 免費註冊
2. 建立新專案，輸入名稱（如 stockscan）和資料庫密碼，選擇最近的區域
3. 等待約 2 分鐘讓專案建立完成

### 取得 API Key
- 左側選單 → Settings → API
- 複製：**Project URL** 和 **anon public key**

### 建立資料庫表格
到左側選單 → **SQL Editor** → New Query，貼上並執行以下 SQL：

```sql
-- 使用者 Profile 表
CREATE TABLE profiles (
  id UUID REFERENCES auth.users(id) PRIMARY KEY,
  display_name TEXT,
  plan TEXT DEFAULT 'free',  -- free / pro / admin
  daily_count INT DEFAULT 0,
  last_date TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 觀察名單
CREATE TABLE watchlist (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  symbol TEXT NOT NULL,
  market TEXT DEFAULT 'tw',
  name TEXT,
  sector TEXT,
  grade TEXT,
  health_score INT,
  added_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, symbol)
);

-- 新聞
CREATE TABLE news (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  title TEXT NOT NULL,
  summary TEXT,
  source TEXT,
  category TEXT DEFAULT 'tw',  -- tw / us / macro
  sentiment TEXT DEFAULT 'neutral',  -- bull / bear / neutral
  url TEXT,
  published_at TIMESTAMPTZ DEFAULT NOW()
);

-- 自動建立 profile（新用戶註冊時）
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger AS $$
BEGIN
  INSERT INTO public.profiles (id, display_name, plan)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'display_name', split_part(NEW.email, '@', 1)),
    COALESCE(NEW.raw_user_meta_data->>'plan', 'free')
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();
```

### 設定 Row Level Security (RLS)
繼續在 SQL Editor 執行：

```sql
-- 開啟 RLS
ALTER TABLE profiles  ENABLE ROW LEVEL SECURITY;
ALTER TABLE watchlist ENABLE ROW LEVEL SECURITY;
ALTER TABLE news      ENABLE ROW LEVEL SECURITY;

-- Profiles: 只能看/改自己的
CREATE POLICY "Users can view own profile"   ON profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Users can update own profile" ON profiles FOR UPDATE USING (auth.uid() = id);

-- Watchlist: 只能 CRUD 自己的
CREATE POLICY "Users manage own watchlist" ON watchlist FOR ALL USING (auth.uid() = user_id);

-- News: 所有登入用戶可讀，admin 可寫（先設全部可讀）
CREATE POLICY "Anyone can read news"  ON news FOR SELECT USING (true);
CREATE POLICY "Service role insert news" ON news FOR INSERT WITH CHECK (true);
CREATE POLICY "Service role delete news" ON news FOR DELETE USING (true);

-- Admin 可讀所有 profiles
CREATE POLICY "Admin can read all profiles" ON profiles FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE id = auth.uid() AND plan = 'admin'
    )
  );
```

---

## 第二步：設定 js/supabase.js

打開 `js/supabase.js`，填入你的資訊：

```javascript
const SUPABASE_URL  = 'https://你的專案ID.supabase.co';   // ← 改這裡
const SUPABASE_ANON = '你的 anon public key';              // ← 改這裡
const DEFAULT_AI_KEY = '';  // 可選：填入共用 AI Key
```

---

## 第三步：設定你自己為管理員

1. 先用 `login.html` 完成一次**正常註冊**
2. 到 Supabase → Table Editor → profiles
3. 找到你的帳號，將 `plan` 欄位改為 `admin`
4. 重新整理頁面，`profile.html` 底部會出現管理員面板

---

## 第四步：部署到 Netlify（免費，5 分鐘）

1. 前往 https://app.netlify.com/drop
2. 把整個 `stockscan` 資料夾拖曳進去
3. 等待 30 秒，得到網址如 `amazing-name-123.netlify.app`
4. 可到 Domain Settings 自訂網址

---

## 第五步：讓朋友加入

### 開放免費註冊
直接把網址傳給朋友，他們可以自己到 `login.html` 註冊

### 升級為 Pro
1. 朋友完成免費註冊
2. 你到 `profile.html` → 管理員面板 → 找到該會員 → 選擇「Pro」
3. 朋友重新登入即生效

---

## 🔑 關於 API Key 管理

### 方案 A：每人自己填（預設）
朋友到「我的」→ 填入自己的 Anthropic API Key

### 方案 B：你提供共用 Key（你付錢）
在 `js/supabase.js` 填入：
```javascript
const DEFAULT_AI_KEY = 'sk-ant-你的key...';
```
⚠️ 注意：Pro 會員才能免費用，Free 每日 5 次限制仍然有效

---

## 📱 加到手機主畫面（變成 APP）

### iPhone
1. 用 Safari 開啟網址
2. 點底部「分享」按鈕
3. 選「加入主畫面」
4. 即可像 APP 一樣使用

### Android
1. 用 Chrome 開啟網址
2. 點右上「⋮」選單
3. 選「加入主畫面」或「安裝 App」

---

## 🔮 Phase 2 規劃（新聞推播）

未來可加入：
- **LINE Notify / LINE Bot**：每日早晨推播市場摘要
- **Email 通知**：Supabase 內建 Email 功能
- **股價警示**：連接 Yahoo Finance API，到達目標價位時推播

需要時告訴我，我可以幫你實作！

---

## ❓ 常見問題

**Q：Supabase 免費版夠用嗎？**
A：免費版支援 50,000 月活躍用戶，資料庫 500MB，對小型社群完全夠用。

**Q：Anthropic API 費用是誰付？**
A：你填入自己 Key → 你付；朋友填自己 Key → 各自付。

**Q：可以賺錢嗎？**
A：Phase 3 可加入 Stripe 金流，收月費訂閱。

---

StockScan v1.0 · 台股美股 AI 健診平台

---

## 點數系統新增 SQL

在 Supabase SQL Editor 執行以下指令，新增點數相關表格：

```sql
-- 點數餘額
CREATE TABLE points (
  user_id UUID REFERENCES auth.users(id) PRIMARY KEY,
  balance INT DEFAULT 0
);

-- 點數異動記錄
CREATE TABLE point_logs (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  amount INT NOT NULL,         -- 正數=加點, 負數=扣點
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS
ALTER TABLE points     ENABLE ROW LEVEL SECURITY;
ALTER TABLE point_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users read own points"   ON points     FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users read own logs"     ON point_logs FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Service manages points"  ON points     FOR ALL   USING (true);
CREATE POLICY "Service manages logs"    ON point_logs FOR ALL   USING (true);
```

## 管理員加點流程

1. 用戶轉帳後截圖傳給你
2. 你到 profile.html → 管理員面板
3. 點「重新整理」找到該用戶
4. 點「＋點數」按鈕輸入點數和備註
5. 完成！用戶重新整理 APP 即看到新點數

## 點數購買頁面（points.html）

記得修改 `points.html` 頂部的 `BANK_INFO`：
- bank：你的銀行名稱
- account：你的帳號
- name：你的戶名
- lineUrl：你的 LINE 連結（讓用戶轉帳後通知你）
