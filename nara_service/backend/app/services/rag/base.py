"""RAG 서비스 Base 클래스 - GPU 및 임베딩 모델 초기화 공통화"""

import torch
from sentence_transformers import SentenceTransformer
from typing import Tuple, Optional


class RAGBase:
    """
    RAG 서비스들의 공통 Base 클래스

    GPU 초기화 및 임베딩 모델 로딩 로직을 공통화하여 중복 제거
    """

    def __init__(self, service_name: str = "RAG"):
        """
        Base 클래스 초기화

        Args:
            service_name: 서비스 이름 (로그용)
        """
        self.service_name = service_name
        self.use_gpu: bool = False
        self.device: str = "cpu"
        self.embedding_model: Optional[SentenceTransformer] = None

        # GPU 및 임베딩 모델 초기화
        self._init_gpu()
        self._init_embedding_model()

    def _init_gpu(self):
        """GPU 가용성 확인 및 device 설정"""
        self.use_gpu = torch.cuda.is_available()
        self.device = "cuda" if self.use_gpu else "cpu"

        if self.use_gpu:
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            print(f"[{self.service_name}] GPU detected: {gpu_name} ({gpu_memory:.1f}GB)")
            print(f"[{self.service_name}] CUDA version: {torch.version.cuda}")
        else:
            print(f"[{self.service_name}] No GPU detected, using CPU")

    def _init_embedding_model(self, model_name: str = 'jhgan/ko-sroberta-multitask'):
        """
        임베딩 모델 초기화

        Args:
            model_name: 사용할 SentenceTransformer 모델 이름
        """
        print(f"[{self.service_name}] Loading embedding model on {self.device}...")
        self.embedding_model = SentenceTransformer(model_name, device=self.device)
        print(f"[{self.service_name}] Embedding model loaded")

    def get_device_info(self) -> Tuple[str, bool]:
        """
        Device 정보 반환

        Returns:
            (device, use_gpu) 튜플
        """
        return self.device, self.use_gpu

    def get_batch_size(self, default_cpu: int = 32, default_gpu: int = 64) -> int:
        """
        GPU 사용 여부에 따른 적절한 배치 크기 반환

        Args:
            default_cpu: CPU 사용 시 기본 배치 크기
            default_gpu: GPU 사용 시 기본 배치 크기

        Returns:
            배치 크기
        """
        return default_gpu if self.use_gpu else default_cpu
