import json
import sqlite3
import time
from dataStructure import *
import requests

from flask import Flask, request

schedule_contr = scheduler()
user_contr = user_controller()

app = Flask(__name__)


def dict_to_json(dd: dict):
    return json.dumps(dd, ensure_ascii=False, indent=4, separators=(',', ':'))


@app.route('/')
def hello_world():  # put application's code here
    return "智能充电桩调度计费系统"


################################################################################
# 用户客户端功能
# 1. 注册
# 2. 登陆
# 3. 提交充电请求
# 4. 修改充电请求
# 5. 查看充电详单信息
# 6. 取消充电
# 7. 查看本车排队号码
# 8. 查看前车等待数量
# 9. 结束充电
# 10. 余额充值
################################################################################


############################################################
# 1. 注册
# 参数: {
#         "uid": "username",
#         "passwd": "password",
#         "capacity": 200       # 车辆电池总容量
#     }
# 返回值{
#         "code":0,        # 成功时返回0, 失败返回非0
#         "msg":"success", # 成功时返回 success, 失败时返回错误原因
#         "data":{}
#     }

############################################################
@app.route('/UserRegister', methods=['POST'])
def user_register():
    user_contr.refresh(*schedule_contr.refresh_system())

    requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    uid = requestData['uid']
    passwd = requestData['passwd']
    capacity = float(requestData['capacity'])
    # <<< 参数

    code = user_contr.user_register(uid, passwd, capacity)
    if code == 1:
        return dict_to_json({"code": 1, "msg": 'uid already exists', "data": {}})
    elif passwd in (None,):
        return dict_to_json({"code": 2, "msg": "passwd can't be null", "data": {}})
    else:
        msg = 'success'
    return dict_to_json({"code": code, "msg": msg, "data": {}})


############################################################
# 2. 登陆
#  参数:{
#     "uid":"username",
#     "passwd":"password"
# }
# 返回值:{
#         "code":0,        # 成功时返回0, 失败返回非0
#         "msg":"success", # 成功时返回 success, 失败时返回错误原因
#         "data":{}
#     }
############################################################
@app.route('/UserLogin', methods=['POST'])
def user_login():
    user_contr.refresh(*schedule_contr.refresh_system())

    requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    uid = requestData['uid']
    passwd = requestData['passwd']
    # <<< 参数

    code = user_contr.user_login(uid, passwd)
    msg = ''
    if code == 0:
        msg = "success"
    elif code == 1:
        msg = 'uid not exists'
    elif code == 2:
        msg = 'passwd is wrong'

    return dict_to_json({"code": code, "msg": msg, "data": {}})


############################################################
# 3. 提交充电请求
# 参数: {
#     "uid":"username",
#     "mode":"F",      # 可选: "T"/"F"
#     "reserve":20     # 预约充电量, 单位: 度
# }
# 返回值: {
#     "code":0,
#     "msg":"success",
#     "data":{
#         "waitid":"F1" # 排队号
#     }
############################################################
@app.route('/UserNewCharge', methods=['POST'])
def user_new_charge():
    user_contr.refresh(*schedule_contr.refresh_system())

    requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    uid = requestData['uid']
    mode = requestData['mode']
    reserve = float(requestData['reserve'])
    # <<< 参数
    if uid not in user_contr.users:
        return dict_to_json({"code": 1,
                             "msg": "user not exists",
                             "data": {}})
    user = user_contr.get_user(uid)
    capacity = user.capacity
    if reserve > capacity:
        return dict_to_json({"code": 2,
                             "msg": f"reserve <{reserve}> can't bigger than capacity <{capacity}>",
                             "data": {}})

    if uid in user_contr.uid_to_waitid:
        return dict_to_json({"code": 3,
                             "msg": f'user {uid} has already reserved a charge',
                             "data": {}})
    wait_area_cnt = schedule_contr.get_wait_area_cnt()
    if SCHEDULE_MODE == 'default' and wait_area_cnt >= schedule_contr.get_wait_area_size():
        return dict_to_json({"code": 4,
                             "msg": f'wait area is full, refuse to get new request',
                             "data": {}})
    if user.balance <= 0:
        return dict_to_json({"code": 5,
                             "msg": f'user has no money, refuse to get new request',
                             "data": {}})

    capacity = user.capacity
    code = 0
    msg = 'success'
    # schedule_controller 处理数据
    waitid = schedule_contr.new_charge_request(uid, mode, reserve, capacity)
    # user_controller 处理数据
    csid = schedule_contr.waitid_to_csid[waitid]
    user_contr.user_new_request(uid, waitid, csid)
    return dict_to_json({"code": code, "msg": msg, "data": {"waitid": waitid}})


