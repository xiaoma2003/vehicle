"""
车辆调度AI算法评测系统 - Flask后端服务
提供RESTful API接口供前端调用
"""
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import os
import json

from schedule_api import ScheduleAPI


app = Flask(__name__,
            template_folder='templates',
            static_folder='static')
CORS(app)

config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
api = ScheduleAPI(config_dir=config_dir)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/config/map', methods=['GET'])
def get_map_config():
    result = api.load_map_config()
    return jsonify(result)


@app.route('/api/config/map', methods=['POST'])
def save_map_config():
    data = request.get_json()
    result = api.save_map_config(data)
    return jsonify(result)


@app.route('/api/config/tasks', methods=['GET'])
def get_tasks_config():
    result = api.load_tasks_config()
    return jsonify(result)


@app.route('/api/config/tasks', methods=['POST'])
def save_tasks_config():
    data = request.get_json()
    result = api.save_tasks_config(data)
    return jsonify(result)


@app.route('/api/config/locomotives', methods=['GET'])
def get_locomotives_config():
    result = api.load_locomotives_config()
    return jsonify(result)


@app.route('/api/config/locomotives', methods=['POST'])
def save_locomotives_config():
    data = request.get_json()
    result = api.save_locomotives_config(data)
    return jsonify(result)


@app.route('/api/config/hyper-params', methods=['GET'])
def get_hyper_params():
    result = api.load_hyper_params()
    return jsonify(result)


@app.route('/api/config/hyper-params', methods=['POST'])
def save_hyper_params():
    data = request.get_json()
    result = api.save_hyper_params(data)
    return jsonify(result)


@app.route('/api/schedule/run', methods=['POST'])
def run_schedule():
    data = request.get_json() or {}
    strategy = data.get('strategy', 'cpsat')
    use_hot_start = data.get('use_hot_start', False)
    result = api.run_schedule(strategy, use_hot_start)
    return jsonify(result)


@app.route('/api/schedule/compare', methods=['POST'])
def compare_strategies():
    data = request.get_json() or {}
    strategies = data.get('strategies', ['cpsat', 'greedy', 'genetic', 'simulated_annealing'])
    result = api.compare_strategies(strategies)
    return jsonify(result)


@app.route('/api/strategies', methods=['GET'])
def get_strategies():
    result = api.get_available_strategies()
    return jsonify(result)


@app.route('/api/locomotives/add', methods=['POST'])
def add_locomotive():
    data = request.get_json()
    result = api.add_locomotive(data)
    return jsonify(result)


@app.route('/api/tasks/add', methods=['POST'])
def add_task():
    data = request.get_json()
    result = api.add_task(data)
    return jsonify(result)


@app.route('/api/nodes/add', methods=['POST'])
def add_node():
    data = request.get_json()
    result = api.add_node(data)
    return jsonify(result)


@app.route('/api/nodes/delete', methods=['POST'])
def delete_node():
    data = request.get_json()
    node_id = data.get('id')
    result = api.delete_node(node_id)
    return jsonify(result)


@app.route('/api/edges/add', methods=['POST'])
def add_edge():
    data = request.get_json()
    result = api.add_edge(data)
    return jsonify(result)


@app.route('/api/tasks/boost-priority', methods=['POST'])
def boost_priority():
    data = request.get_json()
    task_id = data.get('task_id')
    boost_amount = data.get('boost_amount', 10)
    result = api.boost_task_priority(task_id, boost_amount)
    return jsonify(result)


@app.route('/api/emergency/trigger', methods=['POST'])
def trigger_emergency():
    data = request.get_json()
    result = api.trigger_emergency_task(data)
    return jsonify(result)


@app.route('/api/query/runs', methods=['GET'])
def query_runs():
    batch_id = request.args.get('batch_id')
    strategy = request.args.get('strategy')
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 20))
    result = api.query_runs(batch_id, strategy, page, page_size)
    return jsonify(result)


@app.route('/api/query/tasks', methods=['GET'])
def query_tasks():
    batch_id = request.args.get('batch_id')
    task_type = request.args.get('task_type')
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 20))
    result = api.query_tasks(batch_id, task_type, page, page_size)
    return jsonify(result)


@app.route('/api/query/locomotives', methods=['GET'])
def query_locomotives():
    batch_id = request.args.get('batch_id')
    traction_type = request.args.get('traction_type')
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 20))
    result = api.query_locomotives(batch_id, traction_type, page, page_size)
    return jsonify(result)


@app.route('/api/query/logs', methods=['GET'])
def query_logs():
    batch_id = request.args.get('batch_id')
    log_level = request.args.get('log_level')
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 50))
    result = api.query_logs(batch_id, log_level, page, page_size)
    return jsonify(result)


@app.route('/api/runs/<int:run_id>', methods=['GET'])
def get_run_detail(run_id):
    result = api.get_run_detail(run_id)
    return jsonify(result)


@app.route('/api/batches/<batch_id>', methods=['GET'])
def get_batch_history(batch_id):
    result = api.get_batch_history(batch_id)
    return jsonify(result)


@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    result = api.get_statistics()
    return jsonify(result)


@app.route('/api/batch-ids', methods=['GET'])
def get_batch_ids():
    result = api.get_all_batch_ids()
    return jsonify(result)


@app.route('/api/give-way/analyze', methods=['POST'])
def analyze_give_way():
    data = request.get_json()
    high_id = data.get('high_prio_task_id')
    low_id = data.get('low_prio_task_id')
    result = api.get_give_way_analysis(high_id, low_id)
    return jsonify(result)


@app.route('/api/direction/check', methods=['GET'])
def check_direction():
    direction = request.args.get('direction', 'up')
    result = api.check_direction_lock(direction)
    return jsonify(result)


@app.route('/api/logs/delete/<int:log_id>', methods=['DELETE'])
def delete_log(log_id):
    success = api.db.delete_log(log_id)
    if success:
        return jsonify({"success": True, "message": "日志删除成功"})
    else:
        return jsonify({"success": False, "error": "日志不存在"})

@app.route('/api/logs/clear', methods=['POST'])
def clear_all_logs():
    count = api.db.clear_all_logs()
    return jsonify({"success": True, "count": count, "message": f"已清空 {count} 条日志"})

@app.route('/api/locomotives/update', methods=['POST'])
def update_locomotive():
    data = request.get_json()
    result = api.update_locomotive(data)
    return jsonify(result)

@app.route('/api/comparison/export/<batch_id>', methods=['GET'])
def export_comparison_report(batch_id):
    result = api.get_batch_history(batch_id)
    if not result.get('success'):
        return jsonify(result), 404
    
    # Export as JSON format
    output_path = os.path.join(config_dir, f'comparison_report_{batch_id}.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result['data'], f, ensure_ascii=False, indent=2)
    return send_file(output_path, as_attachment=True,
                     download_name=f'comparison_report_{batch_id}.json')

@app.route('/api/export/<batch_id>', methods=['GET'])
def export_batch(batch_id):
    result = api.get_batch_history(batch_id)
    if not result.get('success'):
        return jsonify(result), 404
    output_path = os.path.join(config_dir, f'export_{batch_id}.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result['data'], f, ensure_ascii=False, indent=2)
    return send_file(output_path, as_attachment=True,
                     download_name=f'export_{batch_id}.json')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
