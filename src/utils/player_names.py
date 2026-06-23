from __future__ import annotations

"""
球员中英文名称映射表

目录结构用球员英文名，但报告正文用中文名。
所有函数接受英文名、返回中文名；未收录的返回原名。
"""

_PLAYER_NAME_MAP: dict[str, str] = {
    # ═══ 土耳其 (Türkiye) ═══
    "Abdülkerim Bardakcı": "巴尔达克奇",
    "Arda Güler": "居莱尔",
    "Barış Alper Yılmaz": "伊尔马兹",
    "Can Uzun": "乌尊",
    "Deniz Gül": "居尔",
    "Eren Elmalı": "埃尔马勒",
    "Ferdi Kadıoğlu": "卡迪奥卢",
    "Hakan Çalhanoğlu": "恰尔汗奥卢",
    "İsmail Yüksek": "于克塞克",
    "Kenan Yıldız": "伊尔迪兹",
    "Kerem Aktürkoğlu": "阿克蒂尔克奥卢",
    "Merih Demiral": "德米拉尔",
    "Mert Müldür": "米尔迪尔",
    "Orkun Kökçü": "科克库",
    "Uğurcan Çakır": "恰基尔",
    "Yunus Akgün": "阿克金",
    "Samet Akaydin": "阿卡伊丁",
    "Zeki Çelik": "切利克",
    "Salih Özcan": "厄兹詹",
    "İrfan Can Kahveci": "卡赫韦吉",
    "Cenk Tosun": "托松",

    # ═══ 巴拉圭 (Paraguay) ═══
    "Alexandro Maidana": "迈达纳",
    "Andrés Cubas": "库巴斯",
    "Damián Bobadilla": "博瓦迪利亚",
    "Diego Gómez": "迭戈·戈麦斯",
    "Gabriel Ávalos": "阿瓦洛斯",
    "Gustavo Gómez": "古斯塔沃·戈麦斯",
    "Gustavo Velázquez": "贝拉斯克斯",
    "Isidro Pitta": "皮塔",
    "José Canale": "卡纳莱",
    "Juan Cáceres": "卡塞雷斯",
    "Juan José Cáceres": "卡塞雷斯",
    "Julio Enciso": "恩西索",
    "Júnior Alonso": "阿隆索",
    "Matías Galarza Fonda": "加拉尔萨·方达",
    "Miguel Almirón": "阿尔米隆",
    "Omar Alderete": "阿尔德雷特",
    "Orlando Gill": "希尔",
    "Ramón Sosa": "索萨",
    "Antonio Sanabria": "萨纳布里亚",
    "Ángel Romero": "罗梅罗",
    "Fabián Balbuena": "巴尔布埃纳",
    "Robert Rojas": "罗哈斯",
    "Mathías Villasanti": "比利亚桑蒂",
    "Richard Sánchez": "桑切斯",
    "Carlos Coronel": "科罗内尔",
    "Rodrigo Morínigo": "莫里尼戈",

    # ═══ 挪威 (Norway) ═══
    "Erling Haaland": "哈兰德",
    "Martin Ødegaard": "厄德高",
    "Alexander Sørloth": "索尔洛特",
    "Antonio Nusa": "努萨",
    "Oscar Bobb": "博布",
    "Marcus Pedersen": "佩德森",
    "Kristoffer Ajer": "阿耶尔",
    "Julian Ryerson": "瑞尔森",
    "Sander Berge": "贝格",
    "Patrick Berg": "帕特里克·贝格",
    "Fredrik Aursnes": "奥尔斯内斯",
    "Andreas Schjelderup": "谢尔德鲁普",
    "David Møller Wolfe": "沃尔夫",
    "Torbjørn Heggem": "赫格姆",
    "Leo Østigård": "厄斯蒂高",
    "Ørjan Nyland": "尼兰",

    # ═══ 塞内加尔 (Senegal) ═══
    "Sadio Mané": "马内",
    "Ismaïla Sarr": "伊斯梅拉·萨尔",
    "Nicolas Jackson": "杰克逊",
    "Kalidou Koulibaly": "库利巴利",
    "Edouard Mendy": "爱德华·门迪",
    "Idrissa Gana Gueye": "盖耶",
    "Pape Gueye": "帕佩·盖耶",
    "Pape Matar Sarr": "帕佩·马塔尔·萨尔",
    "Lamine Camara": "卡马拉",
    "Krépin Diatta": "迪亚塔",
    "Ismail Jakobs": "雅各布斯",
    "Moussa Niakhaté": "尼亚卡特",
    "El Hadji Malick Diouf": "迪乌夫",
    "Ibrahim Mbaye": "姆巴耶",
    "Mory Diaw": "迪奥",
    "Pathé Ismaël Ciss": "西斯",
}


def to_chinese(name: str) -> str:
    """英文球员名 → 中文名。"""
    return _PLAYER_NAME_MAP.get(name, name)


def all_names() -> dict:
    """返回完整映射表。"""
    return dict(_PLAYER_NAME_MAP)
