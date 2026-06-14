let selectedPayment = 'Credit';
let discountAmount = 0;
const ORIGINAL_PRICE = 3600;
const PROMO_CODES = { 'MG571H': 1200 };

function selectPayment(type) {
  selectedPayment = type;
  document.querySelectorAll('.payment-opt').forEach(el => el.classList.remove('selected'));
  document.getElementById('pay-' + type).classList.add('selected');
}

function applyPromo() {
  const code = document.getElementById('promo-code').value.trim().toUpperCase();
  const msg = document.getElementById('promo-msg');
  if (PROMO_CODES[code]) {
    discountAmount = PROMO_CODES[code];
    msg.style.display = 'block';
    msg.style.color = '#00c853';
    msg.textContent = '✅ 優惠碼套用成功！折抵 NT$' + discountAmount;
    document.getElementById('discount-row').style.display = 'flex';
    document.getElementById('discount-amt').textContent = '-NT$' + discountAmount;
    document.getElementById('total-amt').textContent = 'NT$' + (ORIGINAL_PRICE - discountAmount);
  } else {
    msg.style.display = 'block';
    msg.style.color = 'var(--red)';
    msg.textContent = '❌ 優惠碼無效';
    discountAmount = 0;
    document.getElementById('discount-row').style.display = 'none';
    document.getElementById('total-amt').textContent = 'NT$' + ORIGINAL_PRICE;
  }
}

async function submitOrder() {
  const name = document.getElementById('buyer-name').value.trim();
  const email = document.getElementById('buyer-email').value.trim();
  const phone = document.getElementById('buyer-phone').value.trim();

  if (!name) { alert('請填寫姓名'); return; }
  if (!email || !email.includes('@')) { alert('請填寫正確的 Email'); return; }
  if (!selectedPayment) { alert('請選擇付款方式'); return; }

  const btn = document.getElementById('submit-btn');
  btn.disabled = true;
  btn.textContent = '處理中...';

  const totalAmt = ORIGINAL_PRICE - discountAmount;
  const promoCode = document.getElementById('promo-code').value.trim().toUpperCase();

  try {
    const resp = await fetch('https://web-production-9ba5b.up.railway.app/ecpay/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, phone, payment_type: selectedPayment, amount: totalAmt, promo_code: promoCode })
    });

    const data = await resp.json();
    if (data.html) {
      const div = document.createElement('div');
      div.innerHTML = data.html;
      document.body.appendChild(div);
      div.querySelector('form').submit();
    } else {
      alert('建立訂單失敗，請稍後再試');
      btn.disabled = false;
      btn.textContent = '前往付款 →';
    }
  } catch(e) {
    alert('網路錯誤，請稍後再試');
    btn.disabled = false;
    btn.textContent = '前往付款 →';
  }
}
