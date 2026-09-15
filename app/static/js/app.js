/**
 * OLTAPI - Single Page Application para Bancada de Provisionamento & Diagnóstico
 * Vanilla JavaScript (ES6+), Zero dependências externas, Alta responsividade.
 */

const API_BASE = '/api/v1';

const state = {
  token: sessionStorage.getItem('oltapi_token') || null,
  user: null,
  olts: [],
  selectedOltId: null,
  unauthOnus: [],
  inventoryOnus: [],
  tenants: [],
  vlans: [],
  currentXray: null,
  currentXrayOltId: null,
  currentXrayFilter: 'all',
  ftpOverview: null,
  autoRefreshInterval: null,
};

// ============================================================================
// Utilitários HTTP com Injeção Automática de Bearer Token
// ============================================================================
async function apiRequest(endpoint, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (state.token && !headers['Authorization'] && !headers['X-API-Key']) {
    headers['Authorization'] = `Bearer ${state.token}`;
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (response.status === 401 && !endpoint.includes('/auth/login') && !endpoint.includes('/setup/init')) {
    logout();
    throw new Error('Sessão expirada. Faça login novamente.');
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const errorMsg = data?.detail || `Erro HTTP ${response.status}`;
    throw new Error(errorMsg);
  }

  return data;
}

function logTerminal(message, type = 'info') {
  const terminal = document.getElementById('terminal-output');
  if (!terminal) return;
  const time = new Date().toLocaleTimeString();
  const prefix = type === 'error' ? '❌ [ERRO]' : type === 'success' ? '✅ [SUCESSO]' : 'ℹ️ [INFO]';
  terminal.textContent += `\n[${time}] ${prefix} ${message}`;
  terminal.scrollTop = terminal.scrollHeight;
}

// ============================================================================
// Inicialização e Verificação de Estado (First-Run Setup vs Login vs App)
// ============================================================================
document.addEventListener('DOMContentLoaded', async () => {
  initEventListeners();
  await checkSystemSetup();
});

async function checkSystemSetup() {
  try {
    const setupStatus = await apiRequest('/setup/status');
    if (!setupStatus.is_configured) {
      showView('setup');
      return;
    }

    // Se o sistema já está configurado, verifica sessão
    if (state.token) {
      await hydrateSession();
    } else {
      showView('login');
    }
  } catch (error) {
    console.error('Erro ao verificar setup inicial:', error);
    showView('login');
  }
}

async function hydrateSession() {
  try {
    const profile = await apiRequest('/auth/me');
    state.user = profile;
    renderUserProfile();
    showView('app');
    await loadOLTs();
  } catch (error) {
    console.warn('Falha na autenticação da sessão existente:', error);
    logout();
  }
}

function showView(viewName) {
  document.getElementById('view-setup').classList.add('hidden');
  document.getElementById('view-login').classList.add('hidden');
  document.getElementById('app').classList.add('hidden');

  if (viewName === 'setup') {
    document.getElementById('view-setup').classList.remove('hidden');
  } else if (viewName === 'login') {
    document.getElementById('view-login').classList.remove('hidden');
  } else if (viewName === 'app') {
    document.getElementById('app').classList.remove('hidden');
  }
}

function renderUserProfile() {
  if (!state.user) return;
  document.getElementById('profile-name').textContent = state.user.name;
  document.getElementById('profile-role').textContent = state.user.role;
  document.getElementById('avatar-initials').textContent = state.user.name.substring(0, 2).toUpperCase();

  const role = state.user.role;
  const navAdmin = document.getElementById('nav-admin');
  const navOlts = document.getElementById('nav-olts');
  const navVlans = document.getElementById('nav-vlans');
  const navConfig = document.getElementById('nav-config');
  const btnNewOlt = document.getElementById('btn-open-modal-olt');
  const btnNewVlan = document.getElementById('btn-open-modal-vlan');

  if (role === 'SUPER_ADMIN') {
    navAdmin?.classList.remove('hidden');
    navOlts?.classList.remove('hidden');
    navVlans?.classList.remove('hidden');
    navConfig?.classList.remove('hidden');
    if (btnNewOlt) btnNewOlt.style.display = '';
    if (btnNewVlan) btnNewVlan.style.display = '';
  } else if (role === 'NOC') {
    navAdmin?.classList.add('hidden');
    navOlts?.classList.remove('hidden');
    navVlans?.classList.remove('hidden');
    navConfig?.classList.remove('hidden');
    if (btnNewOlt) btnNewOlt.style.display = 'none';
    if (btnNewVlan) btnNewVlan.style.display = 'none';
  } else {
    // FIELD_TECH - Estritamente Bancada & Inventário para provisionamento e sinal
    navAdmin?.classList.add('hidden');
    navOlts?.classList.add('hidden');
    navVlans?.classList.add('hidden');
    navConfig?.classList.add('hidden');
    if (btnNewOlt) btnNewOlt.style.display = 'none';
    if (btnNewVlan) btnNewVlan.style.display = 'none';
  }
}

function logout() {
  sessionStorage.removeItem('oltapi_token');
  state.token = null;
  state.user = null;
  if (state.autoRefreshInterval) clearInterval(state.autoRefreshInterval);
  showView('login');
}

// ============================================================================
// OLTs e ONUs Não Autorizadas
// ============================================================================
async function loadOLTs() {
  try {
    const olts = await apiRequest('/olts');
    state.olts = olts;
    const selectOlt = document.getElementById('select-olt');
    selectOlt.innerHTML = '';

    if (olts.length === 0) {
      selectOlt.innerHTML = '<option value="">Nenhuma OLT cadastrada</option>';
      return;
    }

    olts.forEach(olt => {
      const option = document.createElement('option');
      option.value = olt.id;
      option.textContent = `${olt.name} (${olt.vendor.toUpperCase()} • ${olt.model || olt.protocol})`;
      selectOlt.appendChild(option);
    });

    state.selectedOltId = olts[0].id;
    await scanUnauthorizedOnus();
    await loadInventory();

    // Consulta periódica de ONUs não autorizadas a cada 10s
    if (state.autoRefreshInterval) clearInterval(state.autoRefreshInterval);
    state.autoRefreshInterval = setInterval(() => {
      const currentActiveView = document.querySelector('.nav-item.active')?.getAttribute('data-view');
      if (currentActiveView === 'bancada' && state.selectedOltId) {
        scanUnauthorizedOnus(true);
      }
    }, 10000);
  } catch (error) {
    logTerminal(`Erro ao carregar OLTs: ${error.message}`, 'error');
  }
}

async function scanUnauthorizedOnus(silent = false) {
  if (!state.selectedOltId) return;
  const filterSerial = document.getElementById('search-unauth-serial').value.trim();
  const queryParam = filterSerial ? `?serial=${encodeURIComponent(filterSerial)}` : '';

  try {
    if (!silent) logTerminal(`Consultando ONUs não autorizadas na OLT...`);
    const unauth = await apiRequest(`/olts/${state.selectedOltId}/unauthorized${queryParam}`);
    state.unauthOnus = unauth;
    renderUnauthorizedTable();
    if (!silent) logTerminal(`Lista atualizada: ${unauth.length} ONU(s) não autorizada(s) detectada(s).`, 'success');
  } catch (error) {
    if (!silent) logTerminal(`Falha ao consultar ONUs não autorizadas: ${error.message}`, 'error');
  }
}

function renderUnauthorizedTable() {
  const tbody = document.getElementById('tbody-unauth-onus');
  if (!tbody) return;
  tbody.innerHTML = '';

  if (state.unauthOnus.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" style="text-align: center; color: var(--text-muted); padding: 24px;">
          Nenhuma ONU não autorizada detectada nesta OLT no momento.
        </td>
      </tr>
    `;
    return;
  }

  state.unauthOnus.forEach(onu => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td style="font-family: var(--font-mono); font-weight: 600; color: var(--accent-cyan);">
        ${onu.serial}
      </td>
      <td><span class="badge" style="background: var(--bg-surface-elevated);">${onu.port || 'N/A'}</span></td>
      <td>${onu.vendor || onu.model || 'Genérico / Auto'}</td>
      <td style="color: var(--text-secondary); font-size: 12px;">${onu.discovered_at || 'Recente'}</td>
      <td style="text-align: right;">
        <button class="btn btn-primary btn-sm btn-action-provision" data-serial="${onu.serial}" data-port="${onu.port || ''}" data-model="${onu.model || onu.vendor || ''}">
          ⚡ Autorizar ONU
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  // Bind dos botões de autorização
  document.querySelectorAll('.btn-action-provision').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const serial = e.currentTarget.getAttribute('data-serial');
      const port = e.currentTarget.getAttribute('data-port');
      const model = e.currentTarget.getAttribute('data-model');
      openProvisionModal(serial, port, model);
    });
  });
}

// ============================================================================
// Inventário de ONUs & Ações de Ciclo de Vida
// ============================================================================
async function loadInventory() {
  try {
    const onus = await apiRequest('/onus');
    state.inventoryOnus = onus;
    renderInventoryTable();
  } catch (error) {
    logTerminal(`Erro ao carregar inventário de ONUs: ${error.message}`, 'error');
  }
}

function renderInventoryTable() {
  const tbody = document.getElementById('tbody-inventory-onus');
  if (!tbody) return;
  tbody.innerHTML = '';

  const filterText = document.getElementById('search-inv-serial')?.value.toLowerCase().trim();
  const filtered = state.inventoryOnus.filter(onu => {
    if (!filterText) return true;
    return (
      (onu.serial && onu.serial.toLowerCase().includes(filterText)) ||
      (onu.subscriber_name && onu.subscriber_name.toLowerCase().includes(filterText)) ||
      (onu.circuit_id && onu.circuit_id.toLowerCase().includes(filterText))
    );
  });

  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 24px;">
          Nenhuma ONU cadastrada encontrada no inventário.
        </td>
      </tr>
    `;
    return;
  }

  filtered.forEach(onu => {
    const tr = document.createElement('tr');
    const role = state.user?.role || 'FIELD_TECH';
    let actionButtons = `
      <button class="btn btn-secondary btn-sm btn-check-optical" data-olt="${onu.current_olt_id || state.selectedOltId}" data-serial="${onu.serial}" title="Medir Potência Óptica">
        📶 Sinal
      </button>
      <button class="btn btn-secondary btn-sm btn-onu-edit" data-serial="${onu.serial}" title="Editar Dados da ONU">
        ✏️ Editar
      </button>
    `;

    if (role === 'SUPER_ADMIN' || role === 'NOC') {
      const isSuspended = (onu.contract_status === 'SUSPENDED');
      if (isSuspended) {
        actionButtons += `
          <button class="btn btn-success btn-sm btn-onu-resume" data-olt="${onu.current_olt_id || state.selectedOltId}" data-serial="${onu.serial}" title="Desbloquear / Reativar Cliente">
            🔓 Desbloquear
          </button>
        `;
      } else {
        actionButtons += `
          <button class="btn btn-warning btn-sm btn-onu-suspend" data-olt="${onu.current_olt_id || state.selectedOltId}" data-serial="${onu.serial}" title="Bloquear / Suspender Cliente">
            🔒 Bloquear
          </button>
        `;
      }
      actionButtons += `
        <button class="btn btn-secondary btn-sm btn-onu-reboot" data-olt="${onu.current_olt_id || state.selectedOltId}" data-serial="${onu.serial}" title="Reiniciar ONU">
          🔄
        </button>
      `;
    }

    if (role === 'SUPER_ADMIN') {
      actionButtons += `
        <button class="btn btn-danger btn-sm btn-onu-deprovision" data-olt="${onu.current_olt_id || state.selectedOltId}" data-serial="${onu.serial}" title="Desprovisionar">
          🗑️
        </button>
      `;
    }

    tr.innerHTML = `
      <td style="font-family: var(--font-mono); font-weight: 600;">${onu.serial}</td>
      <td>${onu.subscriber_name || onu.description || '<span style="color: var(--text-muted);">Sem assinante</span>'}</td>
      <td>${onu.current_port || 'N/A'}</td>
      <td><span class="badge" style="background: var(--bg-surface-elevated);">${onu.vlan || '-'}</span></td>
      <td id="optical-${onu.serial}"><span class="badge badge-optical-warn">Consultar</span></td>
      <td>
        <span class="badge" style="background: ${onu.contract_status === 'ACTIVE' ? 'rgba(16,185,129,0.15); color: var(--accent-green)' : 'rgba(244,63,94,0.15); color: var(--accent-rose)'};">
          ${onu.contract_status || 'ACTIVE'}
        </span>
      </td>
      <td style="text-align: right; display: flex; gap: 4px; justify-content: flex-end;">
        ${actionButtons}
      </td>
    `;
    tbody.appendChild(tr);
  });

  // Bind dos botões de ciclo de vida
  document.querySelectorAll('.btn-check-optical').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const oltId = e.currentTarget.getAttribute('data-olt');
      const serial = e.currentTarget.getAttribute('data-serial');
      await checkOpticalPower(oltId, serial);
    });
  });

  document.querySelectorAll('.btn-onu-edit').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const serial = e.currentTarget.getAttribute('data-serial');
      await openEditOnuModal(serial);
    });
  });

  document.querySelectorAll('.btn-onu-suspend').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const oltId = e.currentTarget.getAttribute('data-olt');
      const serial = e.currentTarget.getAttribute('data-serial');
      if (confirm(`Deseja realmente BLOQUEAR (suspender) a ONU ${serial}? O acesso do cliente será desativado na OLT.`)) {
        await executeLifecycleAction(oltId, serial, 'suspend');
        await loadInventory();
      }
    });
  });

  document.querySelectorAll('.btn-onu-resume').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const oltId = e.currentTarget.getAttribute('data-olt');
      const serial = e.currentTarget.getAttribute('data-serial');
      if (confirm(`Deseja realmente DESBLOQUEAR (reativar) a ONU ${serial}? O acesso do cliente será reabilitado na OLT.`)) {
        await executeLifecycleAction(oltId, serial, 'resume');
        await loadInventory();
      }
    });
  });

  document.querySelectorAll('.btn-onu-reboot').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const oltId = e.currentTarget.getAttribute('data-olt');
      const serial = e.currentTarget.getAttribute('data-serial');
      if (confirm(`Deseja realmente reiniciar a ONU ${serial}?`)) {
        await executeLifecycleAction(oltId, serial, 'reboot');
      }
    });
  });

  document.querySelectorAll('.btn-onu-deprovision').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const oltId = e.currentTarget.getAttribute('data-olt');
      const serial = e.currentTarget.getAttribute('data-serial');
      if (confirm(`ATENÇÃO: Deseja desprovisionar a ONU ${serial}? Ela será removida da OLT.`)) {
        await deprovisionONU(oltId, serial);
      }
    });
  });
}

