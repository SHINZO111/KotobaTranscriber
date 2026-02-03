"""
建設業用語辞書モジュール
AGEC株式会社の建設業・CM業務に最適化された専門用語管理
"""

import logging
import json
from pathlib import Path
from typing import List, Dict, Optional, Set
import re

logger = logging.getLogger(__name__)


class ConstructionVocabulary:
    """建設業用語辞書管理クラス"""

    # 標準労務費関連用語（令和6年度 建設工事用標準単価）
    STANDARD_LABOR_TERMS = [
        # 職種・工種
        "普通作業員", "土木作業員", "型枠大工", "鉄筋工", "コンクリート工",
        "仕上工", "とび工", "配管工", "電気工", "通信工",
        "溶接工", "塗装工", "防水工", "タイル工", "ガラス工",
        "屋根葺き工", "シーリング工", "断熱工", "内装仕上工", "外装仕上工",
        "運転手", "整地工", "緑化工", "造園工", "舗装工",
        "採土工", "石工", "木工", "畳工", "カーテン工",
        "サッシ工", "建具工", "冷暖房工", "給排水設備工", "消防設備工",
        "エレベーター工", "エスカレーター工", "清掃員", "警備員", "現場代理人",
        "現場監督", "施工管理技士", "主任技術者", "監理技術者", "品質管理責任者",
        "安全管理責任者", "環境管理責任者", "測量士", "測量士補", "建築士",
        "構造設計一級建築士", "設備設計一級建築士", "土木施工管理技士", "建築施工管理技士",
        "電気工事施工管理技士", "管工事施工管理技士", "造園施工管理技士",

        # 賃金・費用関連
        "標準労務費", "現場労務費", "間接労務費", "直接労務費", "歩掛",
        "基準内賃金", "基準外賃金", "手当", "諸手当", "通勤手当",
        "現場手当", "資格手当", "職能手当", "家族手当", "住宅手当",
        "食事手当", "安全手当", "休業手当", "賃金日額", "賃金月額",
        "社会保険料", "健康保険料", "厚生年金保険料", "雇用保険料", "労災保険料",
        "建設業退職金共済", "建退共", "福利厚生費", "教育訓練費", "安全衛生費",
        "休憩時間", "残業時間", "法定外残業", "休日割増", "深夜割増",
        "時間外労働", "休日労働", "深夜労働", "36協定", "変形労働時間制",

        # 労働時間・休暇
        "所定労働時間", "実労働時間", "年間総労働時間", "年間所定労働日数",
        "夏季休暇", "年末年始休暇", "有給休暇", "慶弔休暇", "介護休暇",
        "出産休暇", "育児休暇", "生理休暇", "特別休暇", "リフレッシュ休暇",

        # 建設業法関連
        "建設業法", "建設業許可", "特定建設業", "一般建設業", "営業所",
        "建設業許可番号", "経営事項審査", "建設業登録", "建設業退職金共済",
        "建設労働者", "常用勤務者", "特定技能", "技能実習", "外国人建設労働者",
    ]

    # 建設業法・工事関連専門用語
    CONSTRUCTION_LAW_TERMS = [
        # 法令・規制
        "建築基準法", "建築確認", "建築基準適合証明", "建築検査", "竣工検査",
        "消防法", "消防検査", "消防設備検査", "避難検証", "性能評価",
        "都市計画法", "開発行為", "開発許可", "土地区画整理法", "新住宅市街地開発法",
        "工業団地造成法", "自然公園法", "景観条例", "屋外広告物条例",
        "土壌汚染対策法", "石綿障害予防規則", "ダイオキシン対策特別措置法",
        "建設リサイクル法", "建設発生土", "建設廃棄物", "産業廃棄物",
        "建設機械", "小型移動式クレーン", "高所作業車", "ショベルローダー", "フォークリフト",
        "発電機", "コンプレッサー", "溶接機", "コンクリートミキサー", "プレカット材",

        # 工事種別
        "建築工事", "土木工事", "電気工事", "機械設備工事", "管工事",
        "舗装工事", "外構工事", "解体工事", "伐採工事", "除染工事",
        "耐震補強工事", "リニューアル工事", "改修工事", "修繕工事", "保守工事",
        "新築工事", "増築工事", "改築工事", "建替工事", "曳家工事",
        "マンション大規模修繕", "ビル大規模改修", "医院・クリニック内装工事", "飲食店内装工事",
        "店舗内装工事", "オフィス内装工事", "倉庫内装工事", "工場内装工事",

        # 設計・施工管理
        "基本設計", "実施設計", "施工設計", "詳細設計", "設計図書",
        "仕様書", "積算書", "見積書", "発注書", "契約書",
        "請負契約", "元請", "下請", "孫請", "一次下請", "二次下請",
        "建設業経理士", "経理事務所", "支払保証", "保証金", "前渡金保証",
        "工事請負代金", "中間支払", "検収", "竣工引渡", "引渡検査",
        "完成保証", "瑕疵担保", "履行保証", "工事完成引渡証明書", "保証期間",
        "設計監理", "現場監理", "工程管理", "品質管理", "安全管理",
        "原価管理", "資材管理", "機材管理", "労務管理", "環境管理",
        "文書管理", "図面管理", "写真管理", "記録管理", "建設CALS/EC",
        "施工写真", "工事記録", "安全パトロール", "品質パトロール", "工程会議",
        "安全会議", "品質会議", "打合せ会議", "現場打合せ", "定例打合せ",
        "変更確認", "追加確認", "減額確認", "工事変更", "設計変更",
        "仮設計", "正式設計", "確認申請", "建築確認申請", "消防確認申請",

        # 建築構造
        "鉄骨造", "鉄筋コンクリート造", "鉄骨鉄筋コンクリート造", "木造", "軽量鉄骨造",
        "プレストレストコンクリート造", "ブロック造", "レンガ造", "石造", "土壁造",
        "鉄骨", "柱", "梁", "スラブ", "床版", "壁体", "基礎", "杭",
        "ラーメン構造", "壁式構造", "ブレース", "免震構造", "制震構造",
        "耐力壁", "間仕切り", "エレベーターシャフト", "階段室", "非常階段",
        "窓", "玄関", "勝手口", "バルコニー", "テラス", "バルコニー手すり",
        "屋上", "屋根", "雨樋", "換気口", "採光口", "防火設備", "準防火設備",

        # 設備機器
        "給水設備", "給湯設備", "排水設備", "通風設備", "換気設備",
        "空調設備", "冷房設備", "暖房設備", "エレベーター", "エスカレーター",
        "電気設備", "照明設備", "コンセント", "配電盤", "分電盤",
        "消防設備", "消火栓", "スプリンクラー", "自動火災報知設備", "避難設備",
        "アスベスト", "ダイオキシン", "PCB", "鉛", "シックハウス",
    ]

    # コスト管理用語
    COST_MANAGEMENT_TERMS = [
        # 積算・見積
        "単価", "数量", "金額", "直接費", "間接費", "共通仮設費", "現場管理費",
        "一般管理費", "事務所費", "諸経費", "消費税", "外税", "内税",
        "積算", "概算", "見積", "原価積算", "標準原価", "予定原価",
        "工事原価", "材料費", "外注費", "機械使用料", "運搬費",
        "図面積算", "現場計測", "出来高", "出来高報告", "出来高管理",
        "発注積算", "仮設費積算", "安全費積算", "品質費積算", "環境費積算",

        # 資材・購買
        "材料", "資材", "部材", "設備機器", "什器", "備品",
        "発注", "購買", "仕入", "納品", "検収", "倉庫管理",
        "在庫管理", "発注残", "納期管理", "納期回答", "納期遅延",
        "見積依頼", "RFQ", "発注書", "発注請書", "注文書", "注文請書",
        "納品書", "検収書", "請求書", "受領書", "領収書",
        "アンカーボルト", "補強筋", "型枠材", "型枠支保工", "シート",
        "養生シート", "養生材", "覆工", "保護材", "シーリング材",
        "防水シート", "断熱材", "吸音材", "防音材", "耐火被覆",

        # 外注・協力会社
        "外注", "外注先", "協力業者", "専門工事業者", "指定業者",
        "元請", "一次", "二次", "三次", "下請",
        "協定単価", "出来高単価", "日額単価", "建設単価協会", "建設物価調査会",
        "契約単価", "単価契約", "一括契約", "請負契約", "準委任契約",
        "定期契約", "単発契約", "長期契約", "フレーム契約",
        "技術者派遣", "人材派遣", "労働者派遣", "特定技能", "技能実習生",
        "協力会社評価", "技術力評価", "品質評価", "安全評価", "環境評価",
        "原価低減", "VA", "VE", "バリューエンジニアリング", "コストダウン",
        "ロス削減", "ムダ削減", "在庫削減", "納期短縮", "品質向上",

        # 工事費項目
        "直接工事費", "共通仮設費", "現場管理費", "一般管理費", "利益",
        "設計料", "監理料", "調査料", "測量料", "地質調査費",
        "調査費", "試験費", "検査費", "品質試験費", "安全管理費",
        "環境対策費", "近隣対策費", "防災対策費", "交通対策費", "安全対策費",
        "騒音対策", "振動対策", "粉じん対策", "悪臭対策", "排水対策",
        "解体費", "撤去費", "運搬費", "処分費", "リサイクル費",
        "仮設道路", "仮設電気", "仮設水道", "仮設通信", "仮設トイレ",
        "囲い", "フェンス", "カーテン", "ネット", "シート",
        "看板", "標識", "案内板", "標示板", "安全標語",

        # 機械器具賃率
        "建設機械賃率", "重機", "建設機械", "持込機械", "レンタル機械",
        "台班", "作業台班", "待機台班", "移動台班", "運搬台班",
        "クレーン", "タワークレーン", "ラフタークレーン", "オールテレーン", "クローラークレーン",
        "油圧ショベル", "ブルドーザー", "ホイールローダー", "ダンプトラック", "ミキサー車",
        "ポンプ車", "アスファルトフィニッシャー", "ロードローラー", "振動ローラー", "タイヤローラー",
        "杭打機", "杭抜機", "土留め機", "土のう充填機", "トレンチャー",
        "コンクリートポンプ", "コンクリートミキサー", "コンクリートバイブレーター", "コンクリートカッター", "コア抜き機",
        "溶接機", "エンジン溶接機", "半自動溶接機", "TIG溶接機", "プラズマカッター",
        "発電機", "コンプレッサー", "照明灯車", "高所作業車", "高所作業台車",
        "リフト", "フォークリフト", "スカイマスター", "ブームリフト", "シザースリフト",
        "エレベーター", "リフター", "ウインチ", "チェーンブロック", "電動ホイスト",
        "電動工具", "エア工具", "油圧工具", "計測機器", "測量機器",
        "全測", "レベル", "セオドライト", "GPS測量機", "レーザー墨出し器",
        "レーザー距離計", "デジタルレベル", "ドローン測量", "3Dレーザースキャナー", "BIM/CIM",
    ]

    # AGEC社内用語・略語
    AGEC_SPECIFIC_TERMS = [
        # CM関連
        "CM", "コンストラクションマネジメント", "CM業務", "代理店", "店舗開発",
        "出店支援", "店舗設計", "設計監理", "施工監理", "品質管理",
        "コスト管理", "スケジュール管理", "工程管理", "安全管理", "文書管理",
        "業務委託", "技術派遣", "専門家派遣", "技術サポート", "技術相談",
        "設計段階", "施工段階", "竣工段階", "引渡段階", "アフターメンテナンス",
        "基本設計", "実施設計", "施工設計", "店舗デザイン", "内装デザイン",
        "ファサード", "サイン計画", "什器計画", "照明計画", "カラープラン",
        "FF&E", "建築", "内装", "厨房", "機械", "電気", "設備",
        "専門工事", "専門設計", "専門監理", "専門相談", "技術審査",

        # プロジェクト管理
        "プロジェクト", "プロジェクト管理", "プロジェクトマネージャー", "PM",
        "アカウントマネージャー", "AM", "営業", "開発", "設計", "監理",
        "進捗管理", "予算管理", "品質管理", "リスク管理", "変更管理",
        "ステークホルダー", "打合せ", "会議", "報告", "稟議",
        "工場打合せ", "現場打合せ", "定例打合せ", "臨時打合せ", "緊急打合せ",
        "週次報告", "月次報告", "四半期報告", "最終報告", "竣工報告",
        "事業計画", "出店計画", "開発計画", "施工計画", "営業計画",

        # 店舗業種別
        "飲食店", "ファストフード", "ファミリーレストラン", "居酒屋", "カフェ",
        "コンビニ", "ドラッグストア", "スーパーマーケット", "ホームセンター", "100円ショップ",
        "クリニック", "医院", "歯科医院", "薬局", "調剤薬局",
        "フィットネス", "ジム", "スポーツクラブ", "ヨガスタジオ", "プール",
        "美容院", "理容店", "ネイルサロン", "エステサロン", "マッサージ店",
        "学習塾", "英会話教室", "幼児教室", "音楽教室", "ダンス教室",
        "ペットショップ", "動物病院", "ホテル", "旅館", "ゲストハウス",
        "銀行", "証券会社", "保険会社", "不動産会社", "賃貸管理",
        "コインパーキング", "レンタカー", "ガソリンスタンド", "洗車場", "車検場",
    ]

    def __init__(self, vocabulary_file: Optional[str] = None):
        """
        初期化

        Args:
            vocabulary_file: 語彙ファイルのパス（Noneの場合はデフォルト）
        """
        if vocabulary_file is None:
            vocabulary_file = "config/construction_vocabulary.json"

        self.vocabulary_file = Path(vocabulary_file)
        self.hotwords: List[str] = []
        self.replacements: Dict[str, str] = {}
        self.category_vocabularies: Dict[str, List[str]] = {}

        self.load_vocabulary()
        logger.info(f"ConstructionVocabulary initialized with {len(self.hotwords)} hotwords")

    def load_vocabulary(self):
        """語彙ファイルをロード（存在しない場合はデフォルト作成）"""
        if not self.vocabulary_file.exists():
            logger.info("Construction vocabulary file not found, creating default...")
            self.create_default_vocabulary()
            return

        try:
            with open(self.vocabulary_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.hotwords = data.get('hotwords', [])
            self.replacements = data.get('replacements', {})
            self.category_vocabularies = data.get('categories', {})

            logger.info(f"Loaded {len(self.hotwords)} construction terms from {self.vocabulary_file}")

        except Exception as e:
            logger.error(f"Failed to load construction vocabulary: {e}")
            self.create_default_vocabulary()

    def save_vocabulary(self):
        """語彙ファイルを保存"""
        try:
            data = {
                'hotwords': self.hotwords,
                'replacements': self.replacements,
                'categories': self.category_vocabularies
            }

            self.vocabulary_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.vocabulary_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"Saved construction vocabulary to {self.vocabulary_file}")

        except Exception as e:
            logger.error(f"Failed to save vocabulary: {e}")

    def create_default_vocabulary(self):
        """デフォルトの建設業用語辞書を作成"""
        # すべての用語をマージ
        all_terms = (
            self.STANDARD_LABOR_TERMS +
            self.CONSTRUCTION_LAW_TERMS +
            self.COST_MANAGEMENT_TERMS +
            self.AGEC_SPECIFIC_TERMS
        )

        # 重複を削除
        self.hotwords = sorted(list(set(all_terms)))

        # カテゴリ別に整理
        self.category_vocabularies = {
            'standard_labor': self.STANDARD_LABOR_TERMS,
            'construction_law': self.CONSTRUCTION_LAW_TERMS,
            'cost_management': self.COST_MANAGEMENT_TERMS,
            'agec_specific': self.AGEC_SPECIFIC_TERMS
        }

        # よくある誤認識の修正ルール
        self.replacements = {
            # 標準労務費関連
            "ほおがけ": "歩掛",
            "きじゅんないちんぎん": "基準内賃金",
            "けんせつたいきょきょう": "建設退職共済",
            "けんたいきょう": "建退共",

            # 建設業法関連
            "けんちくかくにん": "建築確認",
            "しょうぼうかくにん": "消防確認",
            "ぜんしん": "全測",
            "たいせつ": "耐震",
            "ばりふり": "バリフリー",

            # CM関連
            "こんまね": "コンストラクションマネジメント",
            "しーえむ": "CM",
            "ぴーえむ": "PM",
            "えふえふいー": "FF&E",
            "びーあいえむ": "BIM",
            "しーあいえむ": "CIM",

            # 工事関連
            "こんくりーと": "コンクリート",
            "てつきん": "鉄筋",
            "かたわく": "型枠",
            "しあげ": "仕上",
            "とび": "とび工",
            "ぐい": "杭",

            # その他専門用語
            "あるふぁ": "アルファ",
            "べーた": "ベータ",
            "がんま": "ガンマ",
            "でるた": "デルタ",
            "あーるえふきゅー": "RFQ",
            "ぶいいー": "VE",
            "ぶいえー": "VA",
        }

        self.save_vocabulary()

    def get_whisper_prompt(self, category: Optional[str] = None) -> str:
        """
        Whisperの初期プロンプトを生成

        Args:
            category: カテゴリ指定（standard_labor, construction_law, cost_management, agec_specific）

        Returns:
            初期プロンプト文字列
        """
        if category and category in self.category_vocabularies:
            words = self.category_vocabularies[category]
        else:
            words = self.hotwords

        # プロンプトは最大244トークン程度に制限
        if len(words) > 80:
            words = words[:80]

        if words:
            prompt = "建設業・CM業務の専門用語に注意: " + "、".join(words[:30])
            return prompt

        return ""

    def apply_replacements(self, text: str) -> str:
        """
        テキストに置換ルールを適用

        Args:
            text: 入力テキスト

        Returns:
            置換後のテキスト
        """
        result = text

        for wrong, correct in self.replacements.items():
            pattern = r'\b' + re.escape(wrong) + r'\b'
            result = re.sub(pattern, correct, result, flags=re.IGNORECASE)

        return result

    def add_term(self, term: str, category: str = "custom"):
        """
        用語を追加

        Args:
            term: 追加する用語
            category: カテゴリ名
        """
        if term and term not in self.hotwords:
            self.hotwords.append(term)
            self.hotwords.sort()

            if category not in self.category_vocabularies:
                self.category_vocabularies[category] = []
            if term not in self.category_vocabularies[category]:
                self.category_vocabularies[category].append(term)

            self.save_vocabulary()
            logger.info(f"Added construction term: {term} ({category})")

    def add_replacement(self, wrong: str, correct: str):
        """
        置換ルールを追加

        Args:
            wrong: 誤認識される単語
            correct: 正しい単語
        """
        self.replacements[wrong] = correct
        self.save_vocabulary()
        logger.info(f"Added replacement: '{wrong}' -> '{correct}'")

    def get_terms_by_category(self, category: str) -> List[str]:
        """
        カテゴリ別の用語リストを取得

        Args:
            category: カテゴリ名

        Returns:
            用語リスト
        """
        return self.category_vocabularies.get(category, [])

    def get_all_categories(self) -> List[str]:
        """
        全カテゴリリストを取得

        Returns:
            カテゴリ名のリスト
        """
        return list(self.category_vocabularies.keys())

    def search_terms(self, keyword: str) -> List[str]:
        """
        キーワードで用語を検索

        Args:
            keyword: 検索キーワード

        Returns:
            一致した用語リスト
        """
        keyword_lower = keyword.lower()
        return [term for term in self.hotwords if keyword_lower in term.lower()]


