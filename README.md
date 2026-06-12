# GeoSite → Surge

[![Update Rules](https://github.com/wfxllb/geosite-to-surge/actions/workflows/update.yml/badge.svg)](https://github.com/wfxllb/geosite-to-surge/actions/workflows/update.yml)

将 [v2fly/domain-list-community](https://github.com/v2fly/domain-list-community) 的 GeoSite 域名分类数据**自动转换**为 [Surge](https://nssurge.com/) 兼容的 `.list` 规则集，每日更新。

## 为什么需要这个？

| 代理工具 | GeoSite 支持 |
|---------|-------------|
| Clash / mihomo | ✅ 原生 `GEOSITE,category,policy` |
| Surge | ❌ 不支持 geosite |

有了这个仓库，Surge 也能像 Clash 一样使用 geosite 规则：

```
RULE-SET,https://raw.githubusercontent.com/wfxllb/geosite-to-surge/main/rules/openai.list,Proxy
RULE-SET,https://raw.githubusercontent.com/wfxllb/geosite-to-surge/main/rules/netflix.list,Proxy
RULE-SET,https://raw.githubusercontent.com/wfxllb/geosite-to-surge/main/rules/telegram.list,Proxy
RULE-SET,https://raw.githubusercontent.com/wfxllb/geosite-to-surge/main/rules/cn.list,DIRECT
```

## 规则格式

Surge RULE-SET (.list) 标准格式，每行一条：

- `DOMAIN-SUFFIX,google.com` — 匹配 `google.com` 及其所有子域名
- `DOMAIN,www.google.com` — 仅精确匹配该域名

## 可用分类

所有 `rules/*.list` 文件，文件名与 v2fly 上游数据目录一致，例如：

| 分类 | 说明 |
|------|------|
| `openai` | OpenAI / ChatGPT |
| `netflix` | Netflix |
| `google` | Google 服务 |
| `telegram` | Telegram |
| `youtube` | YouTube |
| `twitter` | Twitter / X |
| `cn` | 中国大陆常见域名 |
| `geolocation-cn` | 境内 CDN / 服务 |
| `geolocation-!cn` | 境外域名 |
| `category-ads` | 广告/追踪域名 |
| … | （更多见 rules/ 目录） |

## 更新机制

- **定时**：GitHub Actions 每天 UTC 00:00 自动运行
- **手动**：在 Actions 页面点击 "Run workflow"
- 从 [v2fly/domain-list-community](https://github.com/v2fly/domain-list-community) 拉取最新数据 → 转换 → 自动推送

## 技术细节

转换逻辑：

| GeoSite 原格式 | Surge RULE-SET | 说明 |
|---------------|----------------|------|
| `domain:google.com` | `DOMAIN-SUFFIX,google.com` | 域名 + 所有子域名 |
| `full:www.google.com` | `DOMAIN,www.google.com` | 精确匹配 |
| `regexp:.*\.x\.com` | `DOMAIN-SUFFIX,x.com` | 简单正则自动转 |
| `keyword:xxx` | ❌ 跳过 | RULE-SET 不支持关键词 |
| `include:cat` | ✅ 展开合并 | 递归解析引用 |
