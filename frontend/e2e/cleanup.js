import { request } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const API_BASE_URL = process.env.API_BASE_URL ?? 'http://localhost:8010';
const E2E_NAME_RE = /^E2E/i;

const __dirname = path.dirname(fileURLToPath(import.meta.url));

async function del(ctx, url, headers, label) {
  const res = await ctx.delete(url, { headers });
  if (res.ok()) {
    console.log(`[e2e-cleanup] deleted ${label}`);
    return true;
  }
  console.warn(`[e2e-cleanup] could not delete ${label}: ${res.status()}`);
  return false;
}

async function sweepProfile(ctx, profileId) {
  const headers = { 'X-Profile-ID': String(profileId) };

  const entitiesRes = await ctx.get(`${API_BASE_URL}/api/v1/entities`, { headers });
  if (!entitiesRes.ok()) {
    console.log(`[e2e-cleanup] profile ${profileId}: entities endpoint unavailable, skipping`);
    return;
  }

  const entities = await entitiesRes.json();
  const e2eEntities = entities.filter((entity) => E2E_NAME_RE.test(entity.name));

  for (const entity of e2eEntities) {
    const txRes = await ctx.get(`${API_BASE_URL}/api/v1/transactions?entity_id=${entity.id}`, { headers });
    if (txRes.ok()) {
      for (const tx of await txRes.json()) {
        await del(ctx, `${API_BASE_URL}/api/v1/transactions/${tx.id}`, headers, `transaction ${tx.id} (entity ${entity.id})`);
      }
    }

    const snapRes = await ctx.get(`${API_BASE_URL}/api/v1/balance-snapshots?entity_id=${entity.id}`, { headers });
    if (snapRes.ok()) {
      for (const snap of await snapRes.json()) {
        await del(ctx, `${API_BASE_URL}/api/v1/balance-snapshots/${snap.id}`, headers, `balance snapshot ${snap.id} (entity ${entity.id})`);
      }
    }

    await del(ctx, `${API_BASE_URL}/api/v1/entities/${entity.id}`, headers, `entity ${entity.id} (${entity.name})`);
  }
}

async function hardPurge() {
  const dbPath = process.env.E2E_CLEANUP_DB ?? path.resolve(__dirname, '../../backend/data/finhub.db');
  let Database;
  try {
    ({ Database } = await import('bun:sqlite'));
  } catch {
    try {
      ({ Database } = await import('node:sqlite'));
    } catch {
      return;
    }
  }
  const db = new Database(dbPath);
  try {
    const { changes } = db.run("DELETE FROM entities WHERE name LIKE 'E2E%' AND deleted_at IS NOT NULL");
    if (changes > 0) {
      console.log(`[e2e-cleanup] hard-purged ${changes} soft-deleted e2e entity row(s)`);
    }
  } finally {
    db.close();
  }
}

export default async function sweepE2eData() {
  const ctx = await request.newContext();
  try {
    const profilesRes = await ctx.get(`${API_BASE_URL}/api/v1/profiles`);
    if (profilesRes.ok()) {
      const profiles = await profilesRes.json();
      for (const profile of profiles) {
        await sweepProfile(ctx, profile.id);
      }
    } else {
      console.log(`[e2e-cleanup] profiles endpoint unavailable (${profilesRes.status()}), skipping API sweep`);
    }
  } catch (err) {
    console.error('[e2e-cleanup] API sweep failed:', err.message);
  } finally {
    await ctx.dispose();
  }
  try {
    await hardPurge();
  } catch (err) {
    console.warn(`[e2e-cleanup] hard purge skipped: ${err.message}`);
  }
}
