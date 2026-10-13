"""模型引用与原文的比对：允许空白差异，仍然拒绝编造。

采集文本里混有 U+00A0（不间断空格）等不可见字符，模型和用户都看不到它们，
复述时只能写成普通空格。逐字符精确子串比较会把这类**只有空白形状不同**的引用判为
伪造，从而丢弃整条本来有据可查的回答（真实案例：`老君山停车场多少钱`）。

两类字符分别处理：

* 有宽度的空白（含 U+00A0、U+3000）：折成一个普通空格再比较；
* 无宽度的不可见字符（零宽空格、软连字符等）：直接删除再比较。

其余字符仍然必须逐字一致，因此编造引用照旧被拒。返回值始终是**原文切片**，
保证展示出来的引用与来源逐字一致。
"""
from __future__ import annotations

import re

# 无宽度，删除。（不含 U+FEFF 之外的 BOM 变体以外的空白，空白由 \s 处理。）
_INVISIBLE = re.compile(r'[\u00ad\u200b-\u200f\u2060\ufeff]')
# 有宽度的空白；Python 的 \s 对 str 是 Unicode 语义，已覆盖 U+00A0 与 U+3000。
_WHITESPACE = re.compile(r'\s+')


def _normalize(value: str) -> str:
    """删除无宽度字符并把空白折成单个空格，用于比较。"""
    return ' '.join(_WHITESPACE.sub(' ', _INVISIBLE.sub('', value)).split())


def _collapse(text: str) -> tuple[str, list[int]]:
    """按 :func:`_normalize` 的规则折叠 ``text``，同时记录每个字符的原文下标。"""
    kept = [(index, char) for index, char in enumerate(text) if not _INVISIBLE.match(char)]
    chars: list[str] = []
    offsets: list[int] = []
    previous_space = False
    for index, char in kept:
        if char.isspace():
            if previous_space:
                continue
            chars.append(' ')
            offsets.append(index)
            previous_space = True
        else:
            chars.append(char)
            offsets.append(index)
            previous_space = False
    return ''.join(chars), offsets


def locate_quote(text: str, quote: str) -> str | None:
    """返回 ``text`` 中能支持 ``quote`` 的原文切片；无法支持时返回 ``None``。

    Args:
        text: 来源片段原文。
        quote: 模型给出的引用。

    Returns:
        str | None: 原文中的连续切片；仅空白形状不同时也返回**原文写法**（而非模型写法），
            因此调用方直接展示它即可。实质内容对不上则返回 ``None``。
    """
    if not isinstance(text, str) or not isinstance(quote, str) or not quote:
        return None
    if quote in text:
        return quote
    trimmed = quote.strip()
    if trimmed and trimmed in text:
        return trimmed
    target = _normalize(quote)
    if not target:
        return None
    normalized, offsets = _collapse(text)
    at = normalized.find(target)
    if at == -1:
        return None
    # target 不以空白结尾，最后一个匹配字符必然是原文字符，右端点可直接加一。
    return text[offsets[at]:offsets[at + len(target) - 1] + 1]
