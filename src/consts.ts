export const SITE_TITLE = 'Adam Chang';
export const SITE_DESCRIPTION = 'Adam Chang 的個人網站 — 科技、AI、生活隨筆';
export const AUTHOR = 'Adam Chang';

export const NAV = [
  { href: '/', label: '首頁' },
  { href: '/posts/', label: '文章' },
  { href: '/tags/', label: '標籤' },
  { href: '/about/', label: '關於' },
];

export const SOCIAL = [
  { href: 'https://github.com/adam0831', label: 'GitHub' },
  { href: '/rss.xml', label: 'RSS' },
];

// Google Analytics 4 評估 ID（G- 開頭）。留空就不載入 GA；本機 npm run dev 也不會送出資料。
export const GA_MEASUREMENT_ID = '';

export function formatDate(d: Date) {
  return d.toLocaleDateString('zh-TW', { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'Asia/Taipei' });
}