############################################################
# 4.修改充电请求
# 参数:{
#     "uid":"username",
#     "mode":"T",      # 新的充电模式
#     "reserve":20
# }
# 返回值:{
#     "code":0,
#     "msg":"success",
#     "data":{
#         "waitid":"F1"  # 新的 waitid
#     }
# }
############################################################
@app.route('/UserModifyCharge', methods=['POST'])
def user_modify_charge():
    user_contr.refresh(*schedule_contr.refresh_system())

    requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    uid = requestData['uid']
    mode = requestData['mode'] if 'mode' in requestData else None
    reserve = requestData['reserve'] if 'reserve' in requestData else None
    # <<< 参数

    schedule_contr.refresh_system()

    if uid not in user_contr.uid_to_waitid:
        return dict_to_json({"code": 1,
                             "msg": f"user {uid} has no charge request to modify",
                             "data": {"waitid": None}})
    waitid = user_contr.uid_to_waitid[uid]
    wait = schedule_contr.wait_infos[waitid]
    if mode is None:
        # 传入 null 作为 mode 值时, 不更改充电模式
        mode = wait.mode
    if reserve is None:
        reserve = wait.reserve

    if wait.state != 'p':
        return dict_to_json({"code": 2,
                             "msg": f"wait's state is '{wait.state}', refuse modify",
                             "data": {"waitid": None}})
    # user_controller 处理数据
    waitid = user_contr.uid_to_waitid[uid]
    # schedule_controller 处理数据
    waitid = schedule_contr.modify_charge_request(waitid, mode, reserve)
    # user_controller 处理数据
    user_contr.uid_to_waitid[uid] = waitid
    code = 0
    msg = f"success"
    return dict_to_json({"code": code, "msg": msg, "data": {"waitid": waitid}})


############################################################
# 5. 查看充电详单
# 参数: {
#     "uid":"username"
# }
# 返回值: {
#     "code":0,
#     "msg":"success",
#     "data":{
#         "stmts":[
#             {
#                 "csid":17, # 详单号
#                 "uid":"username",
#                 "mode":"T", # 充电模式
#                 "reserve":20.0, # 预约充电量
#                 "pileid":"T#3",
#                 "time_start":"2022-06-17 20:15:40", # 开始充电时间
#                 "time_end":"None", # 结束充电时间
#                 "time_total":"00:00:10", # 充电总时长
#                 "consume":0.02777777777777778, # 实际充电量
#                 "cost_charge":0.02777777777777778, # 充电费
#                 "cost_serve":0.022222222222222223, # 服务费
#                 "cost_total":0.05, # 总费用
#                 "generate_time":"2022-06-17 20:15:50", # 详单的最后修改时间
#                 "finish":"False" # 此次充电是否结束
#             },
#             {
#                 ......
#             }
#         ]
#     }
# }
############################################################
@app.route('/UserCheckCharge', methods=['POST'])
def user_check_charge():
    user_contr.refresh(*schedule_contr.refresh_system())

    requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    uid = requestData['uid']
    # <<< 参数

    if uid not in user_contr.uid_to_csid:
        data = {"stmts": []}
    else:
        csid_list = user_contr.get_user_all_csid(uid)
        csid_list = list(set(csid_list))  # 去重, 虽然我也不知道为什么会重复
        stmt_list = [schedule_contr.charge_stmts[csid] for csid in csid_list]
        # 输出时按csid升序排序
        stmt_toDict_list = [stmt.toDict() for stmt in stmt_list]
        stmt_toDict_list.sort(key=lambda x: x['csid'])
    return dict_to_json({"code": 0, "msg": "success", "data": stmt_toDict_list})


