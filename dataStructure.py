import sqlite3
from config import DB_PATH
from collections import defaultdict


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
        self.time_total = 0  # 总时间
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
        charge_stmt.time_total = None  # 总时间
        charge_stmt.consume = None  # 充电电量
        charge_stmt.charge_time = None  # 充电时长
        charge_stmt.cost_charge = None  # 充电费用
        charge_stmt.cost_serve = None  # 服务费用
        charge_stmt.cost_total = None  # 总费用
        return charge_stmt

        charge_stmt.generate_time = 0  # 详单生成时间

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
            delete from charge_stme
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
    F_cnt = 1
    T_cnt = 1

    def __init__(self, uid, mode, reserve, total, wait_id='F0', state='p'):
        """禁止调用这个构造函数, 一定要调用new_wait_info"""
        self.uid = uid
        self.mode = mode
        self.reserve = reserve
        self.total = total

        self.wait_id = wait_id
        self.state = state
        """state 可选: p(等待区中)/wait(充电区)/ing(正在充电)/end"""
        self.pileid = None

    @staticmethod
    def new_wait_info(uid, mode, reserve, total):
        if mode == 'F':
            wait_id = f"{mode}{wait_info.F_cnt}"
            wait_info.F_cnt += 1
        else:
            wait_id = f"{mode}{wait_info.T_cnt}"
            wait_info.T_cnt += 1
        new_wait = wait_info(uid, mode, reserve, total, wait_id)
        return new_wait

    def show_car_info(self):
        """显示正在排队的车辆的信息"""
        return {"uid": self.uid, "total": self.total, "reserve": self.reserve}


############################################################
# 调度器类
############################################################
class scheduler:
    def __init__(self):
        self.queue_slow = defaultdict(list)  # 快充桩队列
        self.queue_fast = defaultdict(list)  # 慢充桩队列
        self.queue_wait = []  # 等待区队列
        """队列中的元素是wait_info类"""
        self.waitid_to_queue = {}  # 反向索引: waitID->队列号
        """'P'表示在等待区; (F,1)(F,2)表示在快桩;(T,1),(T,2)(T,3)表示在慢桩"""
        self.waitid_to_csid = {}
        """等待号映射到详单号"""
        self.charge_stmts = {}
        """根据csid找到charge_statement对象(只保存需要更新的详单,不保存已结束的详单)"""
        self.wait_infos = {}
        """根据waitid找到wait_info对象"""

    ##############################
    # 部分工具函数
    ##############################
    def wait_to_stmt(self, wait) -> charge_statement:
        stmt_id = self.waitid_to_csid[wait.wait_id]
        return self.charge_stmts[stmt_id]

    ##############################
    # 新增充电请求
    # 参数: mode充电模式, reserve充电时长
    # 返回值: waitID
    # 功能: 处理新新增的充电请求
    #      生成一个详单charge_stmt, 保存到调度器的charge_stmts里
    #      生成一个等待wait,保存到里
    #      更新 waitid_to_csid 映射关系
    #      更新 waitid_to_queue 映射关系
    ##############################
    def new_charge_request(self, uid, mode, reserve, total):
        """新增充电请求 """
        wait = wait_info.new_wait_info(uid, mode, reserve, total)
        charge_stmt = charge_statement.new_charge_statement(wait)
        charge_stmt.save()  # 保存到数据库
        self.charge_stmts[charge_stmt.csid] = charge_stmt
        self.wait_infos[wait.wait_id] = wait
        self.queue_wait.append(wait)
        self.waitid_to_queue[wait.wait_id] = 'P'
        self.waitid_to_csid[wait.wait_id] = charge_stmt.csid
        return wait.wait_id

    ##############################
    # 修改充电请求
    # 功能: 提供wait_id, mode, reserve, 修改充电请求
    ##############################
    def modify_charge_request(self, wait_id, mode, reserve):
        """修改充电请求(只能在等待区修改请求)"""
        try:
            wait = self.wait_infos[wait_id]
        except KeyError as e:
            print('wait_id not exists')
            raise e

        # 修改 wait
        wait.mode = mode
        wait.reserve = reserve
        # 修改 charge_stmt
        stmt = self.wait_to_stmt(wait)
        stmt.mode = mode
        stmt.reserve = reserve
        stmt.save()  # 保存到数据库

    ##############################
    # 取消充电请求
    # 功能: 提供 wait_id, 将该请求从调度队列中删除
    #     如果它在充电区，则更新队列(充电区有空闲)
    ##############################
    def cancel_charge_request(self, wait_id):
        """取消充电请求"""
        try:
            wait = self.wait_infos[wait_id]
        except KeyError as e:
            print('wait_id not exists')
            raise e
        # 从队列中删除 wait
        if wait.state == 'p':
            self.queue_wait.remove(wait)
        elif wait.state == 'wait':
            mode, qid = wait.wait_id[0], int(wait.wait_id[1])
            if mode == 'f':
                self.queue_fast[qid].remove(wait)
            elif mode == 't':
                self.queue_slow[qid].remove(wait)
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
    def update_queue(self):
        """更新排队队列"""
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