async function checkOpticalPower(oltId, serial) {
  const cell = document.getElementById(`optical-${serial}`);
  if (cell) cell.innerHTML = '<span class="badge" style="color: var(--accent-cyan);">Medindo...</span>';
  logTerminal(`Medindo potência óptica da ONU ${serial}...`);

  try {
    const diag = await apiRequest(`/olts/${oltId}/onus/${serial}`);
    const rx = diag.rx_power_dbm !== undefined ? diag.rx_power_dbm : diag.rx_power;
    const tx = diag.tx_power_dbm !== undefined ? diag.tx_power_dbm : diag.tx_power;
    const oltRx = diag.olt_rx_power_dbm !== undefined ? diag.olt_rx_power_dbm : diag.olt_rx_power;

    if (cell) {
      if (rx === null || rx === undefined) {
        cell.innerHTML = `<span class="badge badge-optical-warn">${diag.status === 'offline' ? 'Offline' : 'N/A'}</span>`;
      } else {
        let badgeClassRx = 'badge-optical-good';
        if (rx < -27) badgeClassRx = 'badge-optical-bad';
        else if (rx < -25) badgeClassRx = 'badge-optical-warn';

        let oltRxHtml = '';
        if (oltRx !== null && oltRx !== undefined) {
          let badgeClassOlt = 'badge-optical-good';
          if (oltRx < -27) badgeClassOlt = 'badge-optical-bad';
          else if (oltRx < -25) badgeClassOlt = 'badge-optical-warn';
          oltRxHtml = `<span class="badge ${badgeClassOlt}" style="font-size: 10px; padding: 2px 6px; white-space: nowrap;" title="Potência óptica recebida na OLT vinda da ONU (Uplink)">📤 OLT: ${oltRx} dBm</span>`;
        }

        let txHtml = '';
        if (tx !== null && tx !== undefined) {
          txHtml = `<span class="badge" style="background: rgba(255,255,255,0.06); color: var(--text-secondary); font-size: 10px; padding: 2px 6px; white-space: nowrap;" title="Potência óptica transmitida pela ONU (TX)">TX: ${tx > 0 ? '+' : ''}${tx} dBm</span>`;
        }

        cell.innerHTML = `
          <div style="display: flex; flex-direction: column; gap: 4px; align-items: flex-start; max-width: 100%; overflow: hidden;">
            <span class="badge ${badgeClassRx}" style="font-size: 11px; padding: 2px 6px; white-space: nowrap;" title="Potência óptica recebida na ONU vinda da OLT (Downlink)">📥 ONU: ${rx} dBm</span>
            ${(oltRxHtml || txHtml) ? `<div style="display: flex; gap: 4px; flex-wrap: wrap;">${oltRxHtml}${txHtml}</div>` : ''}
          </div>
        `;
      }
    }

    // Se a API retornou VLAN e a célula da tabela estiver com hífen, atualiza ao vivo na tabela
    if (diag.vlan) {
      const row = cell?.closest('tr');
      if (row) {
        const vlanCell = row.cells[3]?.querySelector('.badge');
        if (vlanCell && (vlanCell.textContent.trim() === '-' || !vlanCell.textContent.trim())) {
          vlanCell.textContent = diag.vlan;
        }
      }
    }

    const rxMsg = rx !== null && rx !== undefined ? `${rx} dBm` : 'N/A';
    const oltRxMsg = oltRx !== null && oltRx !== undefined ? `${oltRx} dBm` : 'N/A';
    const txMsg = tx !== null && tx !== undefined ? `${tx} dBm` : 'N/A';
    logTerminal(`Sinal ONU ${serial}: RX ONU = ${rxMsg} | RX OLT = ${oltRxMsg} | TX = ${txMsg} (Status: ${diag.status})`, 'success');
  } catch (error) {
    if (cell) cell.innerHTML = `<span class="badge badge-optical-bad">Erro</span>`;
    logTerminal(`Falha ao medir potência da ONU ${serial}: ${error.message}`, 'error');
  }
}

async function executeLifecycleAction(oltId, serial, action) {
  logTerminal(`Executando ação '${action}' na ONU ${serial}...`);
  try {
    const resp = await apiRequest(`/olts/${oltId}/onus/${serial}/${action}`, {
      method: 'POST',
    });
    logTerminal(`Ação '${action}' concluída com sucesso na ONU ${serial}.`, 'success');
    alert(`Ação realizada com sucesso: ${resp.message || 'Comando executado.'}`);
  } catch (error) {
    logTerminal(`Erro ao executar '${action}' na ONU ${serial}: ${error.message}`, 'error');
    alert(`Falha: ${error.message}`);
  }
}

async function deprovisionONU(oltId, serial) {
  logTerminal(`Desprovisionando ONU ${serial}...`);
  try {
    await apiRequest(`/olts/${oltId}/onus/${serial}`, {
      method: 'DELETE',
    });
    logTerminal(`ONU ${serial} desprovisionada com sucesso.`, 'success');
    await loadInventory();
    await scanUnauthorizedOnus();
  } catch (error) {
    logTerminal(`Erro ao desprovisionar ONU ${serial}: ${error.message}`, 'error');
    alert(`Falha ao desprovisionar: ${error.message}`);
  }
}

// ============================================================================
// Modal de Provisionamento
// ============================================================================
async function openProvisionModal(serial, port, model = 'auto') {
  document.getElementById('prov-serial').value = serial;
  document.getElementById('prov-port').value = port;
  const modelInput = document.getElementById('prov-onu-model');
  if (modelInput) {
    modelInput.value = (model && model !== 'null' && model !== 'undefined' && model !== 'auto') ? model : 'auto';
  }
  document.getElementById('provision-alert').classList.add('hidden');

  // Sugere modo de operação com base no modelo ou histórico
  const modeSelect = document.getElementById('prov-mode');
  const boxPPPoE = document.getElementById('box-pppoe');
  if (model && model.toUpperCase().includes('BRIDGE')) {
    modeSelect.value = 'bridge';
    boxPPPoE?.classList.add('hidden');
  } else {
    if (modeSelect.value === 'bridge') {
      boxPPPoE?.classList.add('hidden');
    } else {
      boxPPPoE?.classList.remove('hidden');
    }
  }

  // Carrega VLANs reais diretamente da OLT selecionada
  const selectVlan = document.getElementById('prov-vlan');
  selectVlan.innerHTML = '<option value="">Consultando VLANs ativas na OLT...</option>';

  try {
    let vlans = [];
    const oltVlans = await apiRequest(`/olts/${state.selectedOltId}/vlans`);
    if (Array.isArray(oltVlans) && oltVlans.length > 0) {
      vlans = oltVlans.map(v => v.vlan_id);
    }

    // Se o operador tiver restrição de VLANs (Multi-Tenant), aplica o filtro
    if (state.user && state.user.allowed_vlans && state.user.allowed_vlans.length > 0) {
      const allowed = state.user.allowed_vlans.map(Number);
      vlans = vlans.filter(v => allowed.includes(v));
    }

    vlans.sort((a, b) => a - b);

    selectVlan.innerHTML = '<option value="" selected disabled>Selecione a VLAN...</option>';
    if (vlans.length === 0) {
      selectVlan.innerHTML = '<option value="">Nenhuma VLAN configurada nesta OLT</option>';
    } else {
      vlans.forEach(v => {
        const opt = document.createElement('option');
        opt.value = v;
        opt.textContent = `VLAN ${v}`;
        selectVlan.appendChild(opt);
      });
    }
  } catch (e) {
    console.error('Erro ao consultar VLANs da OLT:', e);
    selectVlan.innerHTML = '<option value="">Falha ao carregar VLANs da OLT</option>';
  }

  document.getElementById('modal-provision').classList.add('active');
}

