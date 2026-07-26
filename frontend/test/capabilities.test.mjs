import test from 'node:test';
import assert from 'node:assert/strict';
import { canStartReview, enabledTargetLanguages, targetLanguageControlState } from '../src/capabilities.js';

test('target options are derived from the API capability response', () => {
  const options = enabledTargetLanguages({
    enabled_dubbing_target_languages: ['hi-IN', 'te-IN', 'od-IN'],
  });
  assert.deepEqual(options.map((option) => option.code), ['hi-IN', 'te-IN', 'od-IN']);
  assert.equal(options.find((option) => option.code === 'te-IN').name, 'Telugu');
  assert.equal(enabledTargetLanguages({ enabled_dubbing_target_languages: ['bn-IN', 'od-IN'] })[1].name, 'Odia');
});

test('target control has a recoverable backend-unavailable state', () => {
  assert.deepEqual(targetLanguageControlState('error', [], ''), {
    disabled: true,
    label: 'Backend unavailable',
  });
});

test('start control cannot proceed without a selected target locale', () => {
  assert.equal(canStartReview({ capabilityStatus: 'ready', authorised: true, targetLanguage: '', hasSource: true }), false);
  assert.equal(canStartReview({ capabilityStatus: 'ready', authorised: true, targetLanguage: 'te-IN', hasSource: true }), true);
});
