from flask import Flask, request, jsonify
import pika
import os
import json

app = Flask(__name__)

def publish_to_queue(file_path):
    connection = pika.BlockingConnection(pika.ConnectionParameters(os.getenv('RABBITMQ_HOST', 'localhost')))
    channel = connection.channel()
    channel.queue_declare(queue='audio_queue')
    channel.basic_publish(
        exchange='',
        routing_key='audio_queue',
        body=json.dumps({'file_path': file_path})
    )
    connection.close()

@app.route('/process-audio', methods=['POST'])
def process_audio():
    file_path = request.json.get('file_path')
    print(f'Publish {file_path} to Queue')
    publish_to_queue(file_path)
    return jsonify({'status': 'queued'})

if __name__ == '__main__':
    # Run Flask server
    app.run(port=5000)