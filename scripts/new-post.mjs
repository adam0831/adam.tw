// 用法：npm run new -- my-post-slug "文章標題"
import { writeFileSync, existsSync } from 'node:fs';

const [slug, ...titleParts] = process.argv.slice(2);
if (!slug || !/^[a-z0-9-]+$/.test(slug)) {
  console.error('用法：npm run new -- <英文網址代稱，例如 my-first-post> "文章標題"');
  process.exit(1);
}
const title = titleParts.join(' ') || slug;
const file = `src/content/posts/${slug}.md`;
if (existsSync(file)) {
  console.error(`已經有 ${file} 了`);
  process.exit(1);
}
const today = new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Taipei' });
writeFileSync(
  file,
  `---\ntitle: ${JSON.stringify(title)}\ndescription: ""\ndate: ${today}\ntags: []\ndraft: true\n---\n\n開始寫吧。\n`,
);
console.log(`已建立 ${file}（草稿，寫完把 draft 改成 false 再推上 GitHub）`);
