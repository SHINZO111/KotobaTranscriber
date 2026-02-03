"""
device_manager.py - マルチデバイス管理モジュール
GPU/CPU/MPSの自動選択と管理を行う

使用方法:
    manager = MultiDeviceManager()
    device = manager.select_optimal_device(required_memory_mb=4096)
    torch_device = manager.get_torch_device(device)
"""

import torch
import logging
from enum import Enum, auto
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = logging.getLogger(__name__)


class DeviceType(Enum):
    """デバイスタイプ"""
    CPU = auto()
    CUDA = auto()
    MPS = auto()  # Apple Silicon
    AUTO = auto()


@dataclass
class DeviceInfo:
    """デバイス情報"""
    id: int
    name: str
    type: DeviceType
    total_memory_mb: int
    available_memory_mb: int
    compute_capability: Optional[str] = None
    is_available: bool = True


class MultiDeviceManager:
    """
    マルチデバイス管理クラス
    
    複数のGPUやApple Siliconを自動検出し、
    最適なデバイスを選択する
    """
    
    def __init__(self):
        self.devices: List[DeviceInfo] = []
        self._current_device: Optional[DeviceInfo] = None
        self._scan_devices()
    
    def _scan_devices(self):
        """利用可能なデバイスをスキャン"""
        self.devices = []
        
        # CPUは常に利用可能
        self.devices.append(DeviceInfo(
            id=-1,
            name="CPU",
            type=DeviceType.CPU,
            total_memory_mb=self._get_cpu_memory(),
            available_memory_mb=self._get_cpu_memory(),
            is_available=True
        ))
        
        # CUDAデバイス
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                try:
                    props = torch.cuda.get_device_properties(i)
                    memory_mb = props.total_memory // (1024 * 1024)
                    
                    self.devices.append(DeviceInfo(
                        id=i,
                        name=props.name,
                        type=DeviceType.CUDA,
                        total_memory_mb=memory_mb,
                        available_memory_mb=self._get_gpu_free_memory(i),
                        compute_capability=f"{props.major}.{props.minor}",
                        is_available=True
                    ))
                except Exception as e:
                    logger.warning(f"Failed to query CUDA device {i}: {e}")
        
        # MPS (Apple Silicon)
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            self.devices.append(DeviceInfo(
                id=0,
                name="Apple Silicon MPS",
                type=DeviceType.MPS,
                total_memory_mb=self._get_cpu_memory(),  # 共有メモリ
                available_memory_mb=int(self._get_cpu_memory() * 0.8),
                is_available=True
            ))
        
        logger.info(f"Found {len(self.devices)} devices: {[d.name for d in self.devices]}")
    
    def select_optimal_device(
        self,
        preference: DeviceType = DeviceType.AUTO,
        required_memory_mb: int = 0
    ) -> DeviceInfo:
        """
        最適なデバイスを選択
        
        Args:
            preference: 優先デバイスタイプ
            required_memory_mb: 必要メモリ量
        
        Returns:
            選択されたデバイス情報
            
        Raises:
            RuntimeError: 利用可能なデバイスがない場合
        """
        candidates = self.devices.copy()
        
        # タイプでフィルタ
        if preference != DeviceType.AUTO:
            candidates = [d for d in candidates if d.type == preference]
        
        # メモリ要件でフィルタ
        if required_memory_mb > 0:
            candidates = [
                d for d in candidates 
                if d.available_memory_mb >= required_memory_mb
            ]
        
        if not candidates:
            # フォールバック: CPU
            cpu_device = next((d for d in self.devices if d.type == DeviceType.CPU), None)
            if cpu_device:
                logger.warning("No suitable GPU found, falling back to CPU")
                return cpu_device
            raise RuntimeError("No available device found")
        
        # スコアリング
        def score_device(d: DeviceInfo) -> float:
            score = 0.0
            if d.type == DeviceType.CUDA:
                score += 100
                # メモリが多いほど高スコア
                score += d.available_memory_mb / 1000
                # Compute capabilityが高いほど高スコア
                if d.compute_capability:
                    major, minor = map(int, d.compute_capability.split('.'))
                    score += major * 10 + minor
            elif d.type == DeviceType.MPS:
                score += 50
                score += d.available_memory_mb / 1000
            return score
        
        best = max(candidates, key=score_device)
        self._current_device = best
        
        logger.info(f"Selected device: {best.name} ({best.type.name})")
        return best
    
    def get_torch_device(self, device_info: Optional[DeviceInfo] = None) -> torch.device:
        """
        PyTorchデバイスを取得
        
        Args:
            device_info: デバイス情報（Noneの場合は現在選択中のデバイス）
            
        Returns:
            torch.deviceオブジェクト
        """
        info = device_info or self._current_device
        if info is None:
            info = self.select_optimal_device()
        
        if info.type == DeviceType.CUDA:
            return torch.device(f"cuda:{info.id}")
        elif info.type == DeviceType.MPS:
            return torch.device("mps")
        return torch.device("cpu")
    
    def get_optimal_dtype(self, device_info: Optional[DeviceInfo] = None) -> torch.dtype:
        """
        デバイスに最適なdtypeを取得
        
        Args:
            device_info: デバイス情報
            
        Returns:
            torch.dtype（CUDA/MPS: float16, CPU: float32）
        """
        info = device_info or self._current_device
        if info is None:
            info = self.select_optimal_device()
        
        if info.type in (DeviceType.CUDA, DeviceType.MPS):
            return torch.float16
        return torch.float32
    
    def _get_cpu_memory(self) -> int:
        """CPUメモリを取得（MB）"""
        if PSUTIL_AVAILABLE:
            return psutil.virtual_memory().total // (1024 * 1024)
        return 8192  # デフォルト8GB
    
    def _get_gpu_free_memory(self, device_id: int) -> int:
        """GPU空きメモリを取得（MB）"""
        try:
            return torch.cuda.mem_get_info(device_id)[0] // (1024 * 1024)
        except Exception:
            return 0
    
    def get_device_list(self) -> List[Dict[str, Any]]:
        """デバイス一覧を取得"""
        return [
            {
                'id': d.id,
                'name': d.name,
                'type': d.type.name,
                'total_memory_mb': d.total_memory_mb,
                'available_memory_mb': d.available_memory_mb,
                'compute_capability': d.compute_capability,
                'is_available': d.is_available
            }
            for d in self.devices
        ]
    
    def refresh(self):
        """デバイス情報を更新"""
        self._scan_devices()


