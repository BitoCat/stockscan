# 交易大師 專案備忘錄

## 重要網址

- 網站: https://bitocat.github.io/stockscan
- GitHub: https://github.com/BitoCat/stockscan
- Supabase: https://supabase.com/dashboard/project/kldumnxdlgovaxtiszyn
- Groq Keys: https://console.groq.com/keys
- GitHub Actions: https://github.com/BitoCat/stockscan/actions

## 技術架構

- GitHub Pages: 免費靜態網站託管
- GitHub Actions: 自動部署
- Supabase: 資料庫+用戶認證+圖片儲存
- Groq API: AI股票健診分析
- Yahoo Finance: 即時股價和技術指標
- marked.js: Markdown渲染

## 檔案結構

- index.html: 首頁儀表板
- diagnosis.html: AI股票健診
- daily.html: 每日盤面解析
- news.html: 市場新聞
- announcement.html: 公告頁面
- tutorial.html: 投資教學
- watchlist.html: 觀察名單
- contact.html: 聯繫管理員
- profile.html: 我的帳號
- admin.html: 管理後台
- login.html: 登入註冊
- manifest.json: PWA設定
- js/supabase.js: 共用函數
- css/base.css: 全站樣式

## Supabase 資料表

- profiles: 用戶資料 (id, display_name, plan)
- points: 點數餘額 (user_id, balance)
- point_logs: 點數記錄
- watchlist: 觀察名單
- messages: 用戶訊息客服
- news: 市場新聞 (show_on_home)
- announcements: 官方公告 (is_pinned, show_on_home)
- tutorials: 教學文章 (show_on_home)
- daily_analysis: 每日盤面解析 (show_on_home)

## 用戶方案

- free: 免費，功能全鎖
- tw: 台股會員
- us: 美股會員
- all: 全市場
- admin: 管理員+後台

## 點數系統

- 每日登入補100點
- AI健診扣1點
- 管理員可手動加點

## 部署流程

1. 修改檔案
2. git add .
3. git commit -m "說明"
4. git push origin main
5. 等1分鐘自動部署
6. Cmd+Shift+R 清除快取

## 管理員操作

### 開通用戶
admin.html > 會員管理 > 重新整理 > 改方案

### 回覆訊息+發Groq Key
admin.html > 用戶訊息 > 填回覆 > 填入我的Key > 回覆

### 發布內容
admin.html > 選Tab > 填內容 > 勾選顯示在首頁 > 發布

### 插入圖片
點插入圖片按鈕 > 上傳 > 自動插入游標位置

## 用戶流程

1. 註冊帳號
2. 看到帳號未開通提示
3. 聯繫管理員送出申請
4. 管理員回覆+附Groq Key
5. 用戶一鍵套用Key
6. 管理員升級方案
7. 功能全開

## 常見問題

- 網站沒更新: Cmd+Shift+R
- git push失敗: Token過期，重新產生Classic Token(repo+workflow)
- AI診斷失敗: 檢查Groq Key格式(gsk_開頭)
- 功能被鎖: 後台升級用戶方案
- 頁面空白: Safari Console看錯誤
