"""
GPU Utilities - GPU 환경 확인 및 설정

NVIDIA GPU가 있으면 GPU 기반 처리를 활성화하고,
없으면 CPU로 폴백합니다.
"""
import torch
from typing import Dict, Any, Optional


class GPUConfig:
    """GPU 설정 및 정보"""

    def __init__(self):
        self.available = torch.cuda.is_available()
        self.device = "cuda" if self.available else "cpu"
        self.gpu_count = torch.cuda.device_count() if self.available else 0

    def get_info(self) -> Dict[str, Any]:
        """GPU 정보 반환"""
        if not self.available:
            return {
                "available": False,
                "device": "cpu",
                "gpu_count": 0,
                "message": "No NVIDIA GPU detected. Using CPU."
            }

        # GPU 정보 수집
        gpu_info = {
            "available": True,
            "device": "cuda",
            "gpu_count": self.gpu_count,
            "cuda_version": torch.version.cuda,
            "cudnn_version": torch.backends.cudnn.version() if torch.backends.cudnn.is_available() else None,
            "gpus": []
        }

        # 각 GPU 정보
        for i in range(self.gpu_count):
            props = torch.cuda.get_device_properties(i)
            gpu_info["gpus"].append({
                "id": i,
                "name": torch.cuda.get_device_name(i),
                "total_memory_gb": props.total_memory / 1024**3,
                "compute_capability": f"{props.major}.{props.minor}",
                "multi_processor_count": props.multi_processor_count
            })

        return gpu_info

    def print_info(self):
        """GPU 정보 출력"""
        info = self.get_info()

        if not info["available"]:
            print(f"\n{'='*60}")
            print("GPU Status: Not Available")
            print(f"{'='*60}")
            print(info["message"])
            print(f"{'='*60}\n")
            return

        print(f"\n{'='*60}")
        print("GPU Status: Available")
        print(f"{'='*60}")
        print(f"CUDA Version: {info['cuda_version']}")
        print(f"cuDNN Version: {info['cudnn_version']}")
        print(f"GPU Count: {info['gpu_count']}")
        print(f"{'='*60}")

        for gpu in info["gpus"]:
            print(f"\nGPU {gpu['id']}: {gpu['name']}")
            print(f"  - Memory: {gpu['total_memory_gb']:.1f} GB")
            print(f"  - Compute Capability: {gpu['compute_capability']}")
            print(f"  - Multi-Processors: {gpu['multi_processor_count']}")

        print(f"{'='*60}\n")

    def check_faiss_gpu(self) -> bool:
        """faiss-gpu 설치 여부 확인"""
        try:
            import faiss
            # faiss-gpu가 설치되어 있으면 StandardGpuResources가 있음
            return hasattr(faiss, 'StandardGpuResources')
        except ImportError:
            return False

    def recommend_faiss_install(self):
        """FAISS 설치 권장사항 출력"""
        has_gpu = self.available
        has_faiss_gpu = self.check_faiss_gpu()

        print(f"\n{'='*60}")
        print("FAISS Installation Recommendation")
        print(f"{'='*60}")

        if has_gpu and not has_faiss_gpu:
            print("⚠️  GPU detected but faiss-gpu is not installed!")
            print("\nFor 10-100x faster vector search, install faiss-gpu:")
            print("\n  Windows/Linux:")
            print("    pip uninstall faiss-cpu -y")
            print("    pip install faiss-gpu")
            print("\n  Note: Requires CUDA 12.x")
        elif has_gpu and has_faiss_gpu:
            print("✅ GPU detected and faiss-gpu is installed!")
            print("   Using GPU-accelerated vector search.")
        elif not has_gpu and has_faiss_gpu:
            print("⚠️  faiss-gpu is installed but no GPU detected.")
            print("   faiss-gpu will fall back to CPU mode.")
            print("\n  Consider switching to faiss-cpu:")
            print("    pip uninstall faiss-gpu -y")
            print("    pip install faiss-cpu")
        else:
            print("✅ No GPU detected. Using faiss-cpu (optimal for CPU).")

        print(f"{'='*60}\n")

    def get_optimal_batch_size(self, base_size: int = 32) -> int:
        """
        GPU 메모리에 따른 최적 배치 크기 반환

        Args:
            base_size: CPU 기본 배치 크기

        Returns:
            최적 배치 크기
        """
        if not self.available:
            return base_size

        # GPU 메모리에 따라 배치 크기 조정
        total_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3

        if total_memory >= 16:  # 16GB 이상
            return base_size * 4
        elif total_memory >= 8:  # 8GB 이상
            return base_size * 2
        else:  # 8GB 미만
            return int(base_size * 1.5)


# 싱글톤 인스턴스
gpu_config = GPUConfig()


def get_device() -> str:
    """현재 사용 가능한 디바이스 반환 (cuda 또는 cpu)"""
    return gpu_config.device


def is_gpu_available() -> bool:
    """GPU 사용 가능 여부 반환"""
    return gpu_config.available


def get_gpu_info() -> Dict[str, Any]:
    """GPU 정보 딕셔너리 반환"""
    return gpu_config.get_info()


def print_gpu_status():
    """GPU 상태 출력"""
    gpu_config.print_info()


def print_faiss_recommendation():
    """FAISS 설치 권장사항 출력"""
    gpu_config.recommend_faiss_install()


def get_optimal_batch_size(base_size: int = 32) -> int:
    """최적 배치 크기 반환"""
    return gpu_config.get_optimal_batch_size(base_size)


if __name__ == "__main__":
    # 테스트 실행
    print_gpu_status()
    print_faiss_recommendation()

    print("\nOptimal batch sizes:")
    print(f"  Base (32): {get_optimal_batch_size(32)}")
    print(f"  Base (64): {get_optimal_batch_size(64)}")