############################################################
# 6. 取消充电
# 参数:{
#     "uid":username"
# }
# 返回值:{
#     "code":0,
#     "msg":"success",
#     "data":{}
# }
############################################################
@app.route('/UserCancelCharge', methods=['POST'])
def user_cancel_charge():
    user_contr.refresh(*schedule_contr.refresh_system())

    requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    uid = requestData['uid']
    # <<< 参数
    if uid not in user_contr.uid_to_waitid:
        if uid not in user_contr.uid_to_csid:
            return dict_to_json({"code": 1, "msg": "user has no wait", "data": {}})
        else:
            return dict_to_json({"code": 2, "msg": "user's wait already end, can't cancel", "data": {}})
    waitid = user_contr.uid_to_waitid[uid]
    csid = schedule_contr.waitid_to_csid[waitid]
    # schedule_controller 处理数据
    code = schedule_contr.cancel_charge_request(waitid)
    if code != 0:
        return dict_to_json({"code": 3, "msg": "this wait is charging now, can't cancel", "data": {}})

    # user_controller 处理数据
    user_contr.cancel_charge_request(uid, csid)
    return dict_to_json({"code": 0, "msg": "success", "data": {}})


############################################################
# 7. 查看本车排队号码
# 参数: {
#     "uid":"username"
# }
# 返回值:{
#     "code":0,
#     "msg":"success",
#     "data":{
#         "waitid":"T1"
#     }
# }
############################################################
@app.route('/UserShowWaitid', methods=['POST'])
def user_show_waitid():
    user_contr.refresh(*schedule_contr.refresh_system())

    requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    uid = requestData['uid']
    # <<< 参数

    if uid not in user_contr.uid_to_waitid:
        code, msg, data = 1, "user has no wait", {}
    else:
        waitid = user_contr.uid_to_waitid[uid]
        code, msg, data = 0, "success", {"waitid": waitid}
    return dict_to_json({"code": code, "msg": msg, "data": data})


############################################################
# 8. 查看前车等待数量
# 参数: {
#     "uid":"username"
# }
# 返回值:{
#     "code":0,
#     "msg":"success",
#     "data":{
#         "cnt":0 # 前车排队数量
#     }
# }
############################################################
@app.route('/UserShowPreWaitCnt', methods=['POST'])
def user_show_pre_wait_cnt():
    user_contr.refresh(*schedule_contr.refresh_system())

    requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    uid = requestData['uid'] if requestData['uid'] != '' else None
    # <<< 参数
    if uid is None:
        return dict_to_json({"code": 0, "msg": "success", "data": {"cnt": schedule_contr.get_wait_cnt()}})

    if uid not in user_contr.uid_to_waitid:
        return dict_to_json({"code": 1, "msg": "user has no wait", "data": {}})

    waitid = user_contr.uid_to_waitid[uid]
    wait = schedule_contr.wait_infos[waitid]
    mode = wait.mode
    if wait.state == 'p':
        len_p = schedule_contr.queue_wait[mode].index(wait)
        len_wait = 0
        for pileid, queue in schedule_contr.queue[mode].items():
            len_wait += len(queue)
        cnt = len_p + len_wait
    elif wait.state == 'wait':
        pileid = wait.pileid
        cnt = schedule_contr.queue[mode][pileid].index(wait)
    else:
        cnt = 0
    return dict_to_json({"code": 0, "msg": "success", "data": {"cnt": cnt}})


############################################################
# 9. 结束充电
# 参数:{
#     "uid":"username"
# }
# 返回值:{
#     "code":0,
#     "msg":"success",
#     "data":{}
# }
############################################################
@app.route('/UserEndCharge', methods=['POST'])
def user_end_charge():
    user_contr.refresh(*schedule_contr.refresh_system())

    requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    uid = requestData['uid']
    # <<< 参数

    if uid not in user_contr.uid_to_waitid:
        if uid not in user_contr.uid_to_csid:
            return dict_to_json({"code": 1, "msg": "user has no wait", "data": {}})
        else:
            return dict_to_json({"code": 2, "msg": f"user's wait already end", "data": {}})

    waitid = user_contr.uid_to_waitid[uid]
    wait = schedule_contr.wait_infos[waitid]
    if wait.state != 'ing':
        return dict_to_json({"code": 3, "msg": f"wait.state==<{wait.state}>, can't end", "data": {}})
    # schedule_controller 处理数据
    schedule_contr.user_end_charge(waitid)
    # user_controller 处理数据
    stmt = schedule_contr.wait_to_stmt(wait)
    cost = stmt.cost_charge + stmt.cost_serve  # 收费
    user_contr.users[uid].balance -= cost
    user_contr.user_end_charge(uid)
    return dict_to_json({"code": 0, "msg": "success", "data": {}})


