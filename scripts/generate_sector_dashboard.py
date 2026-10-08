#!/usr/bin/env python3
"""
A股概念板块趋势仪表盘 v2.3
- 概念板块分类 (THS同花顺): PCB/CPO/存储芯片/AI等373个概念
- 多周期排序: 日/5日/20日 (数据不足时显示提示, 不再静默回退)
- Top20领涨 + Bottom10领跌
- 行间内嵌板块详情面板 (点击行间动态展开, 流畅切换)
- 领涨个股多因子筛选 (涨幅×35%+成交额×25%+活跃度×15%+匹配度×15%+价格×10%)
- ETF全覆盖映射 (150+ 概念→ETF 精确匹配)
- v2.3: 行间内嵌详情; 15只领涨股+多因子; ETF映射扩展至150+
"""
from __future__ import annotations

import json
import sys
import os
import re
import concurrent.futures
from datetime import datetime, date, timedelta
from pathlib import Path
from collections import OrderedDict
import warnings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HISTORY_FILE = PROJECT_ROOT / 'outputs' / 'concept_history.json'
MAX_HISTORY_DAYS = 30
MAX_CONCURRENT = 15  # 并发请求数
MAX_STOCKS_PER_CONCEPT = 15  # 每个概念最多展示的个股数

# ── 概念→ETF映射表 (v2.3 大幅扩展) ────────
# 格式: 关键词匹配(概念名包含此词) → [ETF代码, ETF名称]
CONCEPT_ETF_MAP = {
    # 半导体/芯片链
    'PCB': ['159796', 'PCB ETF'],
    '半导体': ['159825', '半导体ETF'], '芯片': ['159825', '半导体ETF'],
    '存储': ['159825', '半导体ETF'], '集成电路': ['159825', '半导体ETF'],
    'CPO': ['159869', '通信ETF'], '光通信': ['159869', '通信ETF'], '光模块': ['159869', '通信ETF'],
    '先进封装': ['588200', '科创芯片ETF'], '中芯国际': ['588200', '科创芯片ETF'],
    '光刻': ['588200', '科创芯片ETF'], '国家大基金': ['588200', '科创芯片ETF'],
    '第三代半导体': ['159825', '半导体ETF'], 'MCU': ['159825', '半导体ETF'],
    'MiniLED': ['561600', '消费电子ETF'], 'OLED': ['561600', '消费电子ETF'],
    # 算力/AI
    '算力': ['516510', '云计算ETF'], 'AI': ['516510', '云计算ETF'],
    '人工智能': ['516510', '云计算ETF'], '大模型': ['159729', '人工智能ETF'],
    'AIGC': ['159729', '人工智能ETF'], 'ChatGPT': ['159729', '人工智能ETF'],
    '东数西算': ['516510', '云计算ETF'], '液冷服务器': ['516510', '云计算ETF'],
    '华为昇腾': ['159729', '人工智能ETF'], '华为鲲鹏': ['159729', '人工智能ETF'],
    '华为欧拉': ['562570', '信创ETF'], '鸿蒙': ['562570', '信创ETF'],
    '华为海思': ['159825', '半导体ETF'], '信创': ['562570', '信创ETF'],
    # 机器人/高端制造
    '机器人': ['562500', '机器人ETF'], '工业母机': ['159667', '工业母机ETF'],
    '工业4': ['159667', '工业母机ETF'], '智能制造': ['159667', '工业母机ETF'],
    '高端装备': ['159667', '工业母机ETF'], '新型工业化': ['159667', '工业母机ETF'],
    '专精特新': ['588000', '科创50ETF'],
    # 新能源链
    '新能源': ['516160', '新能源ETF'], '光伏': ['516880', '光伏ETF'],
    'HJT': ['516880', '光伏ETF'], 'TOPCON': ['516880', '光伏ETF'],
    '钙钛矿': ['516880', '光伏ETF'], 'BC电池': ['516880', '光伏ETF'],
    '锂电': ['159840', '锂电池ETF'], '电池': ['159840', '锂电池ETF'],
    '钠离子': ['159840', '锂电池ETF'], '固态电池': ['159840', '锂电池ETF'],
    '充电桩': ['516160', '新能源ETF'], '换电': ['516160', '新能源ETF'],
    '储能': ['159611', '电力ETF'], '虚拟电厂': ['159611', '电力ETF'],
    '氢能源': ['516160', '新能源ETF'], '风电': ['516160', '新能源ETF'],
    '核电': ['159611', '电力ETF'], '电力': ['159611', '电力ETF'],
    '智能电网': ['159611', '电力ETF'], '特高压': ['159611', '电力ETF'],
    '绿色电力': ['159611', '电力ETF'], '碳中和': ['560550', '碳中和ETF'],
    # 汽车
    '汽车': ['516110', '汽车ETF'], '智能驾驶': ['516520', '智能驾驶ETF'],
    '新能源车': ['516110', '汽车ETF'], '特斯拉': ['516520', '智能驾驶ETF'],
    '比亚迪': ['516110', '汽车ETF'], '无人驾驶': ['516520', '智能驾驶ETF'],
    '低空经济': ['563300', '低空经济ETF'],
    # 军工
    '军工': ['512660', '军工ETF'], '国防': ['512660', '军工ETF'],
    '航母': ['512660', '军工ETF'], '大飞机': ['512660', '军工ETF'],
    '商业航天': ['512660', '军工ETF'],
    # 医药
    '医药': ['512010', '医药ETF'], '医疗': ['512170', '医疗ETF'],
    'CXO': ['512170', '医疗ETF'], '医疗器械': ['512170', '医疗ETF'],
    '创新药': ['512010', '医药ETF'], '中药': ['159647', '中药ETF'],
    '医美': ['512010', '医药ETF'], '辅助生殖': ['512010', '医药ETF'],
    '新冠': ['512170', '医疗ETF'],
    # 消费
    '消费': ['159928', '消费ETF'], '白酒': ['512690', '酒ETF'],
    '食品': ['515710', '食品ETF'], '预制菜': ['515710', '食品ETF'],
    '新零售': ['159928', '消费ETF'], '免税': ['159928', '消费ETF'],
    '猪肉': ['159865', '养殖ETF'], '鸡肉': ['159865', '养殖ETF'],
    '养殖': ['159865', '养殖ETF'], '农业': ['159825', '农业ETF'],
    '种业': ['159825', '农业ETF'], '粮食': ['159825', '农业ETF'],
    # 金融
    '证券': ['512880', '证券ETF'], '券商': ['512880', '证券ETF'],
    '银行': ['512800', '银行ETF'], '保险': ['512070', '非银ETF'],
    '互联网金融': ['516100', '金融科技ETF'], '数字货币': ['516100', '金融科技ETF'],
    '期货': ['512880', '证券ETF'], '多元金融': ['512070', '非银ETF'],
    # 资源/商品
    '有色': ['512400', '有色金属ETF'], '稀土': ['516780', '稀土ETF'],
    '稀土永磁': ['516780', '稀土ETF'], '黄金': ['159934', '黄金ETF'],
    '贵金属': ['159934', '黄金ETF'], '煤炭': ['515220', '煤炭ETF'],
    '钢铁': ['515210', '钢铁ETF'], '化工': ['516020', '化工ETF'],
    '磷化工': ['516020', '化工ETF'], '化肥': ['516020', '化工ETF'],
    '钛白粉': ['516020', '化工ETF'], '有机硅': ['516020', '化工ETF'],
    '油气': ['159697', '油气ETF'], '天然气': ['159697', '油气ETF'],
    '页岩气': ['159697', '油气ETF'],
    # 科技/TMT
    '通信': ['515050', '5GETF'], '5G': ['515050', '5GETF'], '6G': ['515050', '5GETF'],
    '卫星导航': ['515050', '5GETF'], '软件': ['515230', '软件ETF'],
    '计算机': ['512720', '计算机ETF'], '大数据': ['516000', '大数据ETF'],
    '数字经济': ['560800', '数字经济ETF'], '数据要素': ['516000', '大数据ETF'],
    '数据安全': ['562570', '信创ETF'], '跨境支付': ['516100', '金融科技ETF'],
    '区块链': ['516100', '金融科技ETF'], 'Web3': ['516100', '金融科技ETF'],
    '游戏': ['516010', '游戏ETF'], '传媒': ['512980', '传媒ETF'],
    '短剧': ['512980', '传媒ETF'], '直播': ['512980', '传媒ETF'],
    '电子竞技': ['516010', '游戏ETF'], '元宇宙': ['516010', '游戏ETF'],
    '消费电子': ['561600', '消费电子ETF'], '智能穿戴': ['561600', '消费电子ETF'],
    '无线耳机': ['561600', '消费电子ETF'], '苹果': ['561600', '消费电子ETF'],
    '小米': ['561600', '消费电子ETF'], '华为': ['561600', '消费电子ETF'],
    # 地产/基建
    '地产': ['512200', '房地产ETF'], '房地产': ['512200', '房地产ETF'],
    '基建': ['516950', '基建ETF'], '新型城镇化': ['516950', '基建ETF'],
    '装配式建筑': ['516950', '基建ETF'], '水利': ['516950', '基建ETF'],
    '地下管网': ['516950', '基建ETF'], '建筑装饰': ['516950', '基建ETF'],
    # 央企/国企
    '央企': ['517090', '央企ETF'], '国企': ['517180', '国企ETF'],
    '中特估': ['517090', '央企ETF'], '一带一路': ['517090', '央企ETF'],
    # 指数类
    '科创': ['588000', '科创50ETF'], '创业板': ['159915', '创业板ETF'],
    # 区域主题
    '海南': ['159928', '消费ETF'], '粤港澳': ['159915', '创业板ETF'],
    '长三角': ['159915', '创业板ETF'], '雄安': ['516950', '基建ETF'],
    '振兴东北': ['516950', '基建ETF'],
    # 其他
    '环保': ['516160', '新能源ETF'], '碳交易': ['560550', '碳中和ETF'],
    '教育': ['513030', '教育ETF'], '职业教育': ['513030', '教育ETF'],
    '物流': ['516880', '光伏ETF'], '冷链': ['516880', '光伏ETF'],
    '体育': ['516010', '游戏ETF'], '冰雪': ['516010', '游戏ETF'],
    '露营': ['159928', '消费ETF'], '电子烟': ['159928', '消费ETF'],
    '共享单车': ['516110', '汽车ETF'], '网约车': ['516110', '汽车ETF'],
    '量子': ['588000', '科创50ETF'], '脑科学': ['512170', '医疗ETF'],
    '基因': ['512170', '医疗ETF'], '养老': ['512010', '医药ETF'],
    '新质生产力': ['588000', '科创50ETF'], '科创次新': ['588000', '科创50ETF'],
    '牙科': ['512170', '医疗ETF'], '培育钻石': ['512400', '有色金属ETF'],
}

