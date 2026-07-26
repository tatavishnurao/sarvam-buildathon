export function languageDisplayName(localeCode) {
  const productNames = { bn: 'Bengali', od: 'Odia' };
  const languageCode = localeCode.split('-')[0];
  if (productNames[languageCode]) return productNames[languageCode];
  try {
    return new Intl.DisplayNames(['en'], { type: 'language' }).of(languageCode) || localeCode;
  } catch {
    return localeCode;
  }
}

export function enabledTargetLanguages(capabilities) {
  const codes = capabilities?.enabled_dubbing_target_languages;
  if (!Array.isArray(codes)) return [];
  return codes.filter((code) => typeof code === 'string' && code.length > 0).map((code) => ({
    code,
    name: languageDisplayName(code),
  }));
}

export function targetLanguageControlState(status, targetLanguages, selectedCode) {
  if (status === 'loading') return { disabled: true, label: 'Loading languages…' };
  if (status === 'error') return { disabled: true, label: 'Backend unavailable' };
  if (targetLanguages.length === 0) return { disabled: true, label: 'No target languages enabled' };
  return { disabled: false, label: selectedCode ? null : 'Select target language' };
}

export function canStartReview({ capabilityStatus, authorised, targetLanguage, hasSource }) {
  return capabilityStatus === 'ready' && Boolean(authorised && targetLanguage && hasSource);
}