async function handleConfirmProvision() {
  const serial = document.getElementById('prov-serial').value;
  const port = document.getElementById('prov-port').value;
  const mode = document.getElementById('prov-mode').value;
  const profile = document.getElementById('prov-profile').value;
  const onuModel = document.getElementById('prov-onu-model')?.value.trim() || 'auto';
  const vlan = parseInt(document.getElementById('prov-vlan').value, 10);
  const pppoeUser = document.getElementById('prov-pppoe-user').value;
  const pppoePass = document.getElementById('prov-pppoe-pass').value;

  const alertBox = document.getElementById('provision-alert');
  const btnSubmit = document.getElementById('btn-confirm-provision');

  if (!vlan || isNaN(vlan)) {
    alertBox.textContent = 'Selecione uma VLAN válida obtida da OLT.';
    alertBox.classList.remove('hidden');
    return;
  }

  btnSubmit.disabled = true;
  btnSubmit.textContent = 'Autorizando na OLT...';
  logTerminal(`Iniciando autorização da ONU ${serial} na porta ${port} (Modelo: ${onuModel}, Modo: ${mode}, VLAN: ${vlan})...`);

  try {
    const payload = {
      serial,
      port,
      mode,
      vlan,
      onu_model: onuModel,
      profile: profile === 'third_party' ? 'third_party' : 'default',
      pppoe_user: mode === 'router' ? pppoeUser : null,
      pppoe_password: mode === 'router' ? pppoePass : null,
    };

    const resp = await apiRequest(`/olts/${state.selectedOltId}/onus`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    logTerminal(`ONU ${serial} autorizada com sucesso na OLT! Resposta: ${resp.message || 'OK'}`, 'success');
    document.getElementById('modal-provision').classList.remove('active');
    await scanUnauthorizedOnus();
    await loadInventory();
    alert(`ONU ${serial} autorizada com sucesso na OLT!`);
  } catch (error) {
    alertBox.textContent = error.message;
    alertBox.classList.remove('hidden');
    logTerminal(`Falha na autorização da ONU: ${error.message}`, 'error');
  } finally {
    btnSubmit.disabled = false;
    btnSubmit.textContent = 'Autorizar ONU';
  }
}

// ============================================================================
// Modal de Edição de ONU (Inventário)
// ============================================================================
async function openEditOnuModal(serial) {
  const alertBox = document.getElementById('edit-onu-alert');
  if (alertBox) alertBox.classList.add('hidden');

  let onu = state.inventoryOnus.find(o => o.serial === serial);
  if (!onu) {
    try {
      onu = await apiRequest(`/onus/${serial}`);
    } catch (e) {
      logTerminal(`Erro ao buscar dados da ONU ${serial}: ${e.message}`, 'error');
      alert(`Falha ao buscar ONU: ${e.message}`);
      return;
    }
  }

  document.getElementById('edit-onu-serial').value = onu.serial;
  document.getElementById('edit-onu-serial-title').textContent = onu.serial;
  document.getElementById('edit-onu-port').value = onu.current_port || 'N/A';

  const oltId = onu.current_olt_id || state.selectedOltId;
  document.getElementById('edit-onu-olt-id').value = oltId || '';
  
  // Nome amigável da OLT
  const oltObj = state.olts.find(o => o.id === oltId);
  document.getElementById('edit-onu-olt-name').value = oltObj ? oltObj.name : (oltId ? oltId.substring(0, 8) : 'N/A');

  document.getElementById('edit-onu-subscriber').value = onu.subscriber_name || '';
  document.getElementById('edit-onu-circuit').value = onu.circuit_id || '';
  document.getElementById('edit-onu-profile').value = onu.profile || 'DEFAULT';
  document.getElementById('edit-onu-description').value = onu.description || '';

  // Carrega VLANs reais da OLT no dropdown
  const selectVlan = document.getElementById('edit-onu-vlan');
  selectVlan.innerHTML = '<option value="">Consultando VLANs ativas na OLT...</option>';

  try {
    let vlans = [];
    if (oltId) {
      const oltVlans = await apiRequest(`/olts/${oltId}/vlans`);
      if (Array.isArray(oltVlans) && oltVlans.length > 0) {
        vlans = oltVlans.map(v => v.vlan_id);
      }
    }

    if (state.user && state.user.allowed_vlans && state.user.allowed_vlans.length > 0) {
      const allowed = state.user.allowed_vlans.map(Number);
      vlans = vlans.filter(v => allowed.includes(v));
    }

    vlans.sort((a, b) => a - b);

    selectVlan.innerHTML = '<option value="">Sem VLAN definida</option>';
    vlans.forEach(v => {
      const opt = document.createElement('option');
      opt.value = v;
      opt.textContent = `VLAN ${v}`;
      if (onu.vlan && Number(onu.vlan) === v) {
        opt.selected = true;
      }
      selectVlan.appendChild(opt);
    });
  } catch (e) {
    console.error('Erro ao consultar VLANs da OLT para edição:', e);
    selectVlan.innerHTML = `<option value="${onu.vlan || ''}">VLAN ${onu.vlan || 'Atual'}</option>`;
  }

  document.getElementById('modal-edit-onu').classList.add('active');
}

async function handleConfirmEditOnu() {
  const serial = document.getElementById('edit-onu-serial').value;
  const subscriber = document.getElementById('edit-onu-subscriber').value.trim();
  const circuit = document.getElementById('edit-onu-circuit').value.trim();
  const profile = document.getElementById('edit-onu-profile').value.trim();
  const desc = document.getElementById('edit-onu-description').value.trim();
  const vlanVal = document.getElementById('edit-onu-vlan').value;
  const vlan = vlanVal ? parseInt(vlanVal, 10) : null;

  const btn = document.getElementById('btn-confirm-edit-onu');
  const alertBox = document.getElementById('edit-onu-alert');

  btn.disabled = true;
  btn.textContent = 'Salvando...';

  try {
    const payload = {
      subscriber_name: subscriber || null,
      description: desc || null,
      circuit_id: circuit || null,
      profile: profile || 'DEFAULT',
      vlan: vlan,
    };

    const updated = await apiRequest(`/onus/${serial}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });

    logTerminal(`ONU ${serial} atualizada com sucesso! Assinante: ${updated.subscriber_name || 'N/A'}, VLAN: ${updated.vlan || 'N/A'}`, 'success');
    document.getElementById('modal-edit-onu').classList.remove('active');
    await loadInventory();
    alert(`ONU ${serial} atualizada com sucesso!`);
  } catch (error) {
    if (alertBox) {
      alertBox.textContent = `Erro: ${error.message}`;
      alertBox.classList.remove('hidden');
    }
    logTerminal(`Falha ao atualizar ONU ${serial}: ${error.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Salvar Alterações';
  }
}

// ============================================================================
// Event Listeners & Navegação
// ============================================================================
function initEventListeners() {
  // Setup Wizard Form Submit
  const formSetup = document.getElementById('form-setup');
  if (formSetup) {
    formSetup.addEventListener('submit', async (e) => {
      e.preventDefault();
      const masterKey = document.getElementById('setup-master-key').value.trim();
      const providerName = document.getElementById('setup-provider-name').value.trim();
      const adminName = document.getElementById('setup-admin-name').value.trim();
      const adminEmail = document.getElementById('setup-admin-email').value.trim();
      const adminPassword = document.getElementById('setup-admin-password').value;
      const adminPasswordConfirm = document.getElementById('setup-admin-password-confirm')?.value;

      const alertBox = document.getElementById('setup-alert');
      const btn = document.getElementById('btn-submit-setup');

      if (adminPasswordConfirm !== undefined && adminPassword !== adminPasswordConfirm) {
        alertBox.textContent = 'As senhas digitadas não coincidem. Por favor, confirme a mesma senha nos dois campos.';
        alertBox.classList.remove('hidden');
        document.getElementById('setup-admin-password-confirm')?.focus();
        return;
      }

      btn.disabled = true;
      btn.textContent = 'Configurando Sistema...';
      alertBox.classList.add('hidden');

      try {
        await apiRequest('/setup/init', {
          method: 'POST',
          headers: { 'X-API-Key': masterKey },
          body: JSON.stringify({
            provider_name: providerName,
            admin_name: adminName,
            admin_email: adminEmail,
            admin_password: adminPassword,
          }),
        });

        alert('Setup concluído com sucesso! Agora entre com seu e-mail e senha.');
        document.getElementById('login-email').value = adminEmail;
        showView('login');
      } catch (error) {
        alertBox.textContent = error.message;
        alertBox.classList.remove('hidden');
      } finally {
        btn.disabled = false;
        btn.textContent = 'Concluir Setup & Iniciar Sistema';
      }
    });
  }

  // Login Form Submit
  const formLogin = document.getElementById('form-login');
  if (formLogin) {
    formLogin.addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = document.getElementById('login-email').value.trim();
      const password = document.getElementById('login-password').value;
      const alertBox = document.getElementById('login-alert');
      const btn = document.getElementById('btn-submit-login');

      btn.disabled = true;
      btn.textContent = 'Autenticando...';
      alertBox.classList.add('hidden');

      try {
        const data = await apiRequest('/auth/login', {
          method: 'POST',
          body: JSON.stringify({ email, password }),
        });

        state.token = data.access_token;
        sessionStorage.setItem('oltapi_token', data.access_token);
        await hydrateSession();
      } catch (error) {
        alertBox.textContent = error.message;
        alertBox.classList.remove('hidden');
      } finally {
        btn.disabled = false;
        btn.textContent = 'Entrar na Bancada';
      }
    });
  }

  // Logout
  document.getElementById('btn-logout')?.addEventListener('click', logout);

  // Navegação da Sidebar
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
      document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
      const target = e.currentTarget;
      target.classList.add('active');

      const viewId = target.getAttribute('data-view');
      document.getElementById('subview-bancada').classList.add('hidden');
      document.getElementById('subview-inventario').classList.add('hidden');
      document.getElementById('subview-olts').classList.add('hidden');
      document.getElementById('subview-xray').classList.add('hidden');
      document.getElementById('subview-vlans').classList.add('hidden');
      document.getElementById('subview-config').classList.add('hidden');
      document.getElementById('subview-administracao').classList.add('hidden');

      if (viewId === 'bancada') {
        document.getElementById('subview-bancada').classList.remove('hidden');
      } else if (viewId === 'inventario') {
        document.getElementById('subview-inventario').classList.remove('hidden');
        loadInventory();
      } else if (viewId === 'olts') {
        document.getElementById('subview-olts').classList.remove('hidden');
        loadOLTsList();
      } else if (viewId === 'vlans') {
        document.getElementById('subview-vlans').classList.remove('hidden');
        loadVLANsMetrics();
      } else if (viewId === 'config') {
        document.getElementById('subview-config').classList.remove('hidden');
        loadFTPOverview();
      } else if (viewId === 'administracao') {
        document.getElementById('subview-administracao').classList.remove('hidden');
        loadTenants();
      }
    });
  });

  // Seletor de OLTs (Topbar)
  document.getElementById('select-olt')?.addEventListener('change', (e) => {
    state.selectedOltId = e.target.value;
    logTerminal(`OLT alterada para: ${e.target.options[e.target.selectedIndex].text}`);
    scanUnauthorizedOnus();
    const currentActiveView = document.querySelector('.nav-item.active')?.getAttribute('data-view');
    if (currentActiveView === 'vlans') {
      loadVLANsMetrics();
    }
  });

  document.getElementById('btn-refresh-olt')?.addEventListener('click', () => {
    scanUnauthorizedOnus();
    loadInventory();
  });

  // Busca do Radar
  document.getElementById('btn-scan-unauth')?.addEventListener('click', () => scanUnauthorizedOnus());

  // Limpar Terminal
  document.getElementById('btn-clear-terminal')?.addEventListener('click', () => {
    const term = document.getElementById('terminal-output');
    if (term) term.textContent = 'Terminal limpo.';
  });

  // Filtro de Inventário
  document.getElementById('search-inv-serial')?.addEventListener('input', renderInventoryTable);
  document.getElementById('btn-reload-inventory')?.addEventListener('click', loadInventory);

  // Modo Router vs Bridge (alterna visibilidade dos campos PPPoE)
  document.getElementById('prov-mode')?.addEventListener('change', (e) => {
    const boxPPPoE = document.getElementById('box-pppoe');
    if (e.target.value === 'bridge') {
      boxPPPoE.classList.add('hidden');
    } else {
      boxPPPoE.classList.remove('hidden');
    }
  });

  // Disparo do Provisionamento no Modal
  document.getElementById('btn-confirm-provision')?.addEventListener('click', handleConfirmProvision);

  // Disparo de Edição de ONU no Modal
  document.getElementById('btn-confirm-edit-onu')?.addEventListener('click', handleConfirmEditOnu);

  // --- Listeners de OLTs & Raio-X ---
  document.getElementById('btn-reload-olts')?.addEventListener('click', loadOLTsList);

  document.getElementById('btn-open-modal-olt')?.addEventListener('click', () => {
    resetOnboardingModal(true);
    document.getElementById('modal-new-olt')?.classList.add('active');
  });

  document.getElementById('btn-submit-new-olt')?.addEventListener('click', handleStartOnboarding);

  document.getElementById('btn-back-to-olts')?.addEventListener('click', () => {
    document.getElementById('subview-xray').classList.add('hidden');
    document.getElementById('subview-olts').classList.remove('hidden');
    loadOLTsList();
  });

  document.getElementById('btn-refresh-xray')?.addEventListener('click', () => {
    if (state.currentXrayOltId) {
      openOLTXRay(state.currentXrayOltId);
    }
  });

  document.getElementById('btn-copy-config')?.addEventListener('click', () => {
    const text = document.getElementById('xray-running-config')?.textContent;
    if (text) {
      navigator.clipboard.writeText(text).then(() => {
        alert('Configuração copiada para a área de transferência!');
      }).catch(() => {
        alert('Não foi possível copiar automaticamente. Selecione e copie manualmente.');
      });
    }
  });

  // Confirmação defensiva de Exclusão de OLT
  document.getElementById('input-confirm-delete-olt')?.addEventListener('input', (e) => {
    const confirmBtn = document.getElementById('btn-confirm-delete-olt');
    if (!confirmBtn || !pendingDeleteOlt) return;
    const typed = e.target.value.trim();
    if (typed === pendingDeleteOlt.name) {
      confirmBtn.disabled = false;
      confirmBtn.style.opacity = '1.0';
      confirmBtn.style.cursor = 'pointer';
    } else {
      confirmBtn.disabled = true;
      confirmBtn.style.opacity = '0.4';
      confirmBtn.style.cursor = 'not-allowed';
    }
  });

  document.getElementById('btn-confirm-delete-olt')?.addEventListener('click', handleConfirmDeleteOLT);

  // Operações SNMP no Diagnóstico de Chassi
  document.getElementById('btn-xray-test-snmp')?.addEventListener('click', () => handleTestSNMP(false));
  document.getElementById('btn-xray-adopt-snmp')?.addEventListener('click', () => handleTestSNMP(true));
  document.getElementById('btn-xray-provision-snmp')?.addEventListener('click', handleProvisionSNMP);

  // Filtros de Portas no Raio-X
  document.querySelectorAll('.filter-port-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.filter-port-btn').forEach(b => b.classList.remove('active'));
      e.currentTarget.classList.add('active');
      state.currentXrayFilter = e.currentTarget.getAttribute('data-port-filter') || 'all';
      renderXRayPortsGrid();
    });
  });

  // --- Listeners de VLANs ---
  document.getElementById('btn-reload-vlans')?.addEventListener('click', loadVLANsMetrics);

  document.getElementById('btn-open-modal-vlan')?.addEventListener('click', () => {
    document.getElementById('new-vlan-alert')?.classList.add('hidden');
    document.getElementById('modal-new-vlan')?.classList.add('active');
  });

  document.getElementById('btn-submit-new-vlan')?.addEventListener('click', handleCreateVLAN);

  // --- Listeners de FTP ---
  document.getElementById('btn-test-ftp')?.addEventListener('click', testFTPConnection);

  // Fechar Modais (Event Delegation para suportar elementos estáticos e injetados dinamicamente)
  document.addEventListener('click', (e) => {
    const closeBtn = e.target.closest('[data-close-modal]');
    if (closeBtn) {
      const modalId = closeBtn.getAttribute('data-close-modal');
      if (modalId) {
        document.getElementById(modalId)?.classList.remove('active');
      }
    }
  });

  // Alternar Visibilidade de Senhas (Show/Hide Password)
  initPasswordToggles();
}

