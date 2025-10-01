// Global state
let currentTestId = null;
let statusCheckInterval = null;
let currentFilter = 'all';

// Tab switching
document.querySelectorAll('.tab-button').forEach(button => {
    button.addEventListener('click', () => {
        const tabName = button.dataset.tab;

        // Save current tab to localStorage
        localStorage.setItem('currentTab', tabName);

        // Update active tab button
        document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
        button.classList.add('active');

        // Update active tab content
        document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
        document.getElementById(`${tabName}-tab`).classList.add('active');

        // Load config when switching to config tab
        if (tabName === 'config') {
            loadConfig();
        }

        // Load channels when switching to channels tab
        if (tabName === 'channels') {
            // loadChannels() will load groups if needed (avoiding duplicate API calls)
            loadChannels();
        }

        // Load groups when switching to groups tab
        if (tabName === 'groups') {
            loadGroups();
        }
    });
});


// Test form submission
document.getElementById('test-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const baseUrl = document.getElementById('base-url').value;
    const startIp = document.getElementById('start-ip').value;
    const endIp = document.getElementById('end-ip').value;

    // Validate required fields
    if (!baseUrl || !startIp || !endIp) {
        alert('Please fill in all required fields: Base URL, Start IP, and End IP');
        return;
    }

    try {
        const response = await fetch('/api/test/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                base_url: baseUrl,
                start_ip: startIp,
                end_ip: endIp
            })
        });

        const data = await response.json();

        if (data.status === 'started') {
            currentTestId = data.test_id;
            document.getElementById('progress-container').style.display = 'block';
            document.getElementById('results-container').style.display = 'block';

            // Start polling for status
            startStatusCheck();

            // Refresh the test selector to include the new test
            setTimeout(() => loadAllTests(), 500);
        }
    } catch (error) {
        alert('Failed to start test: ' + error.message);
    }
});

// Toggle database configuration visibility
function toggleDatabaseConfig() {
    const dbType = document.getElementById('db-type').value;
    document.getElementById('postgresql-config').style.display = dbType === 'postgresql' ? 'block' : 'none';
}

// Config form submission
document.getElementById('config-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const timeoutValue = document.getElementById('timeout').value;
    const timeout = timeoutValue ? parseInt(timeoutValue) : 10; // Default to 10 if empty
    const queueSizeValue = document.getElementById('queue-size').value;
    const queueSize = queueSizeValue ? parseInt(queueSizeValue) : 5; // Default to 5 if empty
    const customParams = document.getElementById('custom-params').value;

    // Get database configuration
    const dbType = document.getElementById('db-type').value;
    const database = {
        type: dbType
    };

    if (dbType === 'sqlite') {
        database.sqlite_path = 'config/iptv.db';  // Fixed path for SQLite
    } else if (dbType === 'postgresql') {
        database.postgresql = {
            host: document.getElementById('pg-host').value || 'localhost',
            port: parseInt(document.getElementById('pg-port').value) || 5432,
            database: document.getElementById('pg-database').value || 'iptv',
            user: document.getElementById('pg-user').value || 'postgres',
            password: document.getElementById('pg-password').value || ''
        };
    }

    // Get AI model configuration
    const aiEnabled = document.getElementById('ai-enabled').checked;
    const aiApiUrl = document.getElementById('ai-api-url').value;
    const aiApiKey = document.getElementById('ai-api-key').value;
    const aiModel = document.getElementById('ai-model').value;

    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                timeout: timeout,
                queue_size: queueSize,
                custom_params: customParams,
                database: database,
                ai_model: {
                    enabled: aiEnabled,
                    api_url: aiApiUrl,
                    api_key: aiApiKey,
                    model: aiModel
                }
            })
        });

        const data = await response.json();

        if (data.status === 'success') {
            alert('Configuration saved successfully! Please restart the application to apply database changes.');
        }
    } catch (error) {
        alert('Failed to save configuration: ' + error.message);
    }
});

// Function to update filter button counts
function updateFilterButtonCounts(total, success, testing, failed) {
    document.querySelectorAll('.filter-btn').forEach(btn => {
        const filter = btn.dataset.filter;
        if (filter === 'all') {
            btn.textContent = `All (${total})`;
        } else if (filter === 'success') {
            btn.textContent = `Success (${success})`;
        } else if (filter === 'testing') {
            btn.textContent = `Testing (${testing})`;
        } else if (filter === 'failed') {
            btn.textContent = `Failed (${failed})`;
        }
    });
}

// Update resolution filter button counts
function updateResolutionFilterCounts(all, count4k, count1080, count720) {
    // Update test results resolution filter counts
    document.querySelectorAll('#test-tab .resolution-filter-btn').forEach(btn => {
        const resolution = btn.dataset.resolution;
        if (resolution === 'all') {
            btn.innerHTML = `All (${all})`;
        } else if (resolution === '4k') {
            btn.innerHTML = `4K (${count4k})`;
        } else if (resolution === '1080') {
            btn.innerHTML = `1080p (${count1080})`;
        } else if (resolution === '720') {
            btn.innerHTML = `720p (${count720})`;
        }
    });
}

// Current resolution filter for test results
let currentResolutionFilter = 'all';

// Filter buttons
document.querySelectorAll('.filter-btn').forEach(button => {
    button.addEventListener('click', () => {
        currentFilter = button.dataset.filter;

        // Update active filter button
        document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
        button.classList.add('active');

        // Re-render results with filter
        if (currentTestId) {
            checkTestStatus();
        }
    });
});

// Resolution filter buttons for test results
document.querySelectorAll('.resolution-filter-btn').forEach(button => {
    button.addEventListener('click', () => {
        const resolution = button.dataset.resolution;
        currentResolutionFilter = resolution;

        // Update active resolution filter button
        document.querySelectorAll('.resolution-filter-btn').forEach(btn => btn.classList.remove('active'));
        button.classList.add('active');

        // Re-render results with filter
        if (currentTestId) {
            checkTestStatus();
        }
    });
});

// Load configuration
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();

        // Load test configuration (no defaults)
        document.getElementById('base-url').value = config.base_url || '';
        document.getElementById('start-ip').value = config.start_ip || '';
        document.getElementById('end-ip').value = config.end_ip || '';

        // Load FFmpeg configuration (with sensible handling)
        if (config.timeout !== null && config.timeout !== undefined && config.timeout !== '') {
            document.getElementById('timeout').value = config.timeout;
        } else {
            document.getElementById('timeout').value = '';
        }

        // Load queue size
        if (config.queue_size !== null && config.queue_size !== undefined && config.queue_size !== '') {
            document.getElementById('queue-size').value = config.queue_size;
        } else {
            document.getElementById('queue-size').value = '';
        }

        document.getElementById('custom-params').value = config.custom_params || '';

        // Load database configuration
        if (config.database) {
            document.getElementById('db-type').value = config.database.type || 'json';

            if (config.database.type === 'postgresql' && config.database.postgresql) {
                document.getElementById('pg-host').value = config.database.postgresql.host || 'localhost';
                document.getElementById('pg-port').value = config.database.postgresql.port || 5432;
                document.getElementById('pg-database').value = config.database.postgresql.database || 'iptv';
                document.getElementById('pg-user').value = config.database.postgresql.user || 'postgres';
                document.getElementById('pg-password').value = config.database.postgresql.password || '';
            }

            // Show/hide appropriate config sections
            toggleDatabaseConfig();
        }

        // Load AI model configuration
        if (config.ai_model) {
            document.getElementById('ai-enabled').checked = config.ai_model.enabled || false;
            document.getElementById('ai-api-url').value = config.ai_model.api_url || '';
            document.getElementById('ai-api-key').value = config.ai_model.api_key || '';
            document.getElementById('ai-model').value = config.ai_model.model || 'gpt-4-vision-preview';
        }

        // Set language dropdown to current language
        document.getElementById('language-select').value = i18n.getLanguage();
    } catch (error) {
        console.error('Failed to load configuration:', error);
        // Set all fields to empty on error
        document.getElementById('base-url').value = '';
        document.getElementById('start-ip').value = '';
        document.getElementById('end-ip').value = '';
        document.getElementById('timeout').value = '';
        document.getElementById('queue-size').value = '';
        document.getElementById('custom-params').value = '';
    }
}

// Start status checking
function startStatusCheck() {
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
    }

    // Check immediately first
    checkTestStatus();

    // Then check every 300ms for faster updates during retry
    statusCheckInterval = setInterval(checkTestStatus, 300);
}

// Check test status
async function checkTestStatus() {
    if (!currentTestId) return;

    try {
        // Add timestamp to prevent caching
        const response = await fetch(`/api/test/status/${currentTestId}?t=${Date.now()}`);
        const data = await response.json();

        if (data.error) {
            console.error('Test not found');
            clearInterval(statusCheckInterval);
            return;
        }

        // Update progress
        updateProgress(data);

        // Update results
        updateResults(data.results);

        // Check if any results are still in 'testing' status
        let hasTestingStatus = false;
        for (const [ip, result] of Object.entries(data.results)) {
            if (result.status === 'testing') {
                hasTestingStatus = true;
                console.log(`${ip} is still testing, continue polling...`);
                break;
            }
        }

        // Stop checking only if test is completed AND no results are in 'testing' status
        if (data.status === 'completed' && !hasTestingStatus) {
            console.log('All tests completed, stopping status check');
            clearInterval(statusCheckInterval);
            statusCheckInterval = null;
        }
    } catch (error) {
        console.error('Failed to check test status:', error);
    }
}

// Update progress bar
function updateProgress(data) {
    const completed = data.completed || 0;
    const total = data.total || 0;
    const percentage = total > 0 ? (completed / total) * 100 : 0;
    document.getElementById('progress-fill').style.width = percentage + '%';
    document.getElementById('progress-text').textContent = `Testing: ${completed} / ${total}`;
}

