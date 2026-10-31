// 週轉率 / 族群量比 共用（概念股雷達 concepts.html、全市場籌碼雷達 chips.html）
// 資料：Supabase tw_turnover（trading-bot/turnover_scanner.py 每交易日 16:30 寫入）
// 族群量比 = 概念內個股「今日量 ÷ 前20日均量」的中位數。
//   · 用中位數而非平均：一檔冷門股爆量 50 倍不會把整個族群拉成「熱」。
//   · 週轉率 < LIQ_MIN 的冷門股不列入（量太小，量比沒有意義）。
(function (global) {
  var URL = 'https://kldumnxdlgovaxtiszyn.supabase.co';
  var ANON = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtsZHVtbnhkbGdvdmF4dGlzenluIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzgxMjIyNDgsImV4cCI6MjA5MzY5ODI0OH0.P_anfYpSV2tgCPIQ7uZDVBjUFY3UhfEXk9u3XjlzBHI';
  var H = { 'apikey': ANON, 'Authorization': 'Bearer ' + ANON };
  var LIQ_MIN = 0.1;      // 週轉率 % 門檻
  var HOT = 1.5, WARM = 1.15, COLD = 0.7;
  var COLS = 'code,date,turnover,ratio,level,vol_state,setup,signal,zone,industry';

  async function latestDate() {
    var r = await fetch(URL + '/rest/v1/tw_turnover?select=date&order=date.desc&limit=1', { headers: H });
    var d = await r.json();
    return (Array.isArray(d) && d.length) ? d[0].date : null;
  }

  // codes 為 null → 撈全市場（分頁）；否則依代號分批撈
  async function load(codes) {
    var date = await latestDate();
    var map = {};
    if (!date) return { date: null, map: map };
    var add = function (rows) { (Array.isArray(rows) ? rows : []).forEach(function (x) { map[String(x.code)] = x; }); };
    if (!codes) {
      for (var from = 0; ; from += 1000) {
        var res = await fetch(URL + '/rest/v1/tw_turnover?select=' + COLS + '&date=eq.' + date, {
          headers: Object.assign({}, H, { 'Range-Unit': 'items', 'Range': from + '-' + (from + 999) })
        });
        var batch = await res.json();
        add(batch);
        if (!Array.isArray(batch) || batch.length < 1000) break;
      }
    } else {
      var uniq = Array.from(new Set(codes.map(String)));
      for (var i = 0; i < uniq.length; i += 150) {
        var part = uniq.slice(i, i + 150);
        var r2 = await fetch(URL + '/rest/v1/tw_turnover?select=' + COLS + '&date=eq.' + date +
          '&code=in.(' + part.join(',') + ')', { headers: H });
        add(await r2.json());
      }
    }
    return { date: date, map: map };
  }

  function stats(codes, map) {
    var rs = [], hot = 0;
    codes.forEach(function (c) {
      var x = map[String(c)];
      if (!x || x.ratio === null || x.ratio === undefined || (Number(x.turnover) || 0) < LIQ_MIN) return;
      var v = Number(x.ratio);
      rs.push(v);
      if (v >= HOT) hot++;
    });
    if (!rs.length) return null;
    rs.sort(function (a, b) { return a - b; });
    var m = rs.length % 2 ? rs[(rs.length - 1) / 2] : (rs[rs.length / 2 - 1] + rs[rs.length / 2]) / 2;
    return { med: Math.round(m * 100) / 100, hot: hot, n: rs.length };
  }

  // 依官方產業別分組算量比中位數：回 {產業名: stats}（全市場 map 才有意義）
  function industryStats(map) {
    var groups = {};
    Object.keys(map).forEach(function (c) {
      var ind = map[c].industry;
      if (!ind) return;
      (groups[ind] = groups[ind] || []).push(c);
    });
    var out = {};
    Object.keys(groups).forEach(function (ind) {
      var st = stats(groups[ind], map);
      if (st && st.n >= 3) out[ind] = st;      // 有效檔數太少的產業不算
    });
    return out;
  }

  function heat(med) {
    if (med === null || med === undefined) return { cls: 'none', icon: '', label: '-' };
    if (med >= HOT) return { cls: 'hot', icon: '🔥', label: '資金湧入' };
    if (med >= WARM) return { cls: 'warm', icon: '♨️', label: '升溫' };
    if (med <= COLD) return { cls: 'cold', icon: '🧊', label: '冷清' };
    return { cls: 'flat', icon: '', label: '持平' };
  }

  var COLOR = { hot: '#ff5470', warm: '#ffb020', flat: '#8a9bb5', cold: '#4da3ff', none: '#666' };

  function badge(st, withCount) {
    if (!st) return '<span style="color:#666">-</span>';
    var h = heat(st.med);
    return '<span title="族群量比(中位數) ' + st.med + '×｜' + h.label + '｜放量(≥1.5×) ' + st.hot + '/' + st.n + ' 檔" ' +
      'style="color:' + COLOR[h.cls] + ';font-family:monospace;white-space:nowrap">' + h.icon + st.med.toFixed(2) + '×' +
      (withCount ? '<span style="opacity:.7;font-size:.85em"> ' + st.hot + '/' + st.n + '</span>' : '') + '</span>';
  }

  function turnoverCell(x) {
    if (!x || x.turnover === null || x.turnover === undefined) return '<span style="color:#666">-</span>';
    var t = Number(x.turnover);
    var c = t >= 10 ? '#ff5470' : (t >= 3 ? '#ffb020' : (t >= 1 ? '#ddd' : '#777'));
    var tip = (x.level || '') + (x.signal ? '｜' + x.signal : '');
    return '<span title="' + tip.replace(/"/g, '') + '" style="color:' + c + ';font-family:monospace;white-space:nowrap">' +
      t.toFixed(2) + '%</span>' +
      (x.setup ? '<div style="font-size:.78em;color:#999;white-space:nowrap">' + x.setup + '</div>' : '');
  }

  global.TurnoverGroups = { load: load, stats: stats, industryStats: industryStats, heat: heat, badge: badge, turnoverCell: turnoverCell, LIQ_MIN: LIQ_MIN };
})(window);
