import json
import sqlite3
import time
from dataStructure import *

from flask import Flask, request

schedule_contr = scheduler()
user_contr = user_controller()

app = Flask(__name__)


def dict_to_json(dd: dict):
    return json.dumps(dd, ensure_ascii=False)


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
# 参数:{"uID":xxx, "passwd":xxx}
# 返回值: {"code":xxx, "msg":xxx,"data":{xxx}}
############################################################
@app.route('/UserRegister/', methods=['POST'])
def user_register():
    schedule_contr.refresh_system()

    requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    uid = requestData['uid']
    passwd = requestData['passwd']
    capacity = float(requestData['capacity'])
    # <<< 参数

    code = user_contr.user_register(uid, passwd, capacity)
    if code == 1:
        msg = 'uid already exists'
    else:
        msg = 'success'
    return dict_to_json({"code": code, "msg": msg, "data": {}})


############################################################
# 2. 登陆
# 参数:{"uID":xxx, "passwd":xxx}
# 返回值: {"code":xxx, "msg":xxx,"data":{xxx}}
############################################################
@app.route('/UserLogin', methods=['POST'])
def user_login():
    schedule_contr.refresh_system()

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
# 参数: {"uID":xxx, "mode":xxx, #  "reserve":xxx}
# 返回值: {"code":xxx, "msg":xxx,"data":{"waitid":xxx}}

# 实现细节:
# 生成一个"请求",放到排队队列里;
# 生成一个"详单",包含这次请求的状态('等待中','正在充电','已结束')
############################################################
@app.route('/UserNewCharge', methods=['POST'])
def user_new_charge():
    schedule_contr.refresh_system()
    requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    uid = requestData['uid']
    mode = requestData['mode']
    reserve = float(requestData['reserve'])
    # <<< 参数

    user = user_contr.get_user(uid)
    if uid in user_contr.uid_to_waitid:
        code = 1
        msg = f'user {uid} has already reserved a charge'
        waitid = None
    else:
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
############################################################
@app.route('/UserModifyCharge', methods=['POST'])
def user_modify_charge():
    requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    uid = requestData['uid']
    mode = requestData['mode']
    reserve = float(requestData['reserve'])
    # <<< 参数

    schedule_contr.refresh_system()

    if uid not in user_contr.uid_to_waitid:
        code = 1
        msg = f"user {uid} has no charge request to modify"
        waitid = None
    else:
        # user_controller 处理数据
        waitid = user_contr.uid_to_waitid[uid]
        # schedule_controller 处理数据
        waitid = schedule_contr.modify_charge_request(waitid, mode, reserve)
        code = 0
        msg = f"success"
    return dict_to_json({"code": code, "msg": msg, "data": {"waitid": waitid}})


############################################################
# 5. 查看充电详单
############################################################
@app.route('/UserCheckCharge', methods=['POST'])
def user_check_charge():
    schedule_contr.refresh_system()

    requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    uid = requestData['uid']
    # <<< 参数

    if uid not in user_contr.uid_to_csid:
        data = {"stmts": []}
    else:
        csid_list = user_contr.get_user_all_csid(uid)
        stmt_list = [schedule_contr.charge_stmts[csid] for csid in csid_list]
        data = {"stmts": [stmt.toDict() for stmt in stmt_list]}
    return dict_to_json({"code": 0, "msg": "success", "data": data})


############################################################
# 6. 取消充电
############################################################
@app.route('/UserCancelCharge', methods=['POST'])
def user_cancel_charge():
    schedule_contr.refresh_system()

    requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    uid = requestData['uid']
    # <<< 参数
    if uid not in user_contr.uid_to_waitid:
        code = 1
        msg = "user has no charge to cancel"
    else:
        waitid = user_contr.uid_to_waitid[uid]
        csid = schedule_contr.waitid_to_csid[waitid]
        # schedule_controller 处理数据
        code = schedule_contr.cancel_charge_request(waitid)
        if code != 0:
            if code == 1:
                msg = "this wait is charging now, can't cancel"
            elif code == 2:
                msg = "this wait is end now, can't cancel"
            else:
                msg = "unknown error"
            return dict_to_json({"code": code, "msg": msg, "data": {}})

        # user_controller 处理数据
        user_contr.cancel_charge_request(uid, csid)
        msg = "success"
    return dict_to_json({"code": code, "msg": msg, "data": {}})


############################################################
# 7. 查看本车排队号码
############################################################
@app.route('/UserShowWaitid', methods=['POST'])
def user_show_waitid():
    schedule_contr.refresh_system()

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
############################################################
@app.route('/UserShowPreWaitCnt', methods=['POST'])
def user_show_pre_wait_cnt():
    schedule_contr.refresh_system()

    requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    uid = requestData['uid']
    # <<< 参数

    if uid not in user_contr.uid_to_waitid:
        return dict_to_json({"code": 1, "msg": "user has no wait", "data": {}})

    waitid = user_contr.uid_to_waitid[uid]
    wait = schedule_contr.wait_infos[waitid]
    mode = wait.mode
    if wait.state == 'p':
        len_wait = schedule_contr.queue_wait[mode].index(wait)
        cnt = len_wait + WAIT_QUEUE_LEN
    elif wait.state == 'wait':
        pileid = wait.pileid
        cnt = schedule_contr.queue[mode][pileid].index(wait)
    else:
        cnt = 0
    return dict_to_json({"code": 0, "msg": "success", "data": {"cnt": cnt}})


