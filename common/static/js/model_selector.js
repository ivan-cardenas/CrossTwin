function initModelSelector(modelsByApp) {
    const appSelect = document.getElementById('app-select');
    const modelSelect = document.getElementById('model-select');

    if (!appSelect || !modelSelect) {
        console.error('Model selector elements not found');
        return;
    }

    // Populate app dropdown
    Object.keys(modelsByApp).sort().forEach(app => {
        const option = document.createElement('option');
        option.value = app;
        option.textContent = app;
        appSelect.appendChild(option);
    });

    // Update models when app changes
    appSelect.addEventListener('change', function() {
        const selectedApp = this.value;
        
        // Clear current options
        modelSelect.innerHTML = '';
        
        if (!selectedApp) {
            modelSelect.innerHTML = '<option value="">— Select App First —</option>';
            modelSelect.disabled = true;
            return;
        }
        
        // Add placeholder
        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = '— Select Model —';
        modelSelect.appendChild(placeholder);
        
        // Add models for selected app
        modelsByApp[selectedApp].forEach(model => {
            const option = document.createElement('option');
            option.value = model.value;
            option.textContent = model.label;
            modelSelect.appendChild(option);
        });
        
        modelSelect.disabled = false;
    });
}