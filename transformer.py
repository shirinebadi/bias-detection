import pika
import json
import speech_recognition as sr
from pydub import AudioSegment
import os
import grpc
from proto import bias_detection_pb2
from proto import bias_detection_pb2_grpc

def transcribe_audio(audio_path):
    print('Recieved New Request')
    # wav_path = os.path.splitext(audio_path)[0] + '.wav'
    # audio = AudioSegment.from_file(audio_path, format="mp3", 
    #                               parameters=["-sample_width", "2", 
    #                                         "-channels", "1", 
    #                                         "-sample_rate", "16000"])
    # audio.export(wav_path, format="wav")
    
    recognizer = sr.Recognizer()
    with sr.AudioFile(audio_path) as source:
        audio = recognizer.record(source)
        text = recognizer.recognize_google(audio)
    
    with grpc.insecure_channel('localhost:50051') as channel:
        stub = bias_detection_pb2_grpc.BiasDetectionStub(channel)
        response = stub.AnalyzeBias(
            bias_detection_pb2.BiasRequest(text_content=text)
        )
        return response.bias_score, response.biased_phrases

def callback(ch, method, properties, body):
    data = json.loads(body)
    result = transcribe_audio(data['file_path'])
    print(f"Bias score: {result[0]}")
    print(f"Biased phrases: {result[1]}")

def start_consumer():
    connection = pika.BlockingConnection(pika.ConnectionParameters(os.getenv('RABBITMQ_HOST', 'localhost')))
    channel = connection.channel()  # Changed from create_channel()
    channel.queue_declare(queue='audio_queue')
    channel.basic_consume(
        queue='audio_queue',
        on_message_callback=callback,
        auto_ack=True
    )
    print("Waiting for messages...")
    channel.start_consuming()

if __name__ == '__main__':
    start_consumer()