############################################################
# 9. 结束充电
############################################################
@app.route('/UserEndCharge', methods=['POST'])
def user_end_charge():
    schedule_contr.refresh_system()

    requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    uid = requestData['uid']
    # <<< 参数

    if uid not in user_contr.uid_to_waitid:
        return dict_to_json({"code": 1, "msg": "user has no wait", "data": {}})
    waitid = user_contr.uid_to_waitid[uid]
    wait = schedule_contr.wait_infos[waitid]
    # schedule_controller 处理数据
    schedule_contr.user_end_charge(waitid)
    # user_controller 处理数据
    user_contr.user_end_charge(uid)
    return dict_to_json({"code": 0, "msg": "success", "data": {}})


############################################################
# 10. 余额充值
############################################################
@app.route('/UserAddBalance', methods=['POST'])
def user_add_balance():
    schedule_contr.refresh_system()

    requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    uid = requestData['uid']
    money = requestData['money']
    # <<< 参数

    if uid not in user_contr.users:
        return dict_to_json({"code": 1, "msg": "user not exists", "data": {}})
    user_contr.users[uid].add_balance(money)
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
############################################################
@app.route('/AdminStartPile', methods=['POST'])
def admin_start_pile():
    """管理员开启充电桩 """
    schedule_contr.refresh_system()

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
############################################################
@app.route('/AdminStopPile', methods=['POST'])
def admin_stop_pile():
    """管理员关闭充电桩 """
    schedule_contr.refresh_system()

    requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    pileid = requestData['pileid']
    # <<< 参数

    if pileid not in PILEID['F'] + PILEID['T']:
        return dict_to_json({"code": 1, "msg": "pileid is invalid", "data": {}})
    mode = pileid[0]
    if pileid not in schedule_contr.queue[mode]:
        return dict_to_json({"code": 2, "msg": "pile already stop", "data": {}})

    schedule_contr.stop_charge_pile(pileid)
    return dict_to_json({"code": 0, "msg": "success", "data": {}})


############################################################
# 3. 查看充电桩的状态
############################################################
@app.route('/ShowPileInfo', methods=['POST'])
def show_pile_info():
    """查看充电桩状态"""
    schedule_contr.refresh_system()

    requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    # <<< 参数

    piles = {}
    for mode in ['T', 'F']:
        for pileid in PILEID[mode]:
            piles[pileid] = charge_pile(pileid)
            if pileid in schedule_contr.queue[mode]:
                piles[pileid].state = 'on'
            else:
                piles[pileid].state = 'off'
    for csid, stmt in schedule_contr.charge_stmts.items():
        pile = piles[stmt.pileid]
        pile.charge_cnt += 1
        pile.charge_time += HMS_to_seconds(stmt.time_total)
        pile.charge_capacity += stmt.consume
        pile.cost_charge += stmt.cost_charge
        pile.cost_serve += stmt.cost_serve
    data = {pileid: pile_obj.toDict() for pileid, pile_obj in piles.items()}
    return dict_to_json({"code": 0, "msg": "success", "data": data})


############################################################
# 4. 查看充电桩等候服务的车辆信息
# 参数: 无
# 返回值: {"code":0, "msg":success","data":data}
#      data 是 '充电桩号 pileid' => '桩前队列 queueInfo' 的字典
#  举例:
#   data = {'T#1':[{"uid":"hyn",
#                   "capacity":200,
#                   "reserve":20,
#                   "wait_time_left":600
#                   "wait_time_already":2000},
#                   {"uid":"dxw",...},
#                   ...],
#           'T#2':[...],
#           ......
#           }
############################################################
@app.route('/ShowQueueInfo', methods=['POST'])
def show_queue_info():
    """查看充电桩队列信息"""
    schedule_contr.refresh_system()

    requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    # <<< 参数


############################################################
# 系统报表生成
# 参数: 无
# 返回值: {"code":0,"msg":"success","data":data"}
#     data 的格式{"timestamp":"xxxx-xx-xx xx:xx:xx","pileinfo":xxx (show_pile_info 中的data)}
############################################################
@app.route('/ShowReport', methods=['POST'])
def show_report():
    """查看系统报表"""
    schedule_contr.refresh_system()

    requestData = json.loads(request.get_data().decode('utf-8'))

    # 参数 >>>
    # <<< 参数


if __name__ == '__main__':
    app.run(threaded=True, host='0.0.0.0', port=8000)
