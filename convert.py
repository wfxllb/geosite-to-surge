#!/usr/bin/env python3
"""
GeoSite → Surge Rule Set Converter

解析 v2fly/domain-list-community 的 data/ 目录，
将 domain:/full:/regexp:/include: 等指令转换为 Surge .list 格式。

用法:
    python convert.py                          # 从本地 data/ 读取
    python convert.py --source /path/to/data   # 指定数据源目录
    python convert.py --output /path/to/rules  # 指定输出目录

输出格式:
    Surge RULE-SET (.list) — 标准 DOMAIN-SUFFIX, / DOMAIN, 格式
    DOMAIN-SUFFIX,domain.com  → 匹配 domain.com 及所有子域名
    DOMAIN,exact.host         → 精确匹配
"""

import os
import re
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional


# ── 可跳过的大体积/不常用分类 ──────────────────────
SKIP_CATEGORIES: Set[str] = set()


def parse_line(line: str) -> Tuple[str, str, str]:
    """
    解析一行 geosite 规则。
    返回: (rule_type, value, attributes)
      rule_type ∈ {domain, full, keyword, regexp, include, comment, empty}
    """
    line = line.strip()
    if not line:
        return ("empty", "", "")

    # 纯注释行
    if line.startswith("#"):
        return ("comment", line, "")

    # 去除行内注释（空格+#）
    if " #" in line:
        line = line.split(" #")[0].strip()
        if not line:
            return ("empty", "", "")

    # 匹配显式指令类型
    for prefix in ("include:", "domain:", "full:", "keyword:", "regexp:"):
        if line.startswith(prefix):
            value = line[len(prefix):].strip()
            # 分离 @attr 属性标记
            parts = value.split("@", 1)
            value = parts[0].strip()
            attrs = parts[1].strip() if len(parts) > 1 else ""
            return (prefix[:-1], value, attrs)

    # 无前缀默认 = domain: (V2Ray 域名列表标准约定)
    value = line
    parts = value.split("@", 1)
    value = parts[0].strip()
    attrs = parts[1].strip() if len(parts) > 1 else ""
    # 跳过无效的域名（无 TLD，如 bare "youtube"）
    if "." not in value:
        return ("skip", value, attrs)
    return ("domain", value, attrs)


def rule_to_surge(rule_type: str, value: str) -> Optional[str]:
    """
    将 geosite 规则转为 Surge RULE-SET 标准格式。
    返回 None 表示无法转换（如 keyword、复杂正则）。
    """
    if rule_type == "domain":
        # domain:google.com → DOMAIN-SUFFIX,google.com
        return f"DOMAIN-SUFFIX,{value}"

    elif rule_type == "full":
        # full:www.google.com → DOMAIN,www.google.com (精确匹配)
        return f"DOMAIN,{value}"

    elif rule_type == "regexp":
        # 尝试转换简单正则为 DOMAIN-SUFFIX
        # .*\.domain\.com → DOMAIN-SUFFIX,domain.com
        # 复杂的正则（含 | 选择、\d 等）直接放弃
        if "|" in value or "(" in value or ")" in value:
            return None
        if re.search(r"\\[dwDsSwW]", value):
            return None
        # 尝试: .*\.foo\.bar\.com
        m = re.match(r"^\.\*((?:\\\.[a-z0-9][-a-z0-9]*)+)$", value, re.IGNORECASE)
        if m:
            suffix = m.group(1).replace("\\.", ".")
            return f"DOMAIN-SUFFIX,{suffix}"
        return None

    elif rule_type == "keyword":
        # Surge RULE-SET 不支持关键字匹配
        return None

    return None


def load_category(
    data_dir: Path,
    category: str,
    resolved: Set[str],
    cache: Dict[str, List[Tuple[str, Optional[str]]]],
    depth: int = 0,
) -> List[Tuple[str, Optional[str]]]:
    """
    递归加载一个 geosite 分类，解析所有 include 引用。
    返回: [(原始行或注释, surge规则或None), ...]
    
    使用 cache 避免重复加载，用 resolved 检测循环引用。
    """
    if category in cache:
        return cache[category]

    if category in resolved:
        print(f"  ⚠ 循环引用: {category}", file=sys.stderr)
        return [("# ⚠ Circular include skipped", None)]

    resolved.add(category)

    file_path = data_dir / category
    if not file_path.exists():
        print(f"  ⚠ 分类文件不存在: {category}", file=sys.stderr)
        return []

    rules: List[Tuple[str, Optional[str]]] = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            rt, val, attrs = parse_line(line)

            if rt == "empty":
                continue

            if rt == "comment":
                continue

            if rt == "include":
                sub = load_category(data_dir, val, resolved.copy(), cache, depth + 1)
                rules.extend(sub)
                continue

            if rt in ("unknown", "skip"):
                continue

            surge = rule_to_surge(rt, val)
            if surge:
                rules.append(("", surge))

    cache[category] = rules
    return rules


def deduplicate(rules: List[Tuple[str, Optional[str]]]) -> List[str]:
    """去除重复域名，保持首次出现顺序。"""
    seen: Set[str] = set()
    result: List[str] = []
    for _, surge in rules:
        if surge and surge not in seen:
            seen.add(surge)
            result.append(surge)
    return result


def count_domains(lines: List[str]) -> int:
    """统计域名规则数量。"""
    return sum(1 for l in lines if l)


def main():
    parser = argparse.ArgumentParser(
        description="GeoSite → Surge Rule Set Converter"
    )
    parser.add_argument(
        "--source", "-s",
        default="domain-list-community/data",
        help="v2fly/domain-list-community data 目录路径",
    )
    parser.add_argument(
        "--output", "-o",
        default="rules",
        help="输出目录路径",
    )
    parser.add_argument(
        "--skip", nargs="*",
        default=[],
        help="跳过的分类名",
    )
    args = parser.parse_args()

    data_dir = Path(args.source)
    if not data_dir.exists():
        print(f"❌ 数据目录不存在: {data_dir}")
        print("   请先 clone v2fly/domain-list-community:")
        print("   git clone https://github.com/v2fly/domain-list-community.git")
        sys.exit(1)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 发现所有分类文件
    categories = sorted(
        f.name
        for f in data_dir.iterdir()
        if f.is_file() and not f.name.startswith(".")
    )

    print(f"📂 发现 {len(categories)} 个 geosite 分类")
    print(f"📝 开始转换为 Surge .list 格式…\n")

    skip_set = SKIP_CATEGORIES | set(args.skip)
    cache: Dict[str, List[Tuple[str, Optional[str]]]] = {}

    converted = 0
    total_domains = 0

    for cat in categories:
        if cat in skip_set:
            continue

        rules = load_category(data_dir, cat, set(), cache)
        if not rules:
            continue

        lines = deduplicate(rules)
        domain_count = count_domains(lines)
        if domain_count == 0:
            continue

        output_file = output_dir / f"{cat}.list"
        with open(output_file, "w", encoding="utf-8", newline="\n") as f:
            for line in lines:
                f.write(line + "\n")

        print(f"  ✅ geosite:{cat:<45s} → {domain_count:>6d} 条规则")
        converted += 1
        total_domains += domain_count

    print(f"\n🎉 完成！{converted} 个分类，{total_domains} 条域名规则")
    print(f"   输出目录: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
