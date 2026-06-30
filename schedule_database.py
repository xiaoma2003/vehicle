"""
车辆调度AI算法评测系统 - SQLite数据库持久化模块
包含7张表：map_configs, task_configs, locomotive_configs, hyper_params,
scheduler_runs, task_assignments, system_logs
"""
import sqlite3
import json
import os
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple


class ScheduleDatabase:
    def __init__(self, db_path: str = "data/schedule_history.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_database()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_database(self):
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS map_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL,
                config_name TEXT,
                nodes_json TEXT NOT NULL,
                edges_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                task_name TEXT,
                task_type TEXT NOT NULL,
                priority INTEGER NOT NULL,
                status TEXT NOT NULL,
                start_node TEXT NOT NULL,
                end_node TEXT NOT NULL,
                material_weight REAL NOT NULL,
                depends_on TEXT,
                extra_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS locomotive_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL,
                locomotive_id TEXT NOT NULL,
                traction_type TEXT NOT NULL,
                max_speed REAL NOT NULL,
                capacity REAL NOT NULL,
                initial_node TEXT NOT NULL,
                battery REAL,
                fuel_tank REAL,
                is_powered_on INTEGER DEFAULT 1,
                is_schedulable INTEGER DEFAULT 1,
                current_task TEXT,
                task_phase TEXT,
                extra_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hyper_params (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL,
                params_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduler_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL,
                strategy_name TEXT NOT NULL,
                strategy_display_name TEXT,
                solve_status TEXT NOT NULL,
                makespan INTEGER,
                solve_time REAL,
                num_tasks INTEGER,
                num_locomotives INTEGER,
                result_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL,
                run_id INTEGER,
                task_id TEXT NOT NULL,
                locomotive_id TEXT NOT NULL,
                strategy_name TEXT NOT NULL,
                start_time INTEGER,
                loading_end INTEGER,
                transport_end INTEGER,
                unloading_end INTEGER,
                path_json TEXT,
                priority INTEGER,
                task_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES scheduler_runs(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT,
                log_level TEXT NOT NULL,
                log_type TEXT NOT NULL,
                message TEXT NOT NULL,
                details_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_batch_map ON map_configs(batch_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_batch_task ON task_configs(batch_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_batch_loco ON locomotive_configs(batch_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_batch_run ON scheduler_runs(batch_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_batch_assignment ON task_assignments(batch_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_run_assignment ON task_assignments(run_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_time ON system_logs(created_at)")

        conn.commit()
        conn.close()

    def save_config_batch(self, batch_id: str, map_config: Dict, tasks_config: Dict,
                          locomotives_config: Dict, hyper_params: Dict) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            cursor.execute(
                "INSERT INTO map_configs (batch_id, config_name, nodes_json, edges_json) VALUES (?, ?, ?, ?)",
                (batch_id, map_config.get("name", "default"),
                 json.dumps(map_config["nodes"], ensure_ascii=False),
                 json.dumps(map_config["edges"], ensure_ascii=False))
            )

            for task in tasks_config["tasks"]:
                cursor.execute("""
                    INSERT INTO task_configs
                    (batch_id, task_id, task_name, task_type, priority, status,
                     start_node, end_node, material_weight, depends_on, extra_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    batch_id, task["id"], task.get("name", task["id"]),
                    task["task_type"], task["priority"], task["status"],
                    task["start_node"], task["end_node"], task["material_weight"],
                    json.dumps(task.get("depends_on", []), ensure_ascii=False),
                    json.dumps({k: v for k, v in task.items()
                               if k not in ["id", "name", "task_type", "priority",
                                           "status", "start_node", "end_node",
                                           "material_weight", "depends_on"]},
                              ensure_ascii=False)
                ))

            for loco in locomotives_config["locomotives"]:
                cursor.execute("""
                    INSERT INTO locomotive_configs
                    (batch_id, locomotive_id, traction_type, max_speed, capacity,
                     initial_node, battery, fuel_tank, is_powered_on, is_schedulable,
                     current_task, task_phase, extra_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    batch_id, loco["id"], loco["traction_type"], loco["max_speed"],
                    loco["Q"], loco["initial_node"],
                    loco.get("battery"), loco.get("fuel_tank"),
                    1 if loco.get("is_powered_on", True) else 0,
                    1 if loco.get("is_schedulable", True) else 0,
                    loco.get("current_task"), loco.get("task_phase"),
                    json.dumps({k: v for k, v in loco.items()
                               if k not in ["id", "traction_type", "max_speed", "Q",
                                           "initial_node", "battery", "fuel_tank",
                                           "is_powered_on", "is_schedulable",
                                           "current_task", "task_phase"]},
                              ensure_ascii=False)
                ))

            cursor.execute(
                "INSERT INTO hyper_params (batch_id, params_json) VALUES (?, ?)",
                (batch_id, json.dumps(hyper_params, ensure_ascii=False))
            )

            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            self._add_log(batch_id, "ERROR", "database", f"保存配置失败: {str(e)}", conn=conn)
            return False
        finally:
            conn.close()

    def save_scheduler_run(self, batch_id: str, strategy_name: str,
                            strategy_display_name: str, result: Dict) -> Optional[int]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO scheduler_runs
                (batch_id, strategy_name, strategy_display_name, solve_status,
                 makespan, solve_time, num_tasks, num_locomotives, result_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                batch_id, strategy_name, strategy_display_name,
                result["solve_status"], result.get("makespan"),
                result.get("solve_time", 0), result.get("num_tasks", 0),
                result.get("num_locomotives", 0),
                json.dumps(result, ensure_ascii=False)
            ))
            run_id = cursor.lastrowid

            for assignment in result.get("assignments", []):
                cursor.execute("""
                    INSERT INTO task_assignments
                    (batch_id, run_id, task_id, locomotive_id, strategy_name,
                     start_time, loading_end, transport_end, unloading_end,
                     path_json, priority, task_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    batch_id, run_id, assignment["task_id"], assignment["locomotive_id"],
                    strategy_name, assignment.get("start_time"),
                    assignment.get("loading_end"), assignment.get("transport_end"),
                    assignment.get("unloading_end"),
                    json.dumps(assignment.get("path", []), ensure_ascii=False),
                    assignment.get("priority"), assignment.get("task_type", "normal")
                ))

            conn.commit()
            return run_id
        except Exception as e:
            conn.rollback()
            self._add_log(batch_id, "ERROR", "database", f"保存调度结果失败: {str(e)}", conn=conn)
            return None
        finally:
            conn.close()

    def _add_log(self, batch_id: Optional[str], log_level: str, log_type: str,
                 message: str, details: Optional[Dict] = None, conn=None):
        if conn is None:
            conn = self._get_conn()
            close_conn = True
        else:
            close_conn = False

        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO system_logs (batch_id, log_level, log_type, message, details_json)
                VALUES (?, ?, ?, ?, ?)
            """, (batch_id, log_level, log_type, message,
                  json.dumps(details, ensure_ascii=False) if details else None))
            conn.commit()
        finally:
            if close_conn:
                conn.close()

    def add_log(self, batch_id: Optional[str], log_level: str, log_type: str,
                message: str, details: Optional[Dict] = None):
        self._add_log(batch_id, log_level, log_type, message, details)

    def query_runs(self, batch_id: Optional[str] = None,
                    strategy_name: Optional[str] = None,
                    solve_status: Optional[str] = None,
                    page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            conditions = []
            params = []

            if batch_id:
                conditions.append("batch_id = ?")
                params.append(batch_id)
            if strategy_name:
                conditions.append("strategy_name = ?")
                params.append(strategy_name)
            if solve_status:
                conditions.append("solve_status = ?")
                params.append(solve_status)

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            cursor.execute(f"SELECT COUNT(*) as cnt FROM scheduler_runs WHERE {where_clause}", params)
            total = cursor.fetchone()["cnt"]

            offset = (page - 1) * page_size
            cursor.execute(f"""
                SELECT * FROM scheduler_runs
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, params + [page_size, offset])

            runs = [dict(row) for row in cursor.fetchall()]
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size,
                "data": runs
            }
        finally:
            conn.close()

    def get_run_detail(self, run_id: int) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scheduler_runs WHERE id = ?", (run_id,))
            run = cursor.fetchone()
            if not run:
                return None

            run_dict = dict(run)

            cursor.execute("""
                SELECT * FROM task_assignments
                WHERE run_id = ?
                ORDER BY start_time
            """, (run_id,))
            assignments = [dict(row) for row in cursor.fetchall()]
            run_dict["assignments"] = assignments

            if run_dict.get("result_json"):
                run_dict["result"] = json.loads(run_dict["result_json"])

            return run_dict
        finally:
            conn.close()

    def get_batch_history(self, batch_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM map_configs WHERE batch_id = ? ORDER BY id DESC LIMIT 1", (batch_id,))
            map_row = cursor.fetchone()
            if not map_row:
                return None

            map_config = {
                "nodes": json.loads(map_row["nodes_json"]),
                "edges": json.loads(map_row["edges_json"])
            }

            cursor.execute("SELECT * FROM task_configs WHERE batch_id = ?", (batch_id,))
            tasks = [dict(row) for row in cursor.fetchall()]

            cursor.execute("SELECT * FROM locomotive_configs WHERE batch_id = ?", (batch_id,))
            locomotives = [dict(row) for row in cursor.fetchall()]

            cursor.execute("SELECT * FROM hyper_params WHERE batch_id = ? ORDER BY id DESC LIMIT 1", (batch_id,))
            hp_row = cursor.fetchone()
            hyper_params = json.loads(hp_row["params_json"]) if hp_row else {}

            cursor.execute("""
                SELECT * FROM scheduler_runs
                WHERE batch_id = ?
                ORDER BY created_at
            """, (batch_id,))
            runs = [dict(row) for row in cursor.fetchall()]

            return {
                "batch_id": batch_id,
                "map_config": map_config,
                "tasks": tasks,
                "locomotives": locomotives,
                "hyper_params": hyper_params,
                "runs": runs
            }
        finally:
            conn.close()

    def query_tasks(self, batch_id: Optional[str] = None,
                     task_type: Optional[str] = None,
                     status: Optional[str] = None,
                     page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            conditions = []
            params = []

            if batch_id:
                conditions.append("batch_id = ?")
                params.append(batch_id)
            if task_type:
                conditions.append("task_type = ?")
                params.append(task_type)
            if status:
                conditions.append("status = ?")
                params.append(status)

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            cursor.execute(f"SELECT COUNT(*) as cnt FROM task_configs WHERE {where_clause}", params)
            total = cursor.fetchone()["cnt"]

            offset = (page - 1) * page_size
            cursor.execute(f"""
                SELECT * FROM task_configs
                WHERE {where_clause}
                ORDER BY priority, id
                LIMIT ? OFFSET ?
            """, params + [page_size, offset])

            tasks = [dict(row) for row in cursor.fetchall()]
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size,
                "data": tasks
            }
        finally:
            conn.close()

    def query_locomotives(self, batch_id: Optional[str] = None,
                           traction_type: Optional[str] = None,
                           page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            conditions = []
            params = []

            if batch_id:
                conditions.append("batch_id = ?")
                params.append(batch_id)
            if traction_type:
                conditions.append("traction_type = ?")
                params.append(traction_type)

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            cursor.execute(f"SELECT COUNT(*) as cnt FROM locomotive_configs WHERE {where_clause}", params)
            total = cursor.fetchone()["cnt"]

            offset = (page - 1) * page_size
            cursor.execute(f"""
                SELECT * FROM locomotive_configs
                WHERE {where_clause}
                ORDER BY locomotive_id
                LIMIT ? OFFSET ?
            """, params + [page_size, offset])

            locomotives = [dict(row) for row in cursor.fetchall()]
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size,
                "data": locomotives
            }
        finally:
            conn.close()

    def query_logs(self, batch_id: Optional[str] = None,
                   log_level: Optional[str] = None,
                   log_type: Optional[str] = None,
                   page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            conditions = []
            params = []

            if batch_id:
                conditions.append("batch_id = ?")
                params.append(batch_id)
            if log_level:
                conditions.append("log_level = ?")
                params.append(log_level)
            if log_type:
                conditions.append("log_type = ?")
                params.append(log_type)

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            cursor.execute(f"SELECT COUNT(*) as cnt FROM system_logs WHERE {where_clause}", params)
            total = cursor.fetchone()["cnt"]

            offset = (page - 1) * page_size
            cursor.execute(f"""
                SELECT * FROM system_logs
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, params + [page_size, offset])

            logs = [dict(row) for row in cursor.fetchall()]
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size,
                "data": logs
            }
        finally:
            conn.close()

    def get_statistics(self) -> Dict[str, Any]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) as cnt FROM scheduler_runs")
            total_runs = cursor.fetchone()["cnt"]

            cursor.execute("SELECT COUNT(DISTINCT batch_id) as cnt FROM scheduler_runs")
            total_batches = cursor.fetchone()["cnt"]

            cursor.execute("""
                SELECT strategy_name, COUNT(*) as cnt,
                       AVG(makespan) as avg_makespan,
                       AVG(solve_time) as avg_time
                FROM scheduler_runs
                WHERE solve_status = 'optimal'
                GROUP BY strategy_name
            """)
            strategy_stats = [dict(row) for row in cursor.fetchall()]

            cursor.execute("SELECT MIN(makespan) as best FROM scheduler_runs WHERE makespan > 0")
            best_makespan = cursor.fetchone()["best"]

            return {
                "total_runs": total_runs,
                "total_batches": total_batches,
                "best_makespan": best_makespan,
                "strategy_stats": strategy_stats
            }
        finally:
            conn.close()

    def delete_log(self, log_id: int) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM system_logs WHERE id = ?", (log_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_logs_batch(self, log_ids: List[int]) -> int:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            placeholders = ','.join('?' * len(log_ids))
            cursor.execute(f"DELETE FROM system_logs WHERE id IN ({placeholders})", log_ids)
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def clear_all_logs(self) -> int:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM system_logs")
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def get_all_batch_ids(self, limit: int = 100) -> List[str]:
        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT batch_id FROM scheduler_runs
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            return [row["batch_id"] for row in cursor.fetchall()]
        finally:
            conn.close()
