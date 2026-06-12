# GeoSite → Surge

[![Convert Rules for Surge](https://github.com/wfxllb/geosite-to-surge/actions/workflows/run.yml/badge.svg)](https://github.com/wfxllb/geosite-to-surge/actions/workflows/run.yml)

将 [Loyalsoldier/v2ray-rules-dat](https://github.com/Loyalsoldier/v2ray-rules-dat)（基于 v2fly/domain-list-community 增强）的 GeoSite 域名分类数据**自动转换**为 [Surge](https://nssurge.com/) 兼容的规则集，每日更新。

## 为什么需要这个？

| 代理工具 | GeoSite 支持 |
|---------|-------------|
| Clash / mihomo | ✅ 原生 `GEOSITE,category,policy` |
| Surge | ❌ 不支持 geosite |

有了这个仓库，Surge 也能像 Clash 一样使用 geosite 规则：

```
RULE-SET,https://raw.githubusercontent.com/wfxllb/geosite-to-surge/release/geo/geosite/openai.conf,Proxy
RULE-SET,https://raw.githubusercontent.com/wfxllb/geosite-to-surge/release/geo/geosite/netflix.conf,Proxy
RULE-SET,https://raw.githubusercontent.com/wfxllb/geosite-to-surge/release/geo/geosite/telegram.conf,Proxy
RULE-SET,https://raw.githubusercontent.com/wfxllb/geosite-to-surge/release/geo/geosite/cn.conf,DIRECT
```

GeoIP 规则也附带提供：

```
RULE-SET,https://raw.githubusercontent.com/wfxllb/geosite-to-surge/release/geo/geoip/CN.conf,DIRECT
```

## 规则格式

Surge RULE-SET 标准格式，每行一条：

- `DOMAIN-SUFFIX,google.com` — 匹配域名及其所有子域名
- `DOMAIN,www.google.com` — 仅精确匹配该域名
- `DOMAIN-KEYWORD,google` — 匹配域名中包含该关键词的

## 可用分类

所有 `release/geo/geosite/*.conf` 文件，例如：

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
| … | （更多见 release 分支） |

## 更新机制

- **定时**：GitHub Actions 每天 UTC 22:30（北京时间 06:30）自动运行
- **手动**：在 Actions 页面点击 "Run workflow"
- 流程：下载最新 `geosite.dat` → MetaCubeX/geo 解包 → sed/grep 转换 → 推到 `release` 分支

## 技术细节

转换逻辑（与 NSZA156/surge-geox-rules 相同）：

| GeoSite 原格式 | Surge 规则 | 说明 |
|---------------|-----------|------|
| `domain:google.com` | `DOMAIN-SUFFIX,google.com` | 域名 + 所有子域名 |
| `full:www.google.com` | `DOMAIN,www.google.com` | 精确匹配 |
| `keyword:xxx` | `DOMAIN-KEYWORD,xxx` | 域名关键词匹配 |
| `include:cat` | ✅ 展开合并 | 引用其他分类 |
| `@attr` | ✅ 自动拆分 | 属性分类独立文件 |

## 数据来源

| 数据 | 上游 |
|------|------|
| GeoSite 域名 | [Loyalsoldier/v2ray-rules-dat](https://github.com/Loyalsoldier/v2ray-rules-dat) |
| GeoIP 国家 | [Loyalsoldier/geoip](https://github.com/Loyalsoldier/geoip) |
