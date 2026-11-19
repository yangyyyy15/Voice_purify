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

    from huggingface_hub import get_token
    from huggingface_hub import hf_hub_download
    from huggingface_hub.utils import LocalEntryNotFoundError
    import yaml
    token = config.HF_TOKEN or get_token()
    if not token:
        raise RuntimeError("未设置 HF_TOKEN。请在 Hugging Face 同意 pyannote/speaker-diarization-3.1 "
                           "和 pyannote/segmentation-3.0 的使用条款，然后运行 huggingface-cli login 或设置 HF_TOKEN")
    # PyTorch 2.6+ defaults to weights_only=True; allow the metadata type in trusted HF checkpoints.
    from pyannote.audio.core.task import Problem, Resolution, Specifications
    torch.serialization.add_safe_globals([
        torch.torch_version.TorchVersion, Problem, Resolution, Specifications,
    ])
    pipeline_ref = config.PYANNOTE_PIPELINE
    if config.WESPEAKER_EMBEDDING.exists():
        # Optional local ONNX alternative to the default PyTorch embedding.
        from pyannote.audio.core.model import CACHE_DIR
        try:
            source_config = hf_hub_download(
                config.PYANNOTE_PIPELINE, "config.yaml", cache_dir=CACHE_DIR,
                local_files_only=True,
            )
        except LocalEntryNotFoundError:
            source_config = hf_hub_download(
                config.PYANNOTE_PIPELINE, "config.yaml", cache_dir=CACHE_DIR,
                use_auth_token=token,
            )
        local_config = cache / "pyannote_pipeline_local.yaml"
        pipeline_config = yaml.safe_load(Path(source_config).read_text(encoding="utf-8"))
        pipeline_config["pipeline"]["params"]["embedding"] = str(config.WESPEAKER_EMBEDDING)
        local_config.write_text(yaml.safe_dump(pipeline_config, allow_unicode=True), encoding="utf-8")
        pipeline_ref = str(local_config)
    pipeline = Pipeline.from_pretrained(pipeline_ref, use_auth_token=token)
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