############################################################
# 10. 余额充值
# 参数: {
#     "uid":"username",
#     "money":1000  # 充值额度
# }
# 返回值: {
#     "code":0,
#     "msg":"success",
#     "data":{
#         "money":3000.0  # 当前余额
#     }
# }
############################################################
@app.route('/UserAddBalance', methods=['POST'])
def user_add_balance():
    user_contr.refresh(*schedule_contr.refresh_system())

    requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    uid = requestData['uid']
    money = requestData['money']
    # <<< 参数

    if uid not in user_contr.users:
        return dict_to_json({"code": 1, "msg": "user not exists", "data": {}})
    cur_money = user_contr.users[uid].add_balance(money)
    return dict_to_json({"code": 0, "msg": "success", "data": {"money": cur_money}})


############################################################
# 中止充电
# 合并了取消充电和结束差点
############################################################
@app.route('/UserEndChargePro', methods=['POST'])
def user_end_charge_pro():
    user_contr.refresh(*schedule_contr.refresh_system())

    requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    uid = requestData['uid']
    # <<< 参数
    if uid not in user_contr.uid_to_waitid:
        if uid not in user_contr.uid_to_csid:
            return dict_to_json({"code": 1, "msg": "user has no wait", "data": {}})
        else:
            return dict_to_json({"code": 2, "msg": "user's wait already end", "data": {}})

    waitid = user_contr.uid_to_waitid[uid]
    csid = schedule_contr.waitid_to_csid[waitid]
    wait = schedule_contr.wait_infos[waitid]

    if wait.state == 'ing':
        schedule_contr.user_end_charge(waitid)
        stmt = schedule_contr.wait_to_stmt(wait)
        cost = stmt.cost_charge + stmt.cost_serve
        user_contr.users[uid].balance -= cost
        user_contr.user_end_charge(uid)
        return dict_to_json({"code": 0, "msg": "success", "data": {}})

    schedule_contr.cancel_charge_request(waitid)
    user_contr.cancel_charge_request(uid, csid)
    return dict_to_json({"code": 0, "msg": "success", "data": {}})


################################################################################
# 管理员客户端功能
# 1. 开启充电桩
# 2. 关闭充电桩
# 3. 查看充电桩状态
# 4. 查看充电桩等候服务的车辆信息
# 5. 报表展示
################################################################################


############################################################
# 1. 开启充电桩
# 参数:{
#     "pileid":"T#1"
# }
# 返回值:{
#     "code":0,
#     "msg":"success",
#     "data":{}
# }
############################################################
@app.route('/AdminStartPile', methods=['POST'])
def admin_start_pile():
    """管理员开启充电桩 """
    user_contr.refresh(*schedule_contr.refresh_system())

    requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    pileid = requestData['pileid']
    # <<< 参数

    if pileid not in PILEID['F'] + PILEID['T']:
        return dict_to_json({"code": 1, "msg": "pileid is invalid", "data": {}})
    mode = pileid[0]
    if pileid in schedule_contr.queue[mode]:
        return dict_to_json({"code": 2, "msg": "pile already start", "data": {}})

    schedule_contr.start_charge_pile(pileid)
    return dict_to_json({"code": 0, "msg": "success", "data": {}})


