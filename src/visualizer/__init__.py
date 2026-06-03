import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# 配置中文字体
import matplotlib.font_manager as fm
_chinese_fonts = [f.name for f in fm.fontManager.ttflist if any(
    k in f.name.lower() for k in ["simhei", "microsoft yahei"]
)]
if _chinese_fonts:
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = [_chinese_fonts[0], "SimHei", "Microsoft YaHei"] + \
        plt.rcParams["font.sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False

HOME_COLOR = "#2ecc71"
HOME_COLOR_DARK = "#27ae60"
AWAY_COLOR = "#3498db"
AWAY_COLOR_DARK = "#2980b9"
NEUTRAL_COLOR = "#95a5a6"
HIGHLIGHT_COLOR = "#e74c3c"
