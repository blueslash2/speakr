import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, Recording, SummaryTask
from task_queue import summary_queue
import threading
from datetime import datetime

def test_add_task_updates_recording_status():
    """测试add_task方法是否正确更新录音状态"""
    
    # 创建测试应用上下文
    with app.app_context():
        # 清理测试数据
        test_recording = Recording.query.filter_by(title='Test Recording').first()
        if test_recording:
            db.session.delete(test_recording)
            db.session.commit()
        
        # 创建测试录音
        test_recording = Recording(
            title='Test Recording',
            status='PENDING',
            user_id=1  # 假设用户ID为1
        )
        db.session.add(test_recording)
        db.session.commit()
        
        print(f"初始录音状态: {test_recording.status}")
        
        # 添加任务
        summary_queue.add_task(app.app_context(), test_recording.id, datetime.utcnow())
        
        # 刷新录音状态
        db.session.refresh(test_recording)
        print(f"添加任务后录音状态: {test_recording.status}")
        
        # 验证状态是否已更新为'QUEUED'
        if test_recording.status == 'QUEUED':
            print("✓ 测试通过：录音状态已正确更新为'QUEUED'")
            return True
        else:
            print("✗ 测试失败：录音状态未正确更新")
            return False

if __name__ == '__main__':
    test_add_task_updates_recording_status()