"""
議事録自動生成モジュール
会議音声から構造化された議事録を自動生成
"""

import logging
import re
import threading
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class StatementType(Enum):
    """発言タイプ"""
    GENERAL = "一般"
    DECISION = "決定事項"
    CONFIRMATION = "確認事項"
    ACTION_ITEM = "アクションアイテム"
    QUESTION = "質問"
    ANSWER = "回答"
    REPORT = "報告"
    PROPOSAL = "提案"


@dataclass
class Statement:
    """発言データ"""
    speaker: str
    text: str
    timestamp: Optional[float] = None
    statement_type: StatementType = StatementType.GENERAL
    confidence: float = 1.0


@dataclass
class ActionItem:
    """アクションアイテム"""
    description: str
    assignee: Optional[str] = None
    due_date: Optional[str] = None
    priority: str = "中"  # 高/中/低
    status: str = "未対応"


@dataclass
class MeetingMinutes:
    """議事録データ"""
    title: str
    date: str
    location: str = ""
    attendees: List[str] = field(default_factory=list)
    agenda: List[str] = field(default_factory=list)
    statements: List[Statement] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    confirmations: List[str] = field(default_factory=list)
    action_items: List[ActionItem] = field(default_factory=list)
    next_meeting: str = ""
    notes: str = ""

    def to_text(self) -> str:
        """テキスト形式で出力"""
        lines = [
            "=" * 60,
            f"議事録: {self.title}",
            "=" * 60,
            f"日時: {self.date}",
            f"場所: {self.location}",
            "",
            "【出席者】",
        ]
        for attendee in self.attendees:
            lines.append(f"  - {attendee}")

        if self.agenda:
            lines.extend(["", "【議題】"])
            for i, item in enumerate(self.agenda, 1):
                lines.append(f"  {i}. {item}")

        lines.extend(["", "【議事内容】", ""])
        current_speaker = None
        for stmt in self.statements:
            if stmt.speaker != current_speaker:
                lines.append(f"\n[{stmt.speaker}]")
                current_speaker = stmt.speaker
            prefix = ""
            if stmt.statement_type == StatementType.DECISION:
                prefix = "[決定] "
            elif stmt.statement_type == StatementType.ACTION_ITEM:
                prefix = "[TODO] "
            elif stmt.statement_type == StatementType.CONFIRMATION:
                prefix = "[確認] "
            lines.append(f"  {prefix}{stmt.text}")

        if self.decisions:
            lines.extend(["", "【決定事項】"])
            for i, decision in enumerate(self.decisions, 1):
                lines.append(f"  {i}. {decision}")

        if self.confirmations:
            lines.extend(["", "【確認事項】"])
            for i, confirmation in enumerate(self.confirmations, 1):
                lines.append(f"  {i}. {confirmation}")

        if self.action_items:
            lines.extend(["", "【アクションアイテム】"])
            for i, item in enumerate(self.action_items, 1):
                assignee = f"担当: {item.assignee}" if item.assignee else "担当: 未割当"
                due = f"期限: {item.due_date}" if item.due_date else "期限: 未設定"
                lines.append(f"  {i}. {item.description}")
                lines.append(f"      ({assignee}, {due}, 優先度: {item.priority})")

        if self.next_meeting:
            lines.extend(["", f"【次回会議】{self.next_meeting}"])

        if self.notes:
            lines.extend(["", "【備考】", self.notes])

        lines.extend(["", "=" * 60, "End of Minutes"])
        return "\n".join(lines)

    def to_markdown(self) -> str:
        """Markdown形式で出力"""
        lines = [
            f"# 議事録: {self.title}",
            "",
            f"**日時:** {self.date}",
            f"**場所:** {self.location}",
            "",
            "## 出席者",
        ]
        for attendee in self.attendees:
            lines.append(f"- {attendee}")

        if self.agenda:
            lines.extend(["", "## 議題"])
            for item in self.agenda:
                lines.append(f"- {item}")

        lines.extend(["", "## 議事内容"])
        current_speaker = None
        for stmt in self.statements:
            if stmt.speaker != current_speaker:
                lines.append(f"\n### {stmt.speaker}")
                current_speaker = stmt.speaker
            prefix = ""
            if stmt.statement_type == StatementType.DECISION:
                prefix = "📝 **決定:** "
            elif stmt.statement_type == StatementType.ACTION_ITEM:
                prefix = "✅ **TODO:** "
            elif stmt.statement_type == StatementType.CONFIRMATION:
                prefix = "❓ **確認:** "
            lines.append(f"- {prefix}{stmt.text}")

        if self.decisions:
            lines.extend(["", "## 決定事項"])
            for decision in self.decisions:
                lines.append(f"- {decision}")

        if self.confirmations:
            lines.extend(["", "## 確認事項"])
            for confirmation in self.confirmations:
                lines.append(f"- {confirmation}")

        if self.action_items:
            lines.extend(["", "## アクションアイテム"])
            for item in self.action_items:
                assignee = item.assignee if item.assignee else "未割当"
                due = item.due_date if item.due_date else "未設定"
                lines.append(f"- [ ] {item.description} (@{assignee}, 期限: {due}, 優先度: {item.priority})")

        if self.next_meeting:
            lines.extend(["", f"## 次回会議\n{self.next_meeting}"])

        if self.notes:
            lines.extend(["", "## 備考", self.notes])

        return "\n".join(lines)