# 清理格式问题的项
for k in list(CONCEPT_ETF_MAP.keys()):
    if '}{' in k:
        del CONCEPT_ETF_MAP[k]


def _match_etf(concept_name):
    """根据概念名匹配最相关的ETF"""
    for keyword, (code, name) in CONCEPT_ETF_MAP.items():
        if keyword in concept_name:
            return {'code': code, 'name': name}
    return None


# ── 数据获取 ──────────────────────────────────────────

def get_index_data():
    """获取主要指数行情（优先新浪API，回退东方财富）"""
    indices = []

    # 方案1: 直接请求新浪API（最可靠）
    try:
        import requests as _req
        code_map = {
            's_sh000001': '上证', 's_sz399001': '深成指', 's_sz399006': '创业板',
            's_sh000688': '科创50', 's_sh000300': '沪深300', 's_sh000016': '上证50',
        }
        resp = _req.get(
            'http://hq.sinajs.cn/list=' + ','.join(code_map.keys()),
            headers={'Referer': 'https://finance.sina.com.cn'},
            timeout=10
        )
        if resp.status_code == 200:
            for code, name in code_map.items():
                line_match = [l for l in resp.text.split('\n') if code in l]
                if line_match:
                    parts = line_match[0].split('"')[1].split(',')
                    if len(parts) >= 4:
                        price = float(parts[1])
                        prev_close = float(parts[2])
                        change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close > 0 else 0
                        vol_yi = round(float(parts[8]) / 1e8, 1) if len(parts) > 8 else 0
                        indices.append({
                            'name': name, 'price': price,
                            'change_pct': change_pct, 'vol_yi': vol_yi,
                        })
        if indices:
            return indices
    except Exception as e:
        print(f"[WARN] Sina index: {e}", file=sys.stderr)

    # 方案2: 东方财富指数行情（可能被代理拦截）
    try:
        import akshare as ak
        df = ak.stock_zh_index_spot_em()
        codes = ['sh000001', 'sz399001', 'sz399006', 'sh000688', 'sh000300', 'sh000016']
        name_map = {
            'sh000001': '上证', 'sz399001': '深成指', 'sz399006': '创业板',
            'sh000688': '科创50', 'sh000300': '沪深300', 'sh000016': '上证50',
        }
        for code in codes:
            row = df[df['代码'] == code]
            if len(row) > 0:
                r = row.iloc[0]
                indices.append({
                    'name': name_map.get(code, code),
                    'price': float(r['最新价']),
                    'change_pct': float(r['涨跌幅']),
                    'vol_yi': round(float(r.get('成交额', 0)) / 1e8, 1),
                })
    except Exception as e:
        print(f"[WARN] index spot: {e}", file=sys.stderr)

    return indices


