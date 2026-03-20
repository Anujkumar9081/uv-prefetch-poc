/**
 * uv-prefetch Dashboard — Frontend Application Logic
 * Handles file upload, API calls, SSE streaming, and UI updates
 */

(function () {
    'use strict';

    // --- DOM References ---
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');
    const loadExampleBtn = document.getElementById('loadExampleBtn');
    const statsRow = document.getElementById('statsRow');
    const packagesSection = document.getElementById('packagesSection');
    const packagesTableBody = document.getElementById('packagesTableBody');
    const prefetchBtn = document.getElementById('prefetchBtn');
    const consoleSection = document.getElementById('consoleSection');
    const consoleLines = document.getElementById('consoleLines');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const sbomSection = document.getElementById('sbomSection');
    const sbomContent = document.getElementById('sbomContent');
    const downloadSbomBtn = document.getElementById('downloadSbomBtn');
    const cacheSection = document.getElementById('cacheSection');
    const cacheGrid = document.getElementById('cacheGrid');
    const connectionStatus = document.getElementById('connectionStatus');
    const statusDot = connectionStatus.querySelector('.status-dot');

    // --- State ---
    let packages = [];
    let eventSource = null;

    // --- Background Particles ---
    function createParticles() {
        const container = document.getElementById('bgParticles');
        for (let i = 0; i < 20; i++) {
            const p = document.createElement('div');
            p.classList.add('particle');
            const size = Math.random() * 4 + 2;
            p.style.width = size + 'px';
            p.style.height = size + 'px';
            p.style.left = Math.random() * 100 + '%';
            p.style.animationDuration = (Math.random() * 15 + 10) + 's';
            p.style.animationDelay = (Math.random() * 10) + 's';
            const colors = ['var(--accent-purple)', 'var(--accent-blue)', 'var(--accent-green)'];
            p.style.background = colors[Math.floor(Math.random() * colors.length)];
            container.appendChild(p);
        }
    }
    createParticles();

    // --- File Upload ---
    uploadZone.addEventListener('click', () => fileInput.click());

    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file) handleFileUpload(file);
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files[0]) handleFileUpload(fileInput.files[0]);
    });

    loadExampleBtn.addEventListener('click', loadExampleLockfile);

    async function handleFileUpload(file) {
        const formData = new FormData();
        formData.append('lockfile', file);

        uploadZone.classList.add('success');
        const uploadText = uploadZone.querySelector('.upload-text');
        uploadText.innerHTML = `<span class="spinner" style="display:inline-block; margin-right: 8px;"></span> Parsing <code>${file.name}</code>...`;

        try {
            const res = await fetch('/api/parse', { method: 'POST', body: formData });
            const data = await res.json();

            if (data.success) {
                packages = data.packages;
                uploadText.textContent = `✓ ${file.name} loaded — ${data.count} packages found`;
                renderPackages(data.packages);
                showStats(data.packages);
                connectSSE();
            } else {
                uploadText.textContent = `✗ Error: ${data.error}`;
                uploadZone.classList.remove('success');
            }
        } catch (err) {
            uploadText.textContent = `✗ Upload failed: ${err.message}`;
            uploadZone.classList.remove('success');
        }
    }

    async function loadExampleLockfile() {
        const uploadText = uploadZone.querySelector('.upload-text');
        uploadText.innerHTML = '<span class="spinner" style="display:inline-block; margin-right: 8px;"></span> Loading example lockfile...';
        uploadZone.classList.add('success');

        try {
            // Read the example lockfile content
            const lockContent = [
                'version = 1',
                'revision = 1',
                'requires-python = ">=3.8"',
                '',
                '[[package]]',
                'name = "six"',
                'version = "1.16.0"',
                'source = { registry = "https://pypi.org/simple" }',
                'hashes = [',
                '    "sha256:8abb2f1d8686cd96738b3dbef81f08e779c9ad4d40455675c1a17f66886da2ce",',
                ']'
            ].join('\n');

            const res = await fetch('/api/parse', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: lockContent })
            });
            const data = await res.json();

            if (data.success) {
                packages = data.packages;
                uploadText.textContent = `✓ Example lockfile loaded — ${data.count} packages found`;
                renderPackages(data.packages);
                showStats(data.packages);
                connectSSE();
            } else {
                uploadText.textContent = `✗ Error: ${data.error}`;
                uploadZone.classList.remove('success');
            }
        } catch (err) {
            uploadText.textContent = `✗ Failed to load example: ${err.message}`;
            uploadZone.classList.remove('success');
        }
    }

    // --- Packages Table ---
    function renderPackages(pkgs) {
        packagesTableBody.innerHTML = '';
        pkgs.forEach((pkg, idx) => {
            const tr = document.createElement('tr');
            tr.id = `pkg-row-${idx}`;
            const source = pkg.source ? (pkg.source.registry || 'local') : 'unknown';
            const hashDisplay = pkg.hashes.length > 0
                ? `<span class="pkg-hash" title="${pkg.hashes[0]}">${pkg.hashes[0].substring(0, 20)}...</span>`
                : '<span style="color:var(--text-muted)">—</span>';

            tr.innerHTML = `
                <td><span class="pkg-name">${pkg.name}</span></td>
                <td><span class="pkg-version">${pkg.version}</span></td>
                <td><span class="pkg-source">${source}</span></td>
                <td>${hashDisplay}</td>
                <td><span class="pkg-status pending" id="pkg-status-${idx}">Pending</span></td>
            `;
            tr.style.animationDelay = `${idx * 50}ms`;
            packagesTableBody.appendChild(tr);
        });

        packagesSection.style.display = 'block';
    }

    function showStats(pkgs) {
        statsRow.style.display = 'grid';
        animateCounter('statPackages', pkgs.length);
        const totalHashes = pkgs.reduce((sum, p) => sum + p.hashes.length, 0);
        animateCounter('statHashes', totalHashes);
    }

    function animateCounter(id, target) {
        const el = document.getElementById(id);
        let current = 0;
        const step = Math.max(1, Math.floor(target / 20));
        const intervalId = setInterval(() => {
            current += step;
            if (current >= target) {
                current = target;
                clearInterval(intervalId);
            }
            el.textContent = current;
        }, 40);
    }

    // --- Prefetch ---
    prefetchBtn.addEventListener('click', startPrefetch);

    async function startPrefetch() {
        prefetchBtn.disabled = true;
        prefetchBtn.innerHTML = '<span class="spinner"></span> Prefetching...';

        consoleSection.style.display = 'block';
        consoleLines.innerHTML = '';

        // Scroll to console
        consoleSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

        try {
            const res = await fetch('/api/prefetch', { method: 'POST' });
            const data = await res.json();

            if (!data.success) {
                addConsoleLine(new Date().toLocaleTimeString(), data.error, 'error');
                prefetchBtn.disabled = false;
                prefetchBtn.innerHTML = `
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                    Start Prefetch
                `;
            }
        } catch (err) {
            addConsoleLine(new Date().toLocaleTimeString(), `Request failed: ${err.message}`, 'error');
            prefetchBtn.disabled = false;
        }
    }

    // --- SSE Connection ---
    function connectSSE() {
        if (eventSource) eventSource.close();

        eventSource = new EventSource('/api/stream');

        eventSource.addEventListener('open', () => {
            statusDot.classList.add('connected');
            connectionStatus.querySelector('.status-dot').nextSibling.textContent = ' Connected';
        });

        eventSource.addEventListener('log', (e) => {
            const data = JSON.parse(e.data);
            addConsoleLine(data.time, data.message, data.level);

            // Update package status in table based on log messages
            updatePackageStatus(data.message, data.level);
        });

        eventSource.addEventListener('progress', (e) => {
            const data = JSON.parse(e.data);
            const pct = data.total > 0 ? Math.round((data.completed + data.failed) / data.total * 100) : 0;
            progressBar.style.width = pct + '%';
            progressText.textContent = pct + '%';

            document.getElementById('statDownloaded').textContent = data.completed;
            document.getElementById('statFailed').textContent = data.failed;
        });

        eventSource.addEventListener('done', (e) => {
            const data = JSON.parse(e.data);
            progressBar.style.width = '100%';
            progressText.textContent = '100%';

            prefetchBtn.disabled = false;
            prefetchBtn.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                Complete!
            `;

            // Load SBOM and cache
            loadSBOM();
            loadCache();
        });

        eventSource.addEventListener('error', () => {
            statusDot.classList.remove('connected');
        });
    }

    function updatePackageStatus(message, level) {
        packages.forEach((pkg, idx) => {
            const statusEl = document.getElementById(`pkg-status-${idx}`);
            if (!statusEl) return;

            if (message.includes(`Resolving ${pkg.name}==`)) {
                statusEl.className = 'pkg-status downloading';
                statusEl.textContent = 'Resolving...';
            } else if (message.includes(`Downloading ${pkg.name}==`)) {
                statusEl.className = 'pkg-status downloading';
                statusEl.textContent = 'Downloading...';
            } else if (message.includes(`${pkg.name}==`) && level === 'success') {
                statusEl.className = 'pkg-status success';
                statusEl.textContent = '✓ Verified';
            } else if (message.includes(`${pkg.name}==`) && level === 'error') {
                statusEl.className = 'pkg-status failed';
                statusEl.textContent = '✗ Failed';
            }
        });
    }

    // --- Console ---
    function addConsoleLine(time, message, level) {
        const line = document.createElement('div');
        line.classList.add('console-line');
        line.innerHTML = `
            <span class="console-time">${time}</span>
            <span class="console-msg ${level}">${escapeHtml(message)}</span>
        `;
        consoleLines.appendChild(line);
        consoleLines.scrollTop = consoleLines.scrollHeight;
    }

    // --- SBOM ---
    async function loadSBOM() {
        try {
            const res = await fetch('/api/sbom');
            const data = await res.json();

            if (!data.error) {
                sbomSection.style.display = 'block';
                sbomContent.innerHTML = syntaxHighlightJSON(JSON.stringify(data, null, 2));
                sbomSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        } catch (err) {
            console.error('Failed to load SBOM:', err);
        }
    }

    downloadSbomBtn.addEventListener('click', async () => {
        try {
            const res = await fetch('/api/sbom');
            const data = await res.json();
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'sbom.json';
            a.click();
            URL.revokeObjectURL(url);
        } catch (err) {
            console.error('Download failed:', err);
        }
    });

    // --- Cache ---
    async function loadCache() {
        try {
            const res = await fetch('/api/cache');
            const data = await res.json();

            if (data.files && data.files.length > 0) {
                cacheSection.style.display = 'block';
                cacheGrid.innerHTML = '';
                data.files.forEach((file) => {
                    const item = document.createElement('div');
                    item.classList.add('cache-item');
                    item.innerHTML = `
                        <div class="cache-item-icon">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                        </div>
                        <div class="cache-item-info">
                            <div class="cache-item-name">${escapeHtml(file.name)}</div>
                            <div class="cache-item-size">${file.size_human}</div>
                        </div>
                    `;
                    cacheGrid.appendChild(item);
                });
            }
        } catch (err) {
            console.error('Failed to load cache:', err);
        }
    }

    // --- Utilities ---
    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function syntaxHighlightJSON(json) {
        return json
            .replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*")\s*:/g, '<span class="sbom-key">$1</span>:')
            .replace(/:\s*("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*")/g, ': <span class="sbom-string">$1</span>')
            .replace(/:\s*(\d+(\.\d+)?)/g, ': <span class="sbom-number">$1</span>');
    }

})();