class MeetingMinutesGenerator:
    """議事録自動生成クラス"""

    # 検索範囲の制限
    AGENDA_SEARCH_LIMIT = 10  # 議題検索: 最初のN発言
    CLOSING_SEARCH_LIMIT = 20  # 締め検索: 最後のN発言

    # 決定事項を示すキーワードパターン
    DECISION_PATTERNS = [
        r"決定(?:しました|した|です|いたしました)",
        r"決め(?:ました|た|ます|ました)",
        r"確定(?:しました|した|です)",
        r"採用(?:します|する|しました|した)",
        r"採択(?:します|する|しました|した)",
        r"承認(?:します|する|しました|した)",
        r"合意(?:しました|した|です)",
        r"決裁(?:しました|した|です)",
        r"ということで(?:決定|確定|決め)",
        r"(?:方針|方針と|方針で|方向性)",
    ]

    # 確認事項を示すキーワードパターン
    CONFIRMATION_PATTERNS = [
        r"確認(?:しました|した|です|ですね|いたします|させてください)",
        r"(?:ご|御)?確認(?:を)?(?:お願い|ください|させて)",
        r"確認事項",
        r"確認(?:させて)?(?:いただき|もらい|いただきたい)",
        r"念のため確認",
        r"以下(?:を)?確認",
        r"一点確認",
    ]

    # アクションアイテム（TODO）を示すキーワードパターン
    ACTION_ITEM_PATTERNS = [
        r"(?:やって|行って|実施して|対応して|調整して|確認して|準備して)(?:もら|いただ|お願い)",
        r"担当(?:して|お願い|をお願い)",
        r"(?:お願い|依頼)(?:します|したい|いたします)",
        r"(?:お願い|依頼)いただ",
        r"引き受け(?:て|ていただ)",
        r"フォロー(?:して|お願い|いただ)",
        r"対応(?:を)?(?:お願い|いただ|して)",
        r"確認(?:を)?(?:お願い|いただ|して)",
        r"準備(?:を)?(?:お願い|いただ|して)",
        r"調整(?:を)?(?:お願い|いただ|して)",
        r"追加(?:で)?(?:お願い|いただ)",
        r"検討(?:を)?(?:お願い|いただ)",
        r"報告(?:を)?(?:お願い|いただ)",
        r"連絡(?:を)?(?:お願い|いただ)",
        r"確認取(?:って|ってお|らせて)",
        r"調査(?:を)?(?:お願い|いただ)",
        r"取りまとめ(?:を)?(?:お願い|いただ)",
        r"まとめ(?:を)?(?:お願い|いただ)",
    ]

    # 期限・日付パターン
    DATE_PATTERNS = [
        r"(?:(\d{1,2})月)?(\d{1,2})日(?:まで)?",
        r"来週(?:の)?(?:月|火|水|木|金|土|日)(?:曜日)?",
        r"今週(?:の)?(?:月|火|水|木|金|土|日)(?:曜日)?",
        r"明日",
        r"明後日",
        r"来月",
        r"今月末",
        r"来月末",
        r"期日",
        r"締め切り",
        r"〆切",
        r"デッドライン",
    ]

    # 優先度パターン
    PRIORITY_PATTERNS = {
        "高": [r"至急", r"緊急", r"急ぎ", r"優先", r"できるだけ早く", r"すぐに", r" ASAP", r"優先度高"],
        "低": [r"余裕があれば", r"時間があるとき", r"優先度低", r"後で良い", r"のちのち"],
    }

    # 報告パターン
    REPORT_PATTERNS = [
        r"報告(?:します|したい|させていただきます)",
        r"(?:現状|進捗|状況)(?:を)?報告",
        r"現在の状況",
        r"(?:進捗|進み具合)",
        r"現時点で",
    ]

    def __init__(self):
        """初期化"""
        self.compile_patterns()

    def compile_patterns(self):
        """正規表現パターンをコンパイル"""
        self.decision_regex = [re.compile(p) for p in self.DECISION_PATTERNS]
        self.confirmation_regex = [re.compile(p) for p in self.CONFIRMATION_PATTERNS]
        self.action_regex = [re.compile(p) for p in self.ACTION_ITEM_PATTERNS]
        self.date_regex = [re.compile(p) for p in self.DATE_PATTERNS]
        self.report_regex = [re.compile(p) for p in self.REPORT_PATTERNS]
        self.priority_regex = {
            level: [re.compile(p) for p in patterns]
            for level, patterns in self.PRIORITY_PATTERNS.items()
        }

    def generate_minutes(
        self,
        segments: List[Dict],
        title: str = "会議",
        date: Optional[str] = None,
        location: str = "",
        attendees: Optional[List[str]] = None,
    ) -> MeetingMinutes:
        """
        書き起こしセグメントから議事録を生成

        Args:
            segments: 書き起こしセグメントのリスト
            title: 会議タイトル
            date: 日付（Noneの場合は今日）
            location: 場所
            attendees: 出席者リスト

        Returns:
            MeetingMinutesオブジェクト
        """
        if date is None:
            date = datetime.now().strftime("%Y年%m月%d日 %H:%M")

        minutes = MeetingMinutes(
            title=title,
            date=date,
            location=location,
            attendees=attendees or [],
        )

        # セグメントを処理
        for segment in segments:
            speaker = segment.get("speaker", "Unknown")
            text = segment.get("text", "").strip()
            timestamp = segment.get("start")

            if not text:
                continue

            # 発言タイプを判定
            stmt_type = self.classify_statement(text)

            statement = Statement(
                speaker=speaker,
                text=text,
                timestamp=timestamp,
                statement_type=stmt_type,
            )
            minutes.statements.append(statement)

            # 決定事項を抽出
            if stmt_type == StatementType.DECISION:
                decision_text = self.extract_decision_text(text)
                if decision_text and decision_text not in minutes.decisions:
                    minutes.decisions.append(decision_text)

            # 確認事項を抽出
            elif stmt_type == StatementType.CONFIRMATION:
                confirmation_text = self.extract_confirmation_text(text)
                if confirmation_text and confirmation_text not in minutes.confirmations:
                    minutes.confirmations.append(confirmation_text)

            # アクションアイテムを抽出
            elif stmt_type == StatementType.ACTION_ITEM:
                action_item = self.extract_action_item(text, speaker)
                minutes.action_items.append(action_item)

        # 議題を推測
        minutes.agenda = self.extract_agenda(minutes.statements)

        # 次回会議を検出
        minutes.next_meeting = self.extract_next_meeting(minutes.statements)

        logger.info(
            f"Generated minutes: {len(minutes.statements)} statements, "
            f"{len(minutes.decisions)} decisions, "
            f"{len(minutes.action_items)} action items"
        )

        return minutes

    def classify_statement(self, text: str) -> StatementType:
        """
        発言テキストからタイプを分類

        Args:
            text: 発言テキスト

        Returns:
            StatementType
        """
        # 決定事項の判定
        for pattern in self.decision_regex:
            if pattern.search(text):
                return StatementType.DECISION

        # アクションアイテムの判定
        for pattern in self.action_regex:
            if pattern.search(text):
                return StatementType.ACTION_ITEM

        # 確認事項の判定
        for pattern in self.confirmation_regex:
            if pattern.search(text):
                return StatementType.CONFIRMATION

        # 報告の判定
        for pattern in self.report_regex:
            if pattern.search(text):
                return StatementType.REPORT

        return StatementType.GENERAL

    def extract_decision_text(self, text: str) -> str:
        """
        決定事項テキストを抽出

        Args:
            text: 元のテキスト

        Returns:
            抽出された決定事項
        """
        # 「決定しました」などの部分を除去して、実際の内容を抽出
        cleaned = text
        for pattern in self.DECISION_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned)

        # 余分な文字を除去
        cleaned = cleaned.strip(" 　、。") 
        return cleaned if cleaned else text

    def extract_confirmation_text(self, text: str) -> str:
        """
        確認事項テキストを抽出

        Args:
            text: 元のテキスト

        Returns:
            抽出された確認事項
        """
        # 「確認してください」などの部分を除去
        cleaned = text
        for pattern in self.CONFIRMATION_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned)

        cleaned = cleaned.strip(" 　、。")
        return cleaned if cleaned else text

    def extract_action_item(self, text: str, default_speaker: str) -> ActionItem:
        """
        アクションアイテムを抽出

        Args:
            text: 発言テキスト
            default_speaker: デフォルトの担当者（発言者）

        Returns:
            ActionItemオブジェクト
        """
        description = text

        # 担当者を抽出（「〇〇さん」「〇〇様」など）
        assignee = None
        assignee_patterns = [
            r"([一-龠々〆ヵヶぁ-んァ-ンーa-zA-Z・]+)(?:さん|様|殿|くん|君)",
            r"([一-龠々〆ヵヶぁ-んァ-ンーa-zA-Z・]+)(?:担当|さんに|様に|殿に)",
        ]
        for pattern in assignee_patterns:
            match = re.search(pattern, text)
            if match:
                assignee = match.group(1)
                break

        if not assignee:
            assignee = default_speaker

        # 期限を抽出
        due_date = None
        for pattern in self.date_regex:
            match = pattern.search(text)
            if match:
                due_date = match.group(0)
                break

        # 優先度を判定
        priority = "中"
        for level, patterns in self.priority_regex.items():
            for pattern in patterns:
                if pattern.search(text):
                    priority = level
                    break
            if priority != "中":
                break

        return ActionItem(
            description=description,
            assignee=assignee,
            due_date=due_date,
            priority=priority,
        )

    def extract_agenda(self, statements: List[Statement]) -> List[str]:
        """
        議題を推測・抽出

        Args:
            statements: 発言リスト

        Returns:
            議題リスト
        """
        agenda_keywords = [
            "議題", "アジェンダ", "今日のテーマ", "本日のテーマ",
            "話し合いたい", "検討したい", "相談したい",
        ]

        agendas = []
        for stmt in statements[:self.AGENDA_SEARCH_LIMIT]:
            for keyword in agenda_keywords:
                if keyword in stmt.text:
                    # キーワード以降を抽出
                    idx = stmt.text.find(keyword)
                    agenda_text = stmt.text[idx:].strip(" 　、。：")
                    if len(agenda_text) > 5:  # 短すぎるものは除外
                        agendas.append(agenda_text)
                    break

        return agendas[:5]  # 最大5項目

    def extract_next_meeting(self, statements: List[Statement]) -> str:
        """
        次回会議の情報を抽出

        Args:
            statements: 発言リスト

        Returns:
            次回会議情報
        """
        next_patterns = [
            r"次回(?:は|の)?(.{2,20})(?:に|で|を)?(?:行い|開催|実施)",
            r"次(?:は|の会議は)(.{2,20})(?:に|で)",
            r"再来週(?:の)?(.{2,15})(?:に|で)",
        ]

        for stmt in statements[-self.CLOSING_SEARCH_LIMIT:]:
            for pattern in next_patterns:
                match = re.search(pattern, stmt.text)
                if match:
                    return match.group(0)

        return ""

    def extract_attendees_from_segments(self, segments: List[Dict]) -> List[str]:
        """
        セグメントから話者リストを抽出

        Args:
            segments: 書き起こしセグメント

        Returns:
            話者リスト（重複なし）
        """
        speakers = set()
        for segment in segments:
            speaker = segment.get("speaker", "Unknown")
            if speaker and speaker != "Unknown":
                speakers.add(speaker)
        return sorted(list(speakers))


# グローバルインスタンス
_minutes_generator = None
_minutes_generator_lock = threading.Lock()


def get_minutes_generator() -> MeetingMinutesGenerator:
    """
    議事録生成器のシングルトンインスタンスを取得

    Returns:
        MeetingMinutesGeneratorインスタンス
    """
    global _minutes_generator
    if _minutes_generator is None:
        with _minutes_generator_lock:
            if _minutes_generator is None:
                _minutes_generator = MeetingMinutesGenerator()
    return _minutes_generator


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    generator = MeetingMinutesGenerator()

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

    minutes = generator.generate_minutes(
        segments=test_segments,
        title="新規店舗開発会議",
        date="2026年2月3日 14:00",
        location="会議室A",
    )

    print("=== Meeting Minutes (Text) ===\n")
    print(minutes.to_text())

    print("\n\n=== Meeting Minutes (Markdown) ===\n")
    print(minutes.to_markdown())
