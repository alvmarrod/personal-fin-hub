import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/svelte';
import { setLocale } from '$lib/i18n/index.svelte';
import Page from '../../routes/backups/+page.svelte';

const { apiMock } = vi.hoisted(() => ({
  apiMock: { get: vi.fn(), post: vi.fn(), postFile: vi.fn(), put: vi.fn(), del: vi.fn() },
}));

vi.mock('$lib/api/client.js', () => ({ api: apiMock }));

const POLICY = {
  enabled: true,
  cron: '03:00',
  timezone: 'Europe/Madrid',
  retention: 2,
  next_run_at: '2026-11-21T02:00:00+00:00',
};

const ITEMS = [
  {
    name: 'finhub.db-20261120-030000.bak',
    size: 1294336,
    created_at: '2026-11-20T02:00:00+00:00',
    tag: 'daily',
    app_version: '0.33.0',
    latest: true,
  },
  {
    name: 'finhub.db-20261119-030000.bak',
    size: 1258291,
    created_at: '2026-11-19T02:00:00+00:00',
    tag: 'manual',
    app_version: '0.33.0',
    latest: false,
  },
];

function mockList(items = ITEMS, policy = POLICY) {
  apiMock.get.mockImplementation((path) => {
    if (path === '/backups') return Promise.resolve({ policy, items });
    if (path === '/backups/activity') return Promise.resolve({ busy: [] });
    return Promise.resolve({});
  });
}

describe('Backups page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setLocale('en-US');
    mockList();
    apiMock.post.mockResolvedValue({ created: { name: 'finhub.db-20261121-030000.bak' }, pruned: [] });
  });

  afterEach(cleanup);

  it('renders the policy and the backup list', async () => {
    render(Page);
    await screen.findByText('finhub.db-20261120-030000.bak');

    expect(screen.getByText('Automatic backups')).toBeTruthy();
    expect(screen.getByText('Every day at 03:00 (Europe/Madrid)')).toBeTruthy();
    expect(screen.getByText('Keeps the 2 newest backups')).toBeTruthy();
    expect(screen.getByText('latest')).toBeTruthy();
  });

  it('labels the origin of each backup', async () => {
    render(Page);
    await screen.findByText('finhub.db-20261120-030000.bak');

    expect(screen.getAllByText('Automatic').length).toBe(1);
    expect(screen.getAllByText('Manual').length).toBe(1);
  });

  it('links each backup to its download endpoint', async () => {
    const { container } = render(Page);
    await screen.findByText('finhub.db-20261120-030000.bak');

    const link = container.querySelector('.backups-download');
    expect(link.getAttribute('href')).toBe('/api/v1/backups/finhub.db-20261120-030000.bak');
    expect(link.getAttribute('download')).toBe('finhub.db-20261120-030000.bak');
  });

  it('creates a backup directly when retention has room', async () => {
    mockList([ITEMS[0]], POLICY);
    render(Page);
    await screen.findByText('finhub.db-20261120-030000.bak');

    await fireEvent.click(screen.getByText('Create backup now'));

    await waitFor(() => expect(apiMock.post).toHaveBeenCalledWith('/backups', {}));
    expect(screen.queryByText('Retention limit reached')).toBeNull();
    await screen.findByText(/Backup created/);
  });

  it('warns before retention deletes an older backup', async () => {
    const { container } = render(Page);
    await screen.findByText('finhub.db-20261120-030000.bak');

    await fireEvent.click(screen.getByText('Create backup now'));

    expect(await screen.findByText('Retention limit reached')).toBeTruthy();
    expect(container.querySelector('.prune-list').textContent).toContain('finhub.db-20261119-030000.bak');

    const buttons = screen.getAllByText('Create backup now');
    await fireEvent.click(buttons[buttons.length - 1]);

    await waitFor(() => expect(apiMock.post).toHaveBeenCalledWith('/backups', {}));
  });

  it('opens the import dialog with a file picker', async () => {
    const { container } = render(Page);
    await screen.findByText('finhub.db-20261120-030000.bak');

    await fireEvent.click(screen.getByText('Import backup'));

    expect(await screen.findByText('Restore a backup')).toBeTruthy();
    expect(container.querySelector('input[type="file"]')).toBeTruthy();
  });

  it('requires the confirmation word and an idle backend before restoring', async () => {
    const { container } = render(Page);
    await screen.findByText('finhub.db-20261120-030000.bak');

    apiMock.post.mockImplementation((path) => {
      if (path.endsWith('/inspect')) {
        return Promise.resolve({ name: ITEMS[0].name, created_at: ITEMS[0].created_at, migrations: [] });
      }
      return Promise.resolve({});
    });

    const restoreButtons = screen.getAllByText('Restore');
    await fireEvent.click(restoreButtons[0]);

    await screen.findByText('Ready to restore.');
    const confirm = screen.getByText('Continue');
    expect(confirm.disabled).toBe(true);

    const input = container.querySelector('.restore-body input.text-input');
    await fireEvent.input(input, { target: { value: 'RESTORE' } });
    await waitFor(() => expect(confirm.disabled).toBe(false));

    await fireEvent.click(confirm);
    await waitFor(() =>
      expect(apiMock.post).toHaveBeenCalledWith(
        `/backups/${encodeURIComponent(ITEMS[0].name)}/restore`,
        {},
      ),
    );
  });

  it('keeps restore disabled while a background job runs', async () => {
    apiMock.get.mockImplementation((path) => {
      if (path === '/backups') return Promise.resolve({ policy: POLICY, items: ITEMS });
      if (path === '/backups/activity') {
        return Promise.resolve({ busy: [{ name: 'Price sync', started_at: '2026-11-20T02:00:00+00:00' }] });
      }
      return Promise.resolve({});
    });
    apiMock.post.mockResolvedValue({ name: ITEMS[0].name, created_at: ITEMS[0].created_at, migrations: [] });

    const { container } = render(Page);
    await screen.findByText('finhub.db-20261120-030000.bak');

    await fireEvent.click(screen.getAllByText('Restore')[0]);
    await screen.findByText('Waiting for 1 background job(s) to finish:');

    const input = container.querySelector('.restore-body input.text-input');
    await fireEvent.input(input, { target: { value: 'RESTORE' } });

    expect(screen.getByText('Continue').disabled).toBe(true);
  });
});
