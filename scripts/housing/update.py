# 雙北（臺北市、新北市）實價登錄：下載 → 整併去重 → 扣除車位 → 彙總，輸出網站用的 JSON／CSV。
# 用法：python scripts/housing/update.py <快取資料夾> <輸出資料夾> [--force]
#   快取資料夾：存放已下載的季資料與各期資料（只保留臺北市 a、新北市 f 的買賣與預售屋檔），下次執行可重複使用。
#   輸出資料夾：meta.json、summary.json、trend.json、breakdown.json、tx_a.csv、tx_f.csv。
# 若內政部本期資料與上次輸出相同（比對 build_time.xml），且沒有加 --force，就不重算，結束碼為 0 並印出 UNCHANGED。
import datetime as dt, io, json, os, re, shutil, sys, time, urllib.request, warnings, zipfile
from zoneinfo import ZoneInfo
import numpy as np, pandas as pd

warnings.filterwarnings('ignore')
CACHE, OUT = sys.argv[1], sys.argv[2]
FORCE = '--force' in sys.argv
BASE = 'https://plvr.land.moi.gov.tw/'
CITY = {'a': '臺北市', 'f': '新北市'}
WANT = re.compile(r'^([af])_lvr_land_([ab])\.csv$')
P = 3.30579  # 1 坪 = 3.30579 平方公尺
SPECIAL = '親友|員工|特殊|關係人|瑕疵|凶宅|債權|拍賣|急買急賣|地上權|含增建|頂樓加蓋|未登記|共有人|政府機關'
num = lambda s: pd.to_numeric(s, errors='coerce')
log = lambda *a: print(*a, file=sys.stderr, flush=True)


# ---------- 下載 ----------
def get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (lvr-update)'})
            with urllib.request.urlopen(req, timeout=180) as r:
                return r.read()
        except Exception as e:  # 網路不穩時重試
            log('  下載失敗', i + 1, e)
            time.sleep(10 * (i + 1))
    raise RuntimeError('下載失敗：' + url)