function initPasswordToggles() {
  document.querySelectorAll('.password-toggle-btn').forEach(btn => {
    if (btn.dataset.initialized === 'true') return;
    btn.dataset.initialized = 'true';

    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const targetId = btn.getAttribute('data-target');
      const input = document.getElementById(targetId);
      if (!input) return;

      const isPassword = input.type === 'password';
      input.type = isPassword ? 'text' : 'password';

      if (isPassword) {
        // Ícone olho cortado (slash) quando visível
        btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" y1="2" x2="22" y2="22"/></svg>`;
        btn.setAttribute('aria-label', 'Ocultar conteúdo');
        btn.setAttribute('title', 'Ocultar conteúdo');
      } else {
        // Ícone olho aberto quando oculto
        btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>`;
        btn.setAttribute('aria-label', 'Exibir conteúdo');
        btn.setAttribute('title', 'Exibir conteúdo');
      }
    });
  });
}


// ============================================================================
// Painel Administrativo (Tenants & Rede Neutra)
// ============================================================================
async function loadTenants() {
  try {
    const tenants = await apiRequest('/tenants');
    state.tenants = tenants;
    const tbody = document.getElementById('tbody-tenants');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (tenants.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">Nenhum inquilino cadastrado.</td></tr>';
      return;
    }

    tenants.forEach(t => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="font-weight: 600;">${t.name}</td>
        <td><span class="badge" style="background: var(--bg-surface-elevated);">${t.type}</span></td>
        <td>${t.vlan_allocations?.map(v => v.vlan_id).join(', ') || '<span style="color: var(--text-muted);">Nenhuma</span>'}</td>
        <td><span class="badge badge-optical-good">Ativo</span></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (error) {
    logTerminal(`Erro ao carregar inquilinos: ${error.message}`, 'error');
  }
}

// ============================================================================
// Módulo: OLTs & Gerenciamento de Chassis
// ============================================================================
async function loadOLTsList() {
  const tbody = document.getElementById('tbody-olts-list');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 20px;">Carregando OLTs...</td></tr>';

  try {
    const olts = await apiRequest('/olts');
    state.olts = olts;
    renderOLTsTable();
  } catch (error) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--accent-rose); padding: 20px;">Erro ao carregar OLTs: ${error.message}</td></tr>`;
    logTerminal(`Erro ao listar OLTs: ${error.message}`, 'error');
  }
}

function renderOLTsTable() {
  const tbody = document.getElementById('tbody-olts-list');
  if (!tbody) return;
  tbody.innerHTML = '';

  if (!state.olts || state.olts.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 30px;">
          Nenhuma OLT cadastrada. Clique em <strong>➕ Cadastrar OLT</strong> para adicionar.
        </td>
      </tr>
    `;
    return;
  }

  state.olts.forEach(olt => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td style="font-weight: 700; font-family: var(--font-mono); color: var(--accent-cyan);">${olt.name}</td>
      <td><span class="badge" style="background: var(--bg-surface-elevated);">${(olt.vendor || '').toUpperCase()} • ${olt.model || 'Auto'}</span></td>
      <td style="font-family: var(--font-mono); font-size: 13px;">${olt.host}:${olt.port}</td>
      <td><span class="badge" style="background: rgba(59,130,246,0.15); color: var(--accent-blue);">${(olt.protocol || 'TELNET').toUpperCase()}</span></td>
      <td id="olt-status-${olt.id}">
        <span class="badge" style="background: rgba(255,255,255,0.08); color: var(--text-secondary);">Não testado</span>
      </td>
      <td style="text-align: right; display: flex; gap: 6px; justify-content: flex-end;">
        <button class="btn btn-secondary btn-sm btn-test-olt" data-id="${olt.id}" title="Testar Conectividade">
          ⚡ Testar
        </button>
        <button class="btn btn-primary btn-sm btn-xray-olt" data-id="${olt.id}" data-name="${olt.name}" title="Telemetria & Diagnóstico de Chassi">
          ⚡ Telemetria
        </button>
        ${(state.user?.role === 'SUPER_ADMIN' || state.user?.role === 'TENANT_ADMIN' || !state.user || state.masterKey) ? `
          <button class="btn btn-secondary btn-sm btn-reveal-olt" data-id="${olt.id}" data-name="${olt.name}" title="Revelar Credenciais (Apenas Administradores)">
            🔑 Senha
          </button>
          <button class="btn btn-secondary btn-sm btn-delete-olt" data-id="${olt.id}" data-name="${olt.name}" title="Excluir OLT (Apenas Administradores)" style="color: var(--status-error); border-color: rgba(239, 68, 68, 0.35);">
            🗑️ Apagar
          </button>
        ` : ''}
        ${state.user?.role === 'SUPER_ADMIN' ? `
          <button class="btn btn-secondary btn-sm btn-sync-olt" data-id="${olt.id}" data-name="${olt.name}" title="Sincronizar Baseline v0">
            📥 Sync v0
          </button>
        ` : ''}
      </td>
    `;
    tbody.appendChild(tr);
  });

  // Binds dos botões da tabela de OLTs
  document.querySelectorAll('.btn-test-olt').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const oltId = e.currentTarget.getAttribute('data-id');
      await testOLTConnection(oltId);
    });
  });

  document.querySelectorAll('.btn-xray-olt').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const oltId = e.currentTarget.getAttribute('data-id');
      const oltName = e.currentTarget.getAttribute('data-name');
      openOLTXRay(oltId, oltName);
    });
  });

  document.querySelectorAll('.btn-reveal-olt').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const oltId = e.currentTarget.getAttribute('data-id');
      const oltName = e.currentTarget.getAttribute('data-name');
      await openRevealCredentialsModal(oltId, oltName);
    });
  });

  document.querySelectorAll('.btn-sync-olt').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const oltId = e.currentTarget.getAttribute('data-id');
      const oltName = e.currentTarget.getAttribute('data-name');
      if (confirm(`Deseja sincronizar e criar o Baseline v0 para a OLT ${oltName}?`)) {
        await syncOLTBaseline(oltId);
      }
    });
  });

  document.querySelectorAll('.btn-delete-olt').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const oltId = e.currentTarget.getAttribute('data-id');
      const oltName = e.currentTarget.getAttribute('data-name');
      openDeleteOLTModal(oltId, oltName);
    });
  });
}

