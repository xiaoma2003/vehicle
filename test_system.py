"""
系统集成测试脚本
测试所有核心模块功能
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_loader import ConfigLoader
from strategy_manager import StrategyManager
from schedule_api import ScheduleAPI
from schedule_database import ScheduleDatabase


def test_config_loader():
    print("=" * 50)
    print("测试1: 配置加载与验证模块")
    print("=" * 50)

    try:
        loader = ConfigLoader("data")
        configs = loader.load_all_configs()

        print(f"✓ 地图节点数: {len(configs['map']['nodes'])}")
        print(f"✓ 地图边数: {len(configs['map']['edges'])}")
        print(f"✓ 任务数: {len(configs['tasks']['tasks'])}")
        print(f"✓ 机车数: {len(configs['locomotives']['locomotives'])}")
        print(f"✓ 超参数项数: {len(configs['hyper_params'])}")

        electric_locomotives = [l for l in configs['locomotives']['locomotives']
                               if l['traction_type'] == 'electric']
        diesel_locomotives = [l for l in configs['locomotives']['locomotives']
                             if l['traction_type'] == 'diesel']
        print(f"✓ 电动机车: {len(electric_locomotives)}台, 柴油机车: {len(diesel_locomotives)}台")

        busy_locomotives = [l for l in configs['locomotives']['locomotives']
                           if l.get('current_task')]
        print(f"✓ 热启动绑定任务的机车: {len(busy_locomotives)}台")

        print("✓ 配置加载测试通过!")
        return True
    except Exception as e:
        print(f"✗ 配置加载测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_strategies():
    print("\n" + "=" * 50)
    print("测试2: 调度策略模块")
    print("=" * 50)

    try:
        loader = ConfigLoader("data")
        configs = loader.load_all_configs()
        manager = StrategyManager()

        strategies = manager.get_available_strategies()
        print(f"✓ 可用策略数: {len(strategies)}")
        for name, info in strategies.items():
            print(f"  - {name}: {info['name']}")

        print("\n测试贪心算法...")
        greedy_result = manager.run_strategy(
            'greedy', configs['map'], configs['tasks'],
            configs['locomotives'], configs['hyper_params']
        )
        print(f"  状态: {greedy_result['solve_status']}")
        print(f"  工期: {greedy_result['makespan']} 分钟")
        print(f"  任务数: {greedy_result.get('num_tasks', 0)}")
        print(f"  耗时: {greedy_result.get('solve_time', 0)}s")

        print("\n测试模拟退火算法...")
        sa_result = manager.run_strategy(
            'simulated_annealing', configs['map'], configs['tasks'],
            configs['locomotives'], configs['hyper_params']
        )
        print(f"  状态: {sa_result['solve_status']}")
        print(f"  工期: {sa_result['makespan']} 分钟")
        print(f"  耗时: {sa_result.get('solve_time', 0)}s")

        print("\n测试遗传算法...")
        ga_result = manager.run_strategy(
            'genetic', configs['map'], configs['tasks'],
            configs['locomotives'], configs['hyper_params']
        )
        print(f"  状态: {ga_result['solve_status']}")
        print(f"  工期: {ga_result['makespan']} 分钟")
        print(f"  耗时: {ga_result.get('solve_time', 0)}s")

        print("\n测试CP-SAT基准策略...")
        cpsat_result = manager.run_strategy(
            'cpsat', configs['map'], configs['tasks'],
            configs['locomotives'], configs['hyper_params']
        )
        print(f"  状态: {cpsat_result['solve_status']}")
        print(f"  工期: {cpsat_result['makespan']} 分钟")
        print(f"  任务数: {cpsat_result.get('num_tasks', 0)}")
        print(f"  耗时: {cpsat_result.get('solve_time', 0)}s")

        print("\n✓ 所有策略测试通过!")
        return True
    except Exception as e:
        print(f"✗ 策略测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database():
    print("\n" + "=" * 50)
    print("测试3: 数据库模块")
    print("=" * 50)

    try:
        db = ScheduleDatabase("data/test_schedule.db")

        batch_id = "test_batch_001"

        loader = ConfigLoader("data")
        configs = loader.load_all_configs()

        result = db.save_config_batch(
            batch_id, configs['map'], configs['tasks'],
            configs['locomotives'], configs['hyper_params']
        )
        print(f"✓ 配置保存: {result}")

        test_result = {
            "solve_status": "optimal",
            "makespan": 500,
            "solve_time": 2.5,
            "num_tasks": 7,
            "num_locomotives": 5,
            "assignments": [
                {"task_id": "T001", "locomotive_id": "L001",
                 "start_time": 0, "loading_end": 10,
                 "transport_end": 100, "unloading_end": 108,
                 "path": ["S1", "C1", "SW1", "M1", "F1", "S4"]}
            ]
        }

        run_id = db.save_scheduler_run(batch_id, "greedy", "贪心算法", test_result)
        print(f"✓ 调度结果保存, run_id: {run_id}")

        db.add_log(batch_id, "INFO", "test", "测试日志条目")

        runs = db.query_runs(batch_id=batch_id, page=1, page_size=10)
        print(f"✓ 查询运行记录: {runs['total']}条")

        tasks = db.query_tasks(batch_id=batch_id, page=1, page_size=10)
        print(f"✓ 查询任务: {tasks['total']}条")

        locomotives = db.query_locomotives(batch_id=batch_id, page=1, page_size=10)
        print(f"✓ 查询机车: {locomotives['total']}条")

        logs = db.query_logs(batch_id=batch_id, page=1, page_size=10)
        print(f"✓ 查询日志: {logs['total']}条")

        stats = db.get_statistics()
        print(f"✓ 统计数据: {stats['total_runs']}次运行")

        run_detail = db.get_run_detail(run_id)
        print(f"✓ 运行详情: {run_detail['strategy_name']}")

        batch_history = db.get_batch_history(batch_id)
        print(f"✓ 批次历史: {len(batch_history['runs'])}次运行")

        if os.path.exists("data/test_schedule.db"):
            os.remove("data/test_schedule.db")
            print("✓ 测试数据库已清理")

        print("✓ 数据库模块测试通过!")
        return True
    except Exception as e:
        print(f"✗ 数据库测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api():
    print("\n" + "=" * 50)
    print("测试4: API接口模块")
    print("=" * 50)

    try:
        api = ScheduleAPI(config_dir="data", db_path="data/api_test.db")

        result = api.get_available_strategies()
        print(f"✓ 获取策略列表: {len(result['data'])}种")

        result = api.run_schedule('greedy')
        print(f"✓ 执行调度: {result['data']['solve_status']}, 工期={result['data']['makespan']}")

        result = api.query_runs(page=1, page_size=10)
        print(f"✓ 查询运行: {result['data']['total']}条")

        new_loco = {
            "id": "TEST01",
            "traction_type": "electric",
            "Q": 30,
            "max_speed": 750,
            "initial_node": "S1",
            "battery": 600,
            "is_powered_on": True,
            "is_schedulable": True,
            "current_task": None,
            "task_phase": None
        }
        result = api.add_locomotive(new_loco)
        print(f"✓ 添加机车: {result['success']}")

        new_task = {
            "id": "TEST_TASK",
            "task_type": "normal",
            "priority": 50,
            "status": "pending",
            "start_node": "S1",
            "end_node": "S2",
            "material_weight": 20,
            "depends_on": []
        }
        result = api.add_task(new_task)
        print(f"✓ 添加任务: {result['success']}")

        result = api.boost_task_priority("TEST_TASK", 20)
        print(f"✓ 提升优先级: {result['data']['old_priority']} -> {result['data']['new_priority']}")

        result = api.get_statistics()
        print(f"✓ 统计信息: {result['data']['total_runs']}次运行")

        if os.path.exists("data/api_test.db"):
            os.remove("data/api_test.db")
            print("✓ 测试数据库已清理")

        print("✓ API接口测试通过!")
        return True
    except Exception as e:
        print(f"✗ API测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_hot_start():
    print("\n" + "=" * 50)
    print("测试5: 热启动功能")
    print("=" * 50)

    try:
        from schedule_engine import HotStartManager

        loader = ConfigLoader("data")
        configs = loader.load_all_configs()

        hot_start = HotStartManager("data")
        busy_locomotives = hot_start.get_busy_locomotives(configs['locomotives'])
        print(f"✓ 热启动检测到忙机车: {busy_locomotives}")

        tasks, locomotives = hot_start.apply_hot_start(
            configs['tasks'], configs['locomotives']
        )

        schedulable_after = [l for l in locomotives['locomotives']
                            if l.get('is_schedulable', True)]
        print(f"✓ 热启动后可调度机车数: {len(schedulable_after)} / {len(locomotives['locomotives'])}")

        running_tasks = hot_start.get_running_tasks(configs['tasks'])
        print(f"✓ 正在执行的任务数: {len(running_tasks)}")

        print("✓ 热启动功能测试通过!")
        return True
    except Exception as e:
        print(f"✗ 热启动测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_give_way():
    print("\n" + "=" * 50)
    print("测试6: 让道机制")
    print("=" * 50)

    try:
        from schedule_engine import GiveWayManager, PriorityScheduler

        loader = ConfigLoader("data")
        configs = loader.load_all_configs()

        priority_scheduler = PriorityScheduler(configs['map'], configs['hyper_params'])
        direction = priority_scheduler.determine_direction("S1", "S4")
        print(f"✓ 方向判定: S1->S4 = {direction}")

        available = priority_scheduler.check_direction_available("up")
        print(f"✓ 上行方向可用: {available}")

        give_way = GiveWayManager(configs['map'], configs['hyper_params'])
        high_task = {
            "task_id": "high_prio",
            "priority": 1,
            "speed": 900,
            "path": ["S1", "C1", "SW1", "M1", "F1", "S4"]
        }
        low_task = {
            "task_id": "low_prio",
            "priority": 50,
            "speed": 600,
            "path": ["S4", "F1", "M1", "SW1", "C1", "S1"],
            "current_path_index": 2
        }

        result = give_way.calculate_give_way(low_task, high_task)
        print(f"✓ 让道计算: 需要让道={result['needs_give_way']}")
        if result['needs_give_way']:
            print(f"  等待节点: {result['wait_node']}")
            print(f"  高优先级任务: {result['high_priority_task_id']}")

        print("✓ 让道机制测试通过!")
        return True
    except Exception as e:
        print(f"✗ 让道机制测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "🚂 车辆调度AI算法评测系统 - 集成测试")
    print("=" * 50)

    tests = [
        ("配置加载模块", test_config_loader),
        ("调度策略模块", test_strategies),
        ("数据库模块", test_database),
        ("API接口模块", test_api),
        ("热启动功能", test_hot_start),
        ("让道机制", test_give_way)
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            print(f"✗ {name}测试异常: {e}")

    print("\n" + "=" * 50)
    print(f"测试完成: {passed} 通过, {failed} 失败")
    print("=" * 50)

    return failed == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