def fetch_market_overview(all_stocks=None):
    """获取市场涨跌统计,可复用已有的全量数据"""
    try:
        df = all_stocks
        if df is None:
            import akshare as ak
            df = ak.stock_zh_a_spot()
        up = int((df['涨跌幅'] > 0).sum())
        down = int((df['涨跌幅'] < 0).sum())
        flat = int((df['涨跌幅'] == 0).sum())
        limit_up = int((df['涨跌幅'] >= 9.9).sum())
        limit_down = int((df['涨跌幅'] <= -9.9).sum())
        total_amount = float(df['成交额'].sum()) / 1e8
        return {
            'total': len(df), 'up': up, 'down': down, 'flat': flat,
            'limit_up': limit_up, 'limit_down': limit_down,
            'amount_yi': round(total_amount, 1),
            'up_ratio': round(up / len(df) * 100, 1),
        }
    except Exception as e:
        print(f"[WARN] market overview: {e}", file=sys.stderr)
        return {'total': 0, 'up': 0, 'down': 0, 'flat': 0,
                'limit_up': 0, 'limit_down': 0, 'amount_yi': 0, 'up_ratio': 0}


def _fetch_one_concept_info(name):
    """获取单个概念板块的详细信息"""
    try:
        import akshare as ak
        df = ak.stock_board_concept_info_ths(symbol=name)
        row = df.set_index('项目')['值'].to_dict()
        change_str = row.get('板块涨幅', '0%')
        try:
            change_pct = float(change_str.replace('%', ''))
        except ValueError:
            change_pct = 0.0

        rank_str = row.get('涨幅排名', '')
        updown_str = row.get('涨跌家数', '0/0')
        try:
            parts = updown_str.split('/')
            up_count = int(parts[0]) if len(parts) > 0 else 0
            down_count = int(parts[1]) if len(parts) > 1 else 0
        except:
            up_count, down_count = 0, 0

        vol_str = row.get('成交额(亿)', '0')
        try:
            amount_yi = float(vol_str)
        except:
            amount_yi = 0.0

        flow_str = row.get('资金净流入(亿)', '0')
        try:
            fund_flow = float(flow_str)
        except:
            fund_flow = 0.0

        return {
            'name': name,
            'change_pct': change_pct,
            'rank': rank_str,
            'up_count': up_count,
            'down_count': down_count,
            'amount_yi': amount_yi,
            'fund_flow': fund_flow,
            'open': row.get('今开', ''),
            'prev_close': row.get('昨收', ''),
            'high': row.get('最高', ''),
            'low': row.get('最低', ''),
        }
    except Exception as e:
        return {'name': name, 'change_pct': 0, 'rank': '', 'up_count': 0, 'down_count': 0,
                'amount_yi': 0, 'fund_flow': 0, 'error': str(e)[:80]}


def fetch_all_concepts():
    """并发获取所有概念板块行情(带重试+缓存降级)"""
    import akshare as ak
    import time as _time

    # Try up to 3 times to get concept names
    all_names = None
    for attempt in range(3):
        try:
            names_df = ak.stock_board_concept_name_ths()
            all_names = names_df['name'].tolist()
            break
        except Exception as e:
            print(f"  [RETRY {attempt+1}/3] stock_board_concept_name_ths failed: {e}", file=sys.stderr)
            if attempt < 2:
                _time.sleep(3)

    # Fallback: combine cached names + hardcoded major concepts
    if not all_names:
        print("  [FALLBACK] combining cached + hardcoded concept names")
        all_names = _build_concept_name_list()
        all_names = list(set(all_names))  # dedup
        print(f"  → combined {len(all_names)} unique concept names")

    print(f"  → 共 {len(all_names)} 个概念板块, 并发获取行情...")

    concepts = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as ex:
        futures = {ex.submit(_fetch_one_concept_info, n): n for n in all_names}
        done = 0
        for future in concurrent.futures.as_completed(futures):
            done += 1
            if done % 50 == 0:
                print(f"    [{done}/{len(all_names)}] ...")
            result = future.result()
            if 'error' not in result:
                concepts.append(result)

    concepts.sort(key=lambda x: x['change_pct'], reverse=True)
    print(f"  → 成功获取 {len(concepts)} 个概念, 耗时约{len(all_names)//MAX_CONCURRENT}s")
    return concepts


def _build_concept_name_list():
    """混合构建概念名称列表：缓存历史 + 硬编码重要概念"""
    names = set()

    # Source 1: Cached history
    history = load_history()
    if history:
        for d in history:
            names.update(history[d].keys())

    # Source 2: Known major THS concept names (supplement missing ones)
    major = [
        '国家大基金持股','存储芯片','先进封装','PCB概念','CPO概念','AI手机','中芯国际概念',
        'MiniLED','OLED','MCU芯片','华为海思概念股','AI PC','科创次新股','光刻机','光刻胶',
        '华为欧拉','华为鲲鹏','鸿蒙概念','华为昇腾','汽车芯片','集成电路概念','第三代半导体',
        '半导体及元件','芯片概念','5G概念','6G概念','通信设备','卫星导航','低空经济',
        '机器人概念','人工智能','ChatGPT概念','AIGC概念','算力租赁','东数西算','液冷服务器',
        '光伏概念','HJT电池','TOPCON电池','钙钛矿电池','BC电池','钠离子电池','固态电池',
        '锂电池','新能源车','特斯拉概念','比亚迪概念','无人驾驶','智能座舱',
        '数字经济','信创','数据要素','数据安全','数字货币','跨境支付','虚拟数字人',
        '元宇宙','混合现实','空间计算','游戏概念','短剧概念','直播概念','网络游戏',
        '医药概念','CXO概念','医疗器械概念','创新药','中药概念','新冠治疗',
        '白酒概念','预制菜','新零售','地摊经济','免税概念',
        '军工概念','航母概念','大飞机','商业航天',
        '碳交易','碳中和','碳达峰','环保概念',
        '国企改革','央企改革','中特估','一带一路',
        '区块链','Web3.0','NFT概念','消费电子','智能穿戴','无线耳机','无线充电',
        '工业母机','新型工业化','专精特新','高压快充','充电桩','换电概念',
        '储能','虚拟电厂','智能电网','特高压','电力改革',
        '核电','风电','绿色电力','氢能源',
        '稀土永磁','有色','小金属','黄金概念','煤炭概念',
        '猪肉','鸡肉','农业种植','种业','粮食概念',
        '建筑装饰','新型城镇化','装配式建筑','水利','地下管网',
        '互联网金融','多元金融','期货概念','信托概念','海南自贸区',
        '天然气','油服','可燃冰','页岩气',
        '超清视频','超导概念','C2M概念','民爆概念',
        '供销社','统一大市场','露营经济','冰雪产业','电子竞技',
        '振兴东北','粤港澳大湾区','长三角一体化','雄安新区',
        '同花顺漂亮100','富时罗素概念股','标普道琼斯A股','深股通','沪股通','MSCI概念',
        '钛白粉概念','有机硅概念','化工概念','化肥概念','磷化工','草甘膦',
        '高端装备','工业4.0','智能制造',
        '参股银行','参股券商','期货概念','保险概念',
        '物流概念','冷链物流','快递概念',
        '教育概念','职业教育','在线教育',
        '体育产业','足球概念','冰雪产业',
        '水利概念','海绵城市','污水处理','垃圾分类',
        '苹果概念','小米概念','华为概念','荣耀概念','OPPO概念',
        '电子烟','烟草概念','工业大麻',
        '共享单车','网约车','移动支付','互联网金融',
        '工业互联网','边缘计算','数字孪生','量子科技','脑科学',
        '基因编辑','辅助生殖','医美概念','养老概念',
        'NFT概念','元宇宙','数字人','Web3.0',
        '新质生产力','中特估','数据要素',
    ]
    names.update(major)
    return list(names)


