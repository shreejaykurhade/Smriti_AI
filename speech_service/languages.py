FLORES = dict(en='eng_Latn', as_='asm_Beng', bn='ben_Beng', brx='brx_Deva', doi='doi_Deva', gu='guj_Gujr', hi='hin_Deva', kn='kan_Knda', ks='kas_Arab', kok='gom_Deva', mai='mai_Deva', ml='mal_Mlym', mni='mni_Mtei', mr='mar_Deva', ne='npi_Deva', or_='ory_Orya', pa='pan_Guru', sa='san_Deva', sat='sat_Olck', sd='snd_Arab', ta='tam_Taml', te='tel_Telu', ur='urd_Arab')
FLORES['as'] = FLORES.pop('as_')
FLORES['or'] = FLORES.pop('or_')
TTS_LANGUAGES = set(FLORES) - {'pa', 'ks'}  # Unofficial model support is not advertised as production-ready.
WHISPER_LANGUAGES = {'en','as','bn','gu','hi','kn','ml','mr','ne','pa','sa','sd','ta','te','ur'}
STYLES = {
    'museum': 'A warm, clear speaker narrates in an engaging, thoughtful tone, with a moderate pace and natural pauses. The voice is close and very clear, with no background noise.',
    'conversation': 'A friendly speaker speaks in a natural, conversational tone, with a moderate pace and expressive intonation. The voice is close and very clear, with no background noise.',
    'calm': 'A calm speaker speaks slowly and clearly, in a gentle, thoughtful tone, with natural pauses. The recording is very clear, with no background noise.',
}
