"""
Step 5：pyannote 说话人分离 + 重叠语音检测。
输出 turns（每个说话人的说话区间，可能互相重叠）和 overlaps（≥2 人同时说话的区间）。
同时保存每个说话人的声纹向量，供阶段 5 声纹库使用。
"""
from pathlib import Path

from .. import config
from .common import load_wav_mono, log


def run(vocals_16k: Path, cache: Path, device: str, num_speakers=None) -> dict:
    import numpy as np
    import torch
    from pyannote.audio import Pipeline

    if not config.HF_TOKEN:
        raise RuntimeError("未设置 HF_TOKEN。请在 Hugging Face 同意 pyannote/speaker-diarization-3.1 "
                           "和 pyannote/segmentation-3.0 的使用条款，然后设置环境变量 HF_TOKEN")
    pipeline = Pipeline.from_pretrained(config.PYANNOTE_PIPELINE, use_auth_token=config.HF_TOKEN)
    if pipeline is None:
        raise RuntimeError("pyannote 模型加载失败，多半是没同意模型使用条款或 token 无效")
    if config.CLUSTERING_THRESHOLD is not None:
        params = pipeline.parameters(instantiated=True)
        params["clustering"]["threshold"] = config.CLUSTERING_THRESHOLD
        pipeline.instantiate(params)
    pipeline.to(torch.device(device))

    # 直接传波形，绕开 pyannote 在 Windows 上读文件的解码问题
    audio, sr = load_wav_mono(vocals_16k, expected_sr=16000)
    kwargs = {}
    n = num_speakers or config.NUM_SPEAKERS
    if n:
        kwargs["num_speakers"] = n
    else:
        if config.MIN_SPEAKERS:
            kwargs["min_speakers"] = config.MIN_SPEAKERS
        if config.MAX_SPEAKERS:
            kwargs["max_speakers"] = config.MAX_SPEAKERS
    log.info("pyannote 参数: %s", kwargs or "自动估计人数")
    diarization, embeddings = pipeline(
        {"waveform": torch.from_numpy(audio)[None], "sample_rate": sr},
        return_embeddings=True, **kwargs)

    turns = [{"start": t.start, "end": t.end, "speaker": spk}
             for t, _, spk in diarization.itertracks(yield_label=True)]
    overlaps = [[s.start, s.end] for s in diarization.get_overlap()]

    labels = diarization.labels()
    if embeddings is not None and len(labels):
        np.save(cache / "speaker_embeddings.npy", embeddings[:len(labels)])
    return {"turns": turns, "overlaps": overlaps, "labels": labels}
