# transformer.py
import pika
import json
import speech_recognition as sr
from pydub import AudioSegment
import os
import grpc
from proto import bias_detection_pb2
from proto import bias_detection_pb2_grpc
import paramiko
import io
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_file_from_sftp(sftp_host, sftp_port, sftp_username, sftp_password, remote_path, local_path):
    try:
        transport = paramiko.Transport((sftp_host, sftp_port))
        transport.connect(username=sftp_username, password=sftp_password)
        sftp = paramiko.SFTPClient.from_transport(transport)
        
        # Create a memory buffer for the file
        with io.BytesIO() as buf:
            sftp.getfo(remote_path, buf)
            buf.seek(0)
            
            # Save to local temp file
            with open(local_path, 'wb') as f:
                f.write(buf.read())
        
        sftp.close()
        transport.close()
        return True
    except Exception as e:
        logger.error(f"SFTP Error: {str(e)}")
        return False

def transcribe_audio(file_path):
   # wav_path = os.path.splitext(file_path)[0] + '.wav'
  #  audio = AudioSegment.from_file(file_path, format="mp3", 
 #                               parameters=["-sample_width", "2", 
      
#                                    "-channels", "1", 
     #                                     "-sample_rate", "16000"])
    #audio.export(wav_path, format="wav")
    
    recognizer = sr.Recognizer()
    with sr.AudioFile(file_path) as source:
        audio = recognizer.record(source)
        text = recognizer.recognize_google(audio)
    
    # Clean up temporary files
    os.remove(file_path)
    
    bias_service_host = os.getenv('BIAS_SERVICE_HOST', 'bias-worker:50051')
    logger.info(f"Connecting to bias service at {bias_service_host}")
    with grpc.insecure_channel(bias_service_host) as channel:
        stub = bias_detection_pb2_grpc.BiasDetectionStub(channel)
        response = stub.AnalyzeBias(
            bias_detection_pb2.BiasRequest(text_content=text)
        )
        return response.bias_score, response.biased_phrases

def send_to_queue(file_path, score):
    try:
        rabbitmq_host = os.getenv('RABBITMQ_HOST', 'localhost')
        logger.info(f"Connecting to RabbitMQ at {rabbitmq_host}")
        
        connection = pika.BlockingConnection(pika.ConnectionParameters(rabbitmq_host))
        channel = connection.channel()
        
        # Declare queue without durability to match existing queue
        channel.queue_declare(queue='result_queue', durable=False)
        
        message = json.dumps({'file_path': file_path, 'score': score})
        logger.info(f"Publishing message: {message}")
        
        channel.basic_publish(
            exchange='',
            routing_key='result_queue',
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
        remote_path = data['file_path']
        logger.info(f"Processing file: {remote_path}")
        
        # SFTP configuration
        sftp_host = os.getenv('SFTP_HOST', 'localhost')
        sftp_port = int(os.getenv('SFTP_PORT', '22'))
        sftp_username = os.getenv('SFTP_USERNAME', 'user')
        sftp_password = os.getenv('SFTP_PASSWORD', 'password')
        
        # Create temp local path
        local_path = f"/tmp/{os.path.basename(remote_path)}"
        
        if get_file_from_sftp(sftp_host, sftp_port, sftp_username, sftp_password, remote_path, local_path):
            result = transcribe_audio(local_path)
            send_to_queue(remote_path, result[0])
            logger.info(f"Bias score: {result[0]}")
            logger.info(f"Biased phrases: {result[1]}")

        else:
            logger.error(f"Failed to download file from SFTP: {remote_path}")
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")

def start_consumer():
    while True:
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
            
            channel.queue_declare(queue='audio_queue', durable=False)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(
                queue='audio_queue',
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

if __name__ == '__main__':
    start_consumer()