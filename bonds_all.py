import pandas as pd
import numpy as np
import pymysql
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from bonds_yield_fun import *
import warnings

# 字符集参数防止乱码
dbconn = pymysql.connect(
    host="localhost",
    database="bonds_group",
    user="root",
    password="hyw980722",
    port=3306,
    charset='utf8'
)

# sql语句
get_bonds_basic = "select * from bonds_basic"
get_bonds_cashflow = "select * from bonds_cashflow"
get_bonds_market = "select * from bonds_market"

# 利用pandas模块导入mysql数据
bonds_basic = pd.read_sql(get_bonds_basic, dbconn)
bonds_cashflow = pd.read_sql(get_bonds_cashflow, dbconn)
bonds_market = pd.read_sql(get_bonds_market, dbconn)
M1_table = pd.merge(bonds_basic, bonds_market, how='left', on=['SEC_CODE', 'SEC_CODE'])
M2_table = pd.merge(M1_table, bonds_cashflow, how='outer', on=['SEC_CODE', 'SEC_CODE'])
M2_table.dropna(axis=0, thresh=5, inplace=True)

# 将数据类型转换为date
M2_table['CARRYDATE'] = M2_table['CARRYDATE'].astype('datetime64[ns]')
M2_table['MATURITYDATE'] = M2_table['MATURITYDATE'].astype('datetime64[ns]')
M2_table['TRADE_DATE'] = M2_table['TRADE_DATE'].astype('datetime64[ns]')
M2_table['ENDDATE'] = M2_table['ENDDATE'].astype('datetime64[ns]')

# 筛选有效行
M2_table["GAPDAYS"] = np.where(M2_table.COUPON_TYPE == 505001000,
                               (M2_table['ENDDATE'] - M2_table['TRADE_DATE']).dt.days, 0)
M2_table = M2_table[M2_table['GAPDAYS'] >= 0]
bonds_all = M2_table.loc[M2_table.groupby("SEC_CODE")["GAPDAYS"].idxmin()]
bonds_all.reset_index(drop=True, inplace=True)
warnings.filterwarnings(action='ignore')

# 标记变化利率
bonds_all['RATE_TYPE'] = 0
for index, row in bonds_all.iterrows():
    if row.COUPON_TYPE == 505001000:
        get_bonds_cashflow = "select * from bonds_cashflow where SEC_CODE ='" + row.SEC_CODE + "'"
        bonds_cashflow_i = pd.read_sql(get_bonds_cashflow, dbconn)
        bonds_cashflow_i.loc["Average"] = round(bonds_cashflow_i.mean(), 2)
        if bonds_cashflow_i['PAYMENTINTEREST']['Average'] != row.COUPONRATE_x:
            bonds_all.RATE_TYPE[index] = 1

# 贴现债券补充利率
bonds_all["COUPONRATE_x"] = np.where(bonds_all.COUPON_TYPE == 505003000, 100 - bonds_all.ISSUEPRICE,
                                     bonds_all.COUPONRATE_x)
bonds_all["COUPONRATE_y"] = np.where(bonds_all.COUPON_TYPE == 505003000, 100 - bonds_all.ISSUEPRICE,
                                     bonds_all.COUPONRATE_y)

# 换算支付频率
bonds_all['FREQUENCY'] = 1
for index, row in bonds_all.iterrows():
    if row.INTERESTFREQUENCY[0:1] == 'Y':
        bonds_all.FREQUENCY[index] = 1.0 / int(row.INTERESTFREQUENCY[1:2])
    elif row.INTERESTFREQUENCY[0:1] == 'M':
        bonds_all.FREQUENCY[index] = 12 / int(row.INTERESTFREQUENCY[1:])

# 计算利息的日期天数
bonds_all["LAST_ENDDATE"] = np.where(bonds_all.COUPON_TYPE == 505001000, bonds_all.ENDDATE - pd.DateOffset(years=1),
                                     bonds_all.CARRYDATE)
bonds_all["DAYS_AI"] = np.where(bonds_all.COUPON_TYPE == 505001000, bonds_all.TRADE_DATE - bonds_all.LAST_ENDDATE,
                                bonds_all.TRADE_DATE - bonds_all.CARRYDATE)

# 特殊年换算
bonds_all['SPECIAL'] = 366
for index, row in bonds_all.iterrows():
    if row.ACTUALBENCHMARK[2:] == '360' or row.ACTUALBENCHMARK[2:] == '3600':
        bonds_all.SPECIAL[index] = 360
    elif row.ACTUALBENCHMARK[2:] == '365' or row.ACTUALBENCHMARK[2:] == '3650':
        bonds_all.SPECIAL[index] = 365

