import scipy.optimize as so
import numpy as np


# 计算债券的到期收益率YTM
# 对于处于最后付息周期的固定利率债券和浮动利率债券、待偿还期在1年以内的到期一次还本附息债券和零息债券
def YTM4(bondtype, PV, M, C, k, N, D, TY, P):
    '''
        bondtype
        PV:表示债券全价；
        M:债券面值;
        C:票面年利息；
        k:年付息频率；
        N:债券期限(年)，即从起息日至到期兑付日的整年数;
        y:到期收益率；
        D:债券结算日至到期兑付日的实际天数；
        TY：当前计息年度的实际天数，算头不算尾
    '''
    if bondtype == 1:
        # 固定利率债券
        FV = M + C / k
    elif bondtype == 2:
        # 到期一次还本付息债券
        FV = M + N * C
    elif bondtype == 3:
        # 300，零息，一年期及以上
        FV = M
    else:
        # 200，贴现，一年期以内
        FV = M + P

    Y = (abs(FV - PV)) * TY / (PV * D)
    return Y


# 公式5
# 对待偿还期在1年以上的到期一次还本附息债券和零息债券
def YTM5(bondtype, PV, M, C, N, d, m, TY):
    '''计算债券到期收益率的函数
        bondtype:表示债券类型,1为到期一次还本付息债券,2为零息债券；
        PV:表示债券全价；
        M:债券面值;
        C:票面年利息；
        N:债券期限(年)，即从起息日至到期兑付日的整年数;
        y:到期收益率；
        d:结算日至下一最近理论付息日的实际天数；
        m:结算日至到期兑付日的整年数;
        TY：当前计息年度的实际天数，算头不算尾
    '''
    if bondtype == 1:
        FV = M + N * C
    else:
        FV = M
    Y = (FV / PV) ** (1 / (d / TY + m)) - 1
    return Y


# 公式6
# 对待偿还期在1年以上的付息债券
def YTM6(PV, C, k, d, n, M, TS):
    '''计算债券到期收益率的函数
        PV:表示债券全价；
        C:票面年利息；
        k:年付息频率；
        y:到期收益率；
        d:债券结算日至下一最近付息日之间的实际天数；
        n:结算日至到期兑付日的债券付息次数；'
        M:债券面值;
        TS:当前付息周期的实际天数。'''

    def f(y):
        coupon = []
        for i in np.arange(0, n):
            coupon.append((C / k) / pow(1 + y / k, d / TS + i))
        return np.sum(coupon) + (M / pow(1 + y / k, d / TS + n - 1)) - PV

    Y = so.fsolve(f, 0.01)
    return Y


# 公式7
# 对待偿还期在1年以上的变化利率附息债券
def YTM7(PV, C, k, d, n, M, TS):
    '''计算债券到期收益率的函数
        PV:表示债券全价；
        C:票面年利息(list)
        k:年付息频率；
        y:到期收益率；
        d:债券结算日至下一最近付息日之间的实际天数；
        n:结算日至到期兑付日的债券付息次数；'
        M:债券面值;
        TS:当前付息周期的实际天数。'''

    def f(y):
        coupon = []
        for i in range(0, n):
            coupon.append((C[i] / k) / pow(1 + y / k, d / TS + i))
        return np.sum(coupon) + (M / pow(1 + y / k, d / TS + n - 1)) - PV

    Y = so.fsolve(f, 0.01)
    return Y