############################################################
# 2. 关闭充电桩
# 参数:{
#     "pileid":"T#1"
# }
# 返回值:{
#     "code":0,
#     "msg":"success",
#     "data":{}
# }
############################################################
@app.route('/AdminStopPile', methods=['POST'])
def admin_stop_pile():
    """管理员关闭充电桩 """
    user_contr.refresh(*schedule_contr.refresh_system())

    requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    pileid = requestData['pileid']
    # <<< 参数

    if pileid not in PILEID['F'] + PILEID['T']:
        return dict_to_json({"code": 1, "msg": "pileid is invalid", "data": {}})
    mode = pileid[0]
    if pileid not in schedule_contr.queue[mode]:
        return dict_to_json({"code": 2, "msg": "pile already stop", "data": {}})

    stmt = schedule_contr.stop_charge_pile(pileid)
    if stmt is not None:
        user = user_contr.users[stmt.uid]
        cost = stmt.cost_charge + stmt.cost_serve
        user.balance -= cost
        user.save()
    return dict_to_json({"code": 0, "msg": "success", "data": {}})


############################################################
# 3. 查看充电桩的状态
# 参数: { }
# 返回值:{
#     "code":0,
#     "msg":"success",
#     "data":{
#         "time":"2022-06-17 22:18:48",
#         "info":[
#             {
#                 "pileid":"T#1",
#                 "charge_cnt":14,
#                 "charge_time":88237,
#                 "charge_capacity":5.102777777777778,
#                 "cost_charge":4.9802777777777765,
#                 "cost_serve":4.082222222222223,
#                 "state":"on"
#             },
#             {
#                 "pileid":"T#2",
#                 "charge_cnt":6,
#                 "charge_time":86429,
#                 "charge_capacity":0.08055555555555566,
#                 "cost_charge":0.7830555555555555,
#                 "cost_serve":0.06444444444444439,
#                 "state":"on"
#             },
#             {
#                 .....
#             }
#         ]
#     }
# }
############################################################
@app.route('/ShowPileInfo', methods=['POST'])
def show_pile_info():
    """查看充电桩状态"""
    user_contr.refresh(*schedule_contr.refresh_system())

    # requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    # <<< 参数

    piles = {}
    now = timestamp()
    for mode in ['T', 'F']:
        for pileid in PILEID[mode]:
            piles[pileid] = charge_pile(pileid)
            if pileid in schedule_contr.queue[mode]:
                piles[pileid].state = 'on'
            else:
                piles[pileid].state = 'off'
    for csid, stmt in schedule_contr.charge_stmts.items():
        if stmt.pileid in [None, 'None']:
            continue
        pile = piles[stmt.pileid]
        pile.charge_cnt += 1
        pile.charge_time += HMS_to_seconds(stmt.time_total)
        pile.charge_capacity += float(stmt.consume)
        pile.cost_charge += stmt.cost_charge
        pile.cost_serve += stmt.cost_serve
    # pile_states = {pileid: pile_obj.toDict() for pileid, pile_obj in piles.items()}
    pile_states = [pile_obj.toDict() for pileid, pile_obj in piles.items()]
    return dict_to_json({"code": 0, "msg": "success", "data": {"time": now, "info": pile_states}})