let revealCountdownInterval = null;

async function openRevealCredentialsModal(oltId, oltName) {
  const modal = document.getElementById('modal-reveal-credentials');
  if (!modal) return;

  document.getElementById('reveal-olt-name').textContent = oltName;
  document.getElementById('reveal-olt-endpoint').textContent = 'Consultando...';
  document.getElementById('reveal-olt-username').textContent = '...';
  document.getElementById('reveal-olt-password').value = '••••••••';
  document.getElementById('reveal-timer-countdown').textContent = '30';

  modal.classList.add('active');

  try {
    const creds = await apiRequest(`/olts/${oltId}/reveal-credentials`, 'POST');
    document.getElementById('reveal-olt-endpoint').textContent = `${creds.host}:${creds.port} (${(creds.protocol || 'telnet').toUpperCase()})`;
    document.getElementById('reveal-olt-username').textContent = creds.username;
    document.getElementById('reveal-olt-password').value = creds.password;

    if (revealCountdownInterval) clearInterval(revealCountdownInterval);
    let secondsLeft = 30;
    revealCountdownInterval = setInterval(() => {
      secondsLeft--;
      const el = document.getElementById('reveal-timer-countdown');
      if (el) el.textContent = secondsLeft;
      if (secondsLeft <= 0) {
        clearInterval(revealCountdownInterval);
        modal.classList.remove('active');
        document.getElementById('reveal-olt-password').value = '••••••••';
      }
    }, 1000);

    const copyBtn = document.getElementById('btn-copy-revealed-pass');
    if (copyBtn) {
      copyBtn.onclick = () => {
        navigator.clipboard.writeText(creds.password);
        copyBtn.textContent = '✅ Copiado!';
        setTimeout(() => { copyBtn.textContent = '📋 Copiar'; }, 2000);
      };
    }
  } catch (error) {
    alert(`Não foi possível revelar credenciais: ${error.message}`);
    modal.classList.remove('active');
  }
}

let pendingDeleteOlt = null;

function openDeleteOLTModal(oltId, oltName) {
  pendingDeleteOlt = { id: oltId, name: oltName };
  const modal = document.getElementById('modal-delete-olt');
  if (!modal) return;

  const targetNameEl = document.getElementById('delete-olt-target-name');
  const namePromptEl = document.getElementById('delete-olt-name-prompt');
  const inputEl = document.getElementById('input-confirm-delete-olt');
  const confirmBtn = document.getElementById('btn-confirm-delete-olt');

  if (targetNameEl) targetNameEl.textContent = oltName;
  if (namePromptEl) namePromptEl.textContent = oltName;
  if (inputEl) {
    inputEl.value = '';
    setTimeout(() => inputEl.focus(), 150);
  }
  if (confirmBtn) {
    confirmBtn.disabled = true;
    confirmBtn.style.opacity = '0.4';
    confirmBtn.style.cursor = 'not-allowed';
    confirmBtn.textContent = '🗑️ Sim, Excluir OLT';
  }

  modal.classList.add('active');
}

async function handleConfirmDeleteOLT() {
  if (!pendingDeleteOlt) return;
  const { id, name } = pendingDeleteOlt;
  const inputEl = document.getElementById('input-confirm-delete-olt');
  if (!inputEl || inputEl.value.trim() !== name) {
    alert('O nome digitado não corresponde exatamente ao nome da OLT.');
    return;
  }

  const confirmBtn = document.getElementById('btn-confirm-delete-olt');
  if (confirmBtn) {
    confirmBtn.disabled = true;
    confirmBtn.textContent = 'Excluindo...';
  }

  try {
    await apiRequest(`/olts/${id}`, 'DELETE');
    logTerminal(`OLT '${name}' excluída com sucesso do sistema.`, 'warning');
    document.getElementById('modal-delete-olt')?.classList.remove('active');
    pendingDeleteOlt = null;

    if (state.currentXrayOltId === id) {
      document.getElementById('subview-xray')?.classList.add('hidden');
      document.getElementById('subview-olts')?.classList.remove('hidden');
      state.currentXrayOltId = null;
    }

    await loadOLTs();
    await loadOLTsList();
  } catch (err) {
    alert(`Erro ao excluir OLT: ${err.message}`);
    logTerminal(`Falha ao excluir OLT '${name}': ${err.message}`, 'error');
  } finally {
    if (confirmBtn) {
      confirmBtn.disabled = true;
      confirmBtn.style.opacity = '0.4';
      confirmBtn.style.cursor = 'not-allowed';
      confirmBtn.textContent = '🗑️ Sim, Excluir OLT';
    }
  }
}

async function testOLTConnection(oltId) {
  const statusCell = document.getElementById(`olt-status-${oltId}`);
  if (statusCell) {
    statusCell.innerHTML = '<span class="badge" style="color: var(--accent-cyan);">Testando...</span>';
  }
  logTerminal(`Testando conectividade com OLT ID ${oltId}...`);

  try {
    const res = await apiRequest(`/olts/${oltId}/test-connection`, { method: 'POST' });
    const reachable = res.reachable;
    if (statusCell) {
      if (reachable) {
        statusCell.innerHTML = `<span class="badge badge-optical-good">Online • ${res.latency_ms ? res.latency_ms + 'ms' : 'OK'}</span>`;
      } else {
        statusCell.innerHTML = `<span class="badge badge-optical-bad" title="${res.message || ''}">Inalcançável</span>`;
      }
    }
    logTerminal(`Conectividade OLT: ${reachable ? 'OK' : 'Falha'} - ${res.message || ''}`, reachable ? 'success' : 'error');
  } catch (err) {
    if (statusCell) {
      statusCell.innerHTML = '<span class="badge badge-optical-bad">Erro</span>';
    }
    logTerminal(`Erro ao testar conexão: ${err.message}`, 'error');
  }
}

function resetOnboardingModal(clearForm = false) {
  document.getElementById('new-olt-alert')?.classList.add('hidden');
  if (clearForm) {
    document.getElementById('form-new-olt')?.reset();
  }
  document.getElementById('onboarding-form-section')?.classList.remove('hidden');
  document.getElementById('onboarding-stepper-section')?.classList.add('hidden');
  document.getElementById('onboarding-summary-card')?.classList.add('hidden');
  
  const footer = document.getElementById('onboarding-modal-footer');
  if (footer) {
    footer.innerHTML = `
      <button class="btn btn-secondary" id="btn-cancel-new-olt" data-close-modal="modal-new-olt">Cancelar</button>
      <button type="button" id="btn-submit-new-olt" class="btn btn-primary">⚡ Iniciar Onboarding Automático</button>
    `;
    document.getElementById('btn-cancel-new-olt')?.addEventListener('click', () => {
      document.getElementById('modal-new-olt')?.classList.remove('active');
    });
    document.getElementById('btn-submit-new-olt')?.addEventListener('click', handleStartOnboarding);
  }

  // Reseta visual dos passos do stepper
  ['connectivity', 'fingerprint', 'baseline', 'snmp', 'inventory'].forEach(k => {
    const stepEl = document.getElementById(`step-${k}`);
    const descEl = document.getElementById(`step-desc-${k}`);
    if (stepEl) stepEl.className = 'stepper-step';
    if (descEl) {
      if (k === 'connectivity') descEl.textContent = 'Testando handshake e autenticação...';
      else if (k === 'fingerprint') descEl.textContent = 'Aguardando conexão...';
      else if (k === 'baseline') descEl.textContent = 'Aguardando identificação...';
      else if (k === 'snmp') descEl.textContent = 'Aguardando backup inicial...';
      else if (k === 'inventory') descEl.textContent = 'Mapeando portas, VLANs e ONUs ativas...';
    }
  });
}

