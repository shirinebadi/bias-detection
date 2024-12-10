from flask import Flask, request, jsonify
import pika
import os
import json
import logging
import sys

app = Flask(__name__)
results = dict()

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

def callback(ch, method, properties, body):
    try:
        data = json.loads(body)
        file_uri = data['file_path']
        score = data['score']
        logger.info(f"Got result for file: {file_uri}")
        results[file_uri] = score
    except Exception as e:
            logger.error(f"Error in Callback - {e}")

def read_from_queue(file_uri):
        try:
            rabbitmq_host = os.getenv('RABBITMQ_SERVICE_HOST', 'localhost')
            logger.info(f"Connecting to RabbitMQ at {rabbitmq_host}")
            
            connection = pika.BlockingConnection(pika.ConnectionParameters(
                host=rabbitmq_host,
                port=int(os.getenv('RABBITMQ_SERVICE_PORT_AMQP', '5672')),
                connection_attempts=5,
                retry_delay=5
            ))
            channel = connection.channel()
            
            channel.queue_declare(queue='result_queue', durable=False)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(
                queue='result_queue',
                on_message_callback=callback,
                auto_ack=True
            )
            
            logger.info("Connected to RabbitMQ. Waiting for messages...")
            channel.start_consuming()
        except pika.exceptions.AMQPConnectionError as e:
            logger.error(f"RabbitMQ connection error: {str(e)}")
            logger.info("Retrying in 5 seconds...")
            import time
            time.sleep(5)


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

@app.route('/get_result', methods=['POST'])
def get_result():
    try:
        file_uri = request.json.get('file_uri')
        if not file_uri:
            return jsonify({'error': 'file_uri is required'}), 400
        logger.info(f'Received request to process file: {file_uri}')
        
        if file_uri in results:
            return jsonify({'file': file_uri , 'score': results[file_uri]}), 200
        
        logger.info("Reading from Result Qeueue")
        read_from_queue(file_uri)
        logger.info("Finished Reading, Looking for the file...")
        
        if file_uri in results:
            return jsonify({'file': file_uri , 'score': results[file_uri]}), 200
        return jsonify({'status': 'File is not ready.'}), 200

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    logger.info("Starting Flask server...")
    app.run(host='0.0.0.0', port=5000)