############################################################
# 4. 查看充电桩等候服务的车辆信息
# 参数: {}
# 返回值:{
#     "code":0,
#     "msg":"success",
#     "data":[
#         {
#             "pileid":"T#1",
#             "queue":[
#                 {
#                     "uid":"a1",
#                     "waitid":"T1",
#                     "capacity":200.0,
#                     "reserve":10.0,
#                     "wait_already":3.0,
#                     "wait_left":0
#                 },
#                 {
#                     ......
#                 }
#             ]
#         },
#         {
#              ......
#         },
#     ]
# }
############################################################
@app.route('/ShowQueueInfo', methods=['POST'])
def show_queue_info():
    """查看充电桩队列信息"""
    user_contr.refresh(*schedule_contr.refresh_system())

    # requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    # <<< 参数
    now = get_time()
    data_raw = defaultdict(list)
    occurance = set()
    for mode in ['T', 'F']:
        for pileid, queue in schedule_contr.queue[mode].items():
            wait_time_left_tmp = 0
            for seq, wait in enumerate(queue):
                # 计算每个wait需要打印的数据
                if seq == 0:
                    stmt = schedule_contr.wait_to_stmt(wait)
                    wait_already = timestamp_to_seconds(stmt.time_start) - timestamp_to_seconds(wait.request_time)
                else:
                    wait_already = now - timestamp_to_seconds(wait.request_time)
                wait_left = wait_time_left_tmp
                wait_time_left_tmp += (wait.reserve - wait.already) / CHG_SPEED[mode] * 3600
                data_raw[pileid].append(
                    {"uid": wait.uid, "waitid": wait.waitid, "capacity": wait.capacity, "reserve": wait.reserve,
                     "wait_already": wait_already, "wait_left": wait_left})
        wait_time_left_tmp = 0
        for seq, wait in enumerate(schedule_contr.queue_wait[mode]):
            wait_already = now - timestamp_to_seconds(wait.request_time)
            wait_left = wait_time_left_tmp
            wait_time_left_tmp += (wait.reserve - wait.already) / CHG_SPEED[mode] * 3600
            if wait in schedule_contr.victim:
                # victim 单独列出来
                data_raw[f"{wait.mode}#victim"].append(
                    {"uid": wait.uid, "waitid": wait.waitid, "capacity": wait.capacity, "reserve": wait.reserve,
                     "wait_already": wait_already, "wait_left": wait_left})
            else:
                data_raw[f"{mode}#wait"].append(
                    {"uid": wait.uid, "waitid": wait.waitid, "capacity": wait.capacity, "reserve": wait.reserve,
                     "wait_already": wait_already, "wait_left": wait_left})
        data = []
        for key, value in data_raw.items():
            item = {"pileid": key, "queue": value}
            data.append(item)
            occurance.add(key)
    for _, ls in PILEID.items():
        for pile in ls:
            if pile not in occurance:
                data.append({"pileid": pile, "queue": []})
                occurance.add(pile)
    if 'F#wait' not in occurance:
        data.append({"pileid": 'F#wait', "queue": []})
    if 'T#wait' not in occurance:
        data.append({"pileid": 'T#wait', "queue": []})
    if 'T#victim' not in occurance:
        data.append({"pileid": 'T#victim', "queue": []})
    if 'F#victim' not in occurance:
        data.append({"pileid": 'F#victim', "queue": []})
    return dict_to_json({"code": 0, "msg": "success", "data": data})


############################################################
# 管理员设置充电桩参数
############################################################

@app.route('/AdminSetPile', methods=['POST'])
def admin_set_pile():
    user_contr.refresh(*schedule_contr.refresh_system())

    requestData = json.loads(request.get_data().decode('utf-8'))

    global QUEUE_LEN, FAILOVER_MODE

    # 参数 >>>
    try:
        queue_len = requestData['queue_len']
    except KeyError:
        queue_len = QUEUE_LEN

    try:
        failover_mode = requestData['failover_mode']
    except KeyError:
        failover_mode = FAILOVER_MODE

    # <<< 参数

    if queue_len <= 0:
        return dict_to_json({"code": 1, "msg": "refuse to set queue_len <= 0",
                             "data": {}})

    if failover_mode not in ['priority', 'shuffle']:
        return dict_to_json({"code": 2, "msg": f"failover_mode <{failover_mode}> not in ('priority','shuffle')",
                             "data": {}})

    QUEUE_LEN = queue_len
    FAILOVER_MODE = failover_mode

    return dict_to_json({"code": 0, "msg": "success",
                         "data": {'F': list(schedule_contr.queue['F'].keys()),
                                  'T': list(schedule_contr.queue['T'].keys())}})


############################################################
# 管理员设置等待区长度
############################################################
@app.route('/AdminSetWait', methods=['POST'])
def admin_set_wait():
    user_contr.refresh(*schedule_contr.refresh_system())

    requestData = json.loads(request.get_data().decode('utf-8'))

    global WAIT_QUEUE_LEN

    # 参数 >>>
    try:
        wait_queue_len = requestData['wait_queue_len']
    except KeyError:
        wait_queue_len = WAIT_QUEUE_LEN
    # <<< 参数

    if wait_queue_len <= 0:
        return dict_to_json({"code": 1, "msg": "refust to set wait_queue_len <= 0",
                             "data": {}})

    WAIT_QUEUE_LEN = wait_queue_len

    return dict_to_json({"code": 0, "msg": "success",
                         "data": {'F': list(schedule_contr.queue['F'].keys()),
                                  'T': list(schedule_contr.queue['T'].keys())}})


if __name__ == '__main__':
    app.run(threaded=True, host='0.0.0.0', port=8000)