// Update results display
function updateResults(results) {
    const resultsGrid = document.getElementById('results-grid');

    // Store existing retry button states
    const retryButtonStates = {};
    resultsGrid.querySelectorAll('.retry-btn').forEach(btn => {
        const card = btn.closest('.result-card');
        const ip = card.querySelector('.result-ip').textContent;
        retryButtonStates[ip] = {
            disabled: btn.disabled,
            text: btn.textContent
        };
    });

    // Calculate counts for each status and resolution
    let successCount = 0;
    let failedCount = 0;
    let testingCount = 0;
    let totalCount = 0;

    // Resolution counts - only count successful streams with resolution data
    let resolution4kCount = 0;
    let resolution1080Count = 0;
    let resolution720Count = 0;

    for (const result of Object.values(results)) {
        totalCount++;
        if (result.status === 'success') {
            successCount++;

            // Count resolutions for successful streams
            if (result.resolution) {
                const [widthStr, heightStr] = result.resolution.split('x');
                const width = parseInt(widthStr);
                const height = parseInt(heightStr);

                // Treat 720x576 (PAL) as 720p
                const is720p = (width === 720 && height === 576) || (width >= 1280 && width < 1920);

                if (width >= 3840) {
                    resolution4kCount++;
                } else if (width >= 1920 && width < 3840) {
                    resolution1080Count++;
                } else if (is720p) {
                    resolution720Count++;
                }
            }
        }
        else if (result.status === 'failed') failedCount++;
        else if (result.status === 'testing') testingCount++;
    }

    // Update filter button text with counts
    updateFilterButtonCounts(totalCount, successCount, testingCount, failedCount);

    // Update resolution filter counts
    updateResolutionFilterCounts(successCount, resolution4kCount, resolution1080Count, resolution720Count);

    // Debug: Log all results keys and specific IP data
    console.log('Results keys:', Object.keys(results));

    // Debug: Log the results for IPs that were retrying
    Object.keys(retryButtonStates).forEach(ip => {
        if (retryButtonStates[ip].text === 'Retrying...') {
            console.log(`Looking for ${ip} in results...`);
            if (results[ip]) {
                console.log(`Status update for ${ip}: ${results[ip].status}`);
            } else {
                console.log(`${ip} not found in results object`);
                // Try to find it by iterating through all results
                for (const [key, value] of Object.entries(results)) {
                    if (value.ip === ip) {
                        console.log(`Found ${ip} under key ${key}: status = ${value.status}`);
                    }
                }
            }
        }
    });

    resultsGrid.innerHTML = '';

    // Sort results by IP
    const sortedResults = Object.entries(results).sort((a, b) => {
        const ipA = a[1].ip.split('.').map(Number);
        const ipB = b[1].ip.split('.').map(Number);

        for (let i = 0; i < 4; i++) {
            if (ipA[i] !== ipB[i]) {
                return ipA[i] - ipB[i];
            }
        }
        return 0;
    });

    // Filter and display results
    for (const [key, result] of sortedResults) {
        // Status filter
        if (currentFilter !== 'all' && result.status !== currentFilter) {
            continue;
        }

        // Resolution filter (only for successful results with resolution)
        if (currentResolutionFilter !== 'all' && result.status === 'success') {
            if (!result.resolution) {
                // Skip if no resolution data
                continue;
            }

            const [widthStr, heightStr] = result.resolution.split('x');
            const width = parseInt(widthStr);
            const height = parseInt(heightStr);

            // Treat 720x576 (and similar PAL resolutions) as 720p
            const is720p = (width === 720 && height === 576) || (width >= 1280 && width < 1920);

            if (currentResolutionFilter === '4k' && width < 3840) {
                continue;
            } else if (currentResolutionFilter === '1080' && (width < 1920 || width >= 3840)) {
                continue;
            } else if (currentResolutionFilter === '720' && !is720p) {
                continue;
            }
        } else if (currentResolutionFilter !== 'all' && result.status !== 'success') {
            // Hide non-success results when resolution filter is active
            continue;
        }

        const resultCard = createResultCard(result);

        // Restore retry button state ONLY if test is still in testing status
        // If status changed from testing to success/failed, the button will be recreated correctly
        if (result.status === 'testing' && retryButtonStates[result.ip] && retryButtonStates[result.ip].text === 'Retrying...') {
            const retryBtn = resultCard.querySelector('.retry-btn');
            if (retryBtn) {
                retryBtn.disabled = true;
                retryBtn.textContent = 'Retrying...';
            }
        }

        resultsGrid.appendChild(resultCard);
    }
}

// Create result card element
function createResultCard(result) {
    const card = document.createElement('div');
    card.className = `result-card ${result.status}`;

    const header = document.createElement('div');
    header.className = 'result-header';

    const ip = document.createElement('div');
    ip.className = 'result-ip';
    ip.textContent = result.ip;

    const badge = document.createElement('span');
    badge.className = `status-badge ${result.status}`;
    badge.textContent = result.status.toUpperCase();

    header.appendChild(ip);
    header.appendChild(badge);
    card.appendChild(header);

    // Screenshot or placeholder
    if (result.screenshot) {
        const screenshot = document.createElement('div');
        screenshot.className = 'result-screenshot';

        const img = document.createElement('img');
        img.src = result.screenshot;
        img.alt = `Screenshot for ${result.ip}`;

        screenshot.appendChild(img);
        card.appendChild(screenshot);
    } else if (result.status === 'success' && result.note) {
        // Stream is accessible but no screenshot
        const placeholder = document.createElement('div');
        placeholder.className = 'result-screenshot no-screenshot';
        placeholder.innerHTML = `
            <div class="no-screenshot-icon">📡</div>
            <div class="no-screenshot-text">Stream OK<br>No Screenshot</div>
        `;
        card.appendChild(placeholder);
    }

    // Info
    const info = document.createElement('div');
    info.className = 'result-info';

    // Full URL display with click to copy
    const urlP = document.createElement('p');
    const urlContainer = document.createElement('div');
    urlContainer.className = 'url-container';
    urlContainer.title = 'Click to copy';

    const urlText = document.createElement('span');
    urlText.innerHTML = `<strong>URL</strong> ${result.url}`;
    urlText.className = 'url-text';

    urlContainer.appendChild(urlText);
    urlContainer.onclick = () => {
        navigator.clipboard.writeText(result.url).then(() => {
            // Show copied feedback
            const originalHTML = urlText.innerHTML;
            urlText.innerHTML = '<strong>Copied!</strong>';
            urlContainer.classList.add('copied');
            setTimeout(() => {
                urlText.innerHTML = originalHTML;
                urlContainer.classList.remove('copied');
                urlText.style.color = '';
            }, 1500);
        });
    };

    info.appendChild(urlContainer);

    // Add resolution display if available
    if (result.resolution) {
        const resolutionContainer = document.createElement('div');
        resolutionContainer.className = 'result-resolution';

        const resolutionBadge = document.createElement('span');
        resolutionBadge.className = 'resolution-badge';

        // Determine quality level based on resolution
        const [widthStr, heightStr] = result.resolution.split('x');
        const width = parseInt(widthStr);
        const height = parseInt(heightStr);

        // Treat 720x576 as 720p
        const is720p = (width === 720 && height === 576) || (width >= 1280 && width < 1920);

        if (width >= 3840) {
            resolutionBadge.classList.add('resolution-4k');
            resolutionBadge.title = '4K Ultra HD';
        } else if (width >= 1920) {
            resolutionBadge.classList.add('resolution-1080p');
            resolutionBadge.title = 'Full HD';
        } else if (is720p) {
            resolutionBadge.classList.add('resolution-720p');
            resolutionBadge.title = 'HD Ready';
        }

        resolutionBadge.textContent = result.resolution;
        resolutionContainer.appendChild(resolutionBadge);
        info.appendChild(resolutionContainer);
    }

    card.appendChild(info);

    // Error message (simplified)
    if (result.error) {
        const error = document.createElement('div');
        error.className = 'error-message';
        // Shorten common error messages
        let errorText = result.error;
        if (errorText.includes('Server returned 5XX')) {
            errorText = 'Server Error (5XX)';
        } else if (errorText.includes('Timeout')) {
            errorText = 'Timeout';
        } else if (errorText.length > 50) {
            errorText = errorText.substring(0, 47) + '...';
        }
        error.textContent = errorText;
        error.title = result.error; // Full error on hover
        card.appendChild(error);
    }

    // Retry button for failed tests or loading indicator for testing
    if (result.status === 'failed') {
        const retryBtn = document.createElement('button');
        retryBtn.className = 'btn btn-primary btn-small retry-btn';
        retryBtn.textContent = 'Retry';
        retryBtn.onclick = () => retryTest(result.ip);
        card.appendChild(retryBtn);
    } else if (result.status === 'testing') {
        const retryBtn = document.createElement('button');
        retryBtn.className = 'btn btn-primary btn-small retry-btn';
        retryBtn.textContent = 'Testing...';
        retryBtn.disabled = true;
        card.appendChild(retryBtn);
    }

    return card;
}

// Retry a failed test
async function retryTest(ip) {
    // Find the retry button and show loading state
    const retryButtons = document.querySelectorAll('.retry-btn');
    let targetButton = null;
    retryButtons.forEach(btn => {
        const card = btn.closest('.result-card');
        if (card && card.querySelector('.result-ip').textContent === ip) {
            targetButton = btn;
            btn.disabled = true;
            btn.textContent = 'Retrying...';
        }
    });

    try {
        const response = await fetch('/api/test/retry', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                test_id: currentTestId,
                ip: ip
            })
        });

        const data = await response.json();

        if (data.status === 'retrying') {
            // Update the status badge immediately
            if (targetButton) {
                const card = targetButton.closest('.result-card');
                const badge = card.querySelector('.status-badge');
                if (badge) {
                    badge.textContent = 'TESTING';
                    badge.className = 'status-badge testing';
                }
                card.classList.remove('failed');
                card.classList.add('testing');
            }

            // Clear any existing interval to avoid conflicts
            if (statusCheckInterval) {
                clearInterval(statusCheckInterval);
            }

            // Start fresh polling
            startStatusCheck();

            // Also set a timeout to force refresh after a reasonable time
            setTimeout(async () => {
                console.log('Force refresh after retry...');
                await checkTestStatus();
            }, 2000);
        }
    } catch (error) {
        alert('Failed to retry test: ' + error.message);
        // Reset button state on error
        if (targetButton) {
            targetButton.disabled = false;
            targetButton.textContent = 'Retry';
        }
    }
}

// Load and display all test results
async function loadAllTests() {
    try {
        const response = await fetch('/api/results');
        const data = await response.json();

        if (Object.keys(data).length === 0) {
            return;
        }

        // Sort tests by start_time or timestamp
        const sortedTests = Object.entries(data).sort((a, b) => {
            const timeA = a[1].start_time || (Object.values(a[1].results || {})[0]?.timestamp) || '';
            const timeB = b[1].start_time || (Object.values(b[1].results || {})[0]?.timestamp) || '';
            return timeB.localeCompare(timeA); // Sort descending (newest first)
        });

        if (sortedTests.length > 0) {
            // Load the most recent test by default
            const [latestTestId, latestTestData] = sortedTests[0];
            currentTestId = latestTestId;

            // Show progress and results containers
            document.getElementById('progress-container').style.display = 'block';
            document.getElementById('results-container').style.display = 'block';

            // Add test selector if multiple tests exist
            if (sortedTests.length > 1) {
                addTestSelector(sortedTests);
            }

            // Update progress and results for the latest test
            updateProgress(latestTestData);
            updateResults(latestTestData.results);

            // If test is still running, start polling
            if (latestTestData.status === 'running') {
                startStatusCheck();
            }
        }
    } catch (error) {
        console.error('Failed to load tests:', error);
    }
}

