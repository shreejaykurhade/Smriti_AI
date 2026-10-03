// The public prototype offers only languages with bundled UI, Whisper input,
// translation and a tested Edge or installed MMS output route. No shared demos.
export const INTERACTION_LANGUAGES = ['en','bn','gu','hi','kn','ml','mr','ne','pa','ta','te','ur'];

export function interactionLanguages(capabilities: {
  stt:boolean; tts:boolean; translation:boolean;
  stt_languages:string[]; tts_languages:string[]; translation_languages?:string[];
} | null) {
  if (!capabilities) return INTERACTION_LANGUAGES;
  if (!capabilities.stt || !capabilities.tts) return [];
  return INTERACTION_LANGUAGES.filter(code => capabilities.stt_languages.includes(code)
    && capabilities.tts_languages.includes(code)
    && (code === 'en' || capabilities.translation && capabilities.translation_languages?.includes(code)));
}