def fetch(name, path, keep_cache=True):
    """下載一個 zip，只解出臺北市、新北市的買賣（a）與預售屋（b）CSV 及 build_time.xml。檔案不存在（伺服器回傳 HTML）時回傳 False。"""
    d = os.path.join(CACHE, name)
    if keep_cache and os.path.exists(os.path.join(d, 'ok')):
        return True
    data = get(BASE + path)
    if data[:2] != b'PK':
        log('  沒有這個檔案：', name)
        return False
    shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for n in z.namelist():
            b = os.path.basename(n)
            if WANT.match(b) or b == 'build_time.xml':
                with open(os.path.join(d, b), 'wb') as f: f.write(z.read(n))
    open(os.path.join(d, 'ok'), 'w').close()
    log('  已下載', name, len(data) // 1024, 'KB')
    return True


def roc(s):
    y, m, d = map(int, s)
    return dt.date(y + 1911, m, d)


os.makedirs(CACHE, exist_ok=True)
today = dt.datetime.now(ZoneInfo('Asia/Taipei')).date()
log('本期資料')
fetch('current', 'Download?type=zip&fileName=lvr_landcsv.zip', keep_cache=False)
release = open(os.path.join(CACHE, 'current', 'build_time.xml'), encoding='utf-8').read()
release = re.search(r'<lvr_time>(.*?)</lvr_time>', release, re.S).group(1).strip()
m_sale = re.search(r'登記日期\s*(\d+)年(\d+)月(\d+)日至\s*(\d+)年(\d+)月(\d+)日之買賣', release)
m_pre = re.search(r'交易日期\s*(\d+)年(\d+)月(\d+)日至\s*(\d+)年(\d+)月(\d+)日之預售屋', release)
sale_end, pre_end = roc(m_sale.groups()[3:]), roc(m_pre.groups()[3:])
log(release)

old = os.path.join(OUT, 'meta.json')
if not FORCE and os.path.exists(old) and json.load(open(old, encoding='utf-8')).get('release') == release:
    print('UNCHANGED'); sys.exit(0)

# 統計期間：買賣登記截止月份往回 12 個月（以交易／簽約月份計）
mon = lambda d: d.strftime('%Y-%m')
add_m = lambda d, k: dt.date(d.year + (d.month - 1 + k) // 12, (d.month - 1 + k) % 12 + 1, 1)
END = sale_end.replace(day=1); START = add_m(END, -11)
M0, M1 = mon(START), mon(END)
# 最近兩個月的中古屋還有案件沒登記（交易後 30 天內登記）；預售屋若最後一個月沒有涵蓋到月底也算未齊
incomplete = {'中古屋': [mon(add_m(END, -1)), M1], '預售屋': [] if (pre_end + dt.timedelta(days=1)).day == 1 else [mon(pre_end)]}
log('統計期間', M0, '～', M1, '未齊', incomplete)

# 季資料：從統計期間第一季到今天所在季；再用各期歷史資料補上最新一季之後的部分
need, sources = ['current'], []
q_end = None
y, q = START.year, (START.month - 1) // 3 + 1
while dt.date(y, 3 * q - 2, 1) <= today:
    name = f'{y - 1911}S{q}'
    log('季資料', name)
    if fetch(name, f'DownloadSeason?season={name}&type=zip&fileName=lvr_landcsv.zip'):
        need.append(name); sources.append(name); q_end = add_m(dt.date(y, 3 * q - 2, 1), 3) - dt.timedelta(days=1)
    y, q = (y + 1, 1) if q == 4 else (y, q + 1)
d = (q_end or START) + dt.timedelta(days=1)
while d <= today:
    for day in (1, 11, 21):
        x = d.replace(day=day)
        if x < (q_end or START) or x > today: continue
        name = 'p' + x.strftime('%Y%m%d')
        if name in need: continue
        log('各期資料', name)
        if fetch(name, f'DownloadHistory?type=history&fileName={x:%Y%m%d}'):
            need.append(name); sources.append(name)
    d = add_m(d.replace(day=1), 1)
sources.append('本期')
for n in os.listdir(CACHE):  # 刪掉用不到的舊快取
    if n not in need: shutil.rmtree(os.path.join(CACHE, n), ignore_errors=True)
order = sorted([n for n in need if n != 'current'], key=lambda n: (n[0] != 'p' and '0' or '1', n)) + ['current']  # 季 → 各期 → 本期，越後面越新


# ---------- 讀檔、去重 ----------
def read_all(kind):
    fr = []
    for rank, n in enumerate(order):
        for c in CITY:
            f = os.path.join(CACHE, n, f'{c}_lvr_land_{kind}.csv')
            if not os.path.exists(f): continue
            d = pd.read_csv(f, dtype=str, skiprows=[1], on_bad_lines='skip', encoding='utf-8-sig')
            d['縣市'] = CITY[c]; d['_rank'] = rank; fr.append(d)
    d = pd.concat(fr, ignore_index=True)
    n0 = len(d); d = d.sort_values('_rank', kind='stable').drop_duplicates('編號', keep='last')  # 同一編號保留最新一期
    log(kind, '讀入', n0, '去重後', len(d))
    return d


def ym(s):
    s = s.astype(str).str.strip(); y = num(s.str[:-4]) + 1911
    return y.astype('Int64').astype(str) + '-' + s.str[-4:-2]


AGE_REF = END.year - 1911
def age(s):
    s = s.fillna('').astype(str); return AGE_REF - num(s.str[:-4])


def clean(d, kind):
    for c in ['總價元', '車位總價元', '建物移轉總面積平方公尺', '車位移轉總面積平方公尺']: d[c] = num(d[c])
    d['含車位'] = d['交易標的'].fillna('').str.contains(r'\+車位')
    d['車位未拆價'] = d['含車位'] & (d['車位總價元'].fillna(0) == 0)
    d['特殊'] = d['備註'].fillna('').str.contains(SPECIAL)
    d['車位數'] = num(d['交易筆棟數'].fillna('').str.extract(r'車位(\d+)')[0]).fillna(0).clip(upper=10)
    d['鄉鎮市區'] = d['鄉鎮市區'].fillna('未知')
    # 車位價格未拆開者：以同行政區有拆價案件的「每個車位價格」中位數 × 車位數估算；該區不足 10 筆則用全縣市中位數
    sp = d[d['含車位'] & (d['車位總價元'] > 0) & (d['車位數'] > 0)]
    per = sp['車位總價元'] / sp['車位數']
    dist_med = per.groupby([sp['縣市'], sp['鄉鎮市區']]).agg(['median', 'size'])
    city_med = per.groupby(sp['縣市']).median()
    m = pd.Series([dist_med.loc[k, 'median'] if k in dist_med.index and dist_med.loc[k, 'size'] >= 10 else city_med.get(k[0], np.nan)
                   for k in zip(d['縣市'], d['鄉鎮市區'])], index=d.index)
    est = (m * d['車位數'].where(d['車位數'] > 0, 1)).where(d['車位未拆價'])
    d['車位價估算'] = d['車位未拆價'] & est.notna()
    d['車位總價元'] = d['車位總價元'].where(~d['車位價估算'], est)
    pk = d['車位總價元'].fillna(0); pka = d['車位移轉總面積平方公尺'].fillna(0)
    d['坪數'] = (d['建物移轉總面積平方公尺'] - pka) / P
    d['總價萬'] = (d['總價元'] - pk) / 1e4
    d['總價萬_含車位'] = d['總價元'] / 1e4
    d['車位價萬'] = pk / 1e4
    d['單價'] = d['總價萬'] / d['坪數']
    d['單價_含車位'] = d['總價萬_含車位'] / (d['建物移轉總面積平方公尺'] / P)
    d['月'] = ym(d['交易年月日'])
    d['屋齡'] = age(d['建築完成年月'])
    # 只取「房地(土地+建物)」與「房地(土地+建物)+車位」的住宅
    keep = d['交易標的'].isin(['房地(土地+建物)', '房地(土地+建物)+車位']) & d['主要用途'].fillna('').str.contains('住') \
        & d['建物型態'].fillna('').str.contains('大樓|華廈|公寓|透天') & (d['坪數'] > 3) & d['月'].between(M0, M1)
    if kind == 'b' and '解約情形' in d: keep &= d['解約情形'].isna()
    d = d[keep].copy()
    d['型態'] = d['建物型態'].str.replace(r'\(.*\)', '', regex=True)
    # 排除特殊交易、無法估算車位價者、估算車位價超過總價一半者，以及單價異常者
    d['納入'] = ~d['特殊'] & ~(d['車位未拆價'] & ~d['車位價估算']) & (d['車位價萬'] <= d['總價萬_含車位'] / 2) & d['單價'].between(3, 400)
    return d


a = clean(read_all('a'), 'a'); b = clean(read_all('b'), 'b')
if len(a) < 1000: raise SystemExit('中古屋筆數異常偏少（%d），可能是欄位或資料格式改變，停止更新' % len(a))
log('中古', len(a), '預售', len(b))

AGES = [(0, 5, '0–5 年'), (6, 10, '6–10 年'), (11, 20, '11–20 年'), (21, 30, '21–30 年'), (31, 40, '31–40 年'), (41, 999, '40 年以上')]
agecut = lambda v: pd.cut(v, [-99] + [h for _, h, _ in AGES], labels=[l for *_, l in AGES])
a['屋齡段'] = agecut(a['屋齡'])


def scopes(d):  # 縣市／行政區兩個層級
    return pd.concat([d.assign(S縣市=d['縣市'], S區='全部'), d.assign(S縣市=d['縣市'], S區=d['鄉鎮市區'])])


def by_age(X, bands=True):  # 中古屋另依屋齡分段；預售屋只有「全部」
    allx = X.assign(S齡='全部')
    if not bands: return allx
    y = X[X['屋齡段'].notna()]
    return pd.concat([allx, y.assign(S齡=y['屋齡段'].astype(str))])


r1 = lambda v: None if pd.isna(v) else round(float(v), 1)
r0 = lambda v: None if pd.isna(v) else int(round(float(v)))
A, B = by_age(scopes(a[a['納入']])), by_age(scopes(b[b['納入']]), False)
AP, BP = by_age(scopes(a)), by_age(scopes(b), False)
K = ['S縣市', 'S區', 'S齡']
REN = {'S縣市': '縣市', 'S區': '區', 'S齡': '屋齡篩選'}

# 1) 摘要
sa = A.groupby(K).agg(中古筆數=('單價', 'size'), 中古單價=('單價', 'median'), 中古總價=('總價萬', 'median'), 中古總價含車位=('總價萬_含車位', 'median'))
sb = B.groupby(K).agg(預售筆數=('單價', 'size'), 預售單價=('單價', 'median'), 預售總價=('總價萬', 'median'))
def park(X, p):
    g = X[X['含車位']].groupby(K)
    o = pd.DataFrame({p + '含車位筆數': g.size(), p + '車位未拆價筆數': g['車位未拆價'].sum(), p + '車位估算筆數': g['車位價估算'].sum()})
    sp = X[X['含車位'] & ~X['車位未拆價']]; g2 = sp.groupby(K)
    o[p + '車位價中位'] = g2['車位價萬'].median(); o[p + '車位佔比'] = (sp['車位價萬'] / sp['總價萬_含車位']).groupby([sp[k] for k in K]).median()
    o[p + '住宅筆數'] = X.groupby(K).size()
    return o
cp = A[A['含車位'] & ~A['車位未拆價']].groupby(K).agg(有車位筆數=('單價', 'size'), 有車位單價含車位=('單價_含車位', 'median'), 有車位單價扣車位=('單價', 'median'))
summ = pd.concat([sa, sb, park(AP, '中古'), park(BP, '預售'), cp], axis=1).reset_index().rename(columns=REN)
for col in summ.columns[3:]:
    summ[col] = summ[col].map(r0 if ('筆數' in col or col in ('中古總價', '中古總價含車位', '預售總價')) else (lambda v: None if pd.isna(v) else round(float(v), 3 if '佔比' in col else 1)))
summ = summ[summ[['中古筆數', '預售筆數']].fillna(0).sum(axis=1) > 0]

# 2) 每月趨勢
t = []
for name, X in [('中古屋', A), ('預售屋', B)]:
    q = lambda p: (lambda v: v.quantile(p))
    g = X.groupby(K + ['月']).agg(筆數=('單價', 'size'), 中位數=('單價', 'median'), 平均=('單價', 'mean'), P25=('單價', q(.25)), P75=('單價', q(.75)),
        最低=('單價', 'min'), 最高=('單價', 'max'), 總價中位=('總價萬', 'median'), 坪數中位=('坪數', 'median'),
        含車位筆數=('含車位', 'sum'), 車位估算筆數=('車位價估算', 'sum')).reset_index()
    g['類別'] = name; t.append(g)
trend = pd.concat(t).rename(columns=REN | {'月': '月份'})
for col in ['中位數', '平均', 'P25', 'P75', '最低', '最高', '坪數中位']: trend[col] = trend[col].map(r1)
for col in ['總價中位', '含車位筆數', '車位估算筆數']: trend[col] = trend[col].map(r0)

# 3) 分項（型態、屋齡、總價帶）
BANDS = [(0, 500, '500 以下'), (500, 1000, '500–1000'), (1000, 1500, '1000–1500'), (1500, 2000, '1500–2000'), (2000, 3000, '2000–3000'), (3000, 5000, '3000–5000'), (5000, 1e9, '5000 以上')]
A['總價帶'] = pd.cut(A['總價萬'], [0] + [h for _, h, _ in BANDS], labels=[l for *_, l in BANDS], right=False)
br = []
for dim, col in [('型態', '型態'), ('屋齡', '屋齡段'), ('總價帶', '總價帶')]:
    g = A.groupby(K + [col], observed=True).agg(筆數=('單價', 'size'), 單價中位=('單價', 'median')).reset_index().rename(columns={col: '項目'})
    g['維度'] = dim; g['項目'] = g['項目'].astype(str); br.append(g)
brk = pd.concat(br).rename(columns=REN); brk['單價中位'] = brk['單價中位'].map(r1)
rank = {l: i for i, (*_, l) in enumerate(AGES)} | {l: i for i, (*_, l) in enumerate(BANDS)}
brk['順序'] = brk['項目'].map(rank).fillna(0).astype(int)

# 4) 逐筆交易明細（只含納入統計的案件），每個縣市一個 CSV
def tx(d, kind):
    return pd.DataFrame({'編號': d['編號'], '區': d['鄉鎮市區'], '類別': kind, '月份': d['月'],
        '交易日': num(d['交易年月日'].str[:-4]).astype('Int64').astype(str) + '/' + d['交易年月日'].str[-4:-2] + '/' + d['交易年月日'].str[-2:],
        '地址': d['土地位置建物門牌'], '建案': d['建案名稱'] if '建案名稱' in d else '', '型態': d['型態'],
        '樓層': d['移轉層次'].fillna('') + '/' + d['總樓層數'].fillna('').astype(str),
        '格局': d['建物現況格局-房'].fillna('') + '房' + d['建物現況格局-廳'].fillna('') + '廳' + d['建物現況格局-衛'].fillna('') + '衛',
        '坪數': d['坪數'].round(2), '總價萬': d['總價萬'].round(1), '單價': d['單價'].round(2),
        '屋齡': d['屋齡'] if kind == '中古屋' else None, '屋齡段': d['屋齡段'].astype(str).replace('nan', '') if kind == '中古屋' else '',
        '車位價萬': d['車位價萬'].round(1), '車位價估算': d['車位價估算'].map({True: '是', False: ''}), '縣市': d['縣市']})
T = pd.concat([tx(a[a['納入']], '中古屋'), tx(b[b['納入']], '預售屋')]).sort_values(['月份', '交易日'])

# ---------- 輸出 ----------
tmp = OUT + '.tmp'
shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
def dump(name, df):
    with open(os.path.join(tmp, name + '.json'), 'w', encoding='utf-8') as f:
        f.write(df.to_json(orient='records', force_ascii=False))
dump('summary', summ)
dump('trend', trend[['縣市', '區', '屋齡篩選', '類別', '月份', '筆數', '中位數', '平均', 'P25', 'P75', '最低', '最高', '總價中位', '坪數中位', '含車位筆數', '車位估算筆數']])
dump('breakdown', brk[['縣市', '區', '屋齡篩選', '維度', '項目', '順序', '筆數', '單價中位']])
inv = {v: k for k, v in CITY.items()}
for city, g in T.groupby('縣市'):
    g.drop(columns='縣市').to_csv(os.path.join(tmp, f'tx_{inv[city]}.csv'), index=False)
meta = {'release': release, 'updated': dt.datetime.now(ZoneInfo('Asia/Taipei')).isoformat(timespec='minutes'),
        'start': M0, 'end': M1, 'saleEnd': sale_end.isoformat(), 'presaleEnd': pre_end.isoformat(), 'ageRef': AGE_REF,
        'incomplete': incomplete, 'sources': sources, 'counts': {'中古屋': int(a['納入'].sum()), '預售屋': int(b['納入'].sum())}}
json.dump(meta, open(os.path.join(tmp, 'meta.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
shutil.rmtree(OUT, ignore_errors=True); os.replace(tmp, OUT)
log('完成', meta['counts'], {f: os.path.getsize(os.path.join(OUT, f)) // 1024 for f in os.listdir(OUT)})
print('UPDATED')
