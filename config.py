DB_PATH = './res.db'
"""数据库路径"""

QUEUE_LEN = 5
"""充电区长度"""
WAIT_QUEUE_LEN = 20
"""等候区长度"""

PILEID = {'F': ['F#1', 'F#2'], 'T': ['T#1', 'T#2', 'T#3']}
"""充电桩ID"""

CHG_SPEED = {'F': 30, 'T': 10}
"""充电速度"""

CHG_RATE = {'H': 1, 'N': 0.7, 'L': 0.4}
"""充电费阶梯电价（°）"""
CHG_ZONE = [([0, 7], 'L'), ([7, 10], 'N'), ([10, 15], 'H'), ([15, 18], 'N'), ([18, 21], 'H'), ([21, 23], 'N'),
            ([23, 24], 'L')]
"""充电时间段"""
SERVE_RATE = 0.8
"""服务费率（°）"""


def get_cost(start: str, end: str, mode: str) -> [float, float]:
    '''
    计算收费结果
    :param start:开始时间，e.g:'2022-6-14 19:00:00'
    :param end: 结束时间,e.g:'2022-6-15 03:00:00'
    :param mode: 充电模式，{'T','F'}
    :return:服务费cost_serve，电费cost_charge
    '''
    from datetime import datetime, timedelta
    start = datetime.strptime(start, '%Y-%m-%d %H:%M:%S')
    end = datetime.strptime(end, '%Y-%m-%d %H:%M:%S')
    delta = end - start

    charge = CHG_SPEED[mode] * delta.total_seconds() / 3600
    cost_serve = 0.8 * charge

    cost_charge_extract_mode = 0
    while delta.total_seconds() > 0:
        hour = start.hour + start.minute / 60 + start.second / 3600
        for (op, ed), status in CHG_ZONE:
            if op - 1e-10 < hour < ed:
                if (ed - hour) * 3600 <= delta.total_seconds():
                    cost_charge_extract_mode += (ed - hour) * CHG_RATE[status]
                    start += timedelta(hours=ed - hour)
                    delta -= timedelta(hours=ed - hour)
                    hour = ed
                else:
                    cost_charge_extract_mode += delta.total_seconds() / 3600 * CHG_RATE[status]
                    delta -= delta
                    break
    cost_charge = cost_charge_extract_mode * CHG_SPEED[mode]
    return cost_serve, cost_charge
