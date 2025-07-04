import sys
import time
import random

def countdown(min_seconds,max_seconds,msg='等待下一次',new_line=True):
        """倒计时显示函数"""
        if new_line:print()
        # 将浮点数转换为整数
        seconds_int = random.randint(min_seconds,max_seconds)
        for i in range(seconds_int, 0, -1):
            sys.stdout.write(f'\r{msg}，还剩 {i} 秒...   ')
            sys.stdout.flush()
            time.sleep(1)
        sys.stdout.write('\r' + ' ' * 50 + '\r')  # 清除倒计时显示
        sys.stdout.flush()  
        # if new_line:print()