# 交易所计时调整+特殊年调整
bonds_all["INTEREST"] = 0.000000
for index, row in bonds_all.iterrows():
    if (row.COUPON_TYPE == 505001000) & (row.SEC_CODE[-1] == 'B'):
        bonds_all.DAYS_AI[index] = row.DAYS_AI - pd.Timedelta(days=1)
    if row.TRADE_DATE.year % 4 == 0 or row.TRADE_DATE.year % 100 == 0:
        bonds_all.INTEREST[index] = row.DAYS_AI.days / row.SPECIAL * row.COUPONRATE_x
    else:
        bonds_all.INTEREST[index] = row.DAYS_AI.days / 365 * row.COUPONRATE_x

print("输出债券应计利息")
print(bonds_all[['SEC_CODE', 'INTEREST']])

# 开始计算
# 只有零息债券、附息债券两种FV。
bonds_all['FV'] = np.where(bonds_all.COUPON_TYPE == 505001000,
                           bonds_all.CURPAR + bonds_all.COUPONRATE_y / bonds_all.FREQUENCY, bonds_all.CURPAR)
bonds_all['D'] = (bonds_all['MATURITYDATE'] - bonds_all['TRADE_DATE']).dt.days
bonds_all['d'] = (bonds_all['LAST_ENDDATE'] + relativedelta(years=+1) / bonds_all['FREQUENCY'] - bonds_all[
    'TRADE_DATE']).dt.days + 1
# bonds_all['Days'] = bonds_all['DAYS_AI'].dt.days

bonds_all['m'] = bonds_all['D'] / 365
bonds_all['m'] = bonds_all['m'].astype('int')
bonds_all['n'] = bonds_all['D'] / 365 / bonds_all['FREQUENCY']
bonds_all['n'] = bonds_all['n'].astype('int')
bonds_all['N'] = (bonds_all['MATURITYDATE'] - bonds_all['CARRYDATE']) / pd.Timedelta(days=365)
bonds_all['N'] = bonds_all['N'].astype('int')

bonds_all['TY'] = 0
for index, row in bonds_all.iterrows():
    bonds_all.TY[index] = row.TRADE_DATE + relativedelta(years=+1) - row.TRADE_DATE
    bonds_all.TY[index] = bonds_all.TY[index].days
bonds_all['TS'] = bonds_all['TY'] / bonds_all['FREQUENCY']

bonds_all['YIELD'] = 0
bonds_all['YIELD'] = bonds_all['YIELD'].astype(float).round(6)
for index, row in bonds_all.iterrows():
    if row.COUPON_TYPE == 505001000 and row.D <= 365 * row.FREQUENCY:
        # 最后一个周期+固定利率 公式4
        bonds_all.YIELD[index] = YTM4(bondtype=1, PV=row.OPEN_PRICE, M=row.CURPAR, C=row.COUPONRATE_y, k=row.FREQUENCY,
                                      N=row.N, D=row.D, TY=row.TY, P=row.PAYMENTINTEREST)
    elif row.COUPON_TYPE == 505002000 and row.D <= 365:
        # 最后一年+贴现债券 公式4
        bonds_all.YIELD[index] = YTM4(bondtype=4, PV=row.OPEN_PRICE, M=row.CURPAR, C=row.COUPONRATE_y, k=row.FREQUENCY,
                                      N=row.N, D=row.D, TY=row.TY, P=row.PAYMENTINTEREST)
    elif row.COUPON_TYPE == 505003000 and row.D <= 365:
        # 最后一年+零息债券 公式4
        bonds_all.YIELD[index] = YTM4(bondtype=3, PV=row.OPEN_PRICE, M=row.CURPAR, C=row.COUPONRATE_y, k=row.FREQUENCY,
                                      N=row.N, D=row.D, TY=row.TY, P=row.PAYMENTINTEREST)
    elif row.COUPON_TYPE != 505001000:
        # 还有数年+一次还本付息 公式5
        bonds_all.YIELD[index] = YTM5(bondtype=3, PV=row.OPEN_PRICE, M=row.CURPAR, C=row.COUPONRATE_y, N=row.N, d=row.d,
                                      m=row.m, TY=row.TY)
    elif row.COUPON_TYPE == 505001000 and row.RATE_TYPE == 0:
        # 还有数年+需要多次付息 公式
        bonds_all.YIELD[index] = YTM6(PV=row.OPEN_PRICE, C=row.COUPONRATE_y, k=row.FREQUENCY, d=row.d, n=row.n,
                                      M=row.CURPAR, TS=row.TS)
    elif row.COUPON_TYPE == 505001000 and row.RATE_TYPE == 1:
        # 非固定利率 公式7
        get_bonds_cashflow = "select * from bonds_cashflow where SEC_CODE ='" + row.SEC_CODE + "'"
        bonds_cashflow_i = pd.read_sql(get_bonds_cashflow, dbconn)
        bonds_cashflow_i['ENDDATE'] = bonds_cashflow_i['ENDDATE'].astype('datetime64[ns]')
        bonds_cashflow_i["GAPDAYS"] = (bonds_cashflow_i['ENDDATE'] - row.TRADE_DATE).dt.days
        bonds_cashflow_i = bonds_cashflow_i[bonds_cashflow_i['GAPDAYS'] >= 0]
        bonds_cashflow_i.reset_index(drop=True, inplace=True)
        n_i = len(bonds_cashflow_i)
        bonds_all.YIELD[index] = YTM7(PV=row.OPEN_PRICE, C=bonds_cashflow_i["COUPONRATE"], k=row.FREQUENCY, d=row.d,
                                      n=n_i, M=row.CURPAR, TS=row.TS)
    else:
        print("ERROR:" + row.SEC_CODE)