// Delete test history
async function deleteTestHistory(testId) {
    try {
        const response = await fetch(`/api/test/delete/${testId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.status === 'success') {
            // Remove the deleted test from the dropdown immediately
            const selector = document.getElementById('test-selector');
            const optionToRemove = selector.querySelector(`option[value="${testId}"]`);

            if (optionToRemove) {
                optionToRemove.remove();

                // If the deleted test was selected, select the first available option
                if (selector.value === '' || selector.value === testId) {
                    if (selector.options.length > 0) {
                        selector.selectedIndex = 0;
                        currentTestId = selector.options[0].value;
                        // Load the newly selected test
                        await checkTestStatus();
                    } else {
                        // No tests left, clear the results
                        currentTestId = null;
                        results = {};
                        updateResultsDisplay();
                        document.getElementById('test-selector-container').style.display = 'none';
                    }
                }
            }

            // Show success message (less intrusive than alert)
            console.log('Test history deleted successfully');

            // Optionally reload all tests to ensure consistency
            setTimeout(() => loadAllTests(), 500);
        } else {
            alert('Failed to delete test history: ' + (data.message || 'Unknown error'));
        }
    } catch (error) {
        alert('Failed to delete test history: ' + error.message);
    }
}

// Add test selector dropdown
function addTestSelector(sortedTests) {
    const resultsHeader = document.querySelector('.results-header');

    // Check if selector already exists
    let selectorContainer = document.getElementById('test-selector-container');
    if (!selectorContainer) {
        selectorContainer = document.createElement('div');
        selectorContainer.id = 'test-selector-container';
        selectorContainer.style.cssText = 'display: flex; align-items: center; gap: 10px; margin-bottom: 10px;';

        const label = document.createElement('label');
        label.textContent = 'Select Test: ';
        label.style.fontWeight = '600';

        const selector = document.createElement('select');
        selector.id = 'test-selector';
        selector.style.cssText = 'padding: 8px; border: 2px solid #e0e0e0; border-radius: 6px; font-size: 0.9rem;';

        selectorContainer.appendChild(label);
        selectorContainer.appendChild(selector);

        // Add delete button
        const deleteBtn = document.createElement('button');
        deleteBtn.textContent = '🗑️';
        deleteBtn.className = 'btn btn-danger btn-small';
        deleteBtn.style.marginLeft = '10px';
        deleteBtn.style.padding = '6px 12px';
        deleteBtn.style.fontSize = '1rem';
        deleteBtn.title = 'Delete';
        deleteBtn.id = 'delete-test-btn';
        selectorContainer.appendChild(deleteBtn);

        // Insert before the results header
        resultsHeader.parentElement.insertBefore(selectorContainer, resultsHeader);

        // Add change event listener
        selector.addEventListener('change', async (e) => {
            currentTestId = e.target.value;
            clearInterval(statusCheckInterval);
            await checkTestStatus();

            // Restart polling if test is running
            const response = await fetch(`/api/test/status/${currentTestId}`);
            const data = await response.json();
            if (data.status === 'running') {
                startStatusCheck();
            }
        });

        // Add delete button click event listener
        deleteBtn.addEventListener('click', async () => {
            const selectedTestId = selector.value;
            if (!selectedTestId) return;

            if (confirm('Delete this test history and all associated screenshots?')) {
                await deleteTestHistory(selectedTestId);
            }
        });
    }

    // Update selector options
    const selector = document.getElementById('test-selector');
    selector.innerHTML = '';

    sortedTests.forEach(([testId, testData]) => {
        const option = document.createElement('option');
        option.value = testId;

        const startTime = testData.start_time ||
                         (Object.values(testData.results || {})[0]?.timestamp) ||
                         'Unknown time';
        const formattedTime = startTime !== 'Unknown time' ?
                            new Date(startTime).toLocaleString() : startTime;

        option.textContent = `${testData.start_ip} - ${testData.end_ip} (${formattedTime}) - ${testData.status}`;

        if (testId === currentTestId) {
            option.selected = true;
        }

        selector.appendChild(option);
    });
}

// TV Channels Management
// Global variable to store all channels and groups
let allChannels = {};
let allChannelsCache = null;  // Cache all channels (without filters) to avoid duplicate API calls
let allGroupsCache = {};  // Cache groups data for sorting
let channelStats = null;  // Statistics from backend
let currentGroupFilter = 'all';
let currentChannelResolutionFilter = 'all';  // Default to 'all'
let currentConnectivityFilter = 'all';  // Default to 'all' (show all channels)
let currentIPFilter = '';
let isLoadingChannels = false;  // Flag to prevent duplicate API calls
let isLoadingGroups = false;  // Flag to prevent duplicate groups API calls

// Helper function to clear groups cache when groups data changes
function clearGroupsCache() {
    allGroupsCache = {};
}

async function loadChannels() {
    // Prevent duplicate API calls
    if (isLoadingChannels) {
        console.log('loadChannels already in progress, skipping...');
        return;
    }

    isLoadingChannels = true;

    // Clear cache to ensure fresh data is loaded
    allChannelsCache = null;

    try {
        // Restore saved filters or use defaults
        const savedConnectivityFilter = localStorage.getItem('connectivityFilter');
        if (savedConnectivityFilter) {
            currentConnectivityFilter = savedConnectivityFilter;
        } else {
            // Save default filter to localStorage
            localStorage.setItem('connectivityFilter', currentConnectivityFilter);
        }

        const savedGroupFilter = localStorage.getItem('groupFilter');
        if (savedGroupFilter) {
            currentGroupFilter = savedGroupFilter;
        }

        const savedResolutionFilter = localStorage.getItem('resolutionFilter');
        if (savedResolutionFilter) {
            currentChannelResolutionFilter = savedResolutionFilter;
        } else {
            // Save default filter to localStorage
            localStorage.setItem('resolutionFilter', currentChannelResolutionFilter);
        }

        // Build API URL with filter parameters
        const params = new URLSearchParams({
            group: currentGroupFilter,
            resolution: currentChannelResolutionFilter,
            connectivity: currentConnectivityFilter,
            search: currentIPFilter
        });

        // Load groups first if not cached (avoid duplicate API calls)
        if (Object.keys(allGroupsCache).length === 0 && !isLoadingGroups) {
            isLoadingGroups = true;
            try {
                const groupsResponse = await fetch('/api/groups');
                const groupsData = await groupsResponse.json();
                if (groupsData.status === 'success') {
                    allGroupsCache = groupsData.groups;
                }
            } catch (error) {
                console.error('Failed to load groups:', error);
            } finally {
                isLoadingGroups = false;
            }
        }

        // Wait for groups to finish loading if in progress
        while (isLoadingGroups) {
            await new Promise(resolve => setTimeout(resolve, 50));
        }

        // Load channels with filters
        const response = await fetch(`/api/channels?${params}`);
        const data = await response.json();

        if (data.status === 'success') {
            allChannels = data.channels;
            channelStats = data.stats;  // Save statistics from backend
            updateGroupFilterButtons();

            // Restore filter button states after buttons are created
            setTimeout(() => {
                // Update connectivity filter button
                const connectivityBtn = document.querySelector(`[data-connectivity="${currentConnectivityFilter}"]`);
                if (connectivityBtn) {
                    document.querySelectorAll('.connectivity-filter-btn').forEach(btn => {
                        btn.classList.remove('active');
                    });
                    connectivityBtn.classList.add('active');
                }

                // Update group filter button
                const groupBtn = document.querySelector(`[data-group="${currentGroupFilter}"]`);
                if (groupBtn) {
                    document.querySelectorAll('.group-filter-btn').forEach(btn => {
                        btn.classList.remove('active');
                    });
                    groupBtn.classList.add('active');
                }

                // Update resolution filter button (channels tab only)
                const resolutionBtn = document.querySelector(`.resolution-filter-buttons [data-resolution="${currentChannelResolutionFilter}"]`);
                if (resolutionBtn) {
                    document.querySelectorAll('.resolution-filter-buttons .resolution-filter-btn').forEach(btn => {
                        btn.classList.remove('active');
                    });
                    resolutionBtn.classList.add('active');
                }
            }, 100);

            displayChannels(allChannels);
        }
    } catch (error) {
        console.error('Failed to load channels:', error);
    } finally {
        isLoadingChannels = false;
    }
}

// Update group filter buttons using backend statistics
function updateGroupFilterButtons() {
    if (!channelStats) return;  // Wait for stats from backend

    const filterContainer = document.getElementById('group-filter-buttons');
    if (!filterContainer) return;

    // Clear existing group buttons (except "All")
    const existingButtons = filterContainer.querySelectorAll('.group-filter-btn:not([data-group="all"])');
    existingButtons.forEach(btn => btn.remove());

    // Use statistics from backend
    const totalCount = channelStats.total;
    const resolutionCounts = channelStats.resolution;
    const connectivityCounts = channelStats.connectivity;
    const groupCounts = channelStats.groups;

    // Update "All Channels" count
    const allCountElement = document.getElementById('filter-count-all');
    if (allCountElement) {
        allCountElement.textContent = totalCount;
    }

    // Update resolution counts
    document.getElementById('resolution-count-all').textContent = totalCount;
    document.getElementById('resolution-count-4k').textContent = resolutionCounts['4k'] || 0;
    document.getElementById('resolution-count-1080').textContent = resolutionCounts['1080'] || 0;
    document.getElementById('resolution-count-720').textContent = resolutionCounts['720'] || 0;
    document.getElementById('resolution-count-unknown').textContent = resolutionCounts['unknown'] || 0;

    // Update connectivity counts
    document.getElementById('connectivity-count-all').textContent = totalCount;
    document.getElementById('connectivity-count-online').textContent = connectivityCounts['online'] || 0;
    document.getElementById('connectivity-count-offline').textContent = connectivityCounts['offline'] || 0;
    document.getElementById('connectivity-count-failed').textContent = connectivityCounts['failed'] || 0;
    document.getElementById('connectivity-count-testing').textContent = connectivityCounts['testing'] || 0;
    document.getElementById('connectivity-count-untested').textContent = connectivityCounts['untested'] || 0;

    // Add buttons for each group from backend stats (sorted by sort_order)
    const sortedGroups = Object.entries(groupCounts).sort((a, b) => {
        const orderA = a[1].sort_order || 9999;
        const orderB = b[1].sort_order || 9999;
        return orderA - orderB;
    });

    sortedGroups.forEach(([groupId, groupInfo]) => {
        const btn = document.createElement('button');
        btn.className = 'group-filter-btn';
        btn.dataset.group = groupId;
        btn.innerHTML = `
            ${groupInfo.name}
            <span class="filter-count">${groupInfo.count}</span>
        `;
        btn.onclick = () => filterChannelsByGroup(groupId);
        filterContainer.appendChild(btn);
    });
}

// Filter channels by group
function filterChannelsByGroup(groupId) {
    currentGroupFilter = groupId;

    // Save to localStorage
    localStorage.setItem('groupFilter', groupId);

    // Update active button state
    document.querySelectorAll('.group-filter-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-group="${groupId}"]`).classList.add('active');

    // Reload channels with new filter from server
    loadChannels();
}

// Filter channels by resolution
function filterChannelsByResolution(resolution) {
    currentChannelResolutionFilter = resolution;

    // Save to localStorage
    localStorage.setItem('resolutionFilter', resolution);

    // Update active button state
    document.querySelectorAll('.resolution-filter-buttons .resolution-filter-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`.resolution-filter-buttons [data-resolution="${resolution}"]`).classList.add('active');

    // Reload channels with new filter from server
    loadChannels();
}

// Filter channels by connectivity
function filterChannelsByConnectivity(connectivity) {
    currentConnectivityFilter = connectivity;

    // Save to localStorage
    localStorage.setItem('connectivityFilter', connectivity);

    // Update active button state
    document.querySelectorAll('.connectivity-filter-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-connectivity="${connectivity}"]`).classList.add('active');

    // Reload channels with new filter from server
    loadChannels();
}

// Filter channels by IP or channel name (fuzzy search)
function filterChannelsByIPOrName() {
    const input = document.getElementById('ip-filter-input');
    currentIPFilter = input.value.trim();

    // Reload channels with new search filter from server
    loadChannels();
}

// Clear IP filter
function clearIPFilter() {
    document.getElementById('ip-filter-input').value = '';
    currentIPFilter = '';

    // Reload channels from server
    loadChannels();
}

function displayChannels(channels) {
    const channelsTbody = document.getElementById('channels-tbody');
    const channelsCount = document.getElementById('channels-count');

    channelsTbody.innerHTML = '';

    // Channels are already sorted by the backend, so just display them in order
    // Backend sorting rules:
    // 1. Group sort_order (grouped channels first, sorted by group order)
    // 2. Resolution (higher resolution first within same group)
    // 3. Channel name (natural sorting for names with numbers like CCTV1, CCTV2, CCTV11)
    // 4. Test status (failed tests go to the bottom)

    // Update count display - show online count from backend stats
    const onlineCount = channelStats ? channelStats.connectivity.online : 0;
    channelsCount.textContent = `共 ${onlineCount} 个频道`;

    // Handle both array and object formats for backward compatibility
    const channelsList = Array.isArray(channels)
        ? channels
        : Object.entries(channels).map(([ip, channel]) => ({ip, ...channel}));

    channelsList.forEach(channel => {
        const ip = channel.ip;
        const row = createChannelRow(ip, channel);
        channelsTbody.appendChild(row);
    });
}

function createChannelRow(ip, channel) {
    const row = document.createElement('tr');
    row.dataset.ip = ip;

    // Highlight newly imported channels
    if (newlyImportedChannels.has(ip)) {
        row.classList.add('newly-imported');
    }

    // 截图 column
    const screenshotTd = document.createElement('td');
    const screenshotDiv = document.createElement('div');
    screenshotDiv.className = 'channel-screenshot-cell';

    if (channel.screenshot) {
        screenshotDiv.onclick = () => enlargeImage(channel.screenshot);
        const img = document.createElement('img');
        img.src = channel.screenshot;
        img.alt = channel.name || 'Channel Screenshot';
        screenshotDiv.appendChild(img);
    } else {
        // No screenshot available, show placeholder
        screenshotDiv.className += ' no-screenshot';
        screenshotDiv.innerHTML = `
            <div class="no-screenshot-icon">📡</div>
            <div class="no-screenshot-text">No Image</div>
        `;
    }

    screenshotTd.appendChild(screenshotDiv);

    // 台标 column (logo preview only, click to enlarge and edit)
    const logoTd = document.createElement('td');
    const logoContainer = document.createElement('div');
    logoContainer.className = 'logo-container-merged';

    // Logo preview (clickable to enlarge and edit)
    const logoPreview = document.createElement('div');
    logoPreview.className = 'logo-preview-merged';
    logoPreview.style.cursor = 'pointer';

    if (channel.logo) {
        const logoImg = document.createElement('img');
        logoImg.src = channel.logo;
        logoImg.className = 'channel-logo-merged';
        logoImg.title = '点击查看和编辑';
        logoPreview.appendChild(logoImg);
    } else {
        const noLogoSpan = document.createElement('span');
        noLogoSpan.className = 'no-logo-merged';
        noLogoSpan.textContent = '点击添加';
        logoPreview.appendChild(noLogoSpan);
    }

    // Click to open image modal with URL editor
    logoPreview.onclick = () => openLogoModal(ip, channel.logo || '', logoPreview);

    logoContainer.appendChild(logoPreview);
    logoTd.appendChild(logoContainer);

    // IP column
    const ipTd = document.createElement('td');
    ipTd.textContent = ip;
    ipTd.className = 'channel-ip';

    // 频道名 column (editable on click, auto-save on blur)
    const nameTd = document.createElement('td');
    const nameInput = document.createElement('input');
    nameInput.type = 'text';
    nameInput.className = 'channel-field channel-name';
    nameInput.value = channel.name || '';
    nameInput.placeholder = '频道名';
    nameInput.readOnly = false; // Always editable

    // Save on blur
    nameInput.onblur = () => {
        saveChannelField(ip, 'name', nameInput.value);
    };

    // Select all text on focus for easier editing
    nameInput.onfocus = () => {
        nameInput.select();
    };

    nameTd.appendChild(nameInput);

    // TVG ID column (editable on click, auto-save on blur)
    const tvgIdTd = document.createElement('td');
    const tvgIdInput = document.createElement('input');
    tvgIdInput.type = 'text';
    tvgIdInput.className = 'channel-field channel-tvg-id';
    tvgIdInput.value = channel.tvg_id || '';
    tvgIdInput.placeholder = 'TVG ID';
    tvgIdInput.readOnly = false; // Always editable

    // Save on blur
    tvgIdInput.onblur = () => {
        saveChannelField(ip, 'tvg_id', tvgIdInput.value);
    };

    // Select all text on focus for easier editing
    tvgIdInput.onfocus = () => {
        tvgIdInput.select();
    };

    tvgIdTd.appendChild(tvgIdInput);

    // 分辨率 column (display resolution)
    const resolutionTd = document.createElement('td');
    const resolutionDiv = document.createElement('div');
    resolutionDiv.className = 'channel-resolution';

    if (channel.resolution) {
        const resolutionBadge = document.createElement('span');
        resolutionBadge.className = 'resolution-badge';

        // Add different styling based on resolution quality
        const [widthStr, heightStr] = channel.resolution.split('x');
        const width = parseInt(widthStr);
        const height = parseInt(heightStr);

        // Treat 720x576 as 720p
        const is720p = (width === 720 && height === 576) || (width >= 1280 && width < 1920);

        if (width >= 3840) {
            resolutionBadge.classList.add('resolution-4k');
            resolutionBadge.title = '4K Ultra HD';
        } else if (width >= 1920) {
            resolutionBadge.classList.add('resolution-1080p');
            resolutionBadge.title = 'Full HD';
        } else if (is720p) {
            resolutionBadge.classList.add('resolution-720p');
            resolutionBadge.title = 'HD Ready';
        }

        resolutionBadge.textContent = channel.resolution;
        resolutionDiv.appendChild(resolutionBadge);
    } else {
        const noResolution = document.createElement('span');
        noResolution.className = 'no-resolution';
        noResolution.textContent = '-';
        resolutionDiv.appendChild(noResolution);
    }

    resolutionTd.appendChild(resolutionDiv);

    // 连通性 column (connectivity status)
    const connectivityTd = document.createElement('td');
    const connectivityDiv = document.createElement('div');
    connectivityDiv.className = 'channel-connectivity';

    const connectivity = channel.connectivity || 'untested';
    const connectivityBadge = document.createElement('span');
    connectivityBadge.className = `connectivity-badge connectivity-${connectivity} clickable`;
    connectivityBadge.style.cursor = 'pointer';

    let statusIcon = '';
    let statusText = '';
    if (connectivity === 'online') {
        statusIcon = '🟢';
        statusText = i18n.get('online') || '在线';
        connectivityBadge.title = '连通正常，点击重新测试';
    } else if (connectivity === 'offline') {
        statusIcon = '🟠';
        statusText = i18n.get('offline') || '离线';
        connectivityBadge.title = '之前通过但现在离线，点击重新测试';
    } else if (connectivity === 'failed') {
        statusIcon = '🔴';
        statusText = i18n.get('failed') || '失败';
        connectivityBadge.title = '流测试失败，点击重新测试';
    } else if (connectivity === 'testing') {
        statusIcon = '🟡';
        statusText = i18n.get('testing') || '测试中';
        connectivityBadge.title = '正在测试...';
    } else {
        statusIcon = '⚪';
        statusText = i18n.get('untested') || '未测试';
        connectivityBadge.title = '未测试，点击测试';
    }

    connectivityBadge.innerHTML = `${statusIcon} <span>${statusText}</span>`;

    // Make badge clickable to test connectivity
    connectivityBadge.onclick = () => testSingleChannelConnectivity(ip);

    connectivityDiv.appendChild(connectivityBadge);
    connectivityTd.appendChild(connectivityDiv);

    // 分组 column (display groups)
    const groupTd = document.createElement('td');
    const groupDiv = document.createElement('div');
    groupDiv.className = 'channel-groups';
    groupDiv.title = 'Click to edit groups';

    // Make the entire div clickable
    groupDiv.onclick = (e) => {
        e.stopPropagation();
        openChannelGroupModal(ip, channel);
    };

    if (channel.groups && channel.groups.length > 0) {
        channel.groups.forEach(group => {
            const groupTag = document.createElement('span');
            groupTag.className = 'group-tag';
            groupTag.textContent = group.name;
            groupDiv.appendChild(groupTag);
        });
    } else {
        const noGroup = document.createElement('span');
        noGroup.className = 'no-group';
        noGroup.textContent = 'Click to add';
        groupDiv.appendChild(noGroup);
    }

    groupTd.appendChild(groupDiv);

    // URL column (clickable to copy)
    const urlTd = document.createElement('td');
    const urlDiv = document.createElement('div');
    urlDiv.className = 'channel-url';
    urlDiv.textContent = channel.url;
    urlDiv.title = channel.url; // Show full URL on hover
    urlDiv.onclick = () => copyToClipboard(channel.url, urlDiv);
    urlTd.appendChild(urlDiv);

    // 回放 column (editable on click, auto-save on blur)
    const playbackTd = document.createElement('td');
    const playbackInput = document.createElement('input');
    playbackInput.type = 'text';
    playbackInput.className = 'channel-field channel-playback';
    playbackInput.value = channel.playback || '';
    playbackInput.placeholder = '回放地址';
    playbackInput.readOnly = false; // Always editable

    // Save on blur
    playbackInput.onblur = () => {
        saveChannelField(ip, 'playback', playbackInput.value);
    };

    // Select all text on focus for easier editing
    playbackInput.onfocus = () => {
        playbackInput.select();
    };

    playbackTd.appendChild(playbackInput);

    // 更新时间 column
    const timeTd = document.createElement('td');
    timeTd.className = 'channel-time';
    timeTd.textContent = new Date(channel.timestamp).toLocaleString('zh-CN');

    row.appendChild(screenshotTd);
    row.appendChild(logoTd);
    row.appendChild(ipTd);
    row.appendChild(nameTd);
    row.appendChild(tvgIdTd);
    row.appendChild(resolutionTd);
    row.appendChild(connectivityTd);
    row.appendChild(groupTd);
    row.appendChild(urlTd);
    row.appendChild(playbackTd);
    row.appendChild(timeTd);

    return row;
}

// Auto-save individual channel field
async function saveChannelField(ip, field, value) {
    try {
        const data = {
            ip: ip
        };

        // Set the field to update
        if (field === 'name') {
            data.name = value;
        } else if (field === 'playback') {
            data.playback = value;
            // Auto-update catchup field based on playback
            if (value && value.trim() !== '') {
                // If playback has value, set catchup to 'default'
                data.catchup = 'default';
            } else {
                // If playback is empty, clear catchup
                data.catchup = '';
            }
        } else if (field === 'logo') {
            data.logo = value;
        } else if (field === 'tvg_id') {
            data.tvg_id = value;
        }

        const response = await fetch('/api/channels/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();
        if (result.status !== 'success') {
            console.error('Failed to save channel field:', result.message);
        } else {
            // Update local cache to reflect changes immediately
            if (Array.isArray(allChannels)) {
                const channel = allChannels.find(ch => ch.ip === ip);
                if (channel) {
                    if (field === 'name') channel.name = value;
                    else if (field === 'playback') {
                        channel.playback = value;
                        channel.catchup = value && value.trim() !== '' ? 'default' : '';
                    }
                    else if (field === 'logo') channel.logo = value;
                    else if (field === 'tvg_id') channel.tvg_id = value;
                }
            } else if (allChannels[ip]) {
                if (field === 'name') allChannels[ip].name = value;
                else if (field === 'playback') {
                    allChannels[ip].playback = value;
                    allChannels[ip].catchup = value && value.trim() !== '' ? 'default' : '';
                }
                else if (field === 'logo') allChannels[ip].logo = value;
                else if (field === 'tvg_id') allChannels[ip].tvg_id = value;
            }

            // Also update allChannelsCache if it exists
            if (allChannelsCache) {
                if (Array.isArray(allChannelsCache)) {
                    const cached = allChannelsCache.find(ch => ch.ip === ip);
                    if (cached) {
                        if (field === 'name') cached.name = value;
                        else if (field === 'playback') {
                            cached.playback = value;
                            cached.catchup = value && value.trim() !== '' ? 'default' : '';
                        }
                        else if (field === 'logo') cached.logo = value;
                        else if (field === 'tvg_id') cached.tvg_id = value;
                    }
                } else if (allChannelsCache[ip]) {
                    if (field === 'name') allChannelsCache[ip].name = value;
                    else if (field === 'playback') {
                        allChannelsCache[ip].playback = value;
                        allChannelsCache[ip].catchup = value && value.trim() !== '' ? 'default' : '';
                    }
                    else if (field === 'logo') allChannelsCache[ip].logo = value;
                    else if (field === 'tvg_id') allChannelsCache[ip].tvg_id = value;
                }
            }
        }
    } catch (error) {
        console.error('Failed to save channel field:', error);
    }
}

// Deprecated: toggleEditChannel - No longer used with auto-save functionality
// Kept for reference only


async function saveChannelInfo(ip, name, group, playback, logo) {
    try {
        const response = await fetch('/api/channels/update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ ip, name, group, playback, logo })
        });

        const data = await response.json();
        if (data.status !== 'success') {
            alert('Failed to save channel info');
        }
    } catch (error) {
        console.error('Failed to save channel info:', error);
    }
}


function copyToClipboard(text, element) {
    // Try using modern clipboard API first
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
            // Show copy success feedback
            const originalBg = element.style.background;
            element.style.background = '#d1fae5';

            setTimeout(() => {
                element.style.background = originalBg;
            }, 1000);
        }).catch(err => {
            console.error('Clipboard API failed:', err);
            // Fallback to execCommand
            fallbackCopyToClipboard(text, element);
        });
    } else {
        // Use fallback method
        fallbackCopyToClipboard(text, element);
    }
}