def _extract_keywords(concept_name):
    """从概念名称中提取搜索关键词"""
    import re as _re
    name = concept_name.replace('概念', '').strip()
    keywords = []
    eng_words = _re.findall(r'[A-Za-z0-9]{2,}', name)
    keywords.extend(eng_words)
    cn_words = _re.findall(r'[\u4e00-\u9fff]{2,}', name)
    stop_words = {'板块','指数','方向','概念','主题','投资','行业','产业','相关','受益'}
    cn_words = [w for w in cn_words if w not in stop_words]
    keywords.extend(cn_words)
    if '国家大基金' in name or '大基金' in name:
        keywords.extend(['半导体', '集成电路', '芯片'])
    if '先进封装' in name:
        keywords.append('封装')
    if '存储' in name:
        keywords.append('存储')
    return list(set(keywords))


def match_concept_stocks(concept_name, all_stocks):
    """通过关键词匹配A股全量数据,返回Top10个股(
    综合得分=涨跌幅×0.5 + 成交额归一化×0.3 + 股价强度×0.2)"""
    keywords = _extract_keywords(concept_name)
    if not keywords:
        return []

    matched = []
    for _, row in all_stocks.iterrows():
        stock_name = str(row.get('名称', ''))
        # 检查股票名是否包含任一关键词
        score = 0
        for kw in keywords:
            if kw.upper() in stock_name.upper():
                score += 1
        if score > 0:
            try:
                chg = float(row.get('涨跌幅', 0))
                amount = float(row.get('成交额', 0)) / 1e8  # 转为亿
                vol = float(row.get('成交量', 0)) / 1e4  # 转为万手
                price = float(row.get('最新价', 0))
            except (ValueError, TypeError):
                continue
            matched.append({
                'code': str(row.get('代码', '')),
                'name': stock_name,
                'price': price,
                'change_pct': chg,
                'amount_yi': amount,
                'volume_wan': vol,
                'match_score': score,
            })

    if not matched:
        return []

    # 计算综合得分并排序 (多因子: 涨幅+流动性+活跃度+匹配度+价格)
    if matched:
        max_amount = max(s['amount_yi'] for s in matched) or 1
        max_vol = max(s.get('volume_wan', 0) for s in matched) or 1
        for s in matched:
            s['composite'] = (
                s['change_pct'] * 0.35                    # 涨跌幅 35%
                + min(s['amount_yi'] / max_amount * 25, 25)  # 成交额归一化 25%
                + min(s.get('volume_wan', 0) / max_vol * 15, 15)  # 成交量归一化 15%
                + s['match_score'] * 3                    # 关键词匹配 15% (3分/词)
                + min(s['price'] / 100 * 10, 10)          # 价格因子 10%
            )

    matched.sort(key=lambda x: x['composite'], reverse=True)
    return matched[:MAX_STOCKS_PER_CONCEPT]


def prefetch_concept_stocks(concepts, all_stocks):
    """为前30个概念预取成分股(Top20领涨+Bottom10领跌)"""
    target = concepts[:20] + concepts[-10:]
    print(f"  → 为 {len(target)} 个概念匹配成分股...")
    stocks_map = {}
    etf_map = {}
    for c in target:
        name = c['name']
        stocks = match_concept_stocks(name, all_stocks)
        if stocks:
            stocks_map[name] = stocks
        etf = _match_etf(name)
        if etf:
            etf_map[name] = etf
    has_stocks = sum(1 for v in stocks_map.values() if v)
    print(f"  → {has_stocks}/{len(target)} 个概念匹配到成分股, {len(etf_map)}个匹配到ETF")
    return stocks_map, etf_map


# ── 历史数据管理 ──────────────────────────────────────

def load_history():
    """加载历史概念数据 (返回OrderedDict确保按键排序)"""
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            # 确保返回OrderedDict, 按日期排序 (popitem兼容 + 排序一致性)
            return OrderedDict(sorted(raw.items()))
        except Exception:
            pass
    return OrderedDict()


def save_history(history):
    """保存历史概念数据 (最多保留MAX_HISTORY_DAYS天)"""
    # 删除最旧的条目直到满足上限 (兼容OrderedDict和普通dict)
    while len(history) > MAX_HISTORY_DAYS:
        oldest_key = next(iter(history))
        del history[oldest_key]
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def update_concept_history(concepts):
    """将今日概念数据存入历史"""
    history = load_history()
    today_str = date.today().isoformat()

    snapshot = {}
    for c in concepts:
        snapshot[c['name']] = {
            'change_pct': c['change_pct'],
            'amount_yi': c['amount_yi'],
            'up_count': c['up_count'],
            'down_count': c['down_count'],
            'fund_flow': c['fund_flow'],
        }
    history[today_str] = snapshot

    # 清理旧数据 (使用兼容方法避免popitem兼容性问题)
    while len(history) > MAX_HISTORY_DAYS:
        oldest_key = next(iter(history))
        del history[oldest_key]
    save_history(history)
    return history


def calc_period_changes(concepts, history):
    """计算多周期涨跌幅"""
    today = date.today()
    periods = {}
    
    # 找5个和20个交易日前的日期
    dates_in_history = sorted(history.keys())
    
    # 5日前
    if len(dates_in_history) >= 5:
        five_days_ago = dates_in_history[-5]
        snapshot_5d = history[five_days_ago]
        changes_5d = {}
        for c in concepts:
            name = c['name']
            if name in snapshot_5d:
                prev = snapshot_5d[name]['change_pct']
                changes_5d[name] = round(c['change_pct'] - prev, 2)
        periods['5d'] = changes_5d
    
    # 20日前
    if len(dates_in_history) >= 20:
        twenty_days_ago = dates_in_history[-20]
        snapshot_20d = history[twenty_days_ago]
        changes_20d = {}
        for c in concepts:
            name = c['name']
            if name in snapshot_20d:
                prev = snapshot_20d[name]['change_pct']
                changes_20d[name] = round(c['change_pct'] - prev, 2)
        periods['20d'] = changes_20d
    
    return periods


# ── HTML生成 ──────────────────────────────────────────

def generate_html(market, indices, concepts, periods, stocks_map=None, etf_map=None):
    """生成完整的自包含HTML仪表盘"""
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
    concepts_json = json.dumps(concepts, ensure_ascii=False)
    periods_json = json.dumps(periods, ensure_ascii=False)
    indices_json = json.dumps(indices, ensure_ascii=False)
    market_json = json.dumps(market, ensure_ascii=False)
    stocks_json = json.dumps(stocks_map or {}, ensure_ascii=False)
    etf_json = json.dumps(etf_map or {}, ensure_ascii=False)
    today_str = date.today().isoformat()

    # 用 Python 字典包装 view state
    view_json = json.dumps({
        'today': today_str,
        'periods_available': [k for k in ['日', '5日', '20日'] if k == '日' or f'{k[0]}d' in periods],
        'concept_count': len(concepts),
    }, ensure_ascii=False)

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no,viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>A股概念板块仪表盘</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;background:#0f0f14;color:#e0e0e0;min-height:100vh}}
.container{{max-width:680px;margin:0 auto;padding:10px}}

