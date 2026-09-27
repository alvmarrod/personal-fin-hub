<script>
  import { t, locale, setLocale, localeOptions } from '$lib/i18n/index.svelte';
  import { displayCurrency, setDisplayCurrency } from '$lib/preferences/currency.svelte';
  import { displayTimezone, setDisplayTimezone, timezoneOptions, detectedTimezone } from '$lib/preferences/timezone.svelte';
  import { api } from '$lib/api/client.js';
  import { onMount } from 'svelte';
  import Select from '$lib/components/Select.svelte';
  import Button from '$lib/components/Button.svelte';
  import CreateProfileModal from '$lib/components/modals/CreateProfileModal.svelte';
  import RenameProfileModal from '$lib/components/modals/RenameProfileModal.svelte';
  import DeleteProfileModal from '$lib/components/modals/DeleteProfileModal.svelte';
  import ConfirmDeleteModal from '$lib/components/modals/ConfirmDeleteModal.svelte';
  import FiscalPeriodModal from '$lib/components/modals/FiscalPeriodModal.svelte';
  import TaxBaseModal from '$lib/components/modals/TaxBaseModal.svelte';
  import TaxDefinitionModal from '$lib/components/modals/TaxDefinitionModal.svelte';
  import BrokerFeeDefinitionModal from '$lib/components/modals/BrokerFeeDefinitionModal.svelte';
  import FiscalCalendarStrip from '$lib/components/FiscalCalendarStrip.svelte';
  import { crud } from '$lib/api/analytics.js';
  import { profiles, loadProfiles, activeProfile, setProfileTimezone } from '$lib/stores/profile.svelte.js';
  import * as tutorialStore from '$lib/tutorial/TutorialStore.svelte';
  import TutorialOverlay from '$lib/tutorial/TutorialOverlay.svelte';
  import ReplayButton from '$lib/tutorial/replay/ReplayButton.svelte';
  import { settings as settingsTutorial } from '$lib/tutorial/definitions/index';
  import settingsMock from '$lib/tutorial/mocks/settings';

  tutorialStore.registerMock('settings', settingsMock);

  let currentLocale = $derived(locale());

  let currencyCodes = $state([]);
  let currentCurrency = $derived(displayCurrency());
  let currentTimezone = $derived(displayTimezone());
  let browserTimezone = $derived(detectedTimezone());
  let tutorialEnabled = $derived(tutorialStore.isEnabled());

  let profileList = $derived(profiles());
  let currentActive = $derived(activeProfile());

  let createOpen = $state(false);
  let renamingProfile = $state(null);
  let confirmingDelete = $state(null);
  let deletingProfile = $state(null);

  let fiscalPeriods = $state([]);
  let periodModalOpen = $state(false);
  let editingPeriod = $state(null);
  let deletingPeriod = $state(null);

  let taxBases = $state([]);
  let taxBaseModalOpen = $state(false);
  let editingTaxBase = $state(null);
  let deletingTaxBase = $state(null);

  let taxDefinitions = $state([]);
  let taxDefinitionModalOpen = $state(false);
  let editingTaxDefinition = $state(null);
  let deletingTaxDefinition = $state(null);

  let brokerFees = $state([]);
  let brokerFeeModalOpen = $state(false);
  let editingBrokerFee = $state(null);
  let deletingBrokerFee = $state(null);

  const defaultRulesetOptions = [
    { value: '', label: t('fiscalRules.rule.inferFromLocale') },
    ...['spain', 'japan', 'default', 'latest', 'none'].map(key => ({
      value: key,
      label: t(`fiscalRules.rule.${key}`),
    })),
  ];

  let currentDefaultRuleset = $derived(currentActive?.default_fiscal_rule || '');

  async function saveDefaultRuleset(value) {
    const ruleset = value || null;
    try {
      await api.patch(`/profiles/${currentActive.id}`, { default_fiscal_rule: ruleset });
      await loadProfiles();
    } catch (e) {
      // revert on error
    }
  }

  async function saveTimezone(value) {
    if (!currentActive?.id) {
      setDisplayTimezone(value);
      return;
    }
    try {
      await setProfileTimezone(currentActive.id, value);
    } catch {
      // keep the current display timezone on failure
    }
  }

  onMount(() => {
    loadProfiles().catch(() => {});
    loadFiscalPeriods().catch(() => {});
    loadTaxBases().catch(() => {});
    loadTaxDefinitions().catch(() => {});
    loadBrokerFees().catch(() => {});
  });

  let _tutWasOn = $state(tutorialStore.isActiveFor('settings'));
  $effect(() => {
    const on = tutorialStore.isActiveFor('settings');
    if (on && !_tutWasOn) {
      loadProfiles().catch(() => {});
      loadFiscalPeriods().catch(() => {});
      loadTaxBases().catch(() => {});
      loadTaxDefinitions().catch(() => {});
      loadBrokerFees().catch(() => {});
    }
    _tutWasOn = on;
  });

  async function loadFiscalPeriods() {
    fiscalPeriods = await crud.fiscalPeriods.getList();
  }

  function openAddPeriod() {
    editingPeriod = null;
    periodModalOpen = true;
  }

  function openEditPeriod(period) {
    editingPeriod = period;
    periodModalOpen = true;
  }

  async function confirmDeletePeriod() {
    if (!deletingPeriod) return;
    try {
      await crud.fiscalPeriods.remove(deletingPeriod.id);
      deletingPeriod = null;
      await loadFiscalPeriods();
    } catch (e) {
      // keep the confirm modal open; it shows the error
      throw e;
    }
  }

  async function loadTaxBases() {
    taxBases = await crud.taxBases.getList();
  }

  function openAddTaxBase() {
    editingTaxBase = null;
    taxBaseModalOpen = true;
  }

  function openEditTaxBase(base) {
    editingTaxBase = base;
    taxBaseModalOpen = true;
  }

  async function confirmDeleteTaxBase() {
    if (!deletingTaxBase) return;
    try {
      await crud.taxBases.remove(deletingTaxBase.id);
      deletingTaxBase = null;
      await loadTaxBases();
    } catch (e) {
      // keep the confirm modal open; it shows the error
      throw e;
    }
  }

  async function loadTaxDefinitions() {
    taxDefinitions = await crud.taxDefinitions.getList();
  }

  function openAddTaxDefinition() {
    editingTaxDefinition = null;
    taxDefinitionModalOpen = true;
  }

  function openEditTaxDefinition(definition) {
    editingTaxDefinition = definition;
    taxDefinitionModalOpen = true;
  }

  async function confirmDeleteTaxDefinition() {
    if (!deletingTaxDefinition) return;
    try {
      await crud.taxDefinitions.remove(deletingTaxDefinition.id);
      deletingTaxDefinition = null;
      await loadTaxDefinitions();
    } catch (e) {
      // keep the confirm modal open; it shows the error
      throw e;
    }
  }

  async function loadBrokerFees() {
    brokerFees = await crud.brokerFeeDefinitions.getList();
  }

  function openAddBrokerFee() {
    editingBrokerFee = null;
    brokerFeeModalOpen = true;
  }

  function openEditBrokerFee(fee) {
    editingBrokerFee = fee;
    brokerFeeModalOpen = true;
  }

  async function confirmDeleteBrokerFee() {
    if (!deletingBrokerFee) return;
    try {
      await crud.brokerFeeDefinitions.remove(deletingBrokerFee.id);
      deletingBrokerFee = null;
      await loadBrokerFees();
    } catch (e) {
      // keep the confirm modal open; it shows the error
      throw e;
    }
  }

  $effect(() => {
    api.get('/currencies').then(codes => {
      currencyCodes = codes;
    }).catch(() => {});
  });

  function selectLocale(code) {
    setLocale(code);
  }

  function selectCurrency(code) {
    setDisplayCurrency(code);
  }
