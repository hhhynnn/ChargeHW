import json
import sqlite3
from config import *
from collections import defaultdict
import time
import datetime


def timestamp(now=time.time()):
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now))


def timestamp_add(time_str, seconds):
    return timestamp(timestamp_to_seconds(time_str) + seconds)


def timestamp_to_seconds(time_str):
    """只支持一种格式: '%Y-%m-%d %H:%M:%S'"""
    pattern = '%Y-%m-%d %H:%M:%S'
    return time.mktime(datetime.datetime.strptime(time_str, pattern).timetuple())


def HMS_to_seconds(time_str):
    """只支持一种格式: '%H:%M:%S'"""
    h, m, s = time_str.split(':')
    return int(h) * 3600 + int(m) * 60 + int(s)


def seconds_to_HMS(seconds):
    return time.strftime("%H:%M:%S", time.gmtime(seconds))


############################################################
# 详单类
############################################################
class charge_statement:

    def __init__(self):
        self.csid = 0  # 详单编号
        self.uid = 0  # 用户id
        self.mode = ''  # 充电类型
        """可选F/T"""
        self.reserve = 0  # 预计充电电量

        self.pileid = 0  # 提供充电的充电桩编号
        self.time_start = 0  # 启动时间

        self.time_end = 0  # 结束时间
        self.time_total = '00:00:00'  # 总时间
        self.consume = 0  # 充电电量
        self.cost_charge = 0  # 充电费用
        self.cost_serve = 0  # 服务费用
        self.cost_total = 0  # 总费用

        self.generate_time = 0  # 详单生成时间

    @staticmethod
    def new_charge_statement(wait):
        new_csid = charge_statement.get_new_csid()
        charge_stmt = charge_statement()

        charge_stmt.csid = new_csid  # 详单编号
        charge_stmt.uid = wait.uid  # 用户id
        charge_stmt.mode = wait.mode  # 充电类型
        charge_stmt.reserve = wait.reserve  # 预计充电电量

        charge_stmt.pileid = None  # 提供充电的充电桩编号
        charge_stmt.time_start = None  # 启动时间

        charge_stmt.time_end = None  # 结束时间
        charge_stmt.time_total = seconds_to_HMS(0)  # 总时间
        charge_stmt.consume = 0.0  # 充电电量
        charge_stmt.cost_charge = 0.0  # 充电费用
        charge_stmt.cost_serve = 0.0  # 服务费用
        charge_stmt.cost_total = 0.0  # 总费用
        charge_stmt.generate_time = timestamp()  # 详单生成时间
        return charge_stmt

    def __str__(self):
        dd = {"csid": self.csid,
              "uid": self.uid,
              "mode": self.mode,
              "reserve": self.reserve,
              "pileid": self.pileid,
              "time_start": self.time_start,
              "time_end": self.time_end,
              "time_total": self.time_total,
              "consume": self.consume,
              "const_charge": self.cost_charge,
              "cost_serve": self.cost_charge,
              "cost_total": self.cost_total,
              "generate_time": self.generate_time}
        return json.dumps(dd, ensure_ascii=False)

    def __repr__(self):
        return self.__str__()

    @staticmethod
    def get_new_csid():
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            select max(csid) from charge_stmt
        """)
        max_id = c.fetchall()[0][0]
        conn.commit()
        conn.close()
        if not max_id:
            return 1
        else:
            return max_id + 1

    def save(self):
        self.generate_time = timestamp()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        def select():
            c.execute(f"""
                select * from charge_stmt
                where csid = '{self.csid}'
            """)
            return c.fetchall()

        def insert():
            c.execute(f"""
            insert into charge_stmt values(
                '{self.csid}',
                '{self.uid}',
                '{self.mode}',
                '{self.reserve}',
                '{self.pileid}',
                '{self.time_start}',
                '{self.time_end}',
                '{self.time_total}',
                '{self.consume}',
                '{self.cost_charge}',
                '{self.cost_serve}',
                '{self.cost_total}',
                '{self.generate_time}'
            )
            """)

        def update():
            c.execute(f"""
            update charge_stmt
            set uid='{self.uid}',
                mode='{self.mode}',
                reserve='{self.reserve}',
                pileid='{self.pileid}',
                time_start='{self.time_start}',
                time_end='{self.time_end}',
                time_total='{self.time_total}',
                consume='{self.consume}',
                cost_charge='{self.cost_charge}',
                cost_serve='{self.cost_serve}',
                cost_total='{self.cost_total}',
                generate_time='{self.generate_time}'
            where csid = '{self.csid}'
            """)

        result = select()
        if not result:
            insert()
        else:
            update()
        conn.commit()
        conn.close()

    def delete(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(f"""
            delete from charge_stmt
            where csid =  '{self.csid}'
        """)
        conn.commit()
        conn.close()


############################################################
# 充电桩类
# 编码提示
############################################################
class charge_pile:
    def __init__(self):
        self.pile_id = 0
        self.charge_cnt = 0  # 充电次数
        self.charge_time = 0  # 累计充电时长
        self.charge_capacity = 0  # 累计充电量
        self.cost_of_charge = 0  # 充电费
        self.cost_of_serve = 0  # 服务费
        self.cost_all = 0  # 总费用


############################################################
# 排队类
############################################################
class wait_info:
    """ 保存排队相关的信息 """
    queue_cnt = {'F': 0, 'T': 0}

    def __init__(self, uid, mode, reserve, total, waitid='F0', state='p'):
        """禁止调用这个构造函数, 一定要调用new_wait_info"""
        self.uid = uid
        self.mode = mode
        """充电模式, 可选: F/T"""
        self.reserve = reserve
        """预约充电量, 单位: 度"""
        self.total = total

        self.waitid = waitid
        self.state = state
        """state 可选: p(等待区中)/wait(充电区)/ing(正在充电)/end"""
        self.pileid = None
        self.already = 0
        """已经充电的充电量"""

    @staticmethod
    def new_waitid(mode):
        wait_info.queue_cnt[mode] += 1
        waitid = f"{mode}{wait_info.queue_cnt[mode]}"
        return waitid

    @staticmethod
    def new_wait_info(uid, mode, reserve, total):
        waitid = wait_info.new_waitid(mode)
        new_wait = wait_info(uid, mode, reserve, total, waitid)
        return new_wait

    def show_car_info(self):
        """显示正在排队的车辆的信息"""
        return {"uid": self.uid, "total": self.total, "reserve": self.reserve}

    def __str__(self):
        dd = {"uid": self.uid, "mode": self.mode, "reserve": self.reserve, "total": self.total,
              "waitid": self.waitid, "state": self.state, "pileid": self.pileid}
        return json.dumps(dd, ensure_ascii=False)

    def __repr__(self):
        return self.__str__()


############################################################
# 调度器类
############################################################
class scheduler:
    def __init__(self):
        self.queue = {'F': defaultdict(list), 'T': defaultdict(list)}
        self.queue_wait = {'F': [], 'T': []}
        """队列中的元素是wait_info类"""
        self.waitid_to_csid = {}
        """等待号映射到详单号"""
        self.charge_stmts = {}
        """根据csid找到charge_statement对象(只保存需要更新的详单,不保存已结束的详单)"""
        self.wait_infos = {}
        """根据waitid找到wait_info对象"""
        self.last_update_time = time.time()

        for mode in ['F', 'T']:
            for pileid in PILEID[mode]:
                self.queue[mode][pileid] = []

    ##############################
    # 工具函数
    ##############################
    def wait_to_stmt(self, wait) -> charge_statement:
        """用wait_info类找到charge_statement类(借助了self.waitid_to_csid)"""
        stmt_id = self.waitid_to_csid[wait.waitid]
        return self.charge_stmts[stmt_id]

    ##############################
    # 新增充电请求
    # 参数: mode充电模式, reserve充电时长
    # 返回值: waitID
    # 功能: 处理新新增的充电请求
    #      生成一个详单charge_stmt, 保存到调度器的charge_stmts里
    #      生成一个等待wait,保存到里
    #      更新 waitid_to_csid 映射关系
    ##############################
    def new_charge_request(self, uid, mode, reserve, total):
        """新增充电请求 """
        wait = wait_info.new_wait_info(uid, mode, reserve, total)
        charge_stmt = charge_statement.new_charge_statement(wait)
        charge_stmt.save()  # 保存到数据库
        self.charge_stmts[charge_stmt.csid] = charge_stmt
        self.wait_infos[wait.waitid] = wait
        self.queue_wait[mode].append(wait)
        self.waitid_to_csid[wait.waitid] = charge_stmt.csid
        return wait.waitid

    ##############################
    # 修改充电请求
    # 返回值: 新的waitid
    # 功能: 提供waitid, mode, reserve, 修改充电请求
    ##############################
    def modify_charge_request(self, waitid, mode, reserve):
        """修改充电请求(只能在等待区修改请求)"""
        try:
            wait = self.wait_infos[waitid]
        except KeyError as e:
            print('waitid not exists')
            raise e

        # 修改 wait
        old_mode = wait.mode
        wait.mode = mode
        wait.reserve = reserve
        if old_mode != wait.mode:
            # 修改这个 wait 的等待队列(等待队列从逻辑上分为快/慢队列)
            self.queue_wait[old_mode].remove(wait)
            self.queue_wait[wait.mode].append(wait)
            # 修改等待号
            old_id = wait.waitid
            wait.waitid = wait_info.new_waitid(wait.mode)
            # 修改 wait_infos 映射
            self.wait_infos.pop(old_id)
            self.wait_infos[wait.waitid] = wait
            # 修改 waitid_to_csid 映射
            csid = self.waitid_to_csid[old_id]
            self.waitid_to_csid.pop(old_id)
            self.waitid_to_csid[wait.waitid] = csid
        # 修改 charge_stmt
        stmt = self.wait_to_stmt(wait)
        stmt.mode = mode
        stmt.reserve = reserve
        stmt.save()  # 保存到数据库
        return wait.waitid

    ##############################
    # 取消充电请求
    # 功能: 提供 waitid, 将该请求从调度队列中删除
    #     如果它在充电区，则更新队列(充电区有空闲)
    ##############################
    def cancel_charge_request(self, waitid):
        """取消充电请求"""
        try:
            wait = self.wait_infos[waitid]
        except KeyError as e:
            print('waitid not exists')
            return
        # 从队列中删除 wait
        if wait.state == 'p':
            self.queue_wait[wait.mode].remove(wait)
        elif wait.state == 'wait':
            pileid = wait.pileid  # 充电桩id
            self.queue[wait.mode][pileid].remove(wait)
        else:
            print('[Error] wait.state is wrong at "cancel_charge_request"')

        # 删除 charge_stmt
        stmt = self.wait_to_stmt(wait)
        stmt.delete()

    ##############################
    # 更新排队队列
    # 功能: 根据当前时间判断是否有车辆完成充电,如果完成充电,则修改相关queue
    #     检测充电区是否有空闲, 有空闲则不断地将等待区的车放入充电区
    #     充电完成的车辆需要计算费用
    #     核心"计费"
    ##############################
    def refresh_system(self):
        """更新排队队列"""
        # 更新时间
        last = self.last_update_time
        now = time.time()
        self.last_update_time = now

        def get_available_pileid(mode):
            """获取有空位的充电区信息"""
            avl_pileid = []
            for pileid, queue in self.queue[mode].items():
                if len(queue) < QUEUE_LEN:
                    avl_pileid.append(pileid)
            return avl_pileid

        def estimate_wait_time(mode):
            wait_times = {}
            for pileid, queue in self.queue[mode].items():
                wait_time = 0
                for wait in queue:
                    chg_left = wait.reserve - wait.already
                    wait_time += chg_left / CHG_SPEED[mode]
                else:
                    wait_times[pileid] = wait_time
            return wait_times

        def call_wait():
            for mode in ['F', 'T']:
                """从等待区叫到充电区"""
                while len(self.queue_wait[mode]) and len(get_available_pileid(mode)):
                    # 1. 选择等待时间最短的队列
                    available_pileid = get_available_pileid(mode)
                    wait_times = {k: v for k, v in estimate_wait_time(mode).items() if k in available_pileid}
                    target_pileid = min(wait_times, key=wait_times.get)
                    # 2. 将其加入这个队列
                    wait = self.queue_wait[mode].pop(0)
                    self.queue[mode][target_pileid].append(wait)
                    # 3. 更新表单
                    wait.state = 'wait'
                    wait.pileid = target_pileid
                    stmt = self.wait_to_stmt(wait)
                    stmt.pileid = target_pileid
                    if len(self.queue[mode][target_pileid]) == 1:
                        # 进去就开始充电
                        wait.state = 'ing'
                        stmt.time_start = timestamp(now)
                    stmt.save()

        def update_queue():
            """
            充电队列随着时间推移，修改相关信息;

            一定要保证两次更新间隔足够小，不会导致一个队列一次性结束2个及以上的充电
            """
            timediff = int(now - last)  # 时间比较单位用s, 并且要求是整数比较
            for mode in ['F', 'T']:
                for pileid, queue in self.queue[mode].items():
                    if len(queue) == 0:
                        continue
                    timeline = 0
                    """时间线, 单位是s"""
                    while timeline < timediff and len(queue) > 0:
                        charger = queue[0]
                        stmt = self.wait_to_stmt(charger)
                        need_power = charger.reserve - charger.already
                        """还需要的充电量, 单位“度”"""
                        need_time = int(need_power / CHG_SPEED[mode] * 3600)
                        if need_time < timediff - timeline:
                            # 直接充满
                            # 1. 修改 wait_info 和 charge_statement 对象信息
                            charger.already = charger.reserve
                            charger.state = 'end'
                            stmt.time_total = seconds_to_HMS(stmt.reserve / CHG_SPEED[mode] * 3600)
                            stmt.time_end = timestamp_add(stmt.time_start, HMS_to_seconds(stmt.time_total))
                            stmt.consume = stmt.reserve
                            # todo :结算充电费用和服务费用
                            stmt.save()
                            # 2. 更新队列
                            queue.pop(0)
                            if len(queue) > 0:
                                newer_charger = queue[0]
                                newer_stmt = self.wait_to_stmt(newer_charger)
                                newer_charger.state = 'ing'
                                newer_stmt.time_start = timestamp(last + timeline)
                                newer_stmt.save()
                            timeline += need_power
                        else:
                            # 只充一半
                            charger.already = charger.already + CHG_SPEED[mode] * [(timediff - timeline) / 3600]
                            stmt.consume = charger.already
                            # todo: 结算充电费用
                            stmt.save()
                            timeline = timediff

        # 更新队列
        update_queue()
        # 叫号
        call_wait()
        update_queue()


##############################
# 用户结束充电
#
##############################
def user_end_charge(self, waitid):
    pass


##############################
# 暂停使用某个充电桩
# 功能: 正在充电的车辆停止计费, 本次充电过程详单记录完成
#     ① 优先级调度: 暂停等待区叫号, 优先给故障队列的车进行调度
#     ② 时间顺序调度: 充电区中未充电的车辆合并为一组
##############################
def stop_charge_pile(self):
    """ 暂停使用某个充电桩 """
    pass


##############################
# 恢复使用某个充电桩
# 功能: 同类型的充电桩混洗，按时间重新调度
##############################
def start_charge_pile(self):
    """恢复使用某个充电桩"""
    pass
