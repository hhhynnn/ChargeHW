import json
import sqlite3
from config import *
from collections import defaultdict
import time
from datetime import datetime, timedelta

START_TIME = time.time()


def timestamp(now: time = None):
    if now is None:
        now = get_time()
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now))


def timestamp_add(time_str, seconds):
    return timestamp(timestamp_to_seconds(time_str) + seconds)


def timestamp_to_seconds(time_str):
    """只支持一种格式: '%Y-%m-%d %H:%M:%S'"""
    pattern = '%Y-%m-%d %H:%M:%S'
    return time.mktime(datetime.strptime(time_str, pattern).timetuple())


def HMS_to_seconds(time_str):
    """只支持一种格式: '%H:%M:%S'"""
    h, m, s = time_str.split(':')
    return int(h) * 3600 + int(m) * 60 + int(s)


def seconds_to_HMS(seconds):
    return time.strftime("%H:%M:%S", time.gmtime(seconds))


def get_time() -> float:
    delta = time.time() - START_TIME
    delta *= TIME_RULER
    now = START_TIME + delta
    return now


def get_cost(start: str, end: str, mode: str) -> [float, float]:
    '''
    计算收费结果

    :param start:开始时间，e.g:'2022-6-14 19:00:00'
    :param end: 结束时间,e.g:'2022-6-15 03:00:00'
    :param mode: 充电模式，{'T','F'}

    :return:服务费cost_serve，电费cost_charge
    '''
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


