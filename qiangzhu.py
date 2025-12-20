import whois
import datetime
import time
import requests 

# ================= 配置区 =================
# 🎯 目标已锁定
DOMAIN = "188388.xyz"  

# 🔔 通知地址 (钉钉/飞书/Bark)
# 如果没有，暂时留空，结果会保存在日志里
WEBHOOK_URL = "" 
# =========================================

def send_notify(title, content):
    """发送通知"""
    print(f"🔔 [通知] {title}: {content}")
    if WEBHOOK_URL:
        try:
            data = {"msgtype": "text", "text": {"content": f"{title}\n{content}"}}
            requests.post(WEBHOOK_URL, json=data)
        except Exception as e:
            print(f"通知发送失败: {e}")

def check():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"--- [{now}] 正在侦测: {DOMAIN} ---")
    
    try:
        # 针对 .xyz 这种后缀，有时候 timeout 设置长一点更稳
        w = whois.whois(DOMAIN)
        
        # 获取状态字符串
        status = ""
        if isinstance(w.status, list):
            status = " ".join(w.status).lower()
        elif w.status:
            status = w.status.lower()
            
        # 1. 核心判定：如果没有 domain_name 信息，或者状态显示为空
        # 注意：有些 .xyz 释放后 whois 会直接抛出异常，有些则是返回空
        if not w.domain_name:
            send_notify("!!! 机会来了 !!!", f"域名 {DOMAIN} 查询不到信息，可能已释放！立即注册！")
            return

        # 2. 状态监测
        if "pendingdelete" in status:
            send_notify("⚠️ 高能预警", f"{DOMAIN} 处于 Pending Delete (待删除) 状态！5天内释放！")
        
        elif "redemptionperiod" in status:
            print(f"当前状态: 🔒 赎回期 (RedemptionPeriod) - 还没到时候")
        
        elif "clienthold" in status or "serverhold" in status:
            print(f"当前状态: ⏸️ 停止解析 (Hold) - 可能是过期宽限期")
            
        elif "ok" in status or "active" in status:
            print(f"当前状态: ✅ 正常注册中 (Active) - 尚未过期或已续费")
            
        else:
            # 打印出来看看具体是什么奇怪的状态
            print(f"当前状态: {status[:60]}")

    except Exception as e:
        err_msg = str(e).lower()
        # 处理 .xyz 常见的 "No match" 或 "Not found"
        if "no match" in err_msg or "not found" in err_msg:
             send_notify("!!! 机会来了 !!!", f"捕获到无记录异常，{DOMAIN} 应该已释放！")
        else:
            print(f"查询出错: {e}")

if __name__ == "__main__":
    check()
