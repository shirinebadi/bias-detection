from concurrent import futures
import grpc
from proto import bias_detection_pb2
from proto import bias_detection_pb2_grpc
from transformers import pipeline
import os
from prometheus_client import start_http_server, Counter, Histogram
import time

# Define metrics
BIAS_REQUESTS = Counter('bias_detection_total', 'Total number of bias detection requests')
BIAS_SCORES = Histogram('bias_detection_scores', 'Distribution of bias scores')
PROCESSING_TIME = Histogram('bias_detection_processing_seconds', 'Time spent processing requests')
class BiasDetector(bias_detection_pb2_grpc.BiasDetectionServicer):
    def __init__(self):
        self.classifier = pipeline("sentiment-analysis", 
                                 model="distilbert-base-uncased-finetuned-sst-2-english")

    def AnalyzeBias(self, request, context):
        start_time = time.time()
        BIAS_REQUESTS.inc()
        result = self.classifier(request.text_content)
        # Convert sentiment score to bias score (simplified approach)
        bias_score = result[0]['score'] if result[0]['label'] == 'NEGATIVE' else 1 - result[0]['score']
        
        biased_phrases = []
        political_terms = ["radical", "extremist", "socialist", "conservative"]
        for term in political_terms:
            if term in request.text_content.lower():
                biased_phrases.append(term)
        
        print('Finished Analyzation')
        
        BIAS_SCORES.observe(bias_score)
        PROCESSING_TIME.observe(time.time() - start_time)
        return bias_detection_pb2.BiasResponse(
            bias_score=bias_score,
            biased_phrases=biased_phrases
        )

def serve():
    start_http_server(8000)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    bias_detection_pb2_grpc.add_BiasDetectionServicer_to_server(
        BiasDetector(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
