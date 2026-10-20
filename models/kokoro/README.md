# Optional local voice models
Ubuntu installation: `.venv/bin/pip install --no-cache-dir -r requirements-voice.txt`, then `.venv/bin/python scripts/setup_voice_models.py`.
Uses the existing ONNX runtime and Kokoro v1.1 Chinese model, not torch inference. Files are downloaded from the URLs declared in setup_voice_models.py; licenses and SHA256 manifest are saved alongside them. Model data is ignored by Git. Mount the model folder here if supplied separately.
On a 2GB server start with cloud voice; enable local voice only after checking memory and disk. Never copy the Windows .runtime folder to Linux.