function fallbackCopyToClipboard(text, element) {
    // Create a temporary textarea element
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);

    try {
        textarea.select();
        textarea.setSelectionRange(0, 99999); // For mobile devices

        const successful = document.execCommand('copy');

        if (successful) {
            // Show copy success feedback
            const originalBg = element.style.background;
            element.style.background = '#d1fae5';

            setTimeout(() => {
                element.style.background = originalBg;
            }, 1000);
        } else {
            alert('复制失败，请手动复制');
        }
    } catch (err) {
        console.error('Fallback copy failed:', err);
        alert('复制失败，请手动复制');
    } finally {
        document.body.removeChild(textarea);
    }
}

function enlargeImage(src) {
    const modal = document.getElementById('image-modal');
    const modalImg = document.getElementById('modal-img');

    // Hide logo URL editor if it exists
    const urlEditor = modal.querySelector('.logo-url-editor');
    if (urlEditor) {
        urlEditor.style.display = 'none';
    }

    modal.classList.add('active');
    modalImg.src = src;
}

// Open logo modal with URL editor
function openLogoModal(ip, logoUrl, previewElement) {
    const modal = document.getElementById('image-modal');
    const modalImg = document.getElementById('modal-img');

    // Check if URL input already exists, if not create it
    let urlInputContainer = modal.querySelector('.logo-url-editor');
    if (!urlInputContainer) {
        urlInputContainer = document.createElement('div');
        urlInputContainer.className = 'logo-url-editor';

        const urlLabel = document.createElement('label');
        urlLabel.textContent = 'Logo URL:';
        urlLabel.style.cssText = 'display: block; color: white; font-size: 0.9rem; margin-bottom: 8px; font-weight: 500;';

        const urlInput = document.createElement('input');
        urlInput.type = 'text';
        urlInput.className = 'logo-url-input-modal';
        urlInput.placeholder = '输入logo图片URL地址';

        const buttonContainer = document.createElement('div');
        buttonContainer.style.cssText = 'display: flex; gap: 10px; margin-top: 12px;';

        const saveBtn = document.createElement('button');
        saveBtn.textContent = '保存';
        saveBtn.className = 'btn btn-primary logo-save-btn';
        saveBtn.style.cssText = 'flex: 1;';

        const cancelBtn = document.createElement('button');
        cancelBtn.textContent = '取消';
        cancelBtn.className = 'btn btn-secondary';
        cancelBtn.style.cssText = 'flex: 1;';

        buttonContainer.appendChild(saveBtn);
        buttonContainer.appendChild(cancelBtn);

        urlInputContainer.appendChild(urlLabel);
        urlInputContainer.appendChild(urlInput);
        urlInputContainer.appendChild(buttonContainer);

        modal.appendChild(urlInputContainer);

        // Cancel button handler (static)
        cancelBtn.onclick = () => {
            modal.classList.remove('active');
        };

        // Real-time preview (static)
        urlInput.oninput = () => {
            const newUrl = urlInput.value.trim();
            if (newUrl) {
                modalImg.src = newUrl;
            } else {
                modalImg.src = '';
            }
        };
    }

    // Get elements
    const saveBtn = urlInputContainer.querySelector('.logo-save-btn');
    const urlInput = urlInputContainer.querySelector('.logo-url-input-modal');

    // Set initial value
    urlInput.value = logoUrl;

    // Update save button handler with current ip and previewElement
    saveBtn.onclick = async () => {
        const newUrl = urlInput.value.trim();
        await saveChannelField(ip, 'logo', newUrl);

        // Update preview in table
        if (newUrl) {
            const img = new Image();
            img.onload = () => {
                previewElement.innerHTML = '';
                const logoImg = document.createElement('img');
                logoImg.src = newUrl;
                logoImg.className = 'channel-logo-merged';
                logoImg.title = '点击查看和编辑';
                previewElement.appendChild(logoImg);
            };
            img.onerror = () => {
                previewElement.innerHTML = '<span class="no-logo-merged">加载失败</span>';
            };
            img.src = newUrl;
        } else {
            previewElement.innerHTML = '<span class="no-logo-merged">点击添加</span>';
        }

        modal.classList.remove('active');
    };

    // Show image and input
    if (logoUrl) {
        modalImg.src = logoUrl;
    } else {
        modalImg.src = '';
    }

    // Show the URL editor
    urlInputContainer.style.display = 'block';

    // Show the modal
    modal.classList.add('active');

    // Focus on input
    setTimeout(() => urlInput.focus(), 100);
}