# グローバルインスタンス
_construction_vocab = None


def get_construction_vocabulary(vocabulary_file: Optional[str] = None) -> ConstructionVocabulary:
    """
    建設業用語辞書のシングルトンインスタンスを取得

    Args:
        vocabulary_file: 語彙ファイルのパス

    Returns:
        ConstructionVocabularyインスタンス
    """
    global _construction_vocab
    if _construction_vocab is None:
        _construction_vocab = ConstructionVocabulary(vocabulary_file)
    return _construction_vocab


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    vocab = ConstructionVocabulary()

    print("=== Construction Vocabulary Test ===\n")

    # 用語数表示
    print(f"Total terms: {len(vocab.hotwords)}\n")

    # カテゴリ別表示
    for category, terms in vocab.category_vocabularies.items():
        print(f"{category}: {len(terms)} terms")
        for term in terms[:5]:
            print(f"  - {term}")
        if len(terms) > 5:
            print(f"  ... and {len(terms) - 5} more")
        print()

    # Whisperプロンプト生成
    prompt = vocab.get_whisper_prompt()
    print(f"Whisper Prompt (first 200 chars):\n{prompt[:200]}...\n")

    # 置換テスト
    test_text = "ほおがけを使ってコンクリート工の基準内ちんぎんを計算する"
    corrected = vocab.apply_replacements(test_text)
    print(f"Original: {test_text}")
    print(f"Corrected: {corrected}\n")

    # 検索テスト
    search_results = vocab.search_terms("管理")
    print(f"Search '管理': {len(search_results)} results")
    for term in search_results[:10]:
        print(f"  - {term}")