async function handleStartOnboarding() {
  const name = document.getElementById('new-olt-name')?.value.trim();
  const host = document.getElementById('new-olt-host')?.value.trim();
  const username = document.getElementById('new-olt-username')?.value.trim();
  const password = document.getElementById('new-olt-password')?.value;
  const customPortVal = document.getElementById('new-olt-custom-port')?.value.trim();
  const customPort = customPortVal ? parseInt(customPortVal, 10) : null;

  const alertBox = document.getElementById('new-olt-alert');
  const btn = document.getElementById('btn-submit-new-olt');
  const cancelBtn = document.getElementById('btn-cancel-new-olt');
  const logBox = document.getElementById('onboarding-terminal-logs');

  if (!name || !host || !username || !password) {
    if (alertBox) {
      alertBox.textContent = 'Preencha todos os campos obrigatórios (Nome, Host/IP, Usuário e Senha).';
      alertBox.classList.remove('hidden');
    }
    return;
  }

  if (alertBox) alertBox.classList.add('hidden');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Onboarding em Andamento...';
  }
  if (cancelBtn) cancelBtn.disabled = true;

  // Transita para visualização do Stepper
  document.getElementById('onboarding-form-section')?.classList.add('hidden');
  document.getElementById('onboarding-stepper-section')?.classList.remove('hidden');

  const updateStep = (key, status, desc) => {
    const stepEl = document.getElementById(`step-${key}`);
    const descEl = document.getElementById(`step-desc-${key}`);
    if (stepEl) stepEl.className = `stepper-step step-${status}`;
    if (descEl && desc) descEl.textContent = desc;
  };

  updateStep('connectivity', 'running', `Iniciando probe SSH (:22) e Telnet (:23) em ${host}...`);
  if (logBox) logBox.textContent = `[1/5] Conectando à OLT em ${host}...`;
  logTerminal(`Iniciando Onboarding Zero-Touch para OLT '${name}' em ${host}...`);

  const mapStepKey = (rawKey) => {
    if (rawKey === 'baseline_backup') return 'baseline';
    if (rawKey === 'inventory_sync') return 'inventory';
    return rawKey;
  };

  try {
    const headers = {
      'Content-Type': 'application/json',
    };
    if (state.token) {
      headers['Authorization'] = `Bearer ${state.token}`;
    }

    const response = await fetch(`${API_BASE}/olts/onboard/stream`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        name,
        host,
        username,
        password,
        custom_port: customPort,
      }),
    });

    if (response.status === 401) {
      logout();
      throw new Error('Sessão expirada. Faça login novamente.');
    }

    if (!response.ok) {
      let errText = `HTTP ${response.status}`;
      try {
        const errJson = await response.json();
        errText = errJson.detail || errJson.message || errText;
      } catch (_) {}
      throw new Error(errText);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    let completedResponse = null;
    let streamError = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // Mantém linha incompleta no buffer

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith('data:')) continue;
        const jsonStr = trimmed.replace(/^data:\s*/, '');
        try {
          const ev = JSON.parse(jsonStr);
          if (ev.type === 'step_update') {
            const stepKey = mapStepKey(ev.step_key);
            updateStep(stepKey, ev.status, ev.message);
            if (logBox) {
              logBox.textContent = `[${ev.step_key.toUpperCase()}] ${ev.message}`;
            }
          } else if (ev.type === 'completed') {
            completedResponse = ev.response;
          } else if (ev.type === 'error') {
            streamError = ev.message;
          }
        } catch (parseErr) {
          if (jsonStr.startsWith('{')) {
            console.warn('Aviso ao processar evento SSE:', parseErr, jsonStr);
          }
        }
      }
    }

    if (streamError) {
      throw new Error(streamError);
    }

    if (!completedResponse) {
      throw new Error('Fluxo de onboarding interrompido sem conclusão.');
    }

    const res = completedResponse;

    // Atualiza status de todas as etapas finais
    if (res.steps) {
      res.steps.forEach(s => {
        updateStep(mapStepKey(s.step_key), s.status, s.details);
      });
    }

    if (logBox) {
      logBox.textContent = `[Concluído] ${res.message}`;
    }

    // Preenche Card Resumo de Conclusão
    const summaryCard = document.getElementById('onboarding-summary-card');
    if (summaryCard) {
      document.getElementById('summary-olt-protocol-badge').textContent = `${(res.protocol || 'TELNET').toUpperCase()} :${res.port}`;
      document.getElementById('summary-olt-name').textContent = res.name;
      document.getElementById('summary-olt-vendor-model').textContent = `${(res.vendor || '').toUpperCase()} • ${res.model || 'Auto'}`;
      document.getElementById('summary-olt-ports').textContent = `${res.active_ports} / ${res.total_ports} UP`;
      document.getElementById('summary-olt-onus').textContent = `${res.total_onus_detected} ONUs`;
      document.getElementById('summary-olt-firmware').textContent = res.firmware_version || 'Detectado';
      document.getElementById('summary-olt-snmp').textContent = res.snmp_active ? `Ativo (${res.snmp_community})` : `Inativo (${res.snmp_community})`;
      summaryCard.classList.remove('hidden');
    }

    // Altera o rodapé para navegação
    const footer = document.getElementById('onboarding-modal-footer');
    if (footer) {
      footer.innerHTML = `
        <button type="button" class="btn btn-secondary" id="btn-onboarding-close">Fechar</button>
        <button type="button" class="btn btn-primary" id="btn-onboarding-goto-xray">⚡ Ver Telemetria do Chassi</button>
      `;
      document.getElementById('btn-onboarding-close')?.addEventListener('click', () => {
        document.getElementById('modal-new-olt')?.classList.remove('active');
        resetOnboardingModal(true);
      });
      document.getElementById('btn-onboarding-goto-xray')?.addEventListener('click', () => {
        document.getElementById('modal-new-olt')?.classList.remove('active');
        resetOnboardingModal(true);
        openOLTXRay(res.olt_id, res.name);
      });
    }

    logTerminal(`Onboarding concluído com sucesso para ${res.name}! ${res.total_onus_detected} ONUs sincronizadas.`, 'success');
    await loadOLTs();
    await loadOLTsList();
  } catch (err) {
    let shortMsg = err.message || 'Erro durante o processo de onboarding.';
    if (shortMsg.includes('Não foi possível autenticar ou conectar') || shortMsg.includes('Falha de conexão')) {
      shortMsg = 'Não foi possível conectar à OLT via SSH ou Telnet. Siga as instruções no card da etapa abaixo para habilitar o acesso.';
    } else if (shortMsg.length > 120) {
      const firstPeriod = shortMsg.indexOf('.');
      if (firstPeriod > 0) {
        shortMsg = shortMsg.slice(0, firstPeriod + 1);
      }
    }

    if (alertBox) {
      alertBox.textContent = `Falha no Onboarding: ${shortMsg}`;
      alertBox.classList.remove('hidden');
    }
    if (logBox) {
      logBox.textContent = `[Falha no Onboarding] ${shortMsg}`;
    }
    const footer = document.getElementById('onboarding-modal-footer');
    if (footer) {
      footer.innerHTML = `
        <button type="button" class="btn btn-secondary" id="btn-onboarding-error-close" data-close-modal="modal-new-olt">Fechar</button>
        <button type="button" class="btn btn-primary" id="btn-onboarding-retry">Tentar Novamente</button>
      `;
      document.getElementById('btn-onboarding-error-close')?.addEventListener('click', () => {
        document.getElementById('modal-new-olt')?.classList.remove('active');
      });
      document.getElementById('btn-onboarding-retry')?.addEventListener('click', () => {
        resetOnboardingModal(false);
      });
    }
    logTerminal(`Falha no onboarding da OLT: ${err.message}`, 'error');
  }
}

// ============================================================================
// Módulo: Raio-X Detalhado da OLT
// ============================================================================
async function openOLTXRay(oltId, oltName) {
  state.currentXrayOltId = oltId;
  document.getElementById('subview-olts').classList.add('hidden');
  document.getElementById('subview-xray').classList.remove('hidden');

  document.getElementById('xray-olt-title').textContent = `⚡ Telemetria do Chassi: ${oltName || ''}`;
  document.getElementById('xray-olt-subtitle').textContent = `Diagnóstico de hardware, interfaces físicas e running-config em tempo real.`;
  const badgeFw = document.getElementById('xray-badge-firmware');
  if (badgeFw) {
    badgeFw.className = 'badge badge-info';
    badgeFw.removeAttribute('style');
    badgeFw.textContent = 'Firmware: Carregando...';
  }
  const badgeUp = document.getElementById('xray-badge-uptime');
  if (badgeUp) {
    badgeUp.className = 'badge badge-optical-good';
    badgeUp.removeAttribute('style');
    badgeUp.textContent = 'Uptime: Carregando...';
  }
  const badgeSnmp = document.getElementById('xray-badge-snmp');
  if (badgeSnmp) {
    badgeSnmp.className = 'badge badge-neutral';
    badgeSnmp.removeAttribute('style');
    badgeSnmp.textContent = 'SNMP: Carregando...';
  }
  document.getElementById('xray-stat-total-ports').textContent = '...';
  document.getElementById('xray-stat-active-ports').textContent = '...';
  document.getElementById('xray-stat-down-ports').textContent = '...';
  document.getElementById('xray-stat-onus-detected').textContent = '...';
  document.getElementById('xray-ports-grid').innerHTML = '<div style="text-align: center; color: var(--text-muted); grid-column: 1 / -1; padding: 30px;">Consultando interfaces físicas e telemetria do chassi...</div>';
  document.getElementById('xray-running-config').textContent = 'Consultando running-config...';

  logTerminal(`Consultando telemetria e estado de portas na OLT ${oltName || oltId}...`);

  try {
    const xray = await apiRequest(`/olts/${oltId}/telemetry`, { method: 'POST' });
    state.currentXray = xray;
    renderXRayView(xray);
    logTerminal(`Telemetria concluída! ${xray.total_onus_detected} ONU(s) e ${xray.ports?.length || 0} porta(s) mapeada(s).`, 'success');
  } catch (error) {
    document.getElementById('xray-ports-grid').innerHTML = `<div style="text-align: center; color: var(--accent-rose); grid-column: 1 / -1; padding: 30px;">Falha na telemetria: ${error.message}</div>`;
    document.getElementById('xray-running-config').textContent = `Falha: ${error.message}`;
    logTerminal(`Falha na telemetria da OLT: ${error.message}`, 'error');
  }
}

function renderXRayView(xray) {
  if (!xray) return;
  const fwBadge = document.getElementById('xray-badge-firmware');
  if (fwBadge) {
    fwBadge.className = 'badge badge-info';
    fwBadge.removeAttribute('style');
    fwBadge.textContent = `Firmware: ${xray.firmware_version || 'Detectado'}`;
  }
  const uptimeBadge = document.getElementById('xray-badge-uptime');
  if (uptimeBadge) {
    uptimeBadge.className = 'badge badge-optical-good';
    uptimeBadge.removeAttribute('style');
    uptimeBadge.textContent = `Uptime: ${xray.uptime_human || 'Ativo'}`;
  }

  // Telemetria e Diagnóstico SNMP
  const snmpBadge = document.getElementById('xray-badge-snmp');
  const snmpPill = document.getElementById('xray-snmp-status-pill');
  const snmpMsg = document.getElementById('xray-snmp-message');
  const snmpInputComm = document.getElementById('xray-snmp-input-community');
  const snmpInputPort = document.getElementById('xray-snmp-input-port');
  const snmpResult = document.getElementById('xray-snmp-result');

  if (snmpInputComm && xray.snmp_community) {
    snmpInputComm.value = xray.snmp_community;
  }
  if (snmpResult) {
    snmpResult.classList.add('hidden');
    snmpResult.textContent = '';
  }

  if (snmpMsg) {
    snmpMsg.textContent = xray.snmp_message || 'Diagnóstico e status do agente SNMP na OLT física.';
  }

  if (xray.snmp_active) {
    if (snmpBadge) {
      snmpBadge.className = 'badge badge-optical-good';
      snmpBadge.removeAttribute('style');
      snmpBadge.textContent = `SNMP: Ativo (${xray.snmp_community || 'v2c'})`;
    }
    if (snmpPill) {
      snmpPill.className = 'badge badge-optical-good';
      snmpPill.removeAttribute('style');
      snmpPill.textContent = 'SNMP Ativo';
    }
  } else if (xray.snmp_status === 'cipher_detected') {
    if (snmpBadge) {
      snmpBadge.className = 'badge badge-optical-warn';
      snmpBadge.removeAttribute('style');
      snmpBadge.textContent = 'SNMP: Criptografado (Huawei Cipher)';
    }
    if (snmpPill) {
      snmpPill.className = 'badge badge-optical-warn';
      snmpPill.removeAttribute('style');
      snmpPill.textContent = 'Cipher Detectado';
    }
  } else if (xray.snmp_status === 'unreachable') {
    if (snmpBadge) {
      snmpBadge.className = 'badge badge-optical-bad';
      snmpBadge.removeAttribute('style');
      snmpBadge.textContent = 'SNMP: Timeout UDP 161';
    }
    if (snmpPill) {
      snmpPill.className = 'badge badge-optical-bad';
      snmpPill.removeAttribute('style');
      snmpPill.textContent = 'Inacessível';
    }
  } else {
    if (snmpBadge) {
      snmpBadge.className = 'badge badge-neutral';
      snmpBadge.removeAttribute('style');
      snmpBadge.textContent = 'SNMP: Não Configurado';
    }
    if (snmpPill) {
      snmpPill.className = 'badge badge-neutral';
      snmpPill.removeAttribute('style');
      snmpPill.textContent = 'Não Configurado';
    }
  }

  const ports = xray.ports || [];
  const activeCount = ports.filter(p => p.oper_status === 'up').length;
  const downCount = ports.filter(p => p.oper_status !== 'up').length;

  document.getElementById('xray-stat-total-ports').textContent = ports.length;
  document.getElementById('xray-stat-active-ports').textContent = activeCount;
  document.getElementById('xray-stat-down-ports').textContent = downCount;
  document.getElementById('xray-stat-onus-detected').textContent = xray.total_onus_detected || 0;

  renderXRayPortsGrid();

  const configPre = document.getElementById('xray-running-config');
  if (configPre) {
    configPre.textContent = xray.running_config_raw || '! Configuração não disponível no momento.';
  }
}

