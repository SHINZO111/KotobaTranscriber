"""
シンプルなVAD（Voice Activity Detection）モジュール
エネルギーベースの音声検出
"""

import numpy as np
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class SimpleVAD:
    """エネルギーベースのシンプルなVAD"""

    def __init__(self,
                 threshold: float = 0.01,
                 min_speech_duration: float = 0.3,
                 min_silence_duration: float = 1.0,
                 sample_rate: int = 16000):
        """
        初期化

        Args:
            threshold: 音声判定の閾値（RMS値）
            min_speech_duration: 最小音声継続時間（秒）
            min_silence_duration: 最小無音継続時間（秒）
            sample_rate: サンプリングレート
        """
        self.threshold = threshold
        self.min_speech_duration = min_speech_duration
        self.min_silence_duration = min_silence_duration
        self.sample_rate = sample_rate

        # 状態管理
        self.is_speech = False
        self.speech_start_time = 0.0
        self.silence_start_time = 0.0
        self.current_time = 0.0

        logger.info(f"SimpleVAD initialized: threshold={threshold}, "
                   f"min_speech={min_speech_duration}s, "
                   f"min_silence={min_silence_duration}s")

    def calculate_energy(self, audio: np.ndarray) -> float:
        """音声のエネルギー（RMS）を計算"""
        return float(np.sqrt(np.mean(audio**2)))

    def is_speech_present(self, audio: np.ndarray) -> Tuple[bool, float]:
        """
        音声が存在するか判定

        Args:
            audio: 音声データ（NumPy配列）

        Returns:
            (音声存在フラグ, エネルギー値)
        """
        energy = self.calculate_energy(audio)

        # チャンクの時間長を計算
        chunk_duration = len(audio) / self.sample_rate
        self.current_time += chunk_duration

        # エネルギーが閾値を超えているかチェック
        has_energy = energy > self.threshold

        if has_energy:
            # 音声検出
            if not self.is_speech:
                # 無音→音声への遷移
                self.speech_start_time = self.current_time
                logger.debug(f"Speech started at {self.current_time:.2f}s (energy: {energy:.4f})")

            self.is_speech = True
            self.silence_start_time = 0.0

        else:
            # 無音検出
            if self.is_speech:
                # 音声→無音への遷移
                if self.silence_start_time == 0.0:
                    self.silence_start_time = self.current_time
                    logger.debug(f"Silence started at {self.current_time:.2f}s (energy: {energy:.4f})")

                # 一定時間無音が続いたら音声終了と判定
                silence_duration = self.current_time - self.silence_start_time
                if silence_duration >= self.min_silence_duration:
                    logger.debug(f"Speech ended at {self.current_time:.2f}s "
                               f"(silence duration: {silence_duration:.2f}s)")
                    self.is_speech = False
                    self.speech_start_time = 0.0

        return self.is_speech, energy

    def reset(self):
        """状態リセット"""
        self.is_speech = False
        self.speech_start_time = 0.0
        self.silence_start_time = 0.0
        self.current_time = 0.0
        logger.debug("VAD state reset")


class AdaptiveVAD(SimpleVAD):
    """適応的閾値を持つVAD（ノイズレベルに応じて自動調整）"""

    def __init__(self,
                 initial_threshold: float = 0.01,
                 adaptation_rate: float = 0.1,
                 **kwargs):
        """
        初期化

        Args:
            initial_threshold: 初期閾値
            adaptation_rate: 適応速度（0.0〜1.0）
            **kwargs: SimpleVADのパラメータ
        """
        super().__init__(threshold=initial_threshold, **kwargs)
        self.adaptation_rate = adaptation_rate
        self.noise_level = initial_threshold
        self.energy_history = []
        self.history_size = 50

        logger.info(f"AdaptiveVAD initialized with adaptation_rate={adaptation_rate}")

    def is_speech_present(self, audio: np.ndarray) -> Tuple[bool, float]:
        """適応的閾値で音声判定"""
        energy = self.calculate_energy(audio)

        # エネルギー履歴を記録
        self.energy_history.append(energy)
        if len(self.energy_history) > self.history_size:
            self.energy_history.pop(0)

        # ノイズレベルを推定（履歴の下位25%の平均）
        if len(self.energy_history) >= 10:
            sorted_energies = sorted(self.energy_history)
            lower_quartile = sorted_energies[:len(sorted_energies)//4]
            estimated_noise = np.mean(lower_quartile)

            # 適応的に閾値を更新
            self.noise_level = (
                self.adaptation_rate * estimated_noise +
                (1 - self.adaptation_rate) * self.noise_level
            )

            # 閾値をノイズレベルの2〜3倍に設定
            self.threshold = max(self.noise_level * 2.5, 0.005)

        # 親クラスのメソッドを呼び出し
        return super().is_speech_present(audio)


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    # テスト用音声データ生成
    sample_rate = 16000
    duration = 5  # 5秒

    # 無音 → 音声 → 無音のパターン
    silence1 = np.random.normal(0, 0.005, sample_rate * 1)  # 1秒無音
    speech = np.sin(2 * np.pi * 440 * np.arange(sample_rate * 2) / sample_rate) * 0.3  # 2秒音声
    silence2 = np.random.normal(0, 0.005, sample_rate * 2)  # 2秒無音

    test_audio = np.concatenate([silence1, speech, silence2])

    # VADテスト
    print("\n=== SimpleVAD Test ===")
    vad = SimpleVAD(threshold=0.01, min_silence_duration=0.5, sample_rate=sample_rate)

    # 0.1秒ごとにチェック
    chunk_size = sample_rate // 10
    for i in range(0, len(test_audio), chunk_size):
        chunk = test_audio[i:i+chunk_size]
        if len(chunk) < chunk_size:
            break

        is_speech, energy = vad.is_speech_present(chunk)
        time_sec = i / sample_rate
        print(f"Time: {time_sec:.2f}s | Energy: {energy:.4f} | Speech: {is_speech}")

    # AdaptiveVADテスト
    print("\n=== AdaptiveVAD Test ===")
    adaptive_vad = AdaptiveVAD(
        initial_threshold=0.01,
        adaptation_rate=0.2,
        min_silence_duration=0.5,
        sample_rate=sample_rate
    )

    for i in range(0, len(test_audio), chunk_size):
        chunk = test_audio[i:i+chunk_size]
        if len(chunk) < chunk_size:
            break

        is_speech, energy = adaptive_vad.is_speech_present(chunk)
        time_sec = i / sample_rate
        print(f"Time: {time_sec:.2f}s | Energy: {energy:.4f} | "
              f"Threshold: {adaptive_vad.threshold:.4f} | Speech: {is_speech}")

    print("\nテスト完了")
