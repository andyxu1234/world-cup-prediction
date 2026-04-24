"""测试分享卡片生成功能"""
import asyncio
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.share_card import generate_share_card_image

# 测试数据
test_data = {
    "home_team": "阿根廷",
    "away_team": "法国",
    "home_flag": "",
    "away_flag": "",
    "match_time": "2026-06-15T18:00:00+00:00",
    "round": "Group Stage - 1",
    "predictions": [
        {
            "model_name": "DeepSeek",
            "result": "home_win",
            "score_home": 2,
            "score_away": 1,
        },
        {
            "model_name": "GPT-4o",
            "result": "draw",
            "score_home": 1,
            "score_away": 1,
        },
        {
            "model_name": "Claude",
            "result": "away_win",
            "score_home": 0,
            "score_away": 2,
        },
    ],
}

def test_generate_share_card():
    """测试生成分享卡片"""
    print("开始生成分享卡片...")
    
    try:
        # 生成图片
        image_bytes = generate_share_card_image(test_data)
        
        # 保存到本地
        output_path = "test_share_card.png"
        with open(output_path, "wb") as f:
            f.write(image_bytes)
        
        print(f"✅ 分享卡片生成成功！")
        print(f"📁 文件已保存到: {os.path.abspath(output_path)}")
        print(f"📊 文件大小: {len(image_bytes)} bytes")
        
        # 检查小程序码文件是否存在
        base_dir = os.path.dirname(os.path.abspath(__file__))
        qr_path = os.path.join(base_dir, "avatars", "mini.jpg")
        if os.path.exists(qr_path):
            print(f"✅ 小程序码文件存在: {qr_path}")
        else:
            print(f"❌ 小程序码文件不存在: {qr_path}")
            
    except Exception as e:
        print(f"❌ 生成失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_generate_share_card()
