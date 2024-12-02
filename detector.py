from concurrent import futures
import grpc
from proto import bias_detection_pb2
from proto import bias_detection_pb2_grpc
from transformers import pipeline

class BiasDetector(bias_detection_pb2_grpc.BiasDetectionServicer):
    def __init__(self):
        self.classifier = pipeline("sentiment-analysis", 
                                 model="distilbert-base-uncased-finetuned-sst-2-english")

    def AnalyzeBias(self, request, context):
        result = self.classifier(request.text_content)
        # Convert sentiment score to bias score (simplified approach)
        bias_score = result[0]['score'] if result[0]['label'] == 'NEGATIVE' else 1 - result[0]['score']
        
        biased_phrases = []
        political_terms = ["radical", "extremist", "socialist", "conservative"]
        for term in political_terms:
            if term in request.text_content.lower():
                biased_phrases.append(term)
        
        print('Finished Analyzation')
        
        return bias_detection_pb2.BiasResponse(
            bias_score=bias_score,
            biased_phrases=biased_phrases
        )

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    bias_detection_pb2_grpc.add_BiasDetectionServicer_to_server(
        BiasDetector(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()