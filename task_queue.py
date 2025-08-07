import threading
import time
from datetime import datetime
from app import SummaryTask, app, db, Recording
import logging
import json
import traceback


class SummaryTaskQueue:
    def __init__(self):
#        self.task_queue = queue.Queue()
        self.worker_thread = None
        self.is_running = False
#        self.current_task = None
        self.lock = threading.Lock()
        self.current_task_id = None  
        self.logger = logging.getLogger('SummaryTaskQueue')

    def start_worker(self):
        """启动工作线程"""
        with self.lock:
            if not self.is_running:
                self.is_running = True
                self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
                self.worker_thread.start()

    def stop_worker(self):
        """停止工作线程"""
        with self.lock:
            self.is_running = False

    def add_task(self, app_context, recording_id, start_time, custom_config=None):
        """添加任务到数据库队列"""
        with app_context:
            config_json = json.dumps(custom_config) if custom_config else None
            task = SummaryTask(
                recording_id=recording_id,
                custom_config=config_json,
                status='QUEUED'
            )
            db.session.add(task)
            db.session.commit()
            # 详细的任务添加日志  
            self.logger.info(f"[QUEUE] Added task {task.id} for recording {recording_id}")  
            self.logger.info(f"[QUEUE] Custom config: {custom_config}")  
            self.logger.info(f"[QUEUE] Current queue size: {self._get_queue_size()}")  
              
            self.start_worker()

    def _get_queue_size(self):
        """获取当前队列大小"""
        try:
            return SummaryTask.query.filter_by(status='QUEUED').count()
        except:
            return "unknown"

    def _worker_loop(self):
        """从数据库获取任务执行"""
        self.logger.info("[WORKER] Summary task worker started")  

        while self.is_running:
            try:
                with app.app_context():
                    # 获取最早的排队任务
                    task = SummaryTask.query.filter_by(status='QUEUED').order_by(SummaryTask.created_at).first()
                    if task:
                        self.logger.info(f"[WORKER] Processing task {task.id} for recording {task.recording_id}")  
                        self.logger.info(f"[WORKER] Task created at: {task.created_at}")  
                        self.logger.info(f"[WORKER] Queue wait time: {datetime.utcnow() - task.created_at}")  
            
                        self.current_task_id = task.id
                        task.status = 'PROCESSING'
                        task.started_at = datetime.utcnow()
                        db.session.commit()
                        self.logger.info(f"[WORKER] Task {task.id} status updated to PROCESSING")  
                          
                        # 执行任务前的状态检查  
                        recording = db.session.get(Recording, task.recording_id)  
                        if recording:  
                            self.logger.info(f"[WORKER] Recording {recording.id} current status: {recording.status}")  
                            self.logger.info(f"[WORKER] Transcription length: {len(recording.transcription) if recording.transcription else 0}")  
                        else:  
                            self.logger.error(f"[WORKER] Recording {task.recording_id} not found!")  
                   
                        # 执行任务  
                        start_exec_time = datetime.utcnow()  
                        self.logger.info(f"[WORKER] Starting task execution at {start_exec_time}")  
                          
                        try:  
                            self._execute_summary_task(task)  
                            exec_time = (datetime.utcnow() - start_exec_time).total_seconds()  
                            self.logger.info(f"[WORKER] Task {task.id} completed successfully in {exec_time}s")  
                              
                            task.status = 'COMPLETED'  
                            task.completed_at = datetime.utcnow()  
                            db.session.commit()  
                              
                        except Exception as exec_error:  
                            exec_time = (datetime.utcnow() - start_exec_time).total_seconds()  
                            self.logger.error(f"[WORKER] Task {task.id} failed after {exec_time}s: {str(exec_error)}")  
                            self.logger.error(f"[WORKER] Full traceback: {traceback.format_exc()}")  
                              
                            task.status = 'FAILED'  
                            task.completed_at = datetime.utcnow()  
                            task.error_message = str(exec_error)  
                            db.session.commit()  
                          
                        self.current_task_id = None  
                        self.logger.info(f"[WORKER] Finished processing task {task.id}")  
                       
                    else:
                        # 没有任务时的详细日志（可以设置为DEBUG级别）  
                        if hasattr(self, '_last_no_task_log'):  
                            if (datetime.utcnow() - self._last_no_task_log).total_seconds() > 60:  
                                self.logger.debug("[WORKER] No tasks in queue, waiting...")  
                                self._last_no_task_log = datetime.utcnow()  
                        else:  
                            self._last_no_task_log = datetime.utcnow()  
                        time.sleep(2)  # 没有任务时等待
            except Exception as e:
                self.logger.error(f"[WORKER] Worker loop error: {str(e)}")  
                self.logger.error(f"[WORKER] Worker traceback: {traceback.format_exc()}")  
                if self.current_task_id:
                    try:
                        with app.app_context():
                            task = SummaryTask.query.get(self.current_task_id)
                            if task:
                                task.status = 'FAILED'
                                task.completed_at = datetime.utcnow()
                                task.error_message = f"Worker error: {str(e)}"  
                                db.session.commit()
                                self.logger.info(f"[WORKER] Marked task {self.current_task_id} as failed due to worker error")  
                    except Exception as cleanup_error:  
                        self.logger.error(f"[WORKER] Failed to cleanup task {self.current_task_id}: {cleanup_error}")  
                    self.current_task_id = None
                time.sleep(5)

    def recover_interrupted_tasks(self):
        """恢复中断的任务"""
        from app import app, SummaryTask, db  
          
        with app.app_context():  
            # 将处理中的任务重置为排队状态  
            interrupted_tasks = SummaryTask.query.filter_by(status='PROCESSING').all()  
            for task in interrupted_tasks:  
                task.status = 'QUEUED'  
                task.started_at = None  
            db.session.commit()
            self.logger.info(f"[RECOVERY] Reset {len(interrupted_tasks)} interrupted tasks to QUEUED status")  
              

    def _execute_summary_task(self, task):
        """执行单个summary任务"""
        from app import generate_summary_task, app  
          
        self.logger.info(f"[EXEC] Executing summary task {task.id}")  
          
        # 直接调用原有的generate_summary_task函数  
        with app.app_context():  
            self.logger.info(f"[EXEC] Calling generate_summary_task for recording {task.recording_id}")  
            generate_summary_task(  
                app.app_context(),  
                task.recording_id,  
                task.created_at  # 使用任务创建时间作为start_time  
            )  
            self.logger.info(f"[EXEC] generate_summary_task completed for task {task.id}")  
  
# 全局队列实例
summary_queue = SummaryTaskQueue()
