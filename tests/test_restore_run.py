import json
import sys

import pytest

from backend import restore_run


def test_restore_preserves_review_and_refuses_overwrite(tmp_path, monkeypatch):
    snapshot = tmp_path / 'snapshot'
    snapshot.mkdir()
    data = dict(video_id='sample', source_video='old', media='old', peaks='old',
                audio_analysis='old', audio_export='old', duration=10,
                speakers=[], segments=[dict(id='s1', start=1, end=2,
                                           text='reviewed text', reviewed=True)])
    (snapshot / 'project.json').write_text(json.dumps(data), encoding='utf-8')
    (snapshot / 'peaks.json').write_text('{"rate":50,"data":[0.1]}', encoding='utf-8')
    media = tmp_path / 'clip.mp4'
    media.write_bytes(b'media')
    for name, directory in [('INPUT_DIR', 'input'), ('CACHE_DIR', 'cache'), ('PROJECTS_DIR', 'projects')]:
        monkeypatch.setattr(restore_run.config, name, tmp_path / directory)
    monkeypatch.setattr(sys, 'argv', ['restore', str(snapshot), '--media', str(media)])
    restore_run.main()
    destination = tmp_path / 'projects/sample.json'
    restored = json.loads(destination.read_text(encoding='utf-8'))
    assert restored['media'] == str(media.resolve())
    assert restored['segments'] == data['segments']
    assert (tmp_path / 'cache/sample/peaks.json').exists()
    original = destination.read_bytes()
    with pytest.raises(SystemExit):
        restore_run.main()
    assert destination.read_bytes() == original
    data['video_id'] = '../escape'
    (snapshot / 'project.json').write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(SystemExit):
        restore_run.main()
    assert not (tmp_path / 'escape.json').exists()
