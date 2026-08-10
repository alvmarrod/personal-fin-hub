import { api, setActiveProfileId } from '$lib/api/client.js';
import { logger } from '$lib/logger.js';

const STORAGE_KEY = 'pfh:activeProfileId';

/**
 * Rune-based profile store.
 *
 * Holds the list of profiles (shared, no per-profile scoping) and the
 * currently active profile id persisted in sessionStorage. The api client
 * reads the active id to attach the `X-Profile-ID` header on every request.
 */

let _activeProfile = $state(null);
let _profiles = $state([]);
let _initialized = false;

/** @returns {{ id: number, name: string } | null} */
export function activeProfile() {
  return _activeProfile;
}

/** @returns {string | null} */
export function activeProfileName() {
  return _activeProfile ? _activeProfile.name : null;
}

/** @returns {boolean} */
export function hasActiveProfile() {
  return _activeProfile !== null;
}

/** @returns {Array<{ id: number, name: string, has_password: boolean }>} */
export function profiles() {
  return _profiles;
}

function persistActive(id) {
  if (typeof sessionStorage === 'undefined') return;
  if (id == null) {
    sessionStorage.removeItem(STORAGE_KEY);
  } else {
    sessionStorage.setItem(STORAGE_KEY, String(id));
  }
}

/**
 * Load the profile list and restore any stored active profile session.
 * Runs at most once per page session. If the list load fails the session
 * is left untouched (the picker surface shows a retry state).
 * @returns {Promise<void>}
 */
export async function initProfiles() {
  logger.debug(`[profile] initProfiles start, _initialized=${_initialized}`);
  if (_initialized) return;
  _initialized = true;
  let loaded = false;
  try {
    await loadProfiles();
    loaded = true;
  } catch {
    // leave any stored session alone; UI surfaces the load error
  }
  if (!loaded || typeof sessionStorage === 'undefined') return;
  const raw = sessionStorage.getItem(STORAGE_KEY);
  logger.debug(`[profile] initProfiles loaded=${loaded}, stored=${raw}`);
  if (raw) {
    const id = Number(raw);
    const match = _profiles.find((p) => p.id === id);
    if (match) {
      logger.debug(`[profile] initProfiles restoring id=${id}`);
      activateProfile(match);
    } else {
      logger.debug(`[profile] initProfiles id=${id} not in list, clearing`);
      setActiveProfileId(null);
      persistActive(null);
    }
  }
}

/** @returns {Promise<Array<{ id: number, name: string, has_password: boolean }>>} */
export async function loadProfiles() {
  _profiles = await api.get('/profiles');
  logger.debug(`[profile] loadProfiles loaded ${_profiles.length} profiles`);
  return _profiles;
}

/**
 * Activate a profile (passwordless path or post-unlock).
 * @param {{ id: number, name: string }} profile
 */
export function activateProfile(profile) {
  logger.debug(`[profile] activateProfile id=${profile.id} name=${profile.name}`);
  _activeProfile = { id: profile.id, name: profile.name };
  setActiveProfileId(profile.id);
  persistActive(profile.id);
}

/**
 * Unlock a password-protected profile and activate it.
 * @param {{ id: number, name: string }} profile
 * @param {string} password
 * @returns {Promise<{ id: number, name: string, has_password: boolean }>}
 */
export async function unlockProfile(profile, password) {
  const updated = await api.post(`/profiles/${profile.id}/unlock`, { password: password || null });
  activateProfile(updated);
  await loadProfiles();
  return updated;
}

/** Clear the active profile session and return to the picker. */
export function logout() {
  logger.debug('[profile] logout');
  _activeProfile = null;
  setActiveProfileId(null);
  persistActive(null);
}

/**
 * Create a new profile and activate it.
 * @param {string} name
 * @param {string | null} password
 * @returns {Promise<{ id: number, name: string, has_password: boolean }>}
 */
export async function createProfile(name, password = null) {
  const created = await api.post('/profiles', { name, password: password || null });
  logger.debug(`[profile] createProfile id=${created.id} name=${created.name}`);
  await loadProfiles();
  activateProfile(created);
  return created;
}

/**
 * Rename a profile.
 * @param {number} id
 * @param {string} name
 * @returns {Promise<{ id: number, name: string, has_password: boolean }>}
 */
export async function renameProfile(id, name) {
  const updated = await api.patch(`/profiles/${id}`, { name });
  await loadProfiles();
  if (_activeProfile && _activeProfile.id === id) {
    _activeProfile = { id: updated.id, name: updated.name };
  }
  return updated;
}

/**
 * Delete a profile. If it was the active profile, the session is cleared.
 * @param {number} id
 * @returns {Promise<void>}
 */
export async function deleteProfile(id) {
  await api.del(`/profiles/${id}`);
  await loadProfiles();
  if (_activeProfile && _activeProfile.id === id) {
    logout();
  }
}
