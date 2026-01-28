// Initialize map
const map = L.map('map').setView([39.8283, -98.5795], 4);

// Add tile layer
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);

// Marker cluster group
let markers = L.markerClusterGroup({
    maxClusterRadius: 50,
    spiderfyOnMaxZoom: true,
    showCoverageOnHover: false,
    zoomToBoundsOnClick: true
});

map.addLayer(markers);

// Store all location data
let allLocations = [];
let currentFilter = 'all';

// Custom marker icon
function createCustomIcon(count) {
    const size = Math.min(40, 20 + Math.log(count + 1) * 8);
    return L.divIcon({
        className: 'custom-marker',
        html: `<div style="
            background: linear-gradient(135deg, #1a365d, #2c5282);
            color: white;
            width: ${size}px;
            height: ${size}px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: ${Math.max(10, size / 3)}px;
            border: 3px solid white;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        ">${count}</div>`,
        iconSize: [size, size],
        iconAnchor: [size / 2, size / 2]
    });
}

// Load locations from API
async function loadLocations(category = 'all') {
    try {
        const url = category === 'all' 
            ? '/api/locations' 
            : `/api/locations?category=${encodeURIComponent(category)}`;
        
        const response = await fetch(url);
        allLocations = await response.json();
        
        updateMap();
        updateResultCount();
    } catch (error) {
        console.error('Error loading locations:', error);
    }
}

// Update map markers
function updateMap() {
    markers.clearLayers();
    
    allLocations.forEach(location => {
        const marker = L.marker([location.lat, location.lng], {
            icon: createCustomIcon(location.people.length)
        });
        
        // Popup content
        const popupContent = `
            <div class="popup-content">
                <h4>${escapeHtml(location.location)}</h4>
                <p class="popup-count">${location.people.length} individual${location.people.length !== 1 ? 's' : ''}</p>
            </div>
        `;
        
        marker.bindPopup(popupContent);
        
        // Click handler to show details
        marker.on('click', () => {
            showLocationDetails(location);
        });
        
        markers.addLayer(marker);
    });
}

// Update result count
function updateResultCount() {
    const totalPeople = allLocations.reduce((sum, loc) => sum + loc.people.length, 0);
    const countEl = document.getElementById('result-count');
    countEl.textContent = `${totalPeople.toLocaleString()} individuals across ${allLocations.length.toLocaleString()} locations`;
}

// Show location details in sidebar
function showLocationDetails(location) {
    const detailsEl = document.getElementById('location-details');
    const personListEl = document.getElementById('person-list');
    
    detailsEl.innerHTML = `
        <div class="location-header">
            <h3>${escapeHtml(location.location)}</h3>
            <p class="count">${location.people.length} individual${location.people.length !== 1 ? 's' : ''}</p>
        </div>
    `;
    
    personListEl.innerHTML = location.people.map(person => `
        <div class="person-card" onclick="showPersonModal(${JSON.stringify(person).replace(/"/g, '&quot;')})">
            <div class="person-card-header">
                <img src="${person.mugshot || '/images/placeholder.png'}" 
                     alt="${escapeHtml(person.name)}" 
                     class="person-thumbnail"
                     onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><rect fill=%22%23e2e8f0%22 width=%22100%22 height=%22100%22/><text x=%2250%22 y=%2255%22 text-anchor=%22middle%22 fill=%22%23718096%22 font-size=%2240%22>?</text></svg>'">
                <div class="person-info">
                    <div class="person-name">${escapeHtml(person.name)}</div>
                    <div class="person-country">${escapeHtml(person.country)}</div>
                </div>
            </div>
            <div class="person-crimes">
                ${person.categories.slice(0, 3).map(cat => `<span class="crime-tag">${escapeHtml(cat)}</span>`).join('')}
                ${person.categories.length > 3 ? `<span class="crime-tag">+${person.categories.length - 3} more</span>` : ''}
            </div>
        </div>
    `).join('');
}

// Show person modal
function showPersonModal(person) {
    const modal = document.getElementById('person-modal');
    const modalBody = document.getElementById('modal-body');
    
    modalBody.innerHTML = `
        <div class="modal-header">
            <img src="${person.mugshot || '/images/placeholder.png'}" 
                 alt="${escapeHtml(person.name)}" 
                 class="modal-mugshot"
                 onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 120%22><rect fill=%22%23e2e8f0%22 width=%22100%22 height=%22120%22/><text x=%2250%22 y=%2265%22 text-anchor=%22middle%22 fill=%22%23718096%22 font-size=%2240%22>?</text></svg>'">
            <div class="modal-info">
                <h2>${escapeHtml(person.name)}</h2>
                <div class="modal-meta">
                    <p><strong>Country:</strong> ${escapeHtml(person.country)}</p>
                    ${person.age ? `<p><strong>Age (estimated):</strong> ${person.age}</p>` : ''}
                    ${person.gender ? `<p><strong>Gender:</strong> ${person.gender}</p>` : ''}
                    ${person.race ? `<p><strong>Race (AI detected):</strong> ${escapeHtml(person.race)}</p>` : ''}
                </div>
                ${person.gang ? `<span class="gang-badge">Gang: ${escapeHtml(person.gang)}</span>` : ''}
            </div>
        </div>
        
        <div class="modal-section">
            <h3>Convicted Of</h3>
            <ul class="convictions-list">
                ${person.convictions.map(conv => `<li>${escapeHtml(conv)}</li>`).join('')}
            </ul>
        </div>
        
        <div class="modal-section">
            <h3>Crime Categories</h3>
            <div class="categories-container">
                ${person.categories.map(cat => `<span class="category-badge">${escapeHtml(cat)}</span>`).join('')}
            </div>
        </div>
    `;
    
    modal.classList.add('active');
}

// Close modal
function closeModal() {
    document.getElementById('person-modal').classList.remove('active');
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Event listeners
document.addEventListener('DOMContentLoaded', () => {
    // Load initial data
    loadLocations();
    
    // Category filter
    document.getElementById('category-filter').addEventListener('change', (e) => {
        currentFilter = e.target.value;
        loadLocations(currentFilter);
    });
    
    // Modal close
    document.querySelector('.close-modal').addEventListener('click', closeModal);
    document.getElementById('person-modal').addEventListener('click', (e) => {
        if (e.target.id === 'person-modal') {
            closeModal();
        }
    });
    
    // Escape key to close modal
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeModal();
        }
    });
});

// Make showPersonModal globally accessible
window.showPersonModal = showPersonModal;