/* header */
.header{{background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);border-radius:14px;padding:18px 14px 14px;margin-bottom:10px;position:relative;overflow:hidden}}
.header::before{{content:'';position:absolute;top:-30px;right:-30px;width:100px;height:100px;background:radial-gradient(circle,rgba(231,76,60,0.3) 0%,transparent 70%)}}
.header-top{{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;position:relative;z-index:1}}
.header h1{{font-size:18px;font-weight:700;letter-spacing:0.5px}}
.header .update{{font-size:10px;color:rgba(255,255,255,0.5)}}
.idx-row{{display:flex;gap:6px;overflow-x:auto;padding-bottom:4px;-webkit-overflow-scrolling:touch;position:relative;z-index:1}}
.idx-row::-webkit-scrollbar{{display:none}}
.idx-card{{flex:0 0 auto;min-width:82px;background:rgba(255,255,255,0.08);border-radius:10px;padding:8px;text-align:center}}
.idx-card .n{{font-size:10px;color:rgba(255,255,255,0.6);margin-bottom:2px}}
.idx-card .p{{font-size:14px;font-weight:700}}
.idx-card .c{{font-size:10px;margin-top:2px}}

/* overview */
.overview{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px}}
.ov-card{{background:#1a1a2e;border-radius:12px;padding:14px 12px;text-align:center;position:relative;overflow:hidden}}
.ov-card .lbl{{font-size:11px;color:#888;margin-bottom:4px}}
.ov-card .val{{font-size:22px;font-weight:700}}
.ov-card .sub{{font-size:10px;color:#666;margin-top:3px}}

/* section */
.sec{{background:#1a1a22;border-radius:14px;padding:14px;margin-bottom:10px}}
.sec-title{{font-size:15px;font-weight:700;margin-bottom:12px;display:flex;align-items:center;gap:6px}}

/* period tabs */
.tabs{{display:flex;gap:6px;margin-bottom:12px}}
.tab{{flex:1;text-align:center;padding:7px 0;font-size:12px;border-radius:8px;cursor:pointer;color:#888;background:rgba(255,255,255,0.04);transition:all 0.2s;font-weight:500}}
.tab.active{{background:#e74c3c;color:#fff;font-weight:700}}

/* concept list */
.c-item{{display:flex;align-items:center;padding:12px 0;border-bottom:1px solid rgba(255,255,255,0.04);gap:8px;cursor:pointer;transition:background 0.15s}}
.c-item:active{{background:rgba(231,76,60,0.08);border-radius:8px;margin:0 -8px;padding:12px 8px}}
.c-item:last-child{{border-bottom:none}}
.c-rank{{width:22px;text-align:center;font-size:11px;color:#666;font-weight:700;flex-shrink:0}}
.c-rank.hot{{color:#e74c3c}}
.c-info{{flex:1;min-width:0}}
.c-name{{font-size:13px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.c-name .rm-concept{{font-size:10px;color:#666}}
.c-meta{{font-size:10px;color:#666;margin-top:2px;display:flex;gap:8px}}
.c-change{{font-size:13px;font-weight:700;text-align:right;min-width:58px;flex-shrink:0}}
.c-bar{{width:50px;height:5px;background:rgba(255,255,255,0.06);border-radius:3px;overflow:hidden;flex-shrink:0}}
.c-bar-fill{{height:100%;border-radius:3px;transition:width 0.3s}}

/* divider */
.divider{{padding:10px 0;text-align:center;font-size:11px;color:#666;position:relative}}
.divider::before,.divider::after{{content:'';position:absolute;top:50%;width:30%;height:1px;background:rgba(255,255,255,0.06)}}
.divider::before{{left:8%}}
.divider::after{{right:8%}}

/* inline detail panel (inserted between rows) */
.c-detail{{margin:10px -8px 12px;background:#1a1a2e;border-radius:14px;padding:16px;border-left:3px solid #e74c3c;animation:fadeIn 0.25s ease}}
@keyframes fadeIn{{from{{opacity:0;transform:translateY(-6px)}}to{{opacity:1;transform:translateY(0)}}}}
.c-detail-close{{float:right;font-size:18px;color:#666;cursor:pointer;width:26px;height:26px;display:flex;align-items:center;justify-content:center;border-radius:50%;background:rgba(255,255,255,0.06);flex-shrink:0}}
.c-detail-close:hover,.c-detail-close:active{{background:rgba(231,76,60,0.2);color:#e74c3c}}
.detail-header{{margin-bottom:14px;display:flex;justify-content:space-between;align-items:flex-start}}
.detail-name{{font-size:17px;font-weight:700;margin-bottom:4px}}
.detail-rank{{font-size:12px;color:#e74c3c}}
.detail-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:14px}}
.detail-stat{{background:rgba(255,255,255,0.03);border-radius:10px;padding:10px}}
.detail-stat .ds-lbl{{font-size:10px;color:#888;margin-bottom:3px}}
.detail-stat .ds-val{{font-size:16px;font-weight:700}}
.detail-stocks{{}}
.detail-stocks h4{{font-size:13px;font-weight:700;margin-bottom:10px;color:#888}}
.stock-row{{display:flex;align-items:center;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.03);gap:8px;font-size:12px}}
.stock-row .sr{{width:18px;color:#666;text-align:center;flex-shrink:0}}
.stock-row .sn{{flex:1;min-width:0;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.stock-row .sc{{font-weight:700;min-width:52px;text-align:right;flex-shrink:0}}
.stock-row .sa{{font-size:10px;color:#666;min-width:46px;text-align:right;flex-shrink:0}}

/* loading */
.loading{{text-align:center;padding:16px;color:#666;font-size:13px}}
.loading::after{{content:'...';animation:dots 1.5s steps(4,end) infinite}}
@keyframes dots{{0%,20%{{content:'.'}}40%{{content:'..'}}60%{{content:'...'}}80%,100%{{content:''}}}}

/* colors */
.up{{color:#e74c3c}}
.down{{color:#2ecc71}}
.flat{{color:#888}}
.bg-up{{background:rgba(231,76,60,0.15)}}
.bg-down{{background:rgba(46,204,113,0.15)}}

.empty{{text-align:center;padding:30px 0;color:#666;font-size:13px}}
.detail-analysis{{background:rgba(255,255,255,0.03);border-radius:10px;padding:12px;margin-bottom:12px;font-size:12px;line-height:1.6}}
.detail-analysis::before{{content:'📋 综合分析';display:block;font-weight:700;margin-bottom:6px;color:#888;font-size:13px}}
.stk-hint{{font-size:10px;color:#666;font-weight:400}}
.etf-rec{{background:linear-gradient(135deg,rgba(231,76,60,0.08) 0%,rgba(231,76,60,0.02) 100%);border:1px solid rgba(231,76,60,0.15);border-radius:12px;padding:12px 14px;margin-top:12px}}
.etf-title{{font-size:12px;font-weight:700;color:#e74c3c;margin-bottom:8px}}
.etf-link{{display:block;color:#e0e0e0;text-decoration:none;font-size:12px;padding:8px 10px;background:rgba(255,255,255,0.04);border-radius:8px;transition:background 0.2s}}
.etf-link:hover,.etf-link:active{{background:rgba(231,76,60,0.12)}}
.footer{{text-align:center;padding:20px 0;color:#555;font-size:10px}}
.footer a{{color:#888}}

@media(max-width:380px){{
    .detail-grid{{grid-template-columns:1fr}}
    .idx-card{{min-width:68px;padding:6px}}
}}
</style>
</head>
<body>
<div class="container">
<div class="header">
  <div class="header-top">
    <h1>🔬 A股概念板块</h1>
    <span class="update">更新 {current_time}</span>
  </div>
  <div class="idx-row" id="idxRow"></div>
</div>
<div class="overview" id="ov"></div>

<div class="sec">
  <div class="sec-title">🏷️ 概念板块排行</div>
  <div class="tabs" id="tabs">
    <div class="tab active" data-period="day">今日</div>
    <div class="tab" data-period="5d" id="tab5d">5日</div>
    <div class="tab" data-period="20d" id="tab20d">20日</div>
  </div>
  <div id="conceptList"></div>
</div>

<div class="footer">
  数据: 同花顺 · 仅供投资参考<br>
  <span>A股概念板块趋势仪表盘 v2.3 | 每日22:10自动更新</span>
</div>
</div>

<script>
var DATA = {concepts_json};
var PERIODS = {periods_json};
var INDICES = {indices_json};
var MARKET = {market_json};
var VIEW = {view_json};
var CONCEPT_STOCKS = {stocks_json};
var CONCEPT_ETFS = {etf_json};

var currentPeriod = 'day';
var selectedConcept = null;
var _rendering = false;  // render guard: prevents concurrent renders

// colors
var UP = '#e74c3c', DOWN = '#2ecc71';
function cclr(v){{ return v>0?UP:v<0?DOWN:'#888'; }}
function ccls(v){{ return v>0?'up':v<0?'down':'flat'; }}
function sign(v){{ return v>0?'+':''; }}

// toast notification
function showToast(msg, duration) {{
    duration = duration || 2500;
    var t = document.getElementById('_toast');
    if (!t) {{
        t = document.createElement('div');
        t.id = '_toast';
        t.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#e74c3c;color:#fff;padding:10px 20px;border-radius:20px;font-size:13px;z-index:9999;opacity:0;transition:opacity 0.3s;pointer-events:none;max-width:90vw;text-align:center;white-space:nowrap';
        document.body.appendChild(t);
    }}
    t.textContent = msg;
    t.style.opacity = '1';
    clearTimeout(t._timer);
    t._timer = setTimeout(function(){{ t.style.opacity = '0'; }}, duration);
}}

// render indices
function rIdx(){{
    var h='';
    (INDICES||[]).forEach(function(i){{
        h+='<div class="idx-card"><div class="n">'+i.name+'</div><div class="p">'+i.price.toFixed(2)+'</div><div class="c '+ccls(i.change_pct)+'">'+sign(i.change_pct)+i.change_pct.toFixed(2)+'%</div></div>';
    }});
    document.getElementById('idxRow').innerHTML=h||'<div class="idx-card"><div class="n">加载中</div><div class="p">--</div></div>';
}}

// render overview
function rOv(){{
    var m=MARKET;
    document.getElementById('ov').innerHTML=
        '<div class="ov-card"><div class="lbl">📈 上涨家数</div><div class="val up">'+m.up+'</div><div class="sub">占比 '+m.up_ratio+'%</div></div>'+
        '<div class="ov-card"><div class="lbl">📉 下跌家数</div><div class="val down">'+m.down+'</div><div class="sub">涨停'+m.limit_up+' / 跌停'+m.limit_down+'</div></div>'+
        '<div class="ov-card"><div class="lbl">💰 成交额</div><div class="val" style="font-size:17px">'+(m.amount_yi/10000).toFixed(2)+'万亿</div><div class="sub">共'+m.total+'只股票</div></div>'+
        '<div class="ov-card"><div class="lbl">🔥 概念板块</div><div class="val up">'+VIEW.concept_count+'</div><div class="sub">实时同花顺数据</div></div>';
}}

// get sorted data for current period (safe: always returns sorted clone)
function getSortedData(){{
    var data = DATA.slice();
    var pd = PERIODS[currentPeriod];
    if (currentPeriod === 'day' || !pd) {{
        // default: sort by today's change_pct descending
        data.sort(function(a,b){{ return (b.change_pct||0) - (a.change_pct||0); }});
    }} else {{
        // sort by period change descending
        data.sort(function(a,b){{ return (pd[b.name]||0) - (pd[a.name]||0); }});
    }}
    return data;
}}

function getItemChange(item){{
    if (!item) return 0;
    var pd = PERIODS[currentPeriod];
    if (pd && currentPeriod !== 'day') return pd[item.name] || item.change_pct || 0;
    return item.change_pct || 0;
}}

// render concept list (top 20 gainers + bottom 10 losers)
function rList(){{
    // Render guard: prevent concurrent renders causing UI thrash
    if (_rendering) return;
    _rendering = true;
    try {{
        var data = getSortedData();
        if (!data.length) {{ document.getElementById('conceptList').innerHTML = '<div class="empty">暂无数据</div>'; return; }}
        var top20 = data.slice(0, 20);
        var bot10 = data.slice(-10).reverse();

        // safe maxAbs calculation with fallback
        var topCh = getItemChange(top20[0]);
        var botCh = getItemChange(bot10[0]);
        var maxAbs = Math.max(Math.abs(topCh), Math.abs(botCh), 0.01);

        var h = '';
        // Top 20
        top20.forEach(function(c,i){{
            var ch = getItemChange(c);
            var cls = ccls(ch), clr = cclr(ch);
            var bw = maxAbs > 0 ? Math.min(Math.abs(ch) / maxAbs * 100, 100) : 0;
            h += '<div class="c-item" data-name="' + c.name.replace(/"/g, '&quot;') + '">';
            h += '<div class="c-rank' + (i<3?' hot':'') + '">' + (i+1) + '</div>';
            h += '<div class="c-info">';
            h += '<div class="c-name">' + c.name.replace('概念','<span class="rm-concept">概念</span>') + '</div>';
            h += '<div class="c-meta">' + (c.up_count||0) + '涨' + (c.down_count||0) + '跌 · ¥' + ((c.amount_yi||0).toFixed(0)) + '亿</div>';
            h += '</div>';
            h += '<div class="c-change ' + cls + '">' + sign(ch) + ch.toFixed(2) + '%</div>';
            h += '<div class="c-bar"><div class="c-bar-fill" style="width:' + bw + '%;background:' + clr + '"></div></div>';
            h += '</div>';
        }});

        // Divider
        h += '<div class="divider">── 跌幅榜 ──</div>';

        // Bottom 10
        bot10.forEach(function(c,i){{
            var ch = getItemChange(c);
            var cls = ccls(ch), clr = cclr(ch);
            var bw = maxAbs > 0 ? Math.min(Math.abs(ch) / maxAbs * 100, 100) : 0;
            h += '<div class="c-item" data-name="' + c.name.replace(/"/g, '&quot;') + '">';
            h += '<div class="c-rank">' + (data.length - i) + '</div>';
            h += '<div class="c-info">';
            h += '<div class="c-name">' + c.name.replace('概念','<span class="rm-concept">概念</span>') + '</div>';
            h += '<div class="c-meta">' + (c.up_count||0) + '涨' + (c.down_count||0) + '跌 · ¥' + ((c.amount_yi||0).toFixed(0)) + '亿</div>';
            h += '</div>';
            h += '<div class="c-change ' + cls + '">' + sign(ch) + ch.toFixed(2) + '%</div>';
            h += '<div class="c-bar"><div class="c-bar-fill" style="width:' + bw + '%;background:' + clr + '"></div></div>';
            h += '</div>';
        }});
        document.getElementById('conceptList').innerHTML = h;
    }} catch(e) {{
        document.getElementById('conceptList').innerHTML = '<div class="empty">渲染出错, 请刷新页面</div>';
    }} finally {{
        _rendering = false;
    }}
}}

// period label mapping
var PERIOD_LABELS = {{'day': '今日', '5d': '近5日', '20d': '近20日'}};

// tab handling - robust with render guard
document.getElementById('tabs').addEventListener('click',function(e){{
    var tab = e.target.closest('.tab');
    if (!tab || !tab.dataset.period) return;
    var period = tab.dataset.period;

    // Check period availability (prevent silent revert)
    if (period !== 'day' && !PERIODS[period]) {{
        showToast('⏳ ' + PERIOD_LABELS[period] + '数据不足, 需积累更多交易日历史');
        return;  // DON'T proceed with the change
    }}

    // Update active tab
    document.querySelectorAll('#tabs .tab').forEach(function(t){{ t.classList.remove('active'); }});
    tab.classList.add('active');
    currentPeriod = period;

    // Render with requestAnimationFrame for smooth UI
    requestAnimationFrame(function(){{ rList(); }});
}});

// concept list click delegation → inline detail
document.getElementById('conceptList').addEventListener('click',function(e){{
    var item = e.target.closest('.c-item');
    if (!item) return;
    // Close any existing inline detail first, then open new one
    openInlineDetail(item.dataset.name, item);
    e.stopPropagation();
}});

// close inline detail when clicking outside
document.addEventListener('click', function(e) {{
    if (_openDetailEl && !e.target.closest('.c-detail') && !e.target.closest('.c-item')) {{
        closeInlineDetail();
    }}
}});

// period availability styling
function updateTabAvailability() {{
    var tab5 = document.getElementById('tab5d');
    var tab20 = document.getElementById('tab20d');
    if (tab5) {{
        if (!PERIODS['5d']) {{
            tab5.style.opacity = '0.35';
            tab5.style.cursor = 'not-allowed';
            tab5.title = '数据不足 (需5个交易日历史)';
        }} else {{
            tab5.style.opacity = '1';
            tab5.style.cursor = 'pointer';
            tab5.title = '';
        }}
    }}
    if (tab20) {{
        if (!PERIODS['20d']) {{
            tab20.style.opacity = '0.35';
            tab20.style.cursor = 'not-allowed';
            tab20.title = '数据不足 (需20个交易日历史)';
        }} else {{
            tab20.style.opacity = '1';
            tab20.style.cursor = 'pointer';
            tab20.title = '';
        }}
    }}
}}

updateTabAvailability();

// inline detail - track currently open detail element
var _openDetailEl = null;
var _openDetailName = null;

// generate detail content HTML (cached by concept name)
var _detailCache = {{}};
function buildDetailHTML(name){{
    if (_detailCache[name]) return _detailCache[name];
    var c = DATA.find(function(x){{return x.name===name;}});
    if (!c) return '<div class="empty">数据加载失败</div>';
    var ch = c.change_pct, cls = ccls(ch);

    var h = '<div class="detail-header">';
    h += '<div><div class="detail-name ' + cls + '">' + c.name + '</div>';
    h += '<div class="detail-rank">涨幅排名: ' + (c.rank||'N/A') + '</div></div>';
    h += '<div class="c-detail-close" onclick="closeInlineDetail()" title="关闭">×</div>';
    h += '</div>';

    h += '<div class="detail-grid">';
    h += '<div class="detail-stat"><div class="ds-lbl">📊 板块涨幅</div><div class="ds-val ' + cls + '">' + sign(ch) + ch.toFixed(2) + '%</div></div>';
    h += '<div class="detail-stat"><div class="ds-lbl">🏠 涨跌家数</div><div class="ds-val">' + (c.up_count||0) + '<span class="up">涨</span> / ' + (c.down_count||0) + '<span class="down">跌</span></div></div>';
    h += '<div class="detail-stat"><div class="ds-lbl">💵 成交额</div><div class="ds-val">¥' + (c.amount_yi||0).toFixed(1) + '亿</div></div>';
    h += '<div class="detail-stat"><div class="ds-lbl">💸 资金流向</div><div class="ds-val ' + ccls(c.fund_flow||0) + '">' + sign(c.fund_flow||0) + (c.fund_flow||0).toFixed(1) + '亿</div></div>';
    if(c.prev_close) h += '<div class="detail-stat"><div class="ds-lbl">📅 昨收/今开</div><div class="ds-val">' + c.prev_close + ' / ' + (c.open||'--') + '</div></div>';
    if(c.high&&c.low) h += '<div class="detail-stat"><div class="ds-lbl">📏 最高/最低</div><div class="ds-val"><span class="up">' + c.high + '</span> / <span class="down">' + c.low + '</span></div></div>';
    h += '</div>';

    h += '<div class="detail-analysis">' + genAnalysis(c) + '</div>';

    // Stocks section (up to 15, multi-factor ranked)
    var stocks = CONCEPT_STOCKS[name];
    if (stocks && stocks.length > 0) {{
        h += '<div class="detail-stocks"><h4>📈 领涨个股 Top' + stocks.length + ' <span class="stk-hint">(多因子筛选: 涨幅×35%+成交额×25%+活跃度×15%+匹配度×15%+价格×10%)</span></h4>';
        stocks.forEach(function(s,i){{
            var cg = s.change_pct || 0;
            var amtStr = (s.amount_yi||0) >= 1 ? (s.amount_yi).toFixed(1) + '亿' : ((s.amount_yi||0)*10000).toFixed(0) + '万';
            h += '<div class="stock-row">';
            h += '<div class="sr">' + (i+1) + '</div>';
            h += '<div class="sn">' + s.name + '</div>';
            h += '<div style="font-size:10px;color:#888;flex-shrink:0">' + (s.code||'') + '</div>';
            h += '<div class="sc ' + ccls(cg) + '">' + sign(cg) + cg.toFixed(2) + '%</div>';
            h += '<div class="sa">' + amtStr + '</div>';
            h += '</div>';
        }});
        h += '</div>';
    }} else {{
        h += '<div class="detail-stocks"><h4>📈 领涨个股</h4>';
        h += '<div class="empty" style="padding:16px">板块成分股数据暂不可用<br><span style="font-size:11px;color:#555">关键词匹配未返回结果, 数据源可能受限</span></div>';
        h += '</div>';
    }}

    // ETF recommendations
    var etf = CONCEPT_ETFS[name];
    if (etf) {{
        h += '<div class="etf-rec">';
        h += '<div class="etf-title">💰 相关ETF推荐</div>';
        h += '<a class="etf-link" href="https://quote.eastmoney.com/etf/' + etf.code + '.html" target="_blank" rel="noopener">';
        h += '📊 ' + etf.name + ' (' + etf.code + ') → 查看详情</a>';
        h += '</div>';
    }}

    _detailCache[name] = h;
    return h;
}}

function closeInlineDetail(){{
    if (_openDetailEl) {{
        _openDetailEl.parentNode.removeChild(_openDetailEl);
        _openDetailEl = null;
        _openDetailName = null;
    }}
}}

function openInlineDetail(name, clickedItem) {{
    // Same concept clicked → close it
    if (_openDetailName === name) {{
        closeInlineDetail();
        return;
    }}

    // Close previous detail
    closeInlineDetail();

    // Build detail element
    var detail = document.createElement('div');
    detail.className = 'c-detail';
    detail.innerHTML = buildDetailHTML(name);

    // Insert after the clicked row
    clickedItem.parentNode.insertBefore(detail, clickedItem.nextSibling);

    // Track
    _openDetailEl = detail;
    _openDetailName = name;

    // Smooth scroll into view
    requestAnimationFrame(function() {{
        detail.scrollIntoView({{behavior: 'smooth', block: 'nearest'}});
    }});
}}

// init: clear inline detail on re-render
var _origRList = rList;
rList = function() {{
    closeInlineDetail();
    _origRList();
}};

// AI analysis (rules-based)
function genAnalysis(c){{
    var parts=[];
    var ch=c.change_pct||0;
    var rk=c.rank||'--';
    if(ch>3) parts.push('🔥 板块今日强势领涨('+sign(ch)+ch.toFixed(1)+'%),涨幅排名'+rk+',短线资金高度关注');
    else if(ch>0) parts.push('📈 板块今日温和上涨('+sign(ch)+ch.toFixed(1)+'%),涨幅排名'+rk);
    else if(ch>-2) parts.push('⚖️ 板块今日小幅调整('+sign(ch)+ch.toFixed(1)+'%),排名靠后('+rk+'),短期承压');
    else parts.push('⚠️ 板块今日大幅下跌('+sign(ch)+ch.toFixed(1)+'%),排名落后('+rk+'),避险情绪升温');
    if((c.up_count||0)>(c.down_count||0)*3) parts.push('涨跌家数比'+(c.up_count||0)+'/'+(c.down_count||0)+',多方占优,板块内普遍强势');
    else if((c.up_count||0)*3<(c.down_count||0)) parts.push('涨跌家数比'+(c.up_count||0)+'/'+(c.down_count||0)+',空方主导,板块内大面积调整');
    else parts.push('涨跌家数比'+(c.up_count||0)+'/'+(c.down_count||0)+',多空分歧明显');
    if((c.fund_flow||0)>50) parts.push('主力资金大幅净流入'+(c.fund_flow||0).toFixed(1)+'亿,资金面看多');
    else if((c.fund_flow||0)<-50) parts.push('主力资金大幅净流出'+Math.abs(c.fund_flow||0).toFixed(1)+'亿,需警惕出货风险');
    else if((c.fund_flow||0)<0) parts.push('主力资金小幅流出'+Math.abs(c.fund_flow||0).toFixed(1)+'亿');
    if((c.amount_yi||0)>500) parts.push('成交额'+(c.amount_yi||0).toFixed(0)+'亿,量能充沛,活跃度高');
    else if((c.amount_yi||0)<100) parts.push('成交额'+(c.amount_yi||0).toFixed(0)+'亿,量能偏弱,关注度低');
    return parts.join('。<br>')+'.';
}}

// init
rIdx();
rOv();
rList();
</script>
</body>
</html>'''
    return html


# ── 主流程 ────────────────────────────────────────────

def main():
    print("=" * 50)
    print("A股概念板块趋势仪表盘 v2.3")
    print("=" * 50)

    # 0. 预取全量A股数据(用于关键词匹配成分股)
    print("\n📊 获取全量A股行情(用于成分股匹配)...")
    import time
    t0 = time.time()
    try:
        import akshare as ak
        all_stocks = ak.stock_zh_a_spot()
        print(f"  → {len(all_stocks)} 只A股, 耗时{time.time()-t0:.1f}s")
    except Exception as e:
        print(f"  [WARN] 全量数据获取失败: {e}")
        all_stocks = None

    # 1. 市场概览 (复用全量数据)
    print("\n📊 获取市场概览...")
    market = fetch_market_overview(all_stocks)
    indices = get_index_data()
    print(f"  → {market['up']}涨 {market['down']}跌, 成交{market['amount_yi']}亿, {len(indices)}个指数")

    # 2. 概念板块 (THS)
    print("\n🔥 获取概念板块行情...")
    concepts = fetch_all_concepts()
    if not concepts:
        print("[ERROR] 概念数据获取失败", file=sys.stderr)
        return 1

    # 3. 历史数据 & 多周期
    print("\n📅 更新历史数据...")
    history = update_concept_history(concepts)
    periods = calc_period_changes(concepts, history)
    for k, v in periods.items():
        print(f"  → {k}: {len(v)}个概念有历史数据")

    # 4. 预取成分股 + ETF
    print("\n🔍 匹配概念成分股 + ETF...")
    stocks_map = {}
    etf_map = {}
    if all_stocks is not None:
        stocks_map, etf_map = prefetch_concept_stocks(concepts, all_stocks)

    # 5. 生成HTML
    print("\n🎨 生成仪表盘...")
    html = generate_html(market, indices, concepts, periods, stocks_map, etf_map)

    output_dir = PROJECT_ROOT / 'outputs'
    output_dir.mkdir(parents=True, exist_ok=True)

    html_path = output_dir / 'sector_dashboard.html'
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  → HTML: {html_path} ({len(html)} bytes)")

    # JSON 备份
    json_path = output_dir / 'sector_dashboard_data.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'market': market, 'indices': indices, 'concepts': concepts,
            'periods': {k: v for k, v in periods.items()},
            'generated_at': datetime.now().isoformat(),
        }, f, ensure_ascii=False, indent=2)
    print(f"  → JSON: {json_path}")

    print(f"\n✅ 完成! 共{len(concepts)}个概念板块,Top5:")
    for c in concepts[:5]:
        print(f"    {c['name']}: {c['change_pct']:+.2f}% (#{c['rank']})")

    return 0


if __name__ == '__main__':
    sys.exit(main())
