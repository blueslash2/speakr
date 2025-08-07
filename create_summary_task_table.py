#!/usr/bin/env python3  
"""  
创建SummaryTask表的脚本  
用于支持summary任务的持久化队列机制  
"""  
  
import os  
import sys  
from datetime import datetime  
  
# 确保能导入app模块  
try:  
    from app import app, db  
except ImportError as e:  
    print(f"错误：无法导入app模块: {e}")  
    print("请确保在正确的目录下运行此脚本")  
    sys.exit(1)  
  
# 导入SQLAlchemy类型  
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey  
  
class SummaryTask(db.Model):  
    """Summary任务队列表"""  
    __tablename__ = 'summary_tasks'  
      
    id = Column(Integer, primary_key=True)  
    recording_id = Column(Integer, ForeignKey('recording.id'), nullable=False)  
    status = Column(String(20), default='QUEUED')  # QUEUED, PROCESSING, COMPLETED, FAILED  
    custom_config = Column(Text)  # JSON字符串存储自定义配置  
    created_at = Column(DateTime, default=datetime.utcnow)  
    started_at = Column(DateTime)  
    completed_at = Column(DateTime)  
    error_message = Column(Text)  # 错误信息  
      
    def to_dict(self):  
        return {  
            'id': self.id,  
            'recording_id': self.recording_id,  
            'status': self.status,  
            'custom_config': self.custom_config,  
            'created_at': self.created_at,  
            'started_at': self.started_at,  
            'completed_at': self.completed_at,  
            'error_message': self.error_message  
        }  
  
def create_summary_task_table():  
    """创建SummaryTask表"""  
    try:  
        with app.app_context():  
            print("正在创建SummaryTask表...")  
              
            # 检查表是否已存在  
            from sqlalchemy import inspect  
            inspector = inspect(db.engine)  
            existing_tables = inspector.get_table_names()  
              
            if 'summary_tasks' in existing_tables:  
                print("SummaryTask表已存在，跳过创建")  
                return True  
              
            # 创建表  
            SummaryTask.__table__.create(db.engine)  
            print("SummaryTask表创建成功！")  
              
            # 验证表创建  
            inspector = inspect(db.engine)  
            if 'summary_tasks' in inspector.get_table_names():  
                print("验证：SummaryTask表已成功添加到数据库")  
                  
                # 显示表结构  
                columns = inspector.get_columns('summary_tasks')  
                print("\n表结构：")  
                for col in columns:  
                    print(f"  - {col['name']}: {col['type']}")  
                  
                return True  
            else:  
                print("错误：表创建失败")  
                return False  
                  
    except Exception as e:  
        print(f"创建表时发生错误: {e}")  
        return False  
  
def add_column_if_not_exists(table_name, column_name, column_type):  
    """如果列不存在则添加列（兼容现有的迁移机制）"""  
    from sqlalchemy import text  
      
    try:  
        with app.app_context():  
            with db.engine.connect() as conn:  
                # 检查列是否存在  
                result = conn.execute(text(f"PRAGMA table_info({table_name})"))  
                columns = [row[1] for row in result]  
                  
                if column_name not in columns:  
                    print(f"添加列 {column_name} 到 {table_name}")  
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))  
                    conn.commit()  
                    return True  
                return False  
    except Exception as e:  
        print(f"添加列时发生错误: {e}")  
        return False  
  
if __name__ == "__main__":  
    print("开始创建SummaryTask表...")  
    print(f"数据库路径: {app.config.get('SQLALCHEMY_DATABASE_URI')}")  
      
    # 确保数据库目录存在  
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')  
    if db_uri.startswith('sqlite:///'):  
        db_path = db_uri.replace('sqlite:///', '/', 1)  
        db_dir = os.path.dirname(db_path)  
        os.makedirs(db_dir, exist_ok=True)  
        print(f"确保数据库目录存在: {db_dir}")  
      
    success = create_summary_task_table()  
      
    if success:  
        print("\n✅ SummaryTask表创建完成！")  
        print("\n接下来您可以：")  
        print("1. 将SummaryTask模型添加到app.py中")  
        print("2. 实现task_queue.py中的队列管理逻辑")  
        print("3. 修改现有的summary调用代码")  
    else:  
        print("\n❌ 表创建失败，请检查错误信息")  
        sys.exit(1)
