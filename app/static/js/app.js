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

  // Se não for super admin, oculta aba de administração
  const navAdmin = document.getElementById('nav-admin');
  if (state.user.role !== 'SUPER_ADMIN') {
    navAdmin.classList.add('hidden');
  } else {
    navAdmin.classList.remove('hidden');
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
        <button class="btn btn-primary btn-sm btn-action-provision" data-serial="${onu.serial}" data-port="${onu.port || ''}">
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
      openProvisionModal(serial, port);
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
        <button class="btn btn-secondary btn-sm btn-check-optical" data-olt="${onu.current_olt_id || state.selectedOltId}" data-serial="${onu.serial}" title="Medir Potência Óptica">
          📶 Sinal
        </button>
        <button class="btn btn-secondary btn-sm btn-onu-reboot" data-olt="${onu.current_olt_id || state.selectedOltId}" data-serial="${onu.serial}" title="Reiniciar ONU">
          🔄
        </button>
        <button class="btn btn-danger btn-sm btn-onu-deprovision" data-olt="${onu.current_olt_id || state.selectedOltId}" data-serial="${onu.serial}" title="Desprovisionar">
          🗑️
        </button>
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
    const diag = await apiRequest(`/diagnostics/olts/${oltId}/onus/${serial}/optical`);
    const rx = diag.rx_power_dbm !== undefined ? diag.rx_power_dbm : diag.rx_power;
    const tx = diag.tx_power_dbm !== undefined ? diag.tx_power_dbm : diag.tx_power;

    let badgeClass = 'badge-optical-good';
    if (rx < -27) badgeClass = 'badge-optical-bad';
    else if (rx < -25) badgeClass = 'badge-optical-warn';

    if (cell) {
      cell.innerHTML = `<span class="badge ${badgeClass}">${rx} dBm</span>`;
    }
    logTerminal(`Sinal ONU ${serial}: RX = ${rx} dBm | TX = ${tx} dBm`, 'success');
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
async function openProvisionModal(serial, port) {
  document.getElementById('prov-serial').value = serial;
  document.getElementById('prov-port').value = port;
  document.getElementById('provision-alert').classList.add('hidden');

  // Carrega VLANs autorizadas para o inquilino
  const selectVlan = document.getElementById('prov-vlan');
  selectVlan.innerHTML = '<option value="">Carregando...</option>';

  try {
    let vlans = [];
    if (state.user && state.user.allowed_vlans && state.user.allowed_vlans.length > 0) {
      vlans = state.user.allowed_vlans;
    } else {
      // Se for admin, busca do banco ou preenche com padrão
      vlans = [100, 200, 300, 10, 20];
    }

    selectVlan.innerHTML = '';
    vlans.forEach(v => {
      const opt = document.createElement('option');
      opt.value = v;
      opt.textContent = `VLAN ${v}`;
      selectVlan.appendChild(opt);
    });
  } catch (e) {
    selectVlan.innerHTML = '<option value="100">VLAN 100 (Padrão)</option>';
  }

  document.getElementById('modal-provision').classList.add('active');
}

async function handleConfirmProvision() {
  const serial = document.getElementById('prov-serial').value;
  const port = document.getElementById('prov-port').value;
  const mode = document.getElementById('prov-mode').value;
  const profile = document.getElementById('prov-profile').value;
  const vlan = parseInt(document.getElementById('prov-vlan').value, 10);
  const pppoeUser = document.getElementById('prov-pppoe-user').value;
  const pppoePass = document.getElementById('prov-pppoe-pass').value;

  const alertBox = document.getElementById('provision-alert');
  const btnSubmit = document.getElementById('btn-confirm-provision');

  if (!vlan || isNaN(vlan)) {
    alertBox.textContent = 'Selecione uma VLAN válida.';
    alertBox.classList.remove('hidden');
    return;
  }

  btnSubmit.disabled = true;
  btnSubmit.textContent = 'Autorizando na OLT...';
  logTerminal(`Iniciando autorização da ONU ${serial} na porta ${port} (Modo: ${mode}, VLAN: ${vlan})...`);

  try {
    const payload = {
      serial,
      port,
      mode,
      vlan,
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

      const alertBox = document.getElementById('setup-alert');
      const btn = document.getElementById('btn-submit-setup');

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
      document.getElementById('subview-administracao').classList.add('hidden');

      if (viewId === 'bancada') {
        document.getElementById('subview-bancada').classList.remove('hidden');
      } else if (viewId === 'inventario') {
        document.getElementById('subview-inventario').classList.remove('hidden');
        loadInventory();
      } else if (viewId === 'administracao') {
        document.getElementById('subview-administracao').classList.remove('hidden');
        loadTenants();
      }
    });
  });

  // Seletor de OLTs
  document.getElementById('select-olt')?.addEventListener('change', (e) => {
    state.selectedOltId = e.target.value;
    logTerminal(`OLT alterada para: ${e.target.options[e.target.selectedIndex].text}`);
    scanUnauthorizedOnus();
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

  // Fechar Modais
  document.querySelectorAll('[data-close-modal]').forEach(el => {
    el.addEventListener('click', (e) => {
      const modalId = e.currentTarget.getAttribute('data-close-modal');
      document.getElementById(modalId)?.classList.remove('active');
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
