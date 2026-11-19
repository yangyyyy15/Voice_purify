"""
环境验收脚本：检查 GPU、依赖、模型是否可用
"""
import sys
import torch

def check_environment():
    checks = []
    all_pass = True

    print("=" * 60)
    print("Voice_purify 环境验收")
    print("=" * 60)

    # 1. GPU
    print("\n[1/6] 检查 GPU...")
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
        checks.append(f"✓ GPU: {gpu_name}")
        checks.append(f"✓ VRAM: {vram_gb:.1f} GB")
        print(f"  GPU: {gpu_name} ({vram_gb:.1f} GB)")
    else:
        checks.append("✗ GPU 不可用，将使用 CPU（速度会很慢）")
        print("  ✗ GPU 不可用")
        all_pass = False

    # 2. ffmpeg
    print("\n[2/6] 检查 ffmpeg...")
    try:
        import subprocess
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            checks.append(f"✓ ffmpeg: {version[:50]}")
            print(f"  ✓ {version[:60]}")
        else:
            raise Exception()
    except Exception:
        checks.append("✗ ffmpeg 不可用")
        print("  ✗ ffmpeg 未安装或不在 PATH")
        all_pass = False

    # 3. Demucs
    print("\n[3/6] 检查 Demucs...")
    try:
        import demucs
        checks.append("✓ Demucs 可导入")
        print("  ✓ Demucs 已安装")
    except ImportError as e:
        checks.append(f"✗ Demucs 导入失败: {e}")
        print(f"  ✗ 导入失败: {e}")
        all_pass = False

    # 4. pyannote
    print("\n[4/6] 检查 pyannote...")
    try:
        from pyannote.audio import Pipeline
        checks.append("✓ pyannote.audio 可导入")
        print("  ✓ pyannote.audio 已安装")

        # 检查 HF_TOKEN
        import os
        token = os.getenv("HF_TOKEN")
        if not token:
            try:
                from huggingface_hub import get_token
                token = get_token()
            except Exception:
                token = None
        if token:
            checks.append("✓ HF_TOKEN 已设置")
            print("  ✓ Hugging Face token 已配置（环境变量或 CLI 登录）")
        else:
            checks.append("✗ HF_TOKEN 未设置")
            print("  ✗ HF_TOKEN 环境变量未设置")
            print("    请访问: https://huggingface.co/pyannote/speaker-diarization-3.1")
            all_pass = False
    except ImportError as e:
        checks.append(f"✗ pyannote 失败: {e}")
        print(f"  ✗ 导入失败: {e}")
        all_pass = False

    # 5. FunASR
    print("\n[5/6] 检查 FunASR...")
    try:
        from funasr import AutoModel
        checks.append("✓ FunASR 可导入")
        print("  ✓ FunASR 已安装")
    except ImportError as e:
        checks.append(f"✗ FunASR 失败: {e}")
        print(f"  ✗ 导入失败: {e}")
        all_pass = False

    # 6. 其他依赖
    print("\n[6/6] 检查其他依赖...")
    missing = []
    for pkg in ["silero_vad", "librosa", "pydantic", "fastapi"]:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            missing.append(pkg)

    if not missing:
        checks.append("✓ 其他依赖完整")
        print("  ✓ 所有依赖已安装")
    else:
        checks.append(f"✗ 缺少: {', '.join(missing)}")
        print(f"  ✗ 缺少: {', '.join(missing)}")
        all_pass = False

    # 总结
    print("\n" + "=" * 60)
    if all_pass:
        print("✓ 环境验收通过！可以开始处理视频。")
        print("=" * 60)
        return 0
    else:
        print("✗ 有错误需要修复。请参考上面的提示安装缺失组件。")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(check_environment())
