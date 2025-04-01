import os
from flask import Flask, request, jsonify
import subprocess
from threading import Thread
from queue import Queue, Empty
import uuid

app = Flask(__name__)
bot_processes = {}
bot_queues = {}

@app.route('/start_bot', methods=['POST'])
def start_bot():
    bot_name = request.json.get('bot_name')
    bot_code = request.json.get('bot_code')
    
    if not bot_name or not bot_code:
        return jsonify({"status": "error", "message": "Missing bot_name or bot_code"}), 400
    
    if bot_name in bot_processes:
        return jsonify({"status": "error", "message": "Bot already running"}), 400
    
    try:
        # Save the bot code to a file with a unique name
        unique_name = f"{bot_name}_{uuid.uuid4().hex[:6]}"
        filename = f"{unique_name}.py"
        with open(filename, "w") as f:
            f.write(bot_code)
        
        # Create a queue for this bot's output
        bot_queues[unique_name] = Queue()
        
        # Start the bot in a subprocess
        process = subprocess.Popen(
            ["python", filename],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        bot_processes[unique_name] = {
            "process": process,
            "filename": filename,
            "original_name": bot_name
        }
        
        # Start a thread to capture output
        def enqueue_output(process, queue):
            for line in iter(process.stdout.readline, ''):
                queue.put(line)
            process.stdout.close()
        
        thread = Thread(target=enqueue_output, args=(process, bot_queues[unique_name]))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "status": "success",
            "message": "Bot started",
            "assigned_name": unique_name
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/stop_bot', methods=['POST'])
def stop_bot():
    bot_name = request.json.get('bot_name')
    
    if not bot_name:
        return jsonify({"status": "error", "message": "Missing bot_name"}), 400
    
    if bot_name not in bot_processes:
        return jsonify({"status": "error", "message": "Bot not running"}), 404
    
    try:
        # Terminate the process
        bot_processes[bot_name]["process"].terminate()
        
        # Clean up the file
        filename = bot_processes[bot_name]["filename"]
        if os.path.exists(filename):
            os.remove(filename)
        
        # Clean up queues and process tracking
        del bot_queues[bot_name]
        del bot_processes[bot_name]
        
        return jsonify({"status": "success", "message": "Bot stopped"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/get_logs', methods=['GET'])
def get_logs():
    bot_name = request.args.get('bot_name')
    
    if not bot_name:
        return jsonify({"status": "error", "message": "Missing bot_name"}), 400
    
    if bot_name not in bot_queues:
        return jsonify({"status": "error", "message": "Bot not running"}), 404
    
    try:
        logs = []
        while True:
            try:
                logs.append(bot_queues[bot_name].get_nowait())
            except Empty:
                break
        
        return jsonify({"status": "success", "logs": logs})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