</script>

<div class="page-header">
  <div class="page-title-row">
    <h1 class="page-title">{t('settings.title')}</h1>
    <ReplayButton page="settings" />
  </div>
</div>

<div class="settings-section">
  <div class="settings-row row-4">
  <div class="setting-group">
    <div class="setting-label">
      <h2>{t('settings.language')}</h2>
      <p>{t('settings.languageDesc')}</p>
    </div>
    <div class="setting-control">
      <div class="locale-cards">
        {#each localeOptions as opt}
          <button
            class="locale-card"
            class:active={currentLocale === opt.code}
            onclick={() => selectLocale(opt.code)}
          >
            <span class="locale-flag">{opt.code === 'en-US' ? '🇺🇸' : '🇪🇸'}</span>
            <span class="locale-label">{t(opt.code === 'en-US' ? 'settings.languageEn' : 'settings.languageEs')}</span>
            {#if currentLocale === opt.code}
              <svg class="locale-check" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            {/if}
          </button>
        {/each}
      </div>
    </div>
  </div>

  <div class="setting-group">
    <div class="setting-label">
      <h2>{t('settings.tutorials')}</h2>
      <p>{t('settings.tutorialsDesc')}</p>
    </div>
    <div class="setting-control">
      <label class="toggle-label">
        <input
          type="checkbox"
          class="toggle-input"
          checked={tutorialEnabled}
          onchange={(e) => tutorialStore.setEnabled(e.target.checked)}
        />
        <span class="toggle-track">
          <span class="toggle-thumb"></span>
        </span>
        <span class="toggle-text">{tutorialEnabled ? t('settings.tutorialsOn') : t('settings.tutorialsOff')}</span>
      </label>
    </div>
  </div>

  <div class="setting-group">
    <div class="setting-label">
      <h2>{t('settings.timezone')}</h2>
      <p>{t('settings.timezoneDesc')}</p>
      {#if browserTimezone !== currentTimezone}
        <p class="setting-hint">
          {t('settings.timezoneDetected')}: <strong>{browserTimezone}</strong>
          <button class="tz-detect-btn" onclick={() => saveTimezone(browserTimezone)}>{t('settings.timezoneUseDetected')}</button>
        </p>
      {/if}
    </div>
    <div class="setting-control">
      <div class="select-wrap">
        <Select
          value={currentTimezone}
          options={timezoneOptions()}
          onchange={(e) => saveTimezone(e.target.value)}
        />
      </div>
    </div>
  </div>

  <div class="setting-group">
    <div class="setting-label">
      <h2>{t('settings.currency')}</h2>
      <p>{t('settings.currencyDesc')}</p>
    </div>
    <div class="setting-control">
      <div class="currency-select-wrap">
        <Select
          value={currentCurrency}
          options={currencyCodes.map(c => ({ value: c, label: c }))}
          onchange={(e) => selectCurrency(e.target.value)}
        />
      </div>
    </div>
  </div>
  </div>

  <div class="settings-row row-2">
  <div class="setting-group">
    <div class="setting-label">
      <h2>{t('fiscalRules.defaultTitle')}</h2>
      <p>{t('fiscalRules.defaultDesc')}</p>
    </div>
    <div class="setting-control">
      <div class="select-wrap">
        <Select
          value={currentDefaultRuleset}
          options={defaultRulesetOptions}
          onchange={(e) => saveDefaultRuleset(e.target.value)}
        />
      </div>
      {#if currentDefaultRuleset}
        <p class="setting-hint">{t('fiscalRules.defaultHint')}</p>
      {/if}
    </div>
  </div>

  <div class="setting-group">
    <div class="setting-label">
      <h2>{t('profiles.profiles')}</h2>
      <p>{t('profiles.manageDesc')}</p>
    </div>
    <div class="setting-control">
      <div class="profile-actions">
        <Button variant="primary" size="sm" onclick={() => createOpen = true}>{t('profiles.create')}</Button>
      </div>
      <div class="profile-manage-list">
        {#each profileList as p}
          <div class="profile-manage-row">
            <div class="profile-manage-info">
              <span class="profile-manage-name">{p.name}</span>
              {#if currentActive && currentActive.id === p.id}
                <span class="profile-manage-current">{t('profiles.current')}</span>
              {/if}
            </div>
            <div class="profile-manage-controls">
              <Button variant="secondary" size="sm" onclick={() => renamingProfile = p}>{t('profiles.rename')}</Button>
              <Button variant="danger" size="sm" onclick={() => confirmingDelete = p}>{t('common.delete')}</Button>
            </div>
          </div>
        {/each}
      </div>
    </div>
  </div>
  </div>

  <div class="settings-row row-2">
  <div class="setting-group">
    <div class="setting-label">
      <h2>{t('fiscalRules.title')}</h2>
      <p>{t('fiscalRules.description')}</p>
    </div>
    <div class="setting-control">
      <div class="profile-actions">
        <Button variant="primary" size="sm" onclick={openAddPeriod}>{t('fiscalRules.add')}</Button>
      </div>
      <FiscalCalendarStrip
        periods={fiscalPeriods}
        oncreate={async (payload) => { await crud.fiscalPeriods.create(payload); await loadFiscalPeriods(); }}
        onupdate={async (id, payload) => { await crud.fiscalPeriods.update(id, payload); await loadFiscalPeriods(); }}
      />
      {#if fiscalPeriods.length > 0}
        <div class="profile-manage-list">
          {#each fiscalPeriods as period (period.id)}
            <div class="profile-manage-row">
              <div class="profile-manage-info">
                <span class="profile-manage-name">{t(`fiscalRules.rule.${period.rule_key}`)}</span>
                <span class="period-range">{period.start_date}{period.end_date ? ` — ${period.end_date}` : ` — ${t('fiscalRules.openEnded')}`}</span>
              </div>
              <div class="profile-manage-controls">
                <Button variant="secondary" size="sm" onclick={() => openEditPeriod(period)}>{t('common.edit')}</Button>
                <Button variant="danger" size="sm" onclick={() => deletingPeriod = period}>{t('common.delete')}</Button>
              </div>
            </div>
          {/each}
        </div>
      {:else}
        <p class="no-periods">{t('fiscalRules.empty')}</p>
      {/if}
    </div>
  </div>

  <div class="setting-group">
    <div class="setting-label">
      <h2>{t('taxBases.title')}</h2>
      <p>{t('taxBases.description')}</p>
    </div>
    <div class="setting-control">
      <div class="profile-actions">
        <Button variant="primary" size="sm" onclick={openAddTaxBase}>{t('taxBases.add')}</Button>
      </div>
      {#if taxBases.length > 0}
        <div class="profile-manage-list">
          {#each taxBases as tb (tb.id)}
            <div class="profile-manage-row">
              <div class="profile-manage-info">
                <span class="profile-manage-name">{t(`fiscalRules.rule.${tb.ruleset_key}`)} — {tb.name}</span>
                <span class="period-range">
                  {t(`taxBases.computation.${tb.computation}`)}
                  {tb.year_start ? ` · ${tb.year_start}+` : ` · ${t('taxBases.allYears')}`}
                  · {tb.categories.map((c) => t(`taxBases.category.${c}`)).join(', ')}
                </span>
              </div>
              <div class="profile-manage-controls">
                <Button variant="secondary" size="sm" onclick={() => openEditTaxBase(tb)}>{t('common.edit')}</Button>
                <Button variant="danger" size="sm" onclick={() => deletingTaxBase = tb}>{t('common.delete')}</Button>
              </div>
            </div>
          {/each}
        </div>
      {:else}
        <p class="no-periods">{t('taxBases.empty')}</p>
      {/if}
    </div>
  </div>
  </div>

  <div class="settings-row row-2">
  <div class="setting-group">
    <div class="setting-label">
      <h2>{t('taxDefinitions.title')}</h2>
      <p>{t('taxDefinitions.description')}</p>
    </div>
    <div class="setting-control">
      <div class="profile-actions">
        <Button variant="primary" size="sm" onclick={openAddTaxDefinition}>{t('taxDefinitions.add')}</Button>
      </div>
      {#if taxDefinitions.length > 0}
        <div class="profile-manage-list">
          {#each taxDefinitions as td (td.id)}
            <div class="profile-manage-row">
              <div class="profile-manage-info">
                <span class="profile-manage-name">{td.name}</span>
                <span class="period-range">
                  {td.rate != null ? `${(td.rate * 100).toFixed(2)}%` : t('taxDefinitions.rateUnset')}
                  {td.ruleset_key
                    ? ` · ${t(`fiscalRules.rule.${td.ruleset_key}`)}`
                    : ` · ${t('taxDefinitions.rulesetGeneric')}`}
                  {td.year_start ? ` · ${td.year_start}+` : ` · ${t('taxDefinitions.allYears')}`}
                </span>
              </div>
              <div class="profile-manage-controls">
                <Button variant="secondary" size="sm" onclick={() => openEditTaxDefinition(td)}>{t('common.edit')}</Button>
                <Button variant="danger" size="sm" onclick={() => deletingTaxDefinition = td}>{t('common.delete')}</Button>
              </div>
            </div>
          {/each}
        </div>
      {:else}
        <p class="no-periods">{t('taxDefinitions.empty')}</p>
      {/if}
    </div>
  </div>

  <div class="setting-group">
    <div class="setting-label">
      <h2>{t('brokerFees.title')}</h2>
      <p>{t('brokerFees.description')}</p>
    </div>
    <div class="setting-control">
      <div class="profile-actions">
        <Button variant="primary" size="sm" onclick={openAddBrokerFee}>{t('brokerFees.add')}</Button>
      </div>
      {#if brokerFees.length > 0}
        <div class="profile-manage-list">
          {#each brokerFees as bf (bf.id)}
            <div class="profile-manage-row">
              <div class="profile-manage-info">
                <span class="profile-manage-name">{bf.name}</span>
              </div>
              <div class="profile-manage-controls">
                <Button variant="secondary" size="sm" onclick={() => openEditBrokerFee(bf)}>{t('common.edit')}</Button>
                <Button variant="danger" size="sm" onclick={() => deletingBrokerFee = bf}>{t('common.delete')}</Button>
              </div>
            </div>
          {/each}
        </div>
      {:else}
        <p class="no-periods">{t('brokerFees.empty')}</p>
      {/if}
    </div>
  </div>
  </div>
</div>

<CreateProfileModal open={createOpen} onclose={() => createOpen = false} />
<RenameProfileModal open={renamingProfile !== null} onclose={() => renamingProfile = null} profile={renamingProfile} />
<ConfirmDeleteModal
  open={confirmingDelete !== null}
  onclose={() => confirmingDelete = null}
  title={t('profiles.deleteTitle')}
  entityName={confirmingDelete ? confirmingDelete.name : ''}
  message={confirmingDelete ? t('profiles.deleteDesc', { name: confirmingDelete.name }) : ''}
  onconfirm={() => {
    deletingProfile = confirmingDelete;
    confirmingDelete = null;
  }}
/>
<DeleteProfileModal open={deletingProfile !== null} onclose={() => deletingProfile = null} profile={deletingProfile} />

<FiscalPeriodModal
  open={periodModalOpen}
  period={editingPeriod}
  onclose={() => { periodModalOpen = false; editingPeriod = null; }}
  onsuccess={loadFiscalPeriods}
/>
<ConfirmDeleteModal
  open={deletingPeriod !== null}
  onclose={() => deletingPeriod = null}
  onconfirm={confirmDeletePeriod}
  title={t('fiscalRules.deleteTitle')}
  entityName={deletingPeriod ? t(`fiscalRules.rule.${deletingPeriod.rule_key}`) : ''}
  message={t('fiscalRules.deleteMsg')}
/>

<TaxBaseModal
  open={taxBaseModalOpen}
  base={editingTaxBase}
  onclose={() => { taxBaseModalOpen = false; editingTaxBase = null; }}
  onsuccess={loadTaxBases}
/>
<ConfirmDeleteModal
  open={deletingTaxBase !== null}
  onclose={() => deletingTaxBase = null}
  onconfirm={confirmDeleteTaxBase}
  title={t('taxBases.deleteTitle')}
  entityName={deletingTaxBase ? deletingTaxBase.name : ''}
  message={t('taxBases.deleteMsg')}
/>
<TaxDefinitionModal
  open={taxDefinitionModalOpen}
  definition={editingTaxDefinition}
  onclose={() => { taxDefinitionModalOpen = false; editingTaxDefinition = null; }}
  onsuccess={loadTaxDefinitions}
/>
<ConfirmDeleteModal
  open={deletingTaxDefinition !== null}
  onclose={() => deletingTaxDefinition = null}
  onconfirm={confirmDeleteTaxDefinition}
  title={t('taxDefinitions.deleteTitle')}
  entityName={deletingTaxDefinition ? deletingTaxDefinition.name : ''}
  message={t('taxDefinitions.deleteMsg')}
/>
<BrokerFeeDefinitionModal
  open={brokerFeeModalOpen}
  fee={editingBrokerFee}
  onclose={() => { brokerFeeModalOpen = false; editingBrokerFee = null; }}
  onsuccess={loadBrokerFees}
/>
<ConfirmDeleteModal
  open={deletingBrokerFee !== null}
  onclose={() => deletingBrokerFee = null}
  onconfirm={confirmDeleteBrokerFee}
  title={t('brokerFees.deleteTitle')}
  entityName={deletingBrokerFee ? deletingBrokerFee.name : ''}
  message={t('brokerFees.deleteMsg')}
/>

<TutorialOverlay definition={settingsTutorial} page="settings" onfinish={() => {}} />

<style>
  .page-header {
    margin-bottom: var(--space-6);
  }

  .page-title-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .page-title {
    font-size: var(--font-size-2xl);
    font-weight: var(--font-weight-bold);
    color: var(--color-text);
  }

  .settings-section {
    display: grid;
    gap: var(--space-4);
  }

  .settings-row {
    display: grid;
    gap: var(--space-4);
  }

  .settings-row.row-4 {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .settings-row.row-2 {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  @media (max-width: 1100px) {
    .settings-row.row-4 {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 640px) {
    .settings-row.row-4,
    .settings-row.row-2 {
      grid-template-columns: 1fr;
    }
  }

  .setting-group {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-5) var(--space-6);
  }

  .setting-label {
    margin-bottom: var(--space-4);
  }

  .setting-label h2 {
    font-size: var(--font-size-base);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text);
    margin: 0 0 var(--space-1) 0;
  }

  .setting-label p {
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
    margin: 0;
  }

  .locale-cards {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-2);
    width: 100%;
  }

  .locale-card {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg);
    cursor: pointer;
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    color: var(--color-text);
    transition: border-color var(--transition-fast), background var(--transition-fast);
    position: relative;
  }

  .locale-card:hover {
    border-color: var(--color-primary);
  }

  .locale-card.active {
    border-color: var(--color-primary);
    background: var(--color-primary-light, rgba(59, 130, 246, 0.08));
  }

  .locale-flag {
    font-size: var(--font-size-lg);
    line-height: 1;
  }

  .locale-label {
    flex: 1;
    text-align: left;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .locale-check {
    color: var(--color-primary);
    flex-shrink: 0;
  }

  .currency-select-wrap,
  .select-wrap {
    max-width: 200px;
  }

  .toggle-label {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    cursor: pointer;
    user-select: none;
  }

  .toggle-input {
    position: absolute;
    opacity: 0;
    width: 0;
    height: 0;
  }

  .toggle-track {
    position: relative;
    width: 44px;
    height: 24px;
    background: var(--color-border);
    border-radius: 12px;
    transition: background var(--transition-fast);
    flex-shrink: 0;
  }

  .toggle-input:checked + .toggle-track {
    background: var(--color-primary);
  }

  .toggle-thumb {
    position: absolute;
    top: 2px;
    left: 2px;
    width: 20px;
    height: 20px;
    background: white;
    border-radius: 50%;
    transition: transform var(--transition-fast);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
  }

  .toggle-input:checked + .toggle-track .toggle-thumb {
    transform: translateX(20px);
  }

  .toggle-text {
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
  }

  .setting-hint {
    margin-top: var(--space-2);
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
  }

  .tz-detect-btn {
    display: inline;
    padding: 0;
    margin-left: var(--space-2);
    font-size: var(--font-size-sm);
    color: var(--color-primary);
    background: none;
    border: none;
    cursor: pointer;
    text-decoration: underline;
  }

  .profile-actions {
    display: flex;
    justify-content: flex-end;
    margin-bottom: var(--space-3);
  }

  .profile-manage-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .profile-manage-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg);
  }

  .profile-manage-info {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    min-width: 0;
  }

  .profile-manage-name {
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    color: var(--color-text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .profile-manage-current {
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
    color: var(--color-primary);
    background: var(--color-primary-light);
    border-radius: var(--radius-sm);
    padding: var(--space-0-5, 2px) var(--space-2);
    flex-shrink: 0;
  }

  .profile-manage-controls {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-shrink: 0;
  }

  .period-range {
    font-size: var(--font-size-xs);
    color: var(--color-text-secondary);
    white-space: nowrap;
  }

  .no-periods {
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
    margin: 0;
  }
</style>