class DeviceContext:
    """
    デバイスコンテキストマネージャ
    
    使用例:
        with DeviceContext(required_memory_mb=4096) as ctx:
            model = MyModel().to(ctx.device)
            # 処理...
    """
    
    def __init__(self, preference: DeviceType = DeviceType.AUTO, required_memory_mb: int = 0):
        self.manager = MultiDeviceManager()
        self.preference = preference
        self.required_memory_mb = required_memory_mb
        self.device_info: Optional[DeviceInfo] = None
        self.device: Optional[torch.device] = None
        self.dtype: Optional[torch.dtype] = None
    
    def __enter__(self):
        self.device_info = self.manager.select_optimal_device(
            self.preference, 
            self.required_memory_mb
        )
        self.device = self.manager.get_torch_device(self.device_info)
        self.dtype = self.manager.get_optimal_dtype(self.device_info)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # クリーンアップ
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


if __name__ == "__main__":
    # テスト
    logging.basicConfig(level=logging.INFO)
    
    manager = MultiDeviceManager()
    
    print("=== Available Devices ===")
    for device in manager.get_device_list():
        print(f"  {device['type']}: {device['name']} ({device['available_memory_mb']}MB available)")
    
    print("\n=== Optimal Device Selection ===")
    optimal = manager.select_optimal_device()
    print(f"  Selected: {optimal.name}")
    print(f"  PyTorch device: {manager.get_torch_device(optimal)}")
    print(f"  Optimal dtype: {manager.get_optimal_dtype(optimal)}")
    
    print("\n=== Context Manager Test ===")
    with DeviceContext(required_memory_mb=1024) as ctx:
        print(f"  Device: {ctx.device}")
        print(f"  Dtype: {ctx.dtype}")
