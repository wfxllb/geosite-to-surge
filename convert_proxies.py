#!/usr/bin/env python3
"""
Clash 订阅 → Surge 代理列表转换器
支持两种输入格式：
  1. URI 格式（ss:// / trojan:// / vmess:// 每行一个，Base64 整体编码或明文）
  2. Clash YAML 格式（proxies: 列表）
输出：Surge [Proxy] 段格式，可直接粘贴到 .conf 文件，
      也可保存为独立文件通过 policy-path 引用。

用法:
  python3 convert_proxies.py <订阅URL或本地文件> <输出文件>

示例:
  python3 convert_proxies.py "https://your-sub-url" proxies.txt
  python3 convert_proxies.py Nikki.yaml proxies.txt
"""

import sys
import re
import base64
import urllib.request
import urllib.parse
import json

# ── Base64 解码工具 ────────────────────────────────────────────────

def decode_b64(encoded: str) -> str:
    """尝试 Base64 解码，失败则返回原字符串。"""
    try:
        padded = encoded + "=" * (4 - len(encoded) % 4)
        return base64.urlsafe_b64decode(padded).decode("utf-8", errors="ignore")
    except Exception:
        return encoded


# ── URI 解析器 ─────────────────────────────────────────────────────

def parse_ss(uri: str) -> dict | None:
    """解析 ss:// URI（SIP002 格式）"""
    if not uri.startswith("ss://"):
        return None
    rest = uri[5:]
    name = ""
    if "#" in rest:
        rest, name_enc = rest.split("#", 1)
        name = urllib.parse.unquote(name_enc)

    # 新格式: base64(method:password@host:port)#name
    try:
        decoded = decode_b64(rest)
        if "@" in decoded:
            userinfo, serverinfo = decoded.split("@", 1)
            if ":" in userinfo:
                method, password = userinfo.split(":", 1)
                host, port = serverinfo.rsplit(":", 1)
                return {
                    "name": name, "type": "ss",
                    "method": method, "password": password,
                    "host": host, "port": int(port),
                }
    except Exception:
        pass

    # 旧格式: base64(method:password)@host:port#name
    if "@" in rest:
        userinfo_b64, serverinfo = rest.split("@", 1)
        try:
            userinfo = decode_b64(userinfo_b64)
            if ":" in userinfo:
                method, password = userinfo.split(":", 1)
                host, port = serverinfo.rsplit(":", 1)
                return {
                    "name": name, "type": "ss",
                    "method": method, "password": password,
                    "host": host, "port": int(port),
                }
        except Exception:
            pass
    return None


def parse_trojan(uri: str) -> dict | None:
    """解析 trojan:// URI"""
    if not uri.startswith("trojan://"):
        return None
    rest = uri[9:]
    name = ""
    if "#" in rest:
        rest, name_enc = rest.split("#", 1)
        name = urllib.parse.unquote(name_enc)
    if "?" in rest:
        main, query = rest.split("?", 1)
        params = urllib.parse.parse_qs(query)
    else:
        main, params = rest, {}
    if "@" not in main:
        return None
    password, server_part = main.split("@", 1)
    password = urllib.parse.unquote(password)
    host = server_part
    port = 443
    if ":" in host:
        # IPv6 安全处理
        if host.startswith("["):
            idx = host.index("]")
            host, port_part = host[:idx+1], host[idx+2:]
            port = int(port_part)
        else:
            h, p = host.rsplit(":", 1)
            host, port = h, int(p)
    sni = (params.get("sni", params.get("peer", [""]))[0])
    return {
        "name": name, "type": "trojan",
        "password": password, "host": host, "port": port,
        "sni": sni,
    }


def parse_vmess(uri: str) -> dict | None:
    """解析 vmess:// URI（Base64 JSON）"""
    if not uri.startswith("vmess://"):
        return None
    rest = uri[8:]
    name = ""
    if "#" in rest:
        rest, name_enc = rest.split("#", 1)
        name = urllib.parse.unquote(name_enc)
    try:
        decoded = decode_b64(rest)
        cfg = json.loads(decoded)
        return {
            "name": cfg.get("ps", name) or name,
            "type": "vmess",
            "host": cfg.get("add", ""),
            "port": int(cfg.get("port", 443)),
            "uuid": cfg.get("id", ""),
            "alter_id": int(cfg.get("aid", 0)),
            "security": cfg.get("scy", "auto"),
            "network": cfg.get("net", "tcp"),
            "tls": cfg.get("tls", ""),
            "sni": cfg.get("sni", ""),
            "path": cfg.get("path", ""),
            "host_header": cfg.get("host", ""),
        }
    except Exception:
        return None


