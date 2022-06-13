import json
import sqlite3
import time

from flask import Flask, request

app = Flask(__name__)


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
# 返回值: {"msg":xxx}
############################################################
@app.route('/UserRegister/', methods=['POST'])
def userRegister():
    requestData = json.loads(request.get_data().decode('utf-8'))
    uID = requestData['uID']
    passwd = requestData['passwd']
    conn = sqlite3.connect('res.db')
    print(f'user:{uID}, passwd:{passwd}')
    c = conn.cursor()
    c.execute("""
        select uID from user;
    """)
    result = c.fetchall()
    uIDs = [x[0] for x in result]
    if uID not in uIDs:
        c.execute(f"""
            insert into user (uID, passwd) values
            ('{uID}','{passwd}');
        """)
        msg = "success"
    else:
        msg = "uID already exists"
    conn.commit()
    conn.close()
    return json.dumps({"msg": msg})


############################################################
# 2. 登陆
# 参数:{"uID":xxx, "passwd":xxx}
# 返回值: {"msg":xxx}
############################################################
@app.route('/UserLogin', methods=['POST'])
def userLogin():
    requestData = json.loads(request.get_data().decode('utf-8'))
    username = requestData['uID']
    passwd = requestData['passwd']
    conn = sqlite3.connect('res.db')
    c = conn.cursor()
    c.execute("""
        select uID,passwd from user
    """)
    result = c.fetchall()
    if (username, passwd) in result:
        msg = "success"
    elif username in [x[0] for x in result]:
        msg = "wrong passwd"
    else:
        msg = "username not exists"
    conn.commit()
    conn.close()
    return json.dumps({"msg": msg})


############################################################
# 3. 提交充电请求
# 参数: {"uID":xxx,"mode":xxx, #  "reserve":xxx}
# 返回值:{"msg":xxx}
# 实现方法:
# 生成一个"请求",放到排队队列里;
# 生成一个"详单",包含这次请求的状态('等待中','正在充电','已结束')
# 将"请求"放到排队队列中
############################################################
@app.route('/UserNewCharge')
def userNewCharge():
    requestData = json.loads(request.get_data().decode('utf-8'))
    uID = requestData['uID']
    mode = requestData['mode']
    reserve = requestData['reserve']


################################################################################
# 管理员客户端功能
# 1. 开启充电桩
# 2. 关闭充电桩
# 3. 查看充电桩状态
# 4. 查看充电桩等候服务的车辆信息
# 5. 报表展示
################################################################################

if __name__ == '__main__':
    app.run(threaded=True)