############################################################
# 详单类
############################################################
class charge_statement:

    def __init__(self, csid=0, uid=0, mode='', reserve=0, pileid='', time_start='xxxx-xx-xx 00:00:00',
                 time_end='xxx-xx-xx 00:00:00', time_total='00:00:00', consume=0, cost_charge=0, cost_serve=0,
                 generate_time='xxxx-xx-xx 00:00:00', finish='False'):
        self.csid = csid  # 详单编号
        self.uid = uid  # 用户id
        self.mode = mode  # 充电类型
        """可选F/T"""
        self.reserve = reserve  # 预计充电电量

        self.pileid = pileid  # 提供充电的充电桩编号
        self.time_start = time_start  # 启动时间

        self.time_end = time_end  # 结束时间
        self.time_total = time_total  # 总时间
        self.consume = consume  # 充电电量
        self.cost_charge = cost_charge  # 充电费用
        self.cost_serve = cost_serve  # 服务费用

        self.generate_time = generate_time  # 详单生成时间
        self.finish = finish

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
        charge_stmt.generate_time = timestamp()  # 详单生成时间
        charge_stmt.finish = 'False'
        return charge_stmt

    def start_chg_at(self, time_start):
        """
        传入开始充电时间, 更新表单
        """
        self.time_start = time_start

    def cont_chg_at(self, time_cont):
        """传入正在充电的某个时间点, 更新表单"""
        start_sec = timestamp_to_seconds(self.time_start)
        cont_sec = timestamp_to_seconds(time_cont)
        delta_sec = cont_sec - start_sec
        self.time_total = seconds_to_HMS(delta_sec)
        self.consume = CHG_SPEED[self.mode] * (delta_sec / 3600)
        self.cost_serve, self.cost_charge = get_cost(self.time_start, time_cont, self.mode)
        self.generate_time = time_cont

    def end_chg_at(self, time_end):
        """传入结束充电的某个时间点, 更新表单"""
        self.cont_chg_at(time_end)
        self.time_end = time_end
        self.finish = 'True'

    def toDict(self):
        return {"csid": self.csid,
                "uid": self.uid,
                "mode": self.mode,
                "reserve": self.reserve,
                "pileid": self.pileid,
                "time_start": self.time_start,
                "time_end": self.time_end,
                "time_total": self.time_total,
                "consume": self.consume,
                "cost_charge": self.cost_charge,
                "cost_serve": self.cost_serve,
                "cost_total": self.cost_charge + self.cost_serve,
                "generate_time": self.generate_time,
                "finish": self.finish}

    def __str__(self):
        return json.dumps(self.toDict(), ensure_ascii=False)

    def __repr__(self):
        return self.__str__()

    def toJSON(self):
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
                '{self.generate_time}',
                '{self.finish}'
            )
            """)

        def update():
            syntax = f"""
            update charge_stmt
            set uid='{self.uid}',
                mode='{self.mode}',
                reserve='{self.reserve}',
                pileid='{self.pileid}',
                time_start='{self.time_start}',
                time_end='{self.time_end}',
                time_total='{self.time_total}',
                consume='{self.consume}',
                cost_charge={self.cost_charge},
                cost_serve={self.cost_serve},
                generate_time='{self.generate_time}',
                finish = '{self.finish}'
            where csid = '{self.csid}'
            """
            c.execute(syntax)

        result = select()
        if not result:
            insert()
        else:
            update()

        # 更新 user_to_charge_stmt
        c.execute(f"""
            select csid from user_to_charge_stmt
            where uid = '{self.uid}'
        """)
        csid_list = [x[0] for x in c.fetchall()]
        if self.csid not in csid_list:
            c.execute(f"""
                insert into user_to_charge_stmt (uid, csid) values
                ('{self.uid}','{self.csid}')
            """)
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
# 充电桩
# 编码提示 这个类没有用
###########################################################
class charge_pile:
    def __init__(self, pileid, charge_cnt=0, charge_time=0, charge_capacity=0, cost_charge=0, cost_serve=0, state='on'):
        self.pileid = pileid
        self.charge_cnt = charge_cnt  # 充电次数
        self.charge_time = charge_time  # 累计充电时长
        self.charge_capacity = charge_capacity  # 累计充电量
        self.cost_charge = cost_charge  # 充电费
        self.cost_serve = cost_serve  # 服务费
        self.state = state

    def toDict(self):
        return {"pileid": self.pileid, "charge_cnt": self.charge_cnt, "charge_time": self.charge_time,
                "charge_capacity": self.charge_capacity, "cost_charge": self.cost_charge,
                "cost_serve": self.cost_serve, "state": self.state}

    def __str__(self):
        return json.dumps(self.toDict(), ensure_ascii=False)

    def __repr__(self):
        return self.__str__()

    def save(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        keys = self.toDict()[1:] + self.toDict()[0]
        c.execute("""
            update charge_pile
            set charge_cnt ={},charge_time = {},charge_capacity={},cost_charge={},cost_serve = {},state={}
            where pileid = {}
        """.format(*keys))
        conn.commit()
        conn.close()


############################################################
# 排队类
############################################################
class wait_info:
    """ 保存排队相关的信息 """
    queue_cnt = {'F': 0, 'T': 0}

    def __init__(self, uid, mode, reserve, capaticy, waitid='F0', state='p'):
        """禁止调用这个构造函数, 一定要调用new_wait_info"""
        self.uid = uid
        self.mode = mode
        """充电模式, 可选: F/T"""
        self.reserve = reserve
        """预约充电量, 单位: 度"""
        self.capacity = capaticy

        self.waitid = waitid
        self.state = state
        """state 可选: p(等待区中)/wait(充电区)/ing(正在充电)/end"""
        self.pileid = None
        self.already = 0
        """已经充电的充电量"""

        self.request_time = 'xxxx-xx-xx xx:xx:xx'
        """发起申请的时间"""

    @staticmethod
    def new_waitid(mode):
        wait_info.queue_cnt[mode] += 1
        waitid = f"{mode}{wait_info.queue_cnt[mode]}"
        return waitid

    @staticmethod
    def new_wait_info(uid, mode, reserve, total):
        waitid = wait_info.new_waitid(mode)
        new_wait = wait_info(uid, mode, reserve, total, waitid)
        new_wait.request_time = timestamp()
        return new_wait

    def show_car_info(self):
        """显示正在排队的车辆的信息"""
        return {"uid": self.uid, "total": self.capacity, "reserve": self.reserve}

    def __str__(self):
        dd = {"uid": self.uid, "waitid": self.waitid, "mode": self.mode, "state": self.state,
              "reserve": self.reserve, "already": self.already, "total": self.capacity, "pileid": self.pileid, }
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
        self.last_update_time = get_time()

        for mode in ['F', 'T']:
            for pileid in PILEID[mode]:
                self.queue[mode][pileid] = []

        # 初始化 self.charge_stmts 的值
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(""" select * from charge_stmt """)
        stmts = c.fetchall()
        for stmt_tuple in stmts:
            csid = stmt_tuple[0]
            stmt = charge_statement(*stmt_tuple)
            self.charge_stmts[csid] = stmt

        conn.commit()
        conn.close()

    ##############################
    # 工具函数(获取某些属性)
    ##############################
    def wait_to_stmt(self, wait) -> charge_statement:
        """用wait_info类找到charge_statement类(借助了self.waitid_to_csid)"""
        stmt_id = self.waitid_to_csid[wait.waitid]
        return self.charge_stmts[stmt_id]

    def get_charge_area_cnt(self):
        """获取充电区车数量"""
        cnt = 0
        for mode in ['T', 'F']:
            for pileid, queue in self.queue[mode].items():
                cnt += len(queue)
        return cnt

    def get_charge_area_size(self):
        size = 0
        for mode in ['T', 'F']:
            for pileid in self.queue[mode]:
                size += QUEUE_LEN
        return size

    def get_wait_area_cnt(self):
        """获取等待区车数量"""
        cnt = 0
        for mode, queue in self.queue_wait.items():
            cnt += len(queue)
        return cnt

    def get_wait_area_size(self):
        return WAIT_QUEUE_LEN

    ##############################
    # 新增充电请求
    # 参数: mode充电模式, reserve充电时长
    # 返回值: waitID
    # 功能: 处理新新增的充电请求
    #      生成一个详单charge_stmt, 保存到调度器的charge_stmts里
    #      生成一个等待wait,保存到里
    #      更新 waitid_to_csid 映射关系
    ##############################
    def new_charge_request(self, uid, mode, reserve, capacity):
        """新增充电请求 """
        wait = wait_info.new_wait_info(uid, mode, reserve, capacity)
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
            print('[error] waitid not exists')
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
            print('[error] waitid not exists')
            return
        # 从队列中删除 wait
        if wait.state == 'p':
            self.queue_wait[wait.mode].remove(wait)
        elif wait.state == 'wait':
            pileid = wait.pileid  # 充电桩id
            self.queue[wait.mode][pileid].remove(wait)
        else:
            if wait.state == 'ing':
                print('[Error] this wait is charging now, can\'t cancel')
                return 1
            elif wait.state == 'end':
                print('[Error] this wait is end now, can\'t cancel')
                return 2
            else:
                print('[Error] wait.state is wrong in cancel_charge_request')
                return 3  # 错误码

        # 删除 charge_stmt
        stmt = self.wait_to_stmt(wait)
        csid = stmt.csid
        self.charge_stmts.pop(csid)  # 从内存删除
        stmt.delete()  # 从数据库删除
        return 0

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
        pre = self.last_update_time
        now = get_time()
        self.last_update_time = now

        def get_available_pileid(mode):
            """获取有空位的充电区信息"""
            avl_pileid = []
            for pileid, queue in self.queue[mode].items():
                if len(queue) < QUEUE_LEN:
                    avl_pileid.append(pileid)
            return avl_pileid

        def estimate_wait_time(mode):
            """计算等待时间"""
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
            if SCHEDULE_MODE == 'default':
                for mode in ['F', 'T']:
                    """从等待区叫到充电区"""
                    while len(self.queue_wait[mode]) and len(get_available_pileid(mode)):
                        # 1. 选择等待时间最短的队列
                        available_pileid = get_available_pileid(mode)  # 有空位的桩
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
                            stmt.start_chg_at(timestamp(now))
                        stmt.save()
            elif SCHEDULE_MODE == 'flood':
                # 1. 判断充电区是否有车, 如果有车, 则强制等待
                if self.get_charge_area_cnt() > 0:
                    return
                # 2. 如果充电区没有车, 判断申请数量是否达到充电区+等待区数量, 如果不够, 则强制等待
                request_cnt = self.get_wait_area_cnt()  # 请求充电数量
                logic_wait_area_size = self.get_charge_area_size() + self.get_wait_area_size()  # 等待区+充电区空位数
                if request_cnt < logic_wait_area_size:
                    return
                # 3. 充电区没车, 且申请数量数量达到充电区+等待区数量, 开始调度
                valid_pileid = {'T': list(self.queue['T'].keys()), 'F': list(self.queue['F'].keys())}
                waits = self.queue_wait['T'] + self.queue_wait['F']
                waits.sort(key=lambda x: timestamp_to_seconds(x.request_time))
                waits = waits[:logic_wait_area_size]

                ##############################
                # 计算调度顺序
                # 参数: pileid_list => {'T':['T#1', 'T#2','T#3'], 'F':['F#1','F#2']}
                #      waits  => 类型为 list(wait_info), 即元素为 wait_info 的列表
                # 返回值:
                #      seq => {'T#1': list(wait_info), 'T#2':list(wait_info),...}
                ##############################
                def make_seq(pileid_list, wait_list):
                    """根据充电桩号 和 等待类计算最优排队序列"""
                    wait_list.sort(key=lambda x: float(x.reserve))  # 按预约充电量从小到大排序
                    seq_index = []  # 索引, 用来填排队顺序
                    # for pile_id in pileid_list:
                    #     for idx in range(QUEUE_LEN):
                    #         speed = CHG_SPEED[pile_id[0]]
                    #         seq_index.append((pile_id, idx, (QUEUE_LEN - idx) / speed))
                    while len(seq_index) < len(wait_list):
                        # 每加入3个快充，就加入1个慢充
                        for _ in range(3):
                            for pile_id in pileid_list['F']:
                                # seq_index.append(('F', pile_id))
                                # !!!!! 这里只能填 pile_id 进去, 因为下面会遍历 seq_index, 并把其值作为索引保存到seq
                                seq_index.append(pile_id)
                        for pile_id in pileid_list['T']:
                            # seq_index.append(('T', pile_id))
                            seq_index.append(pile_id)
                    # 截断末尾部分
                    seq_index = seq_index[:len(wait_list)]
                    seq_index.reverse()
                    seq = defaultdict(list)
                    # 遍历上面的索引, 依次填每个wait要放进哪个桩
                    for idx in range(len(seq_index)):
                        wait_t = wait_list[idx]
                        pile_id = seq_index[idx]  # !!! 这里遍历了seq_index, 并利用了其值
                        seq[pile_id].append(wait_t)
                    return seq

                best_seq = make_seq(valid_pileid, waits)
                for pileid, wait_seq in best_seq.items():
                    for wait in wait_seq:
                        mode = wait.mode
                        self.queue_wait[mode].remove(wait)  # 从等待队列中删除
                        self.queue[mode][pileid].append(wait)  # 加入充电队列
                        wait.state = 'wait'
                        wait.pileid = pileid
                        stmt = self.wait_to_stmt(wait)
                        stmt.pileid = pileid
                        if len(self.queue[mode][pileid]) == 1:
                            wait.state = 'ing'
                            stmt.start_chg_at(timestamp(now))
                        stmt.save()
            else:
                print('[error] config error')
                pass

        def update_queue():
            """
            充电队列随着时间推移，修改相关信息;
            """
            end_wait_list = []
            timediff = int(now - pre)  # 时间比较单位用s, 并且要求是整数比较
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
                            timeline += need_time
                            # 直接充满
                            end_wait_list.append(charger)
                            # 1. 修改 wait_info 和 charge_statement 对象信息
                            charger.already = charger.reserve
                            charger.state = 'end'
                            time_cur = timestamp(pre + timeline)
                            stmt.end_chg_at(time_cur)
                            stmt.save()
                            # 2. 更新队列
                            queue.pop(0)
                            if len(queue) > 0:
                                newer_charger = queue[0]
                                newer_charger.state = 'ing'
                                newer_stmt = self.wait_to_stmt(newer_charger)
                                newer_stmt.start_chg_at(time_cur)
                                newer_stmt.save()
                            timeline += need_time
                        else:
                            # 只充一半
                            timeline = timediff
                            stmt.cont_chg_at(timestamp(now))
                            charger.already = (HMS_to_seconds(stmt.time_total) / 3600) * CHG_SPEED[charger.mode]
                            stmt.save()
            return end_wait_list

        # 更新队列
        end_list = update_queue()
        # 叫号
        call_wait()
        # update_queue()
        end_stmt_list = [self.wait_to_stmt(x) for x in end_list]
        return end_list, end_stmt_list

    ##############################
    # 用户结束充电
    ##############################
    def user_end_charge(self, waitid):
        """只有正在充电的用户才能调用这个函数(取消充电请求使用 cancel_charge_request)"""
        self.refresh_system()
        wait: wait_info = self.wait_infos[waitid]
        stmt = self.wait_to_stmt(wait)
        mode = wait.mode
        # 0. 验证用户是否正在充电
        if wait.state != 'ing':
            return f'[error] wait.state == {wait.state} in user_end_charge'
        # 1. 修改该wait的详单信息
        wait.state = 'end'
        stmt.end_chg_at(timestamp(self.last_update_time))
        stmt.save()
        wait.already = (HMS_to_seconds(stmt.time_total) / 3600) * CHG_SPEED[wait.mode]

        # 2. 更新队列（下一个车进行充电）
        queue = self.queue[wait.mode][wait.pileid]
        queue.pop(0)
        if len(queue) != 0:
            new_wait: wait_info = queue[0]
            new_wait.state = 'ing'
            new_stmt = self.wait_to_stmt(new_wait)
            new_stmt.start_chg_at(timestamp(self.last_update_time))
            new_stmt.save()
        # 3. 后车进入
        self.refresh_system()
        return "success"

    ##############################
    # 暂停使用某个充电桩
    # 功能: 正在充电的车辆停止计费, 本次充电过程详单记录完成
    #     ① 优先级调度: 暂停等待区叫号, 优先给故障队列的车进行调度
    #     ② 时间顺序调度: 充电区中未充电的车辆合并为一组
    ##############################
    def stop_charge_pile(self, pileid):
        """ 暂停使用某个充电桩, 返回已结束的详单"""
        self.refresh_system()
        now = self.last_update_time
        mode = pileid[0]
        queue = self.queue[mode][pileid]
        self.queue[mode].pop(pileid)  # 清空一个队列
        if len(queue) == 0:
            return
        head: wait_info = queue[0]
        # 让这个仁兄停止充电
        head_stmt = self.wait_to_stmt(head)
        head_stmt.end_chg_at(timestamp(now))
        head_stmt.save()
        # 修改 wait
        head.reserve -= head_stmt.consume
        head.already = 0
        # 给他一个新的详单
        new_stmt = charge_statement.new_charge_statement(head)
        self.charge_stmts[new_stmt.csid] = new_stmt
        self.waitid_to_csid[head.waitid] = new_stmt.csid
        self.charge_stmts[new_stmt.csid] = new_stmt
        new_stmt.save()

        if FAILOVER_MODE == 'priority':
            for wait in queue[::-1]:
                wait.state = 'p'
                wait.pileid = None
                # 修改stmt
                stmt = self.wait_to_stmt(wait)
                stmt.pileid = None
                stmt.save()
                self.queue_wait[mode].insert(0, wait)
        elif FAILOVER_MODE == 'shuffle':
            # 混为一个编队
            for pileid, queue_ in self.queue[mode].items():
                queue.extend(queue_[1:])
                self.queue[mode][pileid] = queue_[:1]
            # 重新排序
            queue.sort(key=lambda x: int(x.waitid[1:]))
            for wait in queue[::-1]:
                wait.state = 'p'
                wait.pileid = None
                stmt = self.wait_to_stmt(wait)
                stmt.pileid = None
                self.queue_wait[mode].insert(0, wait)
                stmt.save()
        self.refresh_system()
        return head_stmt

    ##############################
    # 恢复使用某个充电桩
    # 功能: 同类型的充电桩混洗，按时间重新调度
    ##############################
    def start_charge_pile(self, pileid):
        """恢复使用某个充电桩"""
        self.refresh_system()
        mode = pileid[0]
        self.queue[mode][pileid] = []
        queue_tmp = []
        for pileid, queue_ in self.queue[mode].items():
            queue_tmp.extend(queue_[1:])
            self.queue[mode][pileid] = queue_[:1]
        queue_tmp.sort(key=lambda x: int(x.waitid[1:]))
        for wait in queue_tmp[::-1]:
            wait.pileid = None
            stmt = self.wait_to_stmt(wait)
            stmt.pileid = None
            self.queue_wait[mode].insert(0, wait)
        self.refresh_system()


############################################################
# 用户类
############################################################
class user_info:
    def __init__(self, uid, passwd, capacity, balance=0):
        self.uid = uid
        self.passwd = passwd
        self.capacity = capacity
        self.balance = balance
        self.state = 'off'
        """登陆状态, 可选 on/off"""
        self.cur_wait: wait_info = None

    def add_balance(self, money):
        self.balance += money
        self.save()
        return self.balance

    def save(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(f"""
            select * from user
            where uid = '{self.uid}'
        """)
        result = c.fetchall()
        if not result:
            c.execute(f"""
                insert into user (uid, passwd, balance, capacity) values
                ('{self.uid}','{self.passwd}','{self.balance}','{self.capacity}')
            """)
        else:
            c.execute(f"""
                update user
                set passwd = '{self.passwd}',
                    balance = {self.balance},
                    capacity = {self.capacity}
                where uid = '{self.uid}'
            """)
        conn.commit()
        conn.close()


############################################################
# 用户管理器
# 功能: 1. 同步用户信息到数据库
#      2. 支持 uid => waitid 转换, 查询用户当前的 waitid
#      3. 支持 uid => stmts 转换
# 注: 唯一负责 user 和 user_to_charge_stmt 的更新
############################################################
class user_controller:
    def __init__(self):
        self.users = {}
        self.uid_to_csid = defaultdict(list)
        """ uid 到 csid 的映射,在用户发出充电申请的时候更新, 即 user_new_charge """
        self.uid_to_waitid = {}
        """uid 到 wait 的映射. 在user_new_charge, user_modify_charge事件中更新
        在user_cancel_charge, user_end_charge中删除
        在refresh_system时也可能被删除"""

        # 初始化 self.users 的值
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""select * from user""")
        users = c.fetchall()

        for user in users:
            uid = user[1]
            self.users[uid] = user_info(*user[1:5])

        # 初始化 self.uid_to_csid 的值
        for uid in self.users:
            c.execute(f"""
            select csid from user_to_charge_stmt
            where uid = '{uid}'
            """)
            result = c.fetchall()
            for csid_tuple in result:
                self.uid_to_csid[uid].append(csid_tuple[0])
        conn.commit()
        conn.close()

    def user_to_wait(self, user: user_info):
        uid = user.uid
        if uid not in self.uid_to_waitid:
            return None
        else:
            return self.uid_to_waitid[uid]

    def get_waitid_by_uid(self, uid):
        if uid not in self.users:
            return None
        else:
            return self.uid_to_waitid[uid]

    def get_user_all_csid(self, uid):
        if uid not in self.uid_to_csid:
            return []
        csid_list = self.uid_to_csid[uid]
        return csid_list

    def get_user(self, uid) -> user_info:
        return self.users[uid]

    def user_register(self, uid, passwd, capacity):
        """
        用户注册, 填写 uid, passwd, capacity(电池容量)

        用户名已存在返回 1, 成功返回 0

        """
        if uid in self.users:
            return 1
        # 更新 self.users
        user = user_info(uid, passwd, capacity)
        self.users[uid] = user
        user.save()
        return 0

    def user_login(self, uid, passwd):
        """用户登陆, 用户名错误返回1, 密码错误返回2, 成功返回0"""
        if uid not in self.users:
            return 1
        user = self.users[uid]
        if passwd != user.passwd:
            return 2
        user.state = 'on'
        return 0

    def user_add_balance(self, uid, money):
        """用户不存在返回1, 充值成功返回0"""
        if uid not in self.users:
            return 1
        user = self.users[uid]
        user.add_balance(money)
        return 0

    def user_new_request(self, uid, waitid, csid):
        """假设确实是新的(不会检测是否已存在)"""
        self.uid_to_waitid[uid] = waitid
        self.uid_to_csid[uid].append(csid)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(f"""
            insert into user_to_charge_stmt (uid,csid) values
            ('{uid}','{csid}')
        """)
        conn.commit()
        conn.close()

    def cancel_charge_request(self, uid, csid):
        if uid not in self.uid_to_waitid:
            return
        self.uid_to_waitid.pop(uid)
        self.uid_to_csid[uid].remove(csid)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(f"""
            delete from user_to_charge_stmt
            where uid = '{uid}' and csid = '{csid}'
        """)
        conn.commit()
        conn.close()

    def user_end_charge(self, uid):
        if uid not in self.uid_to_waitid:
            return
        self.uid_to_waitid.pop(uid)
        user = self.users[uid]
        user.cur_wait = None
        user.save()

    def refresh(self, end_wait_list, end_stmt_list):
        for wait in end_wait_list:
            uid = wait.uid
            if uid not in self.uid_to_waitid:
                continue
            self.uid_to_waitid.pop(uid)
        for stmt in end_stmt_list:
            user = self.users[stmt.uid]
            user.balance -= (stmt.cost_charge + stmt.cost_serve)
            user.save()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # 更新 uid_to_csid 映射
        c.execute(f"""
            select uid,csid from user_to_charge_stmt
        """)
        uid_to_csid_tuples = c.fetchall()
        for uid, csid in uid_to_csid_tuples:
            if uid not in self.uid_to_csid:
                self.uid_to_csid[uid] = [csid, ]
            elif csid not in self.uid_to_csid[uid]:
                self.uid_to_csid[uid].append(csid)

        conn.commit()
        conn.close()
