#!/usr/bin/env sh
set -eu
python -m pip install -r requirements.txt -r speech_service/requirements.txt
python -m pip install --no-deps 'parler-tts @ https://github.com/huggingface/parler-tts/archive/d108732cd57788ec86bc857d99a6cabd66663d68.zip'
