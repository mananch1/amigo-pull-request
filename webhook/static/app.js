document.addEventListener('DOMContentLoaded', async () => {
    const loader = document.getElementById('loader');
    const container = document.getElementById('reviews-container');

    try {
        const response = await fetch('/api/reviews');
        const data = await response.json();
        
        loader.classList.add('hidden');
        container.classList.remove('hidden');

        if (data.reviews.length === 0) {
            container.innerHTML = `<p style="text-align:center; grid-column: 1 / -1; color: var(--text-muted);">No reviews detected. Trigger your webhook to start analyzing!</p>`;
            return;
        }

        data.reviews.forEach(review => {
            const card = createReviewCard(review);
            container.appendChild(card);
        });

    } catch (err) {
        console.error("Failed to load reviews:", err);
        loader.innerHTML = `<p style="color: #f85149;">Error connecting to Review API. Is the server running?</p>`;
    }
});

function createReviewCard(review) {
    const card = document.createElement('div');
    card.className = 'review-card';

    const prNumber = review.pr_number ? `PR #${review.pr_number}` : 'Analyzed Commit';
    
    let issuesHtml = '';
    const hasIssues = review.issues && review.issues.length > 0;
    
    if (hasIssues) {
        issuesHtml = `
            <div class="issues-section">
                <h4>Identified Issues</h4>
                ${review.issues.map((iss, idx) => `
                    <div class="issue-item">
                        <input type="checkbox" id="chk-${review.id}-${idx}" value="${iss}">
                        <label for="chk-${review.id}-${idx}">${iss}</label>
                    </div>
                `).join('')}
            </div>
        `;
    } else {
        issuesHtml = `
            <div class="issues-section">
                <p style="color: var(--success); font-weight: 500;">✓ No critical issues detected.</p>
            </div>
        `;
    }

    const compiledSummary = marked.parse(review.summary || '*No summary provided.*');

    card.innerHTML = `
        <div class="pr-id">${prNumber}</div>
        <div class="file-name">${review.file}</div>
        <div class="summary-markdown">${compiledSummary}</div>
        
        ${issuesHtml}
        
        <div class="fix-actions">
            <button class="btn primary-btn" ${!hasIssues ? 'disabled' : ''} 
                    onclick="triggerAgenticFix('${review.repo_url}', '${review.pr_number}', '${review.id}')">
                Autofix Selected Issues
            </button>
        </div>
    `;

    return card;
}

async function triggerAgenticFix(repo, prNumber, reviewId) {
    // Gather selected checkboxes for this specific review card
    const checkboxes = document.querySelectorAll(`input[id^="chk-${reviewId}-"]:checked`);
    const selectedIssues = Array.from(checkboxes).map(chk => chk.value);

    if (selectedIssues.length === 0) {
        alert("Please select at least one issue to fix!");
        return;
    }

    // Show modal loading state
    const modal = document.getElementById('fix-modal');
    const statusText = document.getElementById('fix-status-text');
    const resultDiv = document.getElementById('fix-result');
    const patchPreview = document.getElementById('fix-patch-preview');
    const scanBar = document.querySelector('.scanning-bar');
    
    modal.classList.remove('hidden');
    resultDiv.classList.add('hidden');
    scanBar.style.display = 'block';
    statusText.innerText = "Initializing Groq Worker & Gemini Orchestrator...";

    try {
        const res = await fetch('/api/fix', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                repo_url: repo,
                pr_number: prNumber,
                issues: selectedIssues
            })
        });

        const resultData = await res.json();
        
        if (resultData.status === 'success') {
            scanBar.style.display = 'none';
            statusText.innerText = "";
            resultDiv.classList.remove('hidden');
            patchPreview.textContent = resultData.patch || "No patch generated.";
        } else {
            throw new Error(resultData.message || "Unknown error");
        }
        
    } catch (err) {
        console.error(err);
        statusText.innerText = "❌ Agent failed to generate patch: " + err.message;
        scanBar.style.display = 'none';
        
        setTimeout(() => closeModal(), 3000);
    }
}

function closeModal() {
    document.getElementById('fix-modal').classList.add('hidden');
}