print("输出债券到期收益率")
print(bonds_all[['SEC_CODE', 'YIELD']])

# 计算风险相关值
# 只考虑定期支付利息的债券，零息债券的Mac.D为到期时间T
bonds_code = '132100105.IB'
info = bonds_all[bonds_all['SEC_CODE'].isin([bonds_code])]
info.reset_index(drop=True, inplace=True)

get_bonds_cashflow = "select * from bonds_cashflow where SEC_CODE ='" + bonds_code + "'"
bonds_cashflow = pd.read_sql(get_bonds_cashflow, dbconn)
bonds_cashflow['ENDDATE'] = bonds_cashflow['ENDDATE'].astype('datetime64[ns]')

y = info["YIELD"][0]  # 到期收益率/估值收益率
C = info["COUPONRATE_x"][0]  # 票面年利息
f = info["FREQUENCY"][0]  # 年付息频率
d = info["d"][0]  # 债券结算日至下一最近付息日之间的实际天数
n = info["n"][0]  # 结算日至到期兑付日的债券付息次数；
M = info["CURPAR"][0]  # 债券面值
TS = info["TS"][0]  # 当前付息周期的实际天数
d0 = info["LAST_ENDDATE"][0]  # 上次付息日
d1 = info["TRADE_DATE"][0]  # 定义估值日
bondprice = info["OPEN_PRICE"][0]

bonds_cashflow["GAPDAYS"] = (bonds_cashflow['ENDDATE'] - d1).dt.days
bonds_cashflow = bonds_cashflow[bonds_cashflow['GAPDAYS'] >= 0]
bonds_cashflow.reset_index(drop=True, inplace=True)

# 贴现现金流
bonds_cashflow['discountcashflow'] = 0
bonds_cashflow['discountcashflow'] = bonds_cashflow['discountcashflow'].astype('float64')
for index, row in bonds_all.iterrows():
    bonds_cashflow.discountcashflow[index] = (C / f) / pow(1 + y / f, d / TS + index)

bonds_cashflow.discountcashflow[n] = bonds_cashflow.discountcashflow[n - 1] + M / pow(1 + y / f, d / TS + n)
bonds_cashflow['weight'] = bonds_cashflow['discountcashflow'] / bondprice
bonds_cashflow['year'] = bonds_cashflow['GAPDAYS'] / 365

# 输出指定债券的风险指标
Mac = sum(bonds_cashflow.year * bonds_cashflow.weight)  # 麦考利久期
MD = Mac / (1 + y / f)  # 修正久期
DV01 = MD * bondprice / 10000  # DV01
Con = sum(bonds_cashflow.year * (bonds_cashflow.year + 1) * bonds_cashflow.weight)  # 凸性
MC = Con / (1 + y / 2) ** 2  # 修正凸性

print("输出编号为" + bonds_code + '的债券风险指标：')
print('麦考利久期', round(Mac, 2))
print('修正久期', round(MD, 2))
print('DV01', round(DV01, 4))
print('凸性', round(Con, 2))
print('修正凸性', round(MC, 2))