async function handleTestSNMP(save = false) {
  const oltId = state.currentXrayOltId;
  if (!oltId) return;

  const comm = document.getElementById('xray-snmp-input-community')?.value.trim();
  const port = parseInt(document.getElementById('xray-snmp-input-port')?.value, 10) || 161;
  const resultBox = document.getElementById('xray-snmp-result');
  const btn = save ? document.getElementById('btn-xray-adopt-snmp') : document.getElementById('btn-xray-test-snmp');

  if (resultBox) {
    resultBox.className = 'badge badge-optical-good';
    resultBox.style.display = 'block';
    resultBox.style.background = 'rgba(59,130,246,0.15)';
    resultBox.style.color = 'var(--accent-blue)';
    resultBox.textContent = `Enviando pacote SNMP Get (sysUpTime) para ${state.currentXray?.host || 'OLT'}:${port}...`;
    resultBox.classList.remove('hidden');
  }

  if (btn) btn.disabled = true;
  try {
    const res = await apiRequest(`/olts/${oltId}/snmp/test`, {
      method: 'POST',
      body: JSON.stringify({
        community: comm || null,
        port: port,
        save_if_successful: save,
      }),
    });

    if (resultBox) {
      if (res.reachable) {
        resultBox.style.background = 'rgba(16,185,129,0.15)';
        resultBox.style.color = 'var(--accent-green)';
        resultBox.textContent = `✅ ${res.message}`;
        logTerminal(`Teste SNMP em ${res.host}:${res.port}: Sucesso! Uptime ${res.uptime_seconds}s (${res.latency_ms}ms)`, 'success');
        if (save) {
          await openOLTXRay(oltId, state.currentXray?.olt_name);
          await loadOLTs();
          if (resultBox) {
            resultBox.className = 'badge badge-optical-good';
            resultBox.style.display = 'block';
            resultBox.style.background = 'rgba(16,185,129,0.15)';
            resultBox.style.color = 'var(--accent-green)';
            resultBox.textContent = `✅ Comunidade '${res.community}' salva no cadastro e validada com sucesso!`;
            resultBox.classList.remove('hidden');
          }
        }
      } else {
        resultBox.style.background = 'rgba(239,68,68,0.15)';
        resultBox.style.color = 'var(--accent-rose)';
        resultBox.textContent = `❌ ${res.message}`;
        logTerminal(`Teste SNMP em ${res.host}:${res.port}: Falha ao responder UDP.`, 'error');
      }
    }
  } catch (err) {
    if (resultBox) {
      resultBox.style.background = 'rgba(239,68,68,0.15)';
      resultBox.style.color = 'var(--accent-rose)';
      resultBox.textContent = `Erro ao testar SNMP: ${err.message}`;
    }
    logTerminal(`Erro SNMP: ${err.message}`, 'error');
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function handleProvisionSNMP() {
  const oltId = state.currentXrayOltId;
  if (!oltId) return;

  const comm = document.getElementById('xray-snmp-input-community')?.value.trim();
  const port = parseInt(document.getElementById('xray-snmp-input-port')?.value, 10) || 161;
  const resultBox = document.getElementById('xray-snmp-result');
  const btn = document.getElementById('btn-xray-provision-snmp');

  if (!comm) {
    alert('Informe uma comunidade SNMP para provisionar na OLT.');
    return;
  }

  const confirmed = confirm(
    `ATENÇÃO (Ação de Administrador):\n\nA API irá conectar via CLI na OLT e configurar a comunidade somente-leitura '${comm}', habilitar SNMP v2c e salvar permanentemente na memória flash (save/write).\n\nDeseja prosseguir sem entrar no terminal da OLT?`
  );
  if (!confirmed) return;

  if (resultBox) {
    resultBox.className = 'badge badge-optical-good';
    resultBox.style.display = 'block';
    resultBox.style.background = 'rgba(59,130,246,0.15)';
    resultBox.style.color = 'var(--accent-blue)';
    resultBox.textContent = `Conectando via CLI na OLT para provisionar SNMP e gravar na flash...`;
    resultBox.classList.remove('hidden');
  }

  if (btn) btn.disabled = true;
  try {
    const res = await apiRequest(`/olts/${oltId}/snmp/configure`, {
      method: 'POST',
      body: JSON.stringify({
        community: comm,
        port: port,
      }),
    });

    if (resultBox) {
      resultBox.style.background = 'rgba(16,185,129,0.15)';
      resultBox.style.color = 'var(--accent-green)';
      resultBox.textContent = `✅ ${res.message}`;
    }
    logTerminal(`Provisionamento SNMP na OLT ${res.host}: ${res.message}`, 'success');
    alert(`Comunidade SNMP '${comm}' provisionada com sucesso na OLT!`);
    await openOLTXRay(oltId, state.currentXray?.olt_name);
    await loadOLTs();
    if (resultBox) {
      resultBox.className = 'badge badge-optical-good';
      resultBox.style.display = 'block';
      resultBox.style.background = 'rgba(16,185,129,0.15)';
      resultBox.style.color = 'var(--accent-green)';
      resultBox.textContent = `✅ Comunidade SNMP '${comm}' provisionada na OLT e salva no cadastro!`;
      resultBox.classList.remove('hidden');
    }
  } catch (err) {
    if (resultBox) {
      resultBox.style.background = 'rgba(239,68,68,0.15)';
      resultBox.style.color = 'var(--accent-rose)';
      resultBox.textContent = `Erro ao provisionar SNMP na OLT: ${err.message}`;
    }
    logTerminal(`Erro no provisionamento SNMP: ${err.message}`, 'error');
    alert(`Erro ao provisionar SNMP: ${err.message}`);
  } finally {
    if (btn) btn.disabled = false;
  }
}

function renderXRayPortsGrid() {
  const container = document.getElementById('xray-ports-grid');
  if (!container || !state.currentXray) return;
  container.innerHTML = '';

  const filter = state.currentXrayFilter || 'all';
  const allPorts = state.currentXray.ports || [];

  const filteredPorts = allPorts.filter(p => {
    if (filter === 'all') return true;
    if (filter === 'pon') return p.port_type?.toLowerCase().includes('pon') || p.port_id?.toLowerCase().includes('pon');
    if (filter === 'uplink') return p.port_type?.toLowerCase().includes('uplink') || p.port_type?.toLowerCase().includes('ge') || p.port_id?.toLowerCase().includes('xg') || p.port_id?.toLowerCase().includes('ge');
    return true;
  });

  if (filteredPorts.length === 0) {
    container.innerHTML = `<div style="text-align: center; color: var(--text-muted); grid-column: 1 / -1; padding: 24px;">Nenhuma porta encontrada para o filtro selecionado.</div>`;
    return;
  }

  filteredPorts.forEach(port => {
    const card = document.createElement('div');
    card.className = 'port-card';

    let ledClass = 'led-down';
    let statusText = 'DOWN';
    if (port.oper_status === 'up') {
      ledClass = 'led-up';
      statusText = 'UP';
    } else if (port.oper_status === 'disabled') {
      ledClass = 'led-disabled';
      statusText = 'DISABLED';
    }

    const isPon = port.port_type?.toLowerCase().includes('pon') || port.port_id?.toLowerCase().includes('pon');
    const onuCount = port.onu_count || 0;
    const maxCapacity = port.max_capacity || 128;
    const pct = Math.min(100, Math.round((onuCount / maxCapacity) * 100));

    let metricsHtml = '';
    if (isPon) {
      metricsHtml = `
        <div class="port-metrics">
          <span style="color: var(--text-secondary);">ONUs:</span>
          <span class="port-onu-count">${onuCount} / ${maxCapacity}</span>
        </div>
        <div class="port-progress-bg" title="Capacidade: ${pct}%">
          <div class="port-progress-fill" style="width: ${pct}%;"></div>
        </div>
      `;
    } else {
      metricsHtml = `
        <div class="port-metrics" style="margin-top: 2px;">
          <span style="color: var(--text-secondary);">Tipo:</span>
          <span style="font-family: var(--font-mono); font-size: 11px; font-weight: 600; color: var(--accent-cyan);">Uplink / Core</span>
        </div>
      `;
    }

    card.innerHTML = `
      <div class="port-header">
        <span class="port-name">${port.port_id}</span>
        <span class="port-led ${ledClass}" title="Status: ${statusText}"></span>
      </div>
      <div class="port-type-badge">${port.port_type ? port.port_type.toUpperCase() : (isPon ? 'PON' : 'UPLINK')} • ${statusText}</div>
      ${metricsHtml}
    `;
    container.appendChild(card);
  });
}

async function syncOLTBaseline(oltId) {
  logTerminal(`Iniciando Sincronização & Criação de Baseline v0 para OLT ${oltId}...`);
  try {
    const res = await apiRequest(`/olts/${oltId}/sync`, { method: 'POST' });
    logTerminal(`Sincronização concluída com sucesso! ONUs descobertas: ${res.total_onus_discovered}, Baseline Backup ID: ${res.baseline_backup_id}`, 'success');
    alert(`Importação e Baseline concluídos com sucesso!\n\nONUs Descobertas: ${res.total_onus_discovered}\nNovas ONUs Registradas: ${res.new_onus_registered}\nBackup Baseline: ${res.baseline_backup_id}`);
    await loadInventory();
  } catch (error) {
    logTerminal(`Erro ao sincronizar OLT: ${error.message}`, 'error');
    alert(`Falha na sincronização: ${error.message}`);
  }
}

// ============================================================================
// Módulo: VLANs & Serviços
// ============================================================================
async function loadVLANsMetrics() {
  const tbody = document.getElementById('tbody-vlans-metrics');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 20px;">Carregando métricas de VLANs...</td></tr>';

  if (!state.selectedOltId) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 20px;">Selecione uma OLT ativa na barra superior para visualizar as VLANs.</td></tr>';
    return;
  }

  try {
    const vlans = await apiRequest(`/olts/${state.selectedOltId}/vlans/metrics`);
    state.vlans = vlans;
    renderVLANsTable();
  } catch (error) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--accent-rose); padding: 20px;">Erro ao carregar VLANs: ${error.message}</td></tr>`;
    logTerminal(`Erro ao carregar métricas de VLANs: ${error.message}`, 'error');
  }
}