def parse_vless(uri: str) -> dict | None:
    """解析 vless:// URI"""
    if not uri.startswith("vless://"):
        return None
    rest = uri[8:]
    name = ""
    if "#" in rest:
        rest, name_enc = rest.split("#", 1)
        name = urllib.parse.unquote(name_enc)
    if "?" in rest:
        main, query = rest.split("?", 1)
        params = urllib.parse.parse_qs(query)
    else:
        main, params = rest, {}
    if "@" not in main:
        return None
    uuid, server_part = main.split("@", 1)
    host = server_part
    port = 443
    if ":" in host and not host.startswith("["):
        h, p = host.rsplit(":", 1)
        host, port = h, int(p)
    sni = params.get("sni", params.get("peer", [""]))[0]
    return {
        "name": name, "type": "vless",
        "uuid": uuid, "host": host, "port": port,
        "sni": sni,
        "tls": "tls" in params,
    }


# ── Surge 格式输出 ─────────────────────────────────────────────────

def clean_name(name: str) -> str:
    """清理节点名称，保留中文/英文/数字/常用符号。"""
    name = re.sub(r'[^\w\u4e00-\u9fff\u3400-\u4dbf\-_. \#@（）()\[\]:：]', '', name).strip()
    return name or "node"


def to_surge_ss(p: dict) -> str:
    n = clean_name(p["name"])
    return f'{n} = ss, {p["host"]}, {p["port"]}, encrypt-method={p["method"]}, password={p["password"]}'


def to_surge_trojan(p: dict) -> str:
    n = clean_name(p["name"])
    line = f'{n} = trojan, {p["host"]}, {p["port"]}, password={p["password"]}'
    if p.get("sni"):
        line += f', sni={p["sni"]}'
    return line


def to_surge_vmess(p: dict) -> str:
    n = clean_name(p["name"])
    line = f'{n} = vmess, {p["host"]}, {p["port"]}, username={p["uuid"]}'
    if p.get("alter_id", 0) != 0:
        line += f', alter-id={p["alter_id"]}'
    if p.get("security") and p["security"] != "auto":
        line += f', encrypt-method={p["security"]}'
    if p.get("tls"):
        line += ", tls=true"
    if p.get("sni"):
        line += f', sni={p["sni"]}'
    if p.get("network") == "ws":
        line += ", ws=true"
        if p.get("path"):
            line += f', ws-path={p["path"]}'
        if p.get("host_header"):
            line += f', ws-header=Host:{p["host_header"]}'
    return line


def to_surge_vless(p: dict) -> str:
    n = clean_name(p["name"])
    line = f'{n} = vless, {p["host"]}, {p["port"]}, username={p["uuid"]}'
    if p.get("tls"):
        line += ", tls=true"
    if p.get("sni"):
        line += f', sni={p["sni"]}'
    return line


PARSERS = [parse_ss, parse_trojan, parse_vmess, parse_vless]
FORMATTERS = {
    "ss": to_surge_ss,
    "trojan": to_surge_trojan,
    "vmess": to_surge_vmess,
    "vless": to_surge_vless,
}


# ── 订阅获取 ───────────────────────────────────────────────────────

