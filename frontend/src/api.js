const API_BASE = import.meta.env.VITE_API_BASE_URL;

/**
 * @typedef {Object} Job
 * @property {string} job_id
 * @property {string} status
 * @property {number} progress
 * @property {string} message
 * @property {string} target_language
 * @property {boolean} has_source
 * @property {boolean} has_target
 * @property {string|null} error
 */

async function request(path, options = {}) {
  if (!API_BASE) {
    throw new Error('Backend unavailable');
  }
  const response = await fetch(`${API_BASE}${path}`, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return body;
}

export function createJob(payload) {
  return request('/api/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function uploadJob({ jobId, sourceFile, targetLanguage, sourceLanguage, expectedSpeakers, creatorAuthorised }) {
  const form = new FormData();
  if (jobId) form.append('job_id', jobId);
  if (sourceFile) form.append('source_file', sourceFile);
  form.append('creator_authorised', String(creatorAuthorised));
  form.append('target_language', targetLanguage);
  form.append('source_language', sourceLanguage);
  if (expectedSpeakers) form.append('expected_speakers', String(expectedSpeakers));
  return request('/api/jobs/upload', { method: 'POST', body: form });
}

export function uploadDubbedArtifact(jobId, targetFile) {
  const form = new FormData();
  form.append('target_file', targetFile);
  return request(`/api/jobs/${jobId}/dubbed-artifact`, { method: 'POST', body: form });
}

export function confirmSourceLanguage(jobId, sourceLanguage) {
  return request(`/api/jobs/${jobId}/source-language`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_language: sourceLanguage }),
  });
}

export function getCapabilities() { return request('/api/capabilities'); }

export function runJob(jobId) {
  return request(`/api/jobs/${jobId}/run`, { method: 'POST' });
}

export function getJob(jobId) {
  return request(`/api/jobs/${jobId}`);
}

export function getArtifacts(jobId) {
  return request(`/api/jobs/${jobId}/artifacts`);
}

export function getReport(jobId) {
  return request(`/api/jobs/${jobId}/report`);
}

export function saveCorrection(jobId, payload) {
  return request(`/api/jobs/${jobId}/corrections`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}
