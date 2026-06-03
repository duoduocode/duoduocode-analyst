from __future__ import annotations

# 球员中文名映射表
# key 为 API-Football 返回的英文名，value 为中文译名
PLAYER_CN_NAMES: dict[str, str] = {
    # PSG
    "O. Dembele": "登贝莱",
    "K. Kvaratskhelia": "克瓦拉茨赫利亚",
    "Ousmane Dembélé": "登贝莱",
    "João Neves": "若昂·内维斯",
    "B. Barcola": "巴尔科拉",
    "Achraf Hakimi": "阿什拉夫·哈基米",
    "Matvey Safonov": "萨福诺夫",
    "G. Ramos": "贡萨洛·拉莫斯",
    "Vitinha": "维蒂尼亚",
    "F. Ruiz": "法比安·鲁伊斯",
    "W. Pacho": "帕乔",
    "Marquinhos": "马尔基尼奥斯",
    "L. Hernandez": "卢卡斯·埃尔南德斯",
    "N. Mendes": "努诺·门德斯",
    "D. Doue": "杜埃",
    "S. Mayulu": "马尤卢",
    "P. Kimpembe": "金彭贝",
    "Y. Zague": "扎格",
    "M. Asensio": "阿森西奥",
    "Lee Kang-In": "李刚仁",
    "R. Kolo Muani": "科洛·穆阿尼",
    "G. Restes": "雷斯特",
    "W. Zaire-Emery": "扎伊尔-埃梅里",
    "I. Zabarnyi": "扎巴尔尼",
    "L. Beraldo": "贝拉尔多",

    # Arsenal
    "K. Havertz": "哈弗茨",
    "Bukayo Saka": "萨卡",
    "M. Odegaard": "厄德高",
    "L. Trossard": "特罗萨德",
    "J. Timber": "廷贝尔",
    "G. Martinelli": "马丁内利",
    "V. Gyökeres": "哲凯赖什",
    "N. Madueke": "马杜埃凯",
    "C. Mosquera": "莫斯克拉",
    "Cristhian Mosquera": "莫斯克拉",
    "W. Saliba": "萨利巴",
    "Gabriel": "加布里埃尔",
    "Gabriel Magalhães": "加布里埃尔",
    "R. Calafiori": "卡拉菲奥里",
    "T. Partey": "托马斯",
    "D. Rice": "赖斯",
    "M. Merino": "梅里诺",
    "E. Nwaneri": "恩瓦内里",
    "David Raya": "大卫·拉亚",
    "Neto": "内托",
    "Jorginho": "若日尼奥",
    "K. Tierney": "蒂尔尼",
    "O. Zinchenko": "津琴科",
    "M. Lewis-Skelly": "刘易斯-斯凯利",
    "R. Sterling": "斯特林",
}


def get_cn_name(en_name: str) -> str:
    """查找球员中文名，若未收录则返回原英文名"""
    return PLAYER_CN_NAMES.get(en_name, en_name)