def fetch_content(src: str) -> str:
    """获取订阅内容（支持 URL 或本地文件）。"""
    if src.startswith("http://") or src.startswith("https://"):
        req = urllib.request.Request(
            src, headers={"User-Agent": "Clash", "Accept": "*/*"}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
    else:
        with open(src, "r", encoding="utf-8", errors="ignore") as f:
            raw = f.read().encode()
    # 尝试整体 Base64 解码
    try:
        decoded = base64.b64decode(raw).decode("utf-8", errors="ignore")
        if "ss://" in decoded or "trojan://" in decoded or "vmess://" in decoded:
            return decoded
        if "proxies:" in decoded or "port:" in decoded:
            return decoded
    except Exception:
        pass
    return raw.decode("utf-8", errors="ignore")


def parse_clash_yaml_manual(content: str) -> list[dict]:
    """简单的 YAML proxies 解析（不依赖 pyyaml，手动解析常见字段）。"""
    proxies = []
    in_proxies = False
    current = None
    indent = 0
    for line in content.splitlines():
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        cur_indent = len(line) - len(stripped)
        if stripped.startswith("proxies:"):
            in_proxies = True
            continue
        if in_proxies:
            if cur_indent <= indent and not stripped.startswith("-"):
                in_proxies = False
                continue
            if stripped.startswith("-"):
                if current:
                    proxies.append(current)
                current = {}
                stripped = stripped[1:].lstrip()
            # 简单 key: value 解析
            if ":" in stripped:
                k, v = stripped.split(":", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and current is not None:
                    # 类型转换
                    if v.lower() == "true":
                        current[k] = True
                    elif v.lower() == "false":
                        current[k] = False
                    else:
                        try:
                            if "." in v:
                                current[k] = float(v)
                            else:
                                current[k] = int(v)
                        except Exception:
                            current[k] = v
    if current:
        proxies.append(current)
    return proxies


def convert_clash_proxies(proxies: list[dict]) -> list[str]:
    """将 Clash proxies 列表转为 Surge 格式。"""
    results = []
    for p in proxies:
        t = p.get("type", "")
        name = clean_name(p.get("name", "node"))
        if t == "ss":
            line = f'{name} = ss, {p["server"]}, {p["port"]}, encrypt-method={p.get("cipher", p.get("method", "aes-256-gcm"))}, password={p["password"]}'
            results.append(line)
        elif t == "trojan":
            line = f'{name} = trojan, {p["server"]}, {p["port"]}, password={p["password"]}'
            if p.get("sni") or p.get("servername"):
                line += f', sni={p.get("sni") or p.get("servername")}'
            if p.get("skip-cert-verify"):
                line += ", allow-insecure=true"
            results.append(line)
        elif t == "vmess":
            line = f'{name} = vmess, {p["server"]}, {p["port"]}, username={p["uuid"]}'
            if p.get("alterId", 0) != 0:
                line += f', alter-id={p["alterId"]}'
            if p.get("cipher"):
                line += f', encrypt-method={p["cipher"]}'
            net = p.get("network", "tcp")
            if net == "ws":
                line += ", ws=true"
                opts = p.get("ws-opts", {})
                if opts.get("path"):
                    line += f', ws-path={opts["path"]}'
                headers = opts.get("headers", {})
                if headers.get("Host"):
                    line += f', ws-header=Host:{headers["Host"]}'
            if p.get("tls"):
                line += ", tls=true"
                if p.get("servername") or p.get("sni"):
                    line += f', sni={p.get("servername") or p.get("sni")}'
            results.append(line)
        elif t == "vless":
            line = f'{name} = vless, {p["server"]}, {p["port"]}, username={p["uuid"]}'
            if p.get("tls"):
                line += ", tls=true"
                if p.get("sni") or p.get("servername"):
                    line += f', sni={p.get("sni") or p.get("servername")}'
            results.append(line)
    return results


# ── 主流程 ────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    src = sys.argv[1]
    output_file = sys.argv[2]

    print(f"[1/4] 读取订阅: {src[:60]}{'...' if len(src) > 60 else ''}")
    content = fetch_content(src)
    print(f"       大小: {len(content)} 字节")

    surge_lines: list[str] = []

    # 尝试解析 Clash YAML 格式
    print("[2/4] 检测格式...")
    proxies_yaml = parse_clash_yaml_manual(content)
    if proxies_yaml:
        print(f"       ✅ Clash YAML 格式，发现 {len(proxies_yaml)} 个节点")
        surge_lines = convert_clash_proxies(proxies_yaml)
    else:
        # 尝试提取 URI 格式
        print("       ⚠️  非 YAML，尝试提取 URI...")
        all_uris = re.findall(r'(ss://[^\s#"\'<>\n]+)', content)
        all_uris += re.findall(r'(trojan://[^\s#"\'<>\n]+)', content)
        all_uris += re.findall(r'(vmess://[^\s#"\'<>\n]+)', content)
        all_uris += re.findall(r'(vless://[^\s#"\'<>\n]+)', content)
        print(f"       发现 {len(all_uris)} 个 URI")
        for uri in all_uris:
            for parser in PARSERS:
                parsed = parser(uri)
                if parsed:
                    fmt = FORMATTERS.get(parsed["type"])
                    if fmt:
                        surge_lines.append(fmt(parsed))
                    break

    # 去重
    seen = set()
    unique_lines = []
    for line in surge_lines:
        name = line.split("=")[0].strip()
        if name not in seen:
            seen.add(name)
            unique_lines.append(line)

    print(f"[3/4] 转换完成: {len(unique_lines)} 个节点（已去重）")
    if unique_lines:
        print(f"       示例: {unique_lines[0][:80]}...")

    print(f"[4/4] 写入: {output_file}")
    with open(output_file, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(unique_lines) + "\n")

    print(f"\n✅ 完成！")
    print(f"\n下一步（二选一）:")
    print(f"  A. 将输出的 {output_file} 内容粘贴到 Surge 配置的 [Proxy] 段")
    print(f"  B. 将 {output_file} 上传到可访问的 URL，在 [Proxy Group] 中引用:")
    print(f"     AllNodes = select, policy-path=https://你的URL/{output_file}, hidden=true")
    print(f"\n⚠️  如果节点数为 0，说明订阅格式不支持，请通过 Sub-Store 转换。")


if __name__ == "__main__":
    main()
