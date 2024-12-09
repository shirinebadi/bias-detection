from flask import Flask, request, jsonify
import pika
import os
import json
import logging
import sys

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

def publish_to_queue(file_path):
    try:
        rabbitmq_host = os.getenv('RABBITMQ_HOST', 'localhost')
        logger.info(f"Connecting to RabbitMQ at {rabbitmq_host}")
        
        connection = pika.BlockingConnection(pika.ConnectionParameters(rabbitmq_host))
        channel = connection.channel()
        
        # Declare queue without durability to match existing queue
        channel.queue_declare(queue='audio_queue', durable=False)
        
        message = json.dumps({'file_path': file_path})
        logger.info(f"Publishing message: {message}")
        
        channel.basic_publish(
            exchange='',
            routing_key='audio_queue',
            body=message
        )
        
        logger.info("Message published successfully")
        connection.close()
        return True
    except Exception as e:
        logger.error(f"Error publishing to queue: {str(e)}")
        return False

@app.route('/process-audio', methods=['POST'])
def process_audio():
    try:
        file_path = request.json.get('file_path')
        if not file_path:
            return jsonify({'error': 'file_path is required'}), 400
            
        logger.info(f'Received request to process file: {file_path}')
        
        if publish_to_queue(file_path):
            return jsonify({'status': 'queued', 'file': file_path})
        else:
            return jsonify({'error': 'Failed to queue message'}), 500
            
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    logger.info("Starting Flask server...")
    app.run(host='0.0.0.0', port=5000)