const backupsMock = {
  '/backups': {
    policy: {
      enabled: true,
      cron: '03:00',
      timezone: 'Europe/Madrid',
      retention: 7,
      next_run_at: '2026-11-21T03:00:00+01:00',
    },
    items: [
      {
        name: 'finhub.db-20261120-030000.bak',
        size: 1294336,
        created_at: '2026-11-20T03:00:00+01:00',
        tag: 'daily',
        app_version: '0.33.0',
        latest: true,
      },
      {
        name: 'finhub.db-20261119-030000.bak',
        size: 1258291,
        created_at: '2026-11-19T03:00:00+01:00',
        tag: 'pre-migration',
        app_version: '0.32.1',
        latest: false,
      },
      {
        name: 'finhub.db-20261118-174500.bak',
        size: 1245184,
        created_at: '2026-11-18T17:45:00+01:00',
        tag: 'manual',
        app_version: '0.32.1',
        latest: false,
      },
    ],
  },
  '/backups/activity': { busy: [] },
};

export default backupsMock;
