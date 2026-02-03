"""
議事録生成ラッパーモジュール
meeting_minutes_generator.py の簡易インターフェースを提供
"""

import logging
from typing import List, Dict, Optional, Any
from pathlib import Path

# 既存のMeetingMinutesGeneratorをインポート
from meeting_minutes_generator import (
    MeetingMinutesGenerator as BaseGenerator,
    MeetingMinutes,
    Statement,
    StatementType,
    ActionItem,
    get_minutes_generator as get_base_generator
)

logger = logging.getLogger(__name__)


class MinutesGenerator:
    """
    議事録生成クラス（簡易インターフェース）
    meeting_minutes_generator.py のラッパー
    """

    def __init__(self):
        """初期化"""
        self._generator = BaseGenerator()
        logger.info("MinutesGenerator initialized")

    def generate(
        self,
        segments: List[Dict],
        title: str = "会議",
        date: Optional[str] = None,
        location: str = "",
        attendees: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        書き起こしから議事録を生成

        Args:
            segments: 書き起こしセグメント
            title: 会議タイトル
            date: 日付
            location: 場所
            attendees: 出席者リスト

        Returns:
            議事録データ（辞書形式）
        """
        minutes = self._generator.generate_minutes(
            segments=segments,
            title=title,
            date=date,
            location=location,
            attendees=attendees,
        )

        return {
            "title": minutes.title,
            "date": minutes.date,
            "location": minutes.location,
            "attendees": minutes.attendees,
            "agenda": minutes.agenda,
            "decisions": minutes.decisions,
            "confirmations": minutes.confirmations,
            "action_items": [
                {
                    "description": item.description,
                    "assignee": item.assignee,
                    "due_date": item.due_date,
                    "priority": item.priority,
                    "status": item.status,
                }
                for item in minutes.action_items
            ],
            "statements": [
                {
                    "speaker": stmt.speaker,
                    "text": stmt.text,
                    "timestamp": stmt.timestamp,
                    "statement_type": stmt.statement_type.value,
                }
                for stmt in minutes.statements
            ],
            "next_meeting": minutes.next_meeting,
            "notes": minutes.notes,
            "text_format": minutes.to_text(),
            "markdown_format": minutes.to_markdown(),
        }

    def generate_from_file(
        self,
        transcription_file: str,
        title: str = "会議",
        **kwargs
    ) -> Dict[str, Any]:
        """
        書き起こしファイルから議事録を生成

        Args:
            transcription_file: 書き起こしファイルパス（JSON）
            title: 会議タイトル
            **kwargs: その他のパラメータ

        Returns:
            議事録データ
        """
        import json

        with open(transcription_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        segments = data.get('segments', [])
        return self.generate(segments, title=title, **kwargs)

    def save_minutes(
        self,
        minutes_data: Dict[str, Any],
        output_path: str,
        format_type: str = "markdown"
    ) -> bool:
        """
        議事録をファイルに保存

        Args:
            minutes_data: 議事録データ
            output_path: 出力ファイルパス
            format_type: 形式 ('text', 'markdown', 'json')

        Returns:
            成功したかどうか
        """
        try:
            if format_type == "text":
                content = minutes_data.get("text_format", "")
            elif format_type == "markdown":
                content = minutes_data.get("markdown_format", "")
            elif format_type == "json":
                import json
                content = json.dumps(minutes_data, ensure_ascii=False, indent=2)
            else:
                logger.error(f"Unknown format: {format_type}")
                return False

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"Minutes saved to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save minutes: {e}")
            return False

    def extract_action_items(self, text: str) -> List[Dict[str, str]]:
        """
        テキストからアクションアイテムを抽出

        Args:
            text: 入力テキスト

        Returns:
            アクションアイテムリスト
        """
        # 単純な実装：行単位で解析
        action_items = []
        lines = text.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # アクションキーワードを検出
            action_keywords = ['する', '確認', '準備', '調整', '連絡', '報告', '依頼']
            if any(kw in line for kw in action_keywords):
                # 担当者を抽出
                import re
                assignee_match = re.search(r'([一-龠々〆ヵヶぁ-んァ-ンーa-zA-Z・]+)(?:さん|様|殿|くん|君)', line)
                assignee = assignee_match.group(1) if assignee_match else None

                action_items.append({
                    "description": line,
                    "assignee": assignee,
                    "due_date": None,
                    "priority": "中"
                })

        return action_items

    def classify_statements(self, statements: List[str]) -> Dict[str, List[str]]:
        """
        発言リストを分類

        Args:
            statements: 発言リスト

        Returns:
            分類された発言
        """
        classified = {
            "decisions": [],
            "confirmations": [],
            "action_items": [],
            "general": []
        }

        for stmt in statements:
            stmt_type = self._generator.classify_statement(stmt)

            if stmt_type == StatementType.DECISION:
                classified["decisions"].append(stmt)
            elif stmt_type == StatementType.CONFIRMATION:
                classified["confirmations"].append(stmt)
            elif stmt_type == StatementType.ACTION_ITEM:
                classified["action_items"].append(stmt)
            else:
                classified["general"].append(stmt)

        return classified


# グローバルインスタンス
_minutes_generator = None


def get_minutes_generator() -> MinutesGenerator:
    """
    議事録生成器のシングルトンインスタンスを取得

    Returns:
        MinutesGeneratorインスタンス
    """
    global _minutes_generator
    if _minutes_generator is None:
        _minutes_generator = MinutesGenerator()
    return _minutes_generator


def quick_generate(
    segments: List[Dict],
    title: str = "会議",
    **kwargs
) -> Dict[str, Any]:
    """
    簡易議事録生成関数

    Args:
        segments: 書き起こしセグメント
        title: 会議タイトル
        **kwargs: その他のパラメータ

    Returns:
        議事録データ
    """
    generator = get_minutes_generator()
    return generator.generate(segments, title=title, **kwargs)


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    print("=== Minutes Generator Test ===\n")

    generator = MinutesGenerator()

    # テストデータ
    test_segments = [
        {"speaker": "田中", "text": "本日の会議を始めます。議題は新規店舗開発についてです。", "start": 0},
        {"speaker": "佐藤", "text": "進捗状況を報告します。現時点で設計図は80%完成しています。", "start": 10},
        {"speaker": "山田", "text": "外壁材はタイルに決定しました。", "start": 30},
        {"speaker": "田中", "text": "佐藤さんに施工業者との調整をお願いします。来週金曜日までに。", "start": 45},
        {"speaker": "佐藤", "text": "承知しました。確認させていただきます。", "start": 55},
        {"speaker": "山田", "text": "予算について一点確認です。内装費は予定通りでしょうか。", "start": 60},
        {"speaker": "田中", "text": "次回は来週の月曜日に進捗確認を行いましょう。", "start": 80},
    ]

    # 議事録生成
    minutes = generator.generate(
        segments=test_segments,
        title="新規店舗開発会議",
        date="2026年2月3日 14:00",
        location="会議室A",
        attendees=["田中（PM）", "佐藤（設計）", "山田（工事）"]
    )

    print(f"Title: {minutes['title']}")
    print(f"Date: {minutes['date']}")
    print(f"Attendees: {', '.join(minutes['attendees'])}")
    print(f"\nDecisions ({len(minutes['decisions'])}):")
    for decision in minutes['decisions']:
        print(f"  - {decision}")

    print(f"\nConfirmations ({len(minutes['confirmations'])}):")
    for confirmation in minutes['confirmations']:
        print(f"  - {confirmation}")

    print(f"\nAction Items ({len(minutes['action_items'])}):")
    for item in minutes['action_items']:
        print(f"  - {item['description']}")
        print(f"    担当: {item['assignee']}, 期限: {item['due_date']}, 優先度: {item['priority']}")

    # テキスト形式を表示
    print("\n" + "=" * 60)
    print("TEXT FORMAT:")
    print("=" * 60)
    print(minutes['text_format'][:500] + "...")

    print("\n=== Minutes Generator Test Complete ===")
