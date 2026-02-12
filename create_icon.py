"""
KotobaTranscriber用のアイコン生成スクリプト
モダンでおしゃれなアイコンを複数サイズで生成
"""
from PIL import Image, ImageDraw, ImageFont
import os

def create_app_icon(output_path="icon.ico", sizes=[16, 32, 48, 64, 128, 256]):
    """
    アプリケーションアイコンを生成

    デザイン:
    - 背景: 青紫グラデーション
    - 前景: 白い音声波形 + 日本語「文」
    - スタイル: モダン、ミニマル
    """
    images = []

    for size in sizes:
        # 新しい画像を作成（RGBA - 透明度サポート）
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 背景グラデーション（青→紫）
        for y in range(size):
            # 青 (70, 130, 255) から 紫 (138, 43, 226) へのグラデーション
            ratio = y / size
            r = int(70 + (138 - 70) * ratio)
            g = int(130 + (43 - 130) * ratio)
            b = int(255 + (226 - 255) * ratio)
            draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

        # 円形の背景（柔らかい印象）
        margin = size * 0.05
        draw.ellipse(
            [margin, margin, size - margin, size - margin],
            fill=(255, 255, 255, 0),
            outline=(255, 255, 255, 200),
            width=max(1, size // 40)
        )

        # 音声波形を描画（中央上部）
        wave_y_start = size * 0.25
        wave_height = size * 0.3
        wave_width = size * 0.7
        wave_x_start = size * 0.15

        # 3つの波形バー
        bar_width = wave_width / 5
        bar_spacing = wave_width / 5

        bars = [
            (0.4, 0.6),   # 左のバー（中程度）
            (0.2, 1.0),   # 中央のバー（高い）
            (0.4, 0.7),   # 右のバー（中程度）
        ]

        for i, (start, end) in enumerate(bars):
            x = wave_x_start + i * (bar_width + bar_spacing)
            bar_height = wave_height * (end - start)
            y_top = wave_y_start + wave_height * start

            # 角丸四角形風のバー
            draw.rounded_rectangle(
                [x, y_top, x + bar_width, y_top + bar_height],
                radius=max(1, size // 40),
                fill=(255, 255, 255, 230)
            )

        # 日本語「文」を描画（下部）
        # フォントサイズは画像サイズに応じて調整
        font_size = max(int(size * 0.35), 12)

        try:
            # Windows標準の日本語フォントを試す
            font_paths = [
                "C:/Windows/Fonts/msgothic.ttc",  # MSゴシック
                "C:/Windows/Fonts/meiryo.ttc",    # メイリオ
                "C:/Windows/Fonts/YuGothM.ttc",   # 游ゴシック Medium
            ]

            font = None
            for font_path in font_paths:
                if os.path.exists(font_path):
                    try:
                        font = ImageFont.truetype(font_path, font_size)
                        break
                    except:
                        continue

            if font is None:
                # フォントが見つからない場合はデフォルト
                font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()

        # テキスト「文」を描画
        text = "文"

        # テキストのバウンディングボックスを取得
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # 中央下部に配置
        text_x = (size - text_width) / 2
        text_y = size * 0.65

        # 影を追加（立体感）
        shadow_offset = max(1, size // 80)
        draw.text(
            (text_x + shadow_offset, text_y + shadow_offset),
            text,
            fill=(0, 0, 0, 100),
            font=font
        )

        # メインテキスト
        draw.text(
            (text_x, text_y),
            text,
            fill=(255, 255, 255, 255),
            font=font
        )

        images.append(img)

    # ICOファイルとして保存（複数サイズ）
    images[0].save(
        output_path,
        format='ICO',
        sizes=[(img.width, img.height) for img in images],
        append_images=images[1:]
    )

    print(f"[OK] アイコンを生成しました: {output_path}")
    print(f"     サイズ: {', '.join([f'{s}x{s}' for s in sizes])}")

    # プレビュー用にPNGも出力
    png_path = output_path.replace('.ico', '_preview.png')
    images[-1].save(png_path, 'PNG')
    print(f"[OK] プレビュー画像: {png_path}")

    return output_path

if __name__ == "__main__":
    # アイコンを生成
    icon_path = create_app_icon("icon.ico")

    print("\n[適用箇所]")
    print("  - メインウィンドウ (main.py)")
    print("  - 監視アプリウィンドウ (monitor_app.py)")
    print("  - システムトレイ (monitor_app.py)")
    print("  - タスクバー")
    print("  - PyInstallerビルド (build.spec)")
