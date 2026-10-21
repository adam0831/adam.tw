# adam.tw

Adam Chang 的個人網站。用 [Astro](https://astro.build) 產生靜態網頁，推上 GitHub 後由 GitHub Actions 自動發佈到 GitHub Pages（https://adam.tw）。

## 第一次在 Mac 上設定

```bash
# 需要 Node.js 22 以上（brew install node）
git clone https://github.com/adam0831/adam.tw.git
cd adam.tw
npm install
npm run dev        # 打開 http://localhost:4321 預覽
```

## 寫一篇新文章

```bash
npm run new -- my-post-slug "文章標題"
```

會在 `src/content/posts/my-post-slug.md` 建立一篇草稿，網址是 `https://adam.tw/posts/my-post-slug/`。

文章開頭的設定：

```yaml
---
title: 文章標題
description: 一句話摘要（會出現在列表和搜尋結果）
date: 2026-10-21
tags: [AI, Apple]
draft: true        # 草稿只在本機 npm run dev 看得到；寫完改成 false
---
```

圖片放在 `public/images/`，文章裡用 `![說明](/images/檔名.jpg)`。

## 發佈

```bash
git add .
git commit -m "新文章：文章標題"
git push
```

推到 `main` 之後約一分鐘，網站就會更新。進度在 GitHub 的 **Actions** 分頁看得到。

## 檔案結構

| 位置 | 用途 |
| --- | --- |
| `src/content/posts/` | 文章（Markdown） |
| `src/pages/` | 頁面：首頁、文章列表、標籤、關於、RSS |
| `src/layouts/Base.astro` | 共用的頁首、頁尾、`<head>` |
| `src/styles/global.css` | 全站樣式（自動深色模式） |
| `src/consts.ts` | 網站名稱、選單、社群連結 |
| `public/` | 原樣複製的檔案（`CNAME`、favicon、圖片） |
