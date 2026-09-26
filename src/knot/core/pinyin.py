"""拼音检索：内嵌常用汉字（会计/记账语境）无声调拼音表。

覆盖内置别名与常见科目用字；未收录的字视为不可匹配，不影响其它匹配路径。
"""

from __future__ import annotations

from collections.abc import Iterable

TABLE: dict[str, str] = {}


def _load(pairs: str) -> None:
    """每项形如 '资zi 产chan …'，成对存储以压缩代码体积。"""
    for item in pairs.split():
        TABLE[item[0]] = item[1:]


_load(
    "资zi 产chan 负fu 债zhai 权quan 益yi 收shou 入ru 费fei 用yong 现xian 金jin "
    "银yin 行hang 招zhao 建jian 工gong 商shang 支zhi 付fu 宝bao 微wei 信xin "
    "卡ka 花hua 呗bei 贷dai 款kuan 房fang 车che 期qi 初chu 资zi 本ben 公gong 积ji "
    "工gong 资zi 奖jiang 金jin 理li 财cai 投tou 证zheng 券quan 基ji 股gu 票piao "
    "餐can 饮yin 饭fan 早zao 午wu 晚wan 外wai 卖mai 交jiao 通tong 打da 地di 铁tie "
    "公gong 共gong 居ju 住zhu 水shui 电dian 燃ran 气qi 物wu 业ye 购gou 买mai 医yi 疗liao "
    "娱yu 乐le 教jiao 育yu 人ren 情qing 往wang 来lai 待dai 分fen 类lei 类lei 学xue 习xi "
    "书shu 籍ji 培pei 训xun 礼li 红hong 包bao 转zhuan 账zhang 借jie 还huan 报bao 销xiao "
    "补bu 贴tie 退tui 款kuan 利li 息xi 分fen 红hong 租zu 押ya 折zhe 旧jiu 摊tan 销xiao "
    "应ying 收shou 付fu 预yu 存cun 货huo 固gu 定ding 无wu 形xing 长chang 短duan 流liu 动dong "
    "损sun 益yi 年nian 月yue 日ri 利li 润run 配pei 盈ying 余yu 实shi 保bao 险xian 通tong "
    "讯xun 话hua 网wang 服fu 装zhuang 化hua 妆zhuang 宠chong 旅lv 游you 酒jiu 店dian 机ji "
    "火huo 团tuan 建jian 生sheng 活huo 家jia 庭ting 子zi 女nv 父fu 母mu 朋peng 友you 同tong 事shi "
    "学xue 校xiao 公gong 司si 项xiang 目mu 部bu 门men 费fei 报bao 表biao 图tu 额e "
    "两liang 个ge 零ling 整zheng 舍she 位wei 元yuan 角jiao 分fen 账zhang 户hu 号hao 密mi 码ma"
)

_LETTERS = set("abcdefghijklmnopqrstuvwxyz")
_SEPARATORS = (":", "-", "_", " ")


def _clean(text: str) -> str:
    for separator in _SEPARATORS:
        text = text.replace(separator, "")
    return text


def pinyin_of(text: str) -> str:
    """汉字转无声调拼音；ASCII 字母数字与层级分隔符原样保留并小写。"""
    out = []
    for char in text:
        if char in TABLE:
            out.append(TABLE[char])
        elif char.lower() in _LETTERS or char.isdigit() or char in _SEPARATORS:
            out.append(char.lower())
    return "".join(out)


def initials_of(text: str) -> str:
    """取每个汉字的拼音首字母（ASCII 与分隔符原样保留）。"""
    out = []
    for char in text:
        if char in TABLE:
            out.append(TABLE[char][0])
        elif char.lower() in _LETTERS or char.isdigit() or char in _SEPARATORS:
            out.append(char.lower())
    return "".join(out)


def is_ascii_query(text: str) -> bool:
    return bool(text) and all(char.lower() in _LETTERS or char.isdigit() for char in text)


def match(query: str, candidates: Iterable[str]) -> list[str]:
    """按拼音全拼或首字母匹配候选（前缀优先），忽略层级分隔符。"""
    if not is_ascii_query(query):
        return []
    needle = _clean(query.lower())
    full_hits: list[str] = []
    initial_hits: list[str] = []
    partial: list[str] = []
    for candidate in candidates:
        full = _clean(pinyin_of(candidate))
        initials = _clean(initials_of(candidate))
        if full.startswith(needle) or initials.startswith(needle):
            full_hits.append(candidate)
        elif needle in full:
            initial_hits.append(candidate)
        elif needle in initials:
            partial.append(candidate)
    return sorted(full_hits) + sorted(initial_hits) + sorted(partial)
