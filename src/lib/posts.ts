import { getCollection } from 'astro:content';

/** 已發佈的文章，新到舊。草稿（draft: true）只在本機 `npm run dev` 時顯示。 */
export async function getPosts() {
  const posts = await getCollection('posts', ({ data }) => import.meta.env.DEV || !data.draft);
  return posts.sort((a, b) => b.data.date.valueOf() - a.data.date.valueOf() || b.id.localeCompare(a.id));
}