// Close modal
document.querySelector('.modal-close').addEventListener('click', () => {
    document.getElementById('image-modal').classList.remove('active');
});

document.getElementById('image-modal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) {
        e.currentTarget.classList.remove('active');
    }
});

// Clear channel names button
document.getElementById('clear-names-btn').addEventListener('click', async () => {
    if (!confirm('Are you sure you want to clear all channel names? This action cannot be undone.')) {
        return;
    }

    const btn = document.getElementById('clear-names-btn');
    const originalContent = btn.innerHTML;

    try {
        btn.disabled = true;
        btn.innerHTML = '<span>⏳</span> Clearing...';

        const response = await fetch('/api/channels/clear-names', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (data.status === 'success') {
            alert(`Cleared ${data.cleared} channel names`);
            // Reload channels to show updated names
            await loadChannels();
        } else {
            alert('Failed to clear: ' + (data.message || 'Unknown error'));
        }
    } catch (error) {
        alert('Failed to clear: ' + error.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalContent;
    }
});

// AI Recognition button
document.getElementById('ai-recognize-btn').addEventListener('click', async () => {
    const btn = document.getElementById('ai-recognize-btn');
    const originalContent = btn.innerHTML;

    try {
        // Load config first to check if AI is configured
        const configResponse = await fetch('/api/config');
        const config = await configResponse.json();

        if (!config.ai_model || !config.ai_model.enabled) {
            alert('Please configure and enable AI model in Advanced Settings first');
            // Switch to config tab
            document.querySelectorAll('.tab-button').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.querySelector('[data-tab="config"]').classList.add('active');
            document.getElementById('config-tab').classList.add('active');
            return;
        }

        // Disable button and show loading
        btn.disabled = true;
        btn.innerHTML = '<span>🔄</span> Recognizing...';

        const response = await fetch('/api/channels/recognize', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (data.status === 'started') {
            // Background task started - restore button immediately
            btn.disabled = false;
            btn.innerHTML = originalContent;

            // Show non-blocking notification
            const notification = document.createElement('div');
            notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: #667eea;
                color: white;
                padding: 15px 20px;
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                z-index: 10000;
                animation: slideIn 0.3s ease-out;
            `;
            notification.innerHTML = `
                <strong>AI Recognition Started</strong><br>
                ${data.message}<br>
                <small>Will refresh automatically when complete</small>
            `;
            document.body.appendChild(notification);

            // Auto-remove notification after 5 seconds
            setTimeout(() => {
                notification.remove();
            }, 5000);

            // Auto-refresh periodically to check progress
            let refreshCount = 0;
            const refreshInterval = setInterval(async () => {
                refreshCount++;
                await loadChannels();

                // Stop refreshing after 60 seconds (12 times * 5 seconds)
                if (refreshCount >= 12) {
                    clearInterval(refreshInterval);
                }
            }, 5000); // Refresh every 5 seconds

            // Early return to prevent button from being disabled again
            return;

        } else if (data.status === 'success') {
            if (data.recognized > 0) {
                alert(`Successfully recognized ${data.recognized}/${data.total} channels`);
                // Reload channels to show updated names
                await loadChannels();
            } else if (data.total === 0) {
                alert('No channels to recognize (all channels already have names or no screenshots)');
            } else {
                alert('Could not recognize any channels. Please check if AI configuration is correct');
            }

            if (data.errors && data.errors.length > 0) {
                console.error('Recognition errors:', data.errors);
            }
        } else {
            alert(data.message || 'Recognition failed');
        }
    } catch (error) {
        alert('AI recognition failed: ' + error.message);
    } finally {
        // Restore button
        btn.disabled = false;
        btn.innerHTML = originalContent;
    }
});

// Import M3U
document.getElementById('import-m3u-btn').addEventListener('click', () => {
    openImportM3uModal();
});

function openImportM3uModal() {
    const modal = document.getElementById('import-m3u-modal');
    modal.style.display = 'flex';

    // Reset modal state
    document.getElementById('m3u-file-input').value = '';
    document.getElementById('import-progress').style.display = 'none';
    document.getElementById('import-result').style.display = 'none';
    document.getElementById('import-confirm-btn').disabled = false;
}

function closeImportM3uModal() {
    const modal = document.getElementById('import-m3u-modal');
    modal.style.display = 'none';
}

async function startImportM3u() {
    const fileInput = document.getElementById('m3u-file-input');
    const file = fileInput.files[0];

    if (!file) {
        alert('Please select an M3U file');
        return;
    }

    const progressDiv = document.getElementById('import-progress');
    const resultDiv = document.getElementById('import-result');
    const statusText = document.getElementById('import-status');
    const progressFill = document.getElementById('import-progress-fill');
    const confirmBtn = document.getElementById('import-confirm-btn');

    // Show progress
    progressDiv.style.display = 'block';
    resultDiv.style.display = 'none';
    statusText.textContent = i18n.get('importing');
    progressFill.style.width = '50%';
    confirmBtn.disabled = true;

    try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch('/api/channels/import', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        progressFill.style.width = '100%';

        if (data.status === 'success') {
            // Show success result
            progressDiv.style.display = 'none';
            resultDiv.style.display = 'block';

            let resultText = i18n.get('importSuccess') + '!\n';
            resultText += `新增: ${data.imported} 个频道\n`;
            resultText += `更新: ${data.updated} 个频道\n`;
            resultText += `总计: ${data.total} 个频道`;

            if (data.groups_created > 0) {
                resultText += `\n创建分组: ${data.groups_created} 个`;
            }

            document.getElementById('import-result-text').textContent = resultText;

            // Save newly imported channel IPs for highlighting
            newlyImportedChannels = new Set(data.new_channels || []);

            // Reload channels and groups
            setTimeout(async () => {
                await loadGroups();  // Load groups (also updates allGroupsCache)
                await loadChannels();  // Use cached groups, no duplicate request
                closeImportM3uModal();

                // Clear highlighting after 10 seconds
                setTimeout(() => {
                    newlyImportedChannels.clear();
                    loadChannels(); // Refresh to remove highlighting
                }, 10000);
            }, 2000);
        } else {
            throw new Error(data.message || 'Import failed');
        }
    } catch (error) {
        progressDiv.style.display = 'none';
        alert('Failed to import M3U: ' + error.message);
        confirmBtn.disabled = false;
    }
}

// Export M3U
document.getElementById('export-channels-btn').addEventListener('click', async () => {
    try {
        const response = await fetch('/api/channels/export');
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `channels_${new Date().toISOString().split('T')[0]}.m3u`;
        a.click();
        window.URL.revokeObjectURL(url);
    } catch (error) {
        alert('Failed to export channels: ' + error.message);
    }
});

// Groups management
let currentGroupId = null;
let allGroups = {};
let selectedChannelsForGroup = [];

// Track newly imported channels for highlighting
let newlyImportedChannels = new Set();

// Test connectivity
async function testSingleChannelConnectivity(ip) {
    try {
        // Update UI to show testing status
        const row = document.querySelector(`tr[data-ip="${ip}"]`);
        if (row) {
            const connectivityBadge = row.querySelector('.connectivity-badge');
            if (connectivityBadge) {
                connectivityBadge.className = 'connectivity-badge connectivity-testing';
                connectivityBadge.innerHTML = `🟡 <span>${i18n.get('testing') || '测试中'}</span>`;
            }
        }

        const response = await fetch('/api/channels/test-connectivity', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ips: [ip] })
        });

        const data = await response.json();

        if (data.status === 'success' && data.results.length > 0) {
            // Reload channels to update display
            await loadChannels();
        }
    } catch (error) {
        console.error('Failed to test connectivity:', error);
        alert('测试失败: ' + error.message);
    }
}

// Test all channels connectivity - one by one (serial processing)
async function testAllChannelsConnectivity() {
    const btn = document.getElementById('test-all-connectivity-btn');
    const originalContent = btn.innerHTML;

    try {
        btn.disabled = true;
        const testingText = i18n.get('testing') || 'Testing';
        btn.innerHTML = `<span>⏳</span> <span>${testingText}...</span>`;

        // Get all channel IPs from the current filtered view (allChannels contains filtered results)
        const allChannelIps = Array.isArray(allChannels)
            ? allChannels.map(ch => ch.ip)
            : Object.keys(allChannels);

        if (allChannelIps.length === 0) {
            alert('没有频道可测试');
            return;
        }

        // Test channels one by one (serial processing)
        for (let i = 0; i < allChannelIps.length; i++) {
            const ip = allChannelIps[i];

            // Update UI to show testing status for current channel
            const row = document.querySelector(`tr[data-ip="${ip}"]`);
            if (row) {
                const connectivityBadge = row.querySelector('.connectivity-badge');
                if (connectivityBadge) {
                    connectivityBadge.className = 'connectivity-badge connectivity-testing';
                    connectivityBadge.innerHTML = `🟡 <span>${testingText}</span>`;
                }
            }

            // Update button progress
            const progress = Math.round(((i + 1) / allChannelIps.length) * 100);
            btn.innerHTML = `<span>⏳</span> <span>${testingText} ${i + 1}/${allChannelIps.length} (${progress}%)</span>`;

            try {
                // Test single channel
                const response = await fetch('/api/channels/test-connectivity', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ips: [ip] })
                });

                const data = await response.json();

                // Update the row immediately with all result data (connectivity, screenshot, resolution, etc.)
                if (data.status === 'success' && data.results.length > 0) {
                    const result = data.results[0];
                    if (row) {
                        // Update connectivity badge
                        const connectivityBadge = row.querySelector('.connectivity-badge');
                        if (connectivityBadge) {
                            const connectivity = result.connectivity;
                            let statusIcon = '';
                            let statusText = '';

                            if (connectivity === 'online') {
                                statusIcon = '🟢';
                                statusText = i18n.get('online') || 'Online';
                                connectivityBadge.className = 'connectivity-badge connectivity-online clickable';
                            } else if (connectivity === 'offline') {
                                statusIcon = '🟠';
                                statusText = i18n.get('offline') || 'Offline';
                                connectivityBadge.className = 'connectivity-badge connectivity-offline clickable';
                            } else if (connectivity === 'failed') {
                                statusIcon = '🔴';
                                statusText = i18n.get('failed') || 'Failed';
                                connectivityBadge.className = 'connectivity-badge connectivity-failed clickable';
                            } else {
                                statusIcon = '⚪';
                                statusText = i18n.get('untested') || 'Untested';
                                connectivityBadge.className = 'connectivity-badge connectivity-untested clickable';
                            }

                            connectivityBadge.innerHTML = `${statusIcon} <span>${statusText}</span>`;
                        }

                        // Update screenshot if changed
                        if (result.screenshot) {
                            const screenshotImg = row.querySelector('.channel-screenshot-cell img');
                            if (screenshotImg) {
                                screenshotImg.src = result.screenshot;
                            } else {
                                // No screenshot before, add one
                                const screenshotDiv = row.querySelector('.channel-screenshot-cell');
                                if (screenshotDiv && screenshotDiv.classList.contains('no-screenshot')) {
                                    screenshotDiv.classList.remove('no-screenshot');
                                    screenshotDiv.innerHTML = '';
                                    screenshotDiv.onclick = () => enlargeImage(result.screenshot);
                                    const img = document.createElement('img');
                                    img.src = result.screenshot;
                                    img.alt = result.name || 'Channel Screenshot';
                                    screenshotDiv.appendChild(img);
                                }
                            }
                        }

                        // Update resolution if changed
                        if (result.resolution) {
                            const resolutionBadge = row.querySelector('.resolution-badge');
                            if (resolutionBadge) {
                                const [widthStr, heightStr] = result.resolution.split('x');
                                const width = parseInt(widthStr);
                                const height = parseInt(heightStr);
                                const is720p = (width === 720 && height === 576) || (width >= 1280 && width < 1920);

                                let badgeClass = 'resolution-badge';
                                let badgeTitle = '';
                                if (width >= 3840) {
                                    badgeClass += ' resolution-4k';
                                    badgeTitle = '4K Ultra HD';
                                } else if (width >= 1920) {
                                    badgeClass += ' resolution-1080p';
                                    badgeTitle = 'Full HD';
                                } else if (is720p) {
                                    badgeClass += ' resolution-720p';
                                    badgeTitle = 'HD Ready';
                                }

                                resolutionBadge.className = badgeClass;
                                resolutionBadge.title = badgeTitle;
                                resolutionBadge.textContent = result.resolution;
                            }
                        }

                        // Update local cache
                        if (Array.isArray(allChannels)) {
                            const channel = allChannels.find(ch => ch.ip === ip);
                            if (channel) {
                                Object.assign(channel, result);
                            }
                        } else if (allChannels[ip]) {
                            Object.assign(allChannels[ip], result);
                        }

                        if (allChannelsCache) {
                            if (Array.isArray(allChannelsCache)) {
                                const cached = allChannelsCache.find(ch => ch.ip === ip);
                                if (cached) {
                                    Object.assign(cached, result);
                                }
                            } else if (allChannelsCache[ip]) {
                                Object.assign(allChannelsCache[ip], result);
                            }
                        }
                    }
                }
            } catch (error) {
                console.error(`Failed to test ${ip}:`, error);
                // Continue with next channel even if this one fails
            }
        }

        // Final reload to ensure all data is synchronized
        await loadChannels();

        alert(`测试完成！共测试 ${allChannelIps.length} 个频道`);

    } catch (error) {
        console.error('Failed to test connectivity:', error);
        alert('测试失败: ' + error.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalContent;
    }
}

// Bind test all button
document.getElementById('test-all-connectivity-btn').addEventListener('click', testAllChannelsConnectivity);

// Load groups
async function loadGroups() {
    try {
        const response = await fetch('/api/groups');
        const data = await response.json();

        if (data.status === 'success') {
            allGroups = data.groups;
            allGroupsCache = data.groups;  // Also update cache to avoid duplicate requests
            displayGroupsList();

            // Auto-select first group if no group is currently selected
            if (!currentGroupId && Object.keys(allGroups).length > 0) {
                // Sort groups by sort_order to get the first one
                const sortedGroups = Object.entries(allGroups).sort((a, b) => {
                    const orderA = a[1].sort_order || 999;
                    const orderB = b[1].sort_order || 999;
                    return orderA - orderB;
                });

                // Select the first group
                const firstGroupId = sortedGroups[0][0];
                selectGroup(firstGroupId);
            }
        }
    } catch (error) {
        console.error('Failed to load groups:', error);
    }
}

// Display groups list
function displayGroupsList() {
    const groupsList = document.getElementById('groups-list');
    groupsList.innerHTML = '';

    if (Object.keys(allGroups).length === 0) {
        groupsList.innerHTML = '<li class="no-groups">No groups yet. Click "New Group" to create one.</li>';
        return;
    }

    // Sort groups by sort_order
    const sortedGroups = Object.entries(allGroups).sort((a, b) => {
        const orderA = a[1].sort_order || 999;
        const orderB = b[1].sort_order || 999;
        return orderA - orderB;
    });

    sortedGroups.forEach(([groupId, group]) => {
        const li = document.createElement('li');
        li.className = 'group-item';
        li.draggable = true;
        li.dataset.groupId = groupId;

        if (groupId === currentGroupId) {
            li.classList.add('active');
        }

        li.innerHTML = `
            <span class="drag-handle">☰</span>
            <span class="group-name">${group.name}</span>
            <span class="group-count">(${group.channels ? group.channels.length : 0})</span>
            <div class="group-item-actions">
                <button class="btn-icon" onclick="renameGroup('${groupId}', '${group.name}')" title="Rename">✏️</button>
                <button class="btn-icon" onclick="deleteGroup('${groupId}')" title="Delete">🗑️</button>
            </div>
        `;

        li.onclick = (e) => {
            if (!e.target.classList.contains('btn-icon') && !e.target.classList.contains('drag-handle')) {
                selectGroup(groupId);
            }
        };

        // Add drag events
        li.addEventListener('dragstart', handleDragStart);
        li.addEventListener('dragend', handleDragEnd);
        li.addEventListener('dragover', handleDragOver);
        li.addEventListener('drop', handleDrop);
        li.addEventListener('dragenter', handleDragEnter);
        li.addEventListener('dragleave', handleDragLeave);

        groupsList.appendChild(li);
    });
}

// Drag and drop handlers
let draggedElement = null;

function handleDragStart(e) {
    draggedElement = this;
    this.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', this.innerHTML);
}

function handleDragEnd(e) {
    this.classList.remove('dragging');

    // Remove all drag-over classes
    document.querySelectorAll('.group-item').forEach(item => {
        item.classList.remove('drag-over');
    });
}

function handleDragOver(e) {
    if (e.preventDefault) {
        e.preventDefault();
    }
    e.dataTransfer.dropEffect = 'move';
    return false;
}

function handleDragEnter(e) {
    if (this !== draggedElement) {
        this.classList.add('drag-over');
    }
}

function handleDragLeave(e) {
    this.classList.remove('drag-over');
}

function handleDrop(e) {
    if (e.stopPropagation) {
        e.stopPropagation();
    }

    if (draggedElement !== this) {
        const allItems = Array.from(document.querySelectorAll('.group-item'));
        const draggedIndex = allItems.indexOf(draggedElement);
        const targetIndex = allItems.indexOf(this);

        if (draggedIndex < targetIndex) {
            this.parentNode.insertBefore(draggedElement, this.nextSibling);
        } else {
            this.parentNode.insertBefore(draggedElement, this);
        }

        // Update sort order
        updateGroupsOrder();
    }

    return false;
}

// Update groups order after drag and drop
async function updateGroupsOrder() {
    const groupsList = document.getElementById('groups-list');
    const items = Array.from(groupsList.querySelectorAll('.group-item'));
    const orderList = items.map(item => item.dataset.groupId);

    try {
        const response = await fetch('/api/groups/reorder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order: orderList })
        });

        const data = await response.json();
        if (data.status === 'success') {
            // Reload groups to sync (also updates allGroupsCache)
            await loadGroups();
            // Refresh channels display with new sorting (uses cached groups)
            loadChannels();
        }
    } catch (error) {
        console.error('Failed to update groups order:', error);
    }
}

// Select a group
function selectGroup(groupId) {
    currentGroupId = groupId;
    displayGroupsList(); // Update active state

    const group = allGroups[groupId];
    document.getElementById('group-channels-title').textContent = group.name;
    document.getElementById('group-actions').style.display = 'flex';
    document.getElementById('group-channels-select-all').style.display = 'block';

    displayGroupChannels();
}

// Display channels in selected group
async function displayGroupChannels() {
    if (!currentGroupId) return;

    const group = allGroups[currentGroupId];
    const channelsList = document.getElementById('group-channels-list');

    // Reset select all checkbox
    document.getElementById('select-all-group-channels').checked = false;

    if (!group.channels || group.channels.length === 0) {
        channelsList.innerHTML = '<p class="no-channels">No channels in this group yet</p>';
        document.getElementById('group-channels-select-all').style.display = 'none';
        return;
    }

    // Get full channel info (use cache to avoid duplicate API calls)
    try {
        // Load all channels if not cached
        if (!allChannelsCache) {
            const response = await fetch('/api/channels');
            const data = await response.json();
            if (data.status === 'success') {
                allChannelsCache = data.channels;
            }
        }

        if (allChannelsCache) {
            channelsList.innerHTML = '';

            // Convert channels array to object for quick lookup
            const channelsMap = Array.isArray(allChannelsCache)
                ? Object.fromEntries(allChannelsCache.map(ch => [ch.ip, ch]))
                : allChannelsCache;

            group.channels.forEach(ip => {
                const channel = channelsMap[ip];
                if (!channel) return;

                const item = document.createElement('div');
                item.className = 'group-channel-item';

                const imgHtml = channel.screenshot
                    ? `<img src="${channel.screenshot}" class="channel-thumb" onclick="enlargeImage('${channel.screenshot}')">`
                    : `<div class="channel-thumb no-thumb">📡</div>`;

                // Generate resolution badge HTML
                let resolutionHtml = '';
                if (channel.resolution) {
                    const [widthStr, heightStr] = channel.resolution.split('x');
                    const width = parseInt(widthStr);
                    const height = parseInt(heightStr);
                    const is720p = (width === 720 && height === 576) || (width >= 1280 && width < 1920);

                    let badgeClass = 'resolution-badge';
                    let badgeTitle = '';
                    if (width >= 3840) {
                        badgeClass += ' resolution-4k';
                        badgeTitle = '4K Ultra HD';
                    } else if (width >= 1920) {
                        badgeClass += ' resolution-1080p';
                        badgeTitle = 'Full HD';
                    } else if (is720p) {
                        badgeClass += ' resolution-720p';
                        badgeTitle = 'HD Ready';
                    }
                    resolutionHtml = `<span class="${badgeClass}" title="${badgeTitle}">${channel.resolution}</span>`;
                }

                item.innerHTML = `
                    <input type="checkbox" class="channel-checkbox" data-ip="${ip}">
                    ${imgHtml}
                    <span class="channel-ip">${ip}</span>
                    <span class="channel-name">${channel.name || 'Unnamed'}</span>
                    ${resolutionHtml}
                `;
                channelsList.appendChild(item);
            });
        }
    } catch (error) {
        console.error('Failed to load channel details:', error);
    }
}

// Add new group
document.getElementById('add-group-btn').addEventListener('click', async () => {
    const name = prompt('Enter group name:');
    if (!name) return;

    try {
        const response = await fetch('/api/groups/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });

        const data = await response.json();
        if (data.status === 'success') {
            await loadGroups();
            selectGroup(data.group_id);
        } else {
            alert('Failed to create group: ' + (data.message || 'Unknown error'));
        }
    } catch (error) {
        alert('Failed to create group: ' + error.message);
    }
});

// Rename group
async function renameGroup(groupId, oldName) {
    const newName = prompt('Enter new group name:', oldName);
    if (!newName || newName === oldName) return;

    try {
        const response = await fetch(`/api/groups/${groupId}/rename`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: newName })
        });

        const data = await response.json();
        if (data.status === 'success') {
            await loadGroups();
            if (groupId === currentGroupId) {
                document.getElementById('group-channels-title').textContent = newName;
            }
        }
    } catch (error) {
        alert('Failed to rename: ' + error.message);
    }
}

// Delete group
async function deleteGroup(groupId) {
    if (!confirm('Are you sure you want to delete this group?')) return;

    try {
        const response = await fetch(`/api/groups/${groupId}`, {
            method: 'DELETE'
        });

        const data = await response.json();
        if (data.status === 'success') {
            if (groupId === currentGroupId) {
                currentGroupId = null;
                document.getElementById('group-channels-title').textContent = 'Select a group';
                document.getElementById('group-actions').style.display = 'none';
                document.getElementById('group-channels-select-all').style.display = 'none';
                document.getElementById('group-channels-list').innerHTML = '';
            }
            await loadGroups();
        }
    } catch (error) {
        alert('Failed to delete: ' + error.message);
    }
}

// Add channels button
document.getElementById('add-channels-btn').addEventListener('click', () => {
    if (!currentGroupId) return;
    showAddChannelsModal();
});

// Show add channels modal
async function showAddChannelsModal() {
    const modal = document.getElementById('add-channels-modal');
    modal.style.display = 'flex';

    // Load available channels (use cache to avoid duplicate API calls)
    try {
        // Load all channels if not cached
        if (!allChannelsCache) {
            const response = await fetch('/api/channels');
            const data = await response.json();
            if (data.status === 'success') {
                allChannelsCache = data.channels;
            }
        }

        if (allChannelsCache) {
            const group = allGroups[currentGroupId];
            const existingChannels = new Set(group.channels || []);

            const availableList = document.getElementById('available-channels-list');
            availableList.innerHTML = '';

            // Convert to entries for iteration
            const channelsEntries = Array.isArray(allChannelsCache)
                ? allChannelsCache.map(ch => [ch.ip, ch])
                : Object.entries(allChannelsCache);

            channelsEntries.forEach(([ip, channel]) => {
                if (existingChannels.has(ip)) return; // Skip already added channels

                const item = document.createElement('div');
                item.className = 'available-channel-item';

                const imgHtml = channel.screenshot
                    ? `<img src="${channel.screenshot}" class="channel-thumb">`
                    : `<div class="channel-thumb no-thumb">📡</div>`;

                // Generate resolution badge HTML
                let resolutionHtml = '';
                if (channel.resolution) {
                    const [widthStr, heightStr] = channel.resolution.split('x');
                    const width = parseInt(widthStr);
                    const height = parseInt(heightStr);
                    const is720p = (width === 720 && height === 576) || (width >= 1280 && width < 1920);

                    let badgeClass = 'resolution-badge';
                    let badgeTitle = '';
                    if (width >= 3840) {
                        badgeClass += ' resolution-4k';
                        badgeTitle = '4K Ultra HD';
                    } else if (width >= 1920) {
                        badgeClass += ' resolution-1080p';
                        badgeTitle = 'Full HD';
                    } else if (is720p) {
                        badgeClass += ' resolution-720p';
                        badgeTitle = 'HD Ready';
                    }
                    resolutionHtml = `<span class="${badgeClass}" title="${badgeTitle}">${channel.resolution}</span>`;
                }

                item.innerHTML = `
                    <input type="checkbox" class="channel-select" data-ip="${ip}">
                    ${imgHtml}
                    <span class="channel-ip">${ip}</span>
                    <span class="channel-name">${channel.name || 'Unnamed'}</span>
                    ${resolutionHtml}
                `;
                availableList.appendChild(item);
            });
        }
    } catch (error) {
        console.error('Failed to load channels:', error);
    }
}

// Close modal
function closeAddChannelsModal() {
    document.getElementById('add-channels-modal').style.display = 'none';
    selectedChannelsForGroup = [];
}

// Toggle select all for modal (only visible items)
function toggleSelectAll() {
    const selectAll = document.getElementById('select-all-channels').checked;
    document.querySelectorAll('.available-channel-item').forEach(item => {
        // Only select visible items (not hidden by search)
        if (item.style.display !== 'none') {
            const checkbox = item.querySelector('.channel-select');
            if (checkbox) {
                checkbox.checked = selectAll;
            }
        }
    });
}

// Toggle select all for group channels
function toggleSelectAllGroupChannels() {
    const selectAll = document.getElementById('select-all-group-channels').checked;
    document.querySelectorAll('.channel-checkbox').forEach(checkbox => {
        checkbox.checked = selectAll;
    });
}

// Confirm add channels
async function confirmAddChannels() {
    if (!currentGroupId) return;

    const selectedIps = [];
    document.querySelectorAll('.channel-select:checked').forEach(checkbox => {
        selectedIps.push(checkbox.dataset.ip);
    });

    if (selectedIps.length === 0) {
        alert('Please select at least one channel');
        return;
    }

    try {
        const response = await fetch(`/api/groups/${currentGroupId}/channels`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ channels: selectedIps })
        });

        const data = await response.json();
        if (data.status === 'success') {
            closeAddChannelsModal();
            await loadGroups();
            displayGroupChannels();
        }
    } catch (error) {
        alert('Failed to add channels: ' + error.message);
    }
}

// Remove selected channels
document.getElementById('remove-channels-btn').addEventListener('click', async () => {
    if (!currentGroupId) return;

    const selectedIps = [];
    document.querySelectorAll('.channel-checkbox:checked').forEach(checkbox => {
        selectedIps.push(checkbox.dataset.ip);
    });

    if (selectedIps.length === 0) {
        alert('Please select channels to remove');
        return;
    }

    if (!confirm(`Are you sure you want to remove ${selectedIps.length} channel(s) from the group?`)) return;

    try {
        const response = await fetch(`/api/groups/${currentGroupId}/channels`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ channels: selectedIps })
        });

        const data = await response.json();
        if (data.status === 'success') {
            await loadGroups();
            displayGroupChannels();
        }
    } catch (error) {
        alert('Failed to remove channels: ' + error.message);
    }
});

// Channel search
document.getElementById('channel-search')?.addEventListener('input', (e) => {
    const searchTerm = e.target.value.toLowerCase();

    // Reset select all checkbox when search changes
    document.getElementById('select-all-channels').checked = false;

    document.querySelectorAll('.available-channel-item').forEach(item => {
        const text = item.textContent.toLowerCase();
        item.style.display = text.includes(searchTerm) ? 'flex' : 'none';
    });
});

// Channel Group Modal Functions
let currentChannelForGroups = null;

function openChannelGroupModal(ip, channel) {
    currentChannelForGroups = { ip, channel };

    // Load groups if not already loaded
    if (Object.keys(allGroups).length === 0) {
        loadGroups();
    }

    // Show modal
    const modal = document.getElementById('channel-group-modal');
    modal.style.display = 'flex';

    // Set channel info
    document.getElementById('channel-group-modal-ip').textContent = `Channel: ${channel.name || ip}`;

    // Build group checkboxes
    const groupList = document.getElementById('channel-group-list');
    groupList.innerHTML = '';

    // Get current channel's group IDs
    const channelGroupIds = new Set((channel.groups || []).map(g => g.id));

    // Sort groups by sort_order
    const sortedGroups = Object.entries(allGroups).sort((a, b) => {
        const orderA = a[1].sort_order || 9999;
        const orderB = b[1].sort_order || 9999;
        return orderA - orderB;
    });

    // Add checkbox for each group (sorted by sort_order)
    sortedGroups.forEach(([groupId, group]) => {
        const item = document.createElement('div');
        item.className = 'channel-group-item';
        if (channelGroupIds.has(groupId)) {
            item.classList.add('selected');
        }

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.id = `group-checkbox-${groupId}`;
        checkbox.value = groupId;
        checkbox.checked = channelGroupIds.has(groupId);
        checkbox.onchange = (e) => {
            if (e.target.checked) {
                item.classList.add('selected');
            } else {
                item.classList.remove('selected');
            }
        };

        const label = document.createElement('label');
        label.htmlFor = `group-checkbox-${groupId}`;
        label.textContent = group.name;

        item.appendChild(checkbox);
        item.appendChild(label);
        groupList.appendChild(item);
    });
}

function closeChannelGroupModal() {
    document.getElementById('channel-group-modal').style.display = 'none';
    currentChannelForGroups = null;
}

async function saveChannelGroups() {
    if (!currentChannelForGroups) return;

    const { ip, channel } = currentChannelForGroups;

    // Get selected groups
    const selectedGroups = [];
    document.querySelectorAll('#channel-group-list input[type="checkbox"]:checked').forEach(checkbox => {
        const groupId = checkbox.value;
        selectedGroups.push(groupId);
    });

    try {
        // First, remove channel from all groups
        for (const [groupId, group] of Object.entries(allGroups)) {
            if (group.channels && group.channels.includes(ip)) {
                await fetch(`/api/groups/${groupId}/channels`, {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ channels: [ip] })
                });
            }
        }

        // Then add channel to selected groups
        for (const groupId of selectedGroups) {
            await fetch(`/api/groups/${groupId}/channels`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ channels: [ip] })
            });
        }

        // Reload data and refresh display
        await loadGroups();
        await loadChannels();
        closeChannelGroupModal();
    } catch (error) {
        alert('Failed to update groups: ' + error.message);
    }
}

// Language switching
function switchLanguage(lang) {
    i18n.setLanguage(lang);

    // Update language dropdown if it exists
    const languageSelect = document.getElementById('language-select');
    if (languageSelect) {
        languageSelect.value = lang;
    }
}

// Initialize language on page load
document.addEventListener('DOMContentLoaded', () => {
    const currentLang = i18n.getLanguage();
    i18n.updatePageLanguage();

    // Set initial language dropdown value
    const languageSelect = document.getElementById('language-select');
    if (languageSelect) {
        languageSelect.value = currentLang;
    }

    // Restore last active tab
    const savedTab = localStorage.getItem('currentTab');
    if (savedTab) {
        // Find and click the saved tab button
        const tabButton = document.querySelector(`[data-tab="${savedTab}"]`);
        if (tabButton) {
            tabButton.click();
        }
    }
});

// Load config and all tests on page load
loadConfig();
loadAllTests();