function renderVLANsTable() {
  const tbody = document.getElementById('tbody-vlans-metrics');
  if (!tbody) return;
  tbody.innerHTML = '';

  if (!state.vlans || state.vlans.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 30px;">
          Nenhuma VLAN encontrada nesta OLT. Clique em <strong>➕ Criar VLAN</strong> para adicionar.
        </td>
      </tr>
    `;
    return;
  }

  state.vlans.forEach(vlan => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td style="font-family: var(--font-mono); font-weight: 700; color: var(--accent-cyan); font-size: 14px;">
        VLAN ${vlan.vlan_id}
      </td>
      <td style="font-weight: 600;">${vlan.name}</td>
      <td style="color: var(--text-secondary); font-size: 12px;">${vlan.description || '-'}</td>
      <td>
        <span class="badge" style="background: var(--bg-surface-elevated); font-size: 12px; font-family: var(--font-mono);">
          ${vlan.total_provisioned_onus || 0} ONUs
        </span>
      </td>
      <td>
        <span class="badge badge-optical-good" style="font-size: 12px; font-family: var(--font-mono);">
          ${vlan.total_active_onus || 0} Online
        </span>
      </td>
      <td style="text-align: right;">
        <button class="btn btn-secondary btn-sm btn-vlan-history" data-vlan="${vlan.vlan_id}" data-name="${vlan.name}" title="Ver Histórico de Seriais">
          📜 Histórico de Seriais
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  document.querySelectorAll('.btn-vlan-history').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const vlanId = e.currentTarget.getAttribute('data-vlan');
      const vlanName = e.currentTarget.getAttribute('data-name');
      openVLANHistoryModal(vlanId, vlanName);
    });
  });
}

async function openVLANHistoryModal(vlanId, vlanName) {
  document.getElementById('vlan-history-title').textContent = `${vlanId} (${vlanName || 'Serviço'})`;
  const tbody = document.getElementById('tbody-vlan-history');
  tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 20px;">Carregando histórico de seriais...</td></tr>';
  document.getElementById('modal-vlan-history').classList.add('active');

  try {
    const history = await apiRequest(`/olts/${state.selectedOltId}/vlans/${vlanId}/history`);
    tbody.innerHTML = '';

    if (!history || history.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 24px;">Nenhum serial registrado nesta VLAN até o momento.</td></tr>';
      return;
    }

    history.forEach(item => {
      const tr = document.createElement('tr');
      const firstSeen = item.first_seen ? new Date(item.first_seen).toLocaleString() : '-';
      const lastSeen = item.last_seen ? new Date(item.last_seen).toLocaleString() : '-';
      tr.innerHTML = `
        <td style="font-family: var(--font-mono); font-weight: 600; color: var(--accent-cyan);">${item.serial}</td>
        <td>${item.subscriber_name || item.description || '<span style="color: var(--text-muted);">Sem assinante</span>'}</td>
        <td style="font-size: 12px; color: var(--text-secondary);">${firstSeen}</td>
        <td style="font-size: 12px; color: var(--text-secondary);">${lastSeen}</td>
        <td>
          <span class="badge ${item.is_active ? 'badge-optical-good' : 'badge-optical-warn'}">
            ${item.is_active ? 'Ativo Agora' : 'Anterior'}
          </span>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (error) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--accent-rose); padding: 20px;">Erro: ${error.message}</td></tr>`;
  }
}

async function handleCreateVLAN() {
  if (!state.selectedOltId) {
    alert('Selecione uma OLT ativa para criar a VLAN.');
    return;
  }

  const vlanId = parseInt(document.getElementById('new-vlan-id').value, 10);
  const name = document.getElementById('new-vlan-name').value.trim();
  const desc = document.getElementById('new-vlan-desc').value.trim();
  const portsRaw = document.getElementById('new-vlan-ports').value.trim();

  const alertBox = document.getElementById('new-vlan-alert');
  const btn = document.getElementById('btn-submit-new-vlan');

  if (!vlanId || isNaN(vlanId) || !name) {
    alertBox.textContent = 'Informe um VLAN ID válido e o Nome do serviço.';
    alertBox.classList.remove('hidden');
    return;
  }

  const taggedPorts = portsRaw ? portsRaw.split(',').map(p => p.trim()).filter(Boolean) : [];

  btn.disabled = true;
  btn.textContent = 'Criando & Salvando na Flash...';
  alertBox.classList.add('hidden');

  try {
    await apiRequest(`/olts/${state.selectedOltId}/vlans`, {
      method: 'POST',
      body: JSON.stringify({
        vlan_id: vlanId,
        name,
        description: desc || null,
        tagged_ports: taggedPorts,
      }),
    });

    logTerminal(`VLAN ${vlanId} criada e salva na flash com sucesso!`, 'success');
    document.getElementById('modal-new-vlan').classList.remove('active');
    document.getElementById('form-new-vlan').reset();
    await loadVLANsMetrics();
    alert(`VLAN ${vlanId} criada com sucesso e persistida na memória permanente (flash) da OLT!`);
  } catch (err) {
    alertBox.textContent = err.message;
    alertBox.classList.remove('hidden');
    logTerminal(`Erro ao criar VLAN: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Criar & Salvar na Flash';
  }
}

// ============================================================================
// Módulo: Configurações & Servidor FTP
// ============================================================================
async function loadFTPOverview() {
  const container = document.getElementById('ftp-status-container');
  const tbodyOlts = document.getElementById('tbody-ftp-olts');
  const tbodyBackups = document.getElementById('tbody-ftp-backups');
  if (!container) return;

  container.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 20px;">Consultando estado do servidor FTP...</div>';

  try {
    const overview = await apiRequest('/ftp-servers/overview');
    state.ftpOverview = overview;

    if (!overview.configured) {
      container.innerHTML = `
        <div style="background: rgba(245,158,11,0.08); border: 1px solid rgba(245,158,11,0.25); border-radius: var(--radius-md); padding: 20px;">
          <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
            <span style="font-size: 20px;">⚠️</span>
            <h4 style="font-size: 15px; font-weight: 700; color: var(--accent-amber);">Nenhum Servidor FTP Configurado</h4>
          </div>
          <p style="color: var(--text-secondary); font-size: 13px; line-height: 1.6;">
            O repositório de backups FTP ainda não foi inicializado. Você pode configurá-lo através das variáveis de ambiente no arquivo <code>.env</code> (ex: <code>FTP_HOST</code>, <code>FTP_PORT</code>, <code>FTP_USER</code>, <code>FTP_PASSWORD</code>) ou cadastrar um servidor dedicado via API REST.
          </p>
        </div>
      `;
      if (tbodyOlts) tbodyOlts.innerHTML = '<tr><td colspan="3" style="text-align: center; color: var(--text-muted); padding: 16px;">FTP não configurado.</td></tr>';
      if (tbodyBackups) tbodyBackups.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 16px;">FTP não configurado.</td></tr>';
      return;
    }

    const isOnline = overview.is_online;
    container.innerHTML = `
      <div class="ftp-grid">
        <div class="ftp-item">
          <span class="ftp-item-label">Status Operacional</span>
          <div style="display: flex; align-items: center; gap: 6px; margin-top: 4px;">
            <span class="port-led ${isOnline ? 'led-up' : 'led-disabled'}"></span>
            <span class="badge ${isOnline ? 'badge-optical-good' : 'badge-optical-bad'}">
              ${isOnline ? 'Online • Operacional' : 'Offline • Inalcançável'}
            </span>
          </div>
        </div>
        <div class="ftp-item">
          <span class="ftp-item-label">Host / Porta</span>
          <span class="ftp-item-val">${overview.host}:${overview.port || 21}</span>
        </div>
        <div class="ftp-item">
          <span class="ftp-item-label">Usuário</span>
          <span class="ftp-item-val">${overview.username || '-'}</span>
        </div>
        <div class="ftp-item">
          <span class="ftp-item-label">Origem da Configuração</span>
          <span class="badge" style="background: var(--bg-surface-elevated); margin-top: 4px;">
            ${overview.source === 'env' ? 'Variáveis de Ambiente (.env)' : 'Banco de Dados'}
          </span>
        </div>
        <div class="ftp-item">
          <span class="ftp-item-label">Modo Passivo</span>
          <span class="ftp-item-val">${overview.passive_mode ? 'Ativado (Recomendado)' : 'Desativado'}</span>
        </div>
        <div class="ftp-item">
          <span class="ftp-item-label">Latência do Ping</span>
          <span class="ftp-item-val" style="color: ${isOnline ? 'var(--accent-green)' : 'var(--accent-rose)'};">
            ${overview.latency_ms !== null ? overview.latency_ms + ' ms' : 'N/A'}
          </span>
        </div>
      </div>
    `;

    // Bound OLTs
    if (tbodyOlts) {
      tbodyOlts.innerHTML = '';
      const olts = overview.bound_olts || [];
      if (olts.length === 0) {
        tbodyOlts.innerHTML = '<tr><td colspan="3" style="text-align: center; color: var(--text-muted); padding: 16px;">Nenhuma OLT vinculada a este FTP.</td></tr>';
      } else {
        olts.forEach(o => {
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td style="font-weight: 600; color: var(--accent-cyan);">${o.name}</td>
            <td style="font-family: var(--font-mono); font-size: 12px;">${o.host}</td>
            <td><span class="badge" style="background: var(--bg-surface-elevated);">${o.model || '-'}</span></td>
          `;
          tbodyOlts.appendChild(tr);
        });
      }
    }

    // Backups
    if (tbodyBackups) {
      tbodyBackups.innerHTML = '';
      const backups = overview.backups || [];
      if (backups.length === 0) {
        tbodyBackups.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 16px;">Nenhum arquivo de backup encontrado.</td></tr>';
      } else {
        backups.forEach(b => {
          const tr = document.createElement('tr');
          const dt = b.created_at ? new Date(b.created_at).toLocaleString() : '-';
          const sizeKb = b.file_size ? `${(b.file_size / 1024).toFixed(1)} KB` : '-';
          tr.innerHTML = `
            <td style="font-family: var(--font-mono); font-weight: 600;">${b.filename || b.backup_id}</td>
            <td>${b.olt_name || '-'}</td>
            <td style="font-size: 12px;">${sizeKb}</td>
            <td style="font-size: 12px; color: var(--text-secondary);">${dt}</td>
          `;
          tbodyBackups.appendChild(tr);
        });
      }
    }
  } catch (error) {
    container.innerHTML = `<div style="text-align: center; color: var(--accent-rose); padding: 20px;">Falha ao carregar visão geral do FTP: ${error.message}</div>`;
    logTerminal(`Falha ao carregar FTP Overview: ${error.message}`, 'error');
  }
}

async function testFTPConnection() {
  logTerminal('Testando conectividade direta com o servidor FTP...');
  const btn = document.getElementById('btn-test-ftp');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Testando...';
  }

  try {
    await loadFTPOverview();
    logTerminal('Verificação de conectividade FTP concluída.', 'success');
  } catch (error) {
    logTerminal(`Erro ao testar FTP: ${error.message}`, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '⚡ Testar Conectividade FTP';
    }
  }
}
