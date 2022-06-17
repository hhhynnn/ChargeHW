DB_PATH = './res.db'
"""数据库路径"""

QUEUE_LEN = 2
"""充电区长度"""
WAIT_QUEUE_LEN = 5
"""等候区长度"""

PILEID = {'F': ['F#1', 'F#2'], 'T': ['T#1', 'T#2', 'T#3']}
"""充电桩ID"""

CHG_SPEED = {'F': 30, 'T': 10}
"""充电速度"""

CHG_RATE = {'H': 1, 'N': 0.7, 'L': 0.4}
"""充电费阶梯电价（°）"""
CHG_ZONE = [([0, 7], 'L'), ([7, 10], 'N'), ([10, 15], 'H'), ([15, 18], 'N'),
            ([18, 21], 'H'), ([21, 23], 'N'), ([23, 24], 'L')]
"""充电时间段"""
SERVE_RATE = 0.8
"""服务费率（°）"""

SCHEDULE_MODE = 'flood'
"""
调度策略, 可选 default/flood/

default: 每次调度一辆车
flood: 一次性调度多辆车, 整体时间最短
"""

FAILOVER_MODE = 'priority'
"""
故障恢复策略

priority: 优先级调度
shuffle: 
"""
