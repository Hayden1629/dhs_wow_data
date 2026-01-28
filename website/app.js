const express = require('express');
const path = require('path');
const fs = require('fs');
const { parse } = require('csv-parse/sync');

const app = express();
const PORT = 3000;

// View engine setup
app.set('view engine', 'pug');
app.set('views', path.join(__dirname, 'views'));

// Static files
app.use(express.static(path.join(__dirname, 'public')));
app.use('/mugshots', express.static(path.join(__dirname, '../output/mugshots')));

// Parse geocode locations from file
function parseGeocodeLocations() {
    const geocodePath = path.join(__dirname, '../geocode_locations.txt');
    const content = fs.readFileSync(geocodePath, 'utf-8');
    const locations = {};
    
    const regex = /✓\s*(.+?):\s*\((-?\d+\.?\d*),\s*(-?\d+\.?\d*)\)/g;
    let match;
    
    while ((match = regex.exec(content)) !== null) {
        const location = match[1].trim();
        const lat = parseFloat(match[2]);
        const lng = parseFloat(match[3]);
        locations[location.toLowerCase()] = { lat, lng };
    }
    
    return locations;
}

// Parse CSV data
function loadCSVData() {
    const csvPath = path.join(__dirname, '../transformed_df.csv');
    const content = fs.readFileSync(csvPath, 'utf-8');
    const records = parse(content, {
        columns: true,
        skip_empty_lines: true
    });
    return records;
}

// Process data for the map
function processData() {
    const locations = parseGeocodeLocations();
    const records = loadCSVData();
    
    // Group by location
    const locationGroups = {};
    const allCategories = new Set();
    let totalMen = 0;
    let totalWomen = 0;
    let totalWithAge = 0;
    let totalAge = 0;
    const countryCounts = {};
    const gangCounts = {};
    const categoryCounts = {};
    const raceCounts = {};
    
    records.forEach(record => {
        const arrested = record.ARRESTED || '';
        const arrestedLower = arrested.toLowerCase();
        
        // Find coordinates
        let coords = locations[arrestedLower];
        if (!coords) {
            // Try partial match
            for (const [key, value] of Object.entries(locations)) {
                if (arrestedLower.includes(key) || key.includes(arrestedLower)) {
                    coords = value;
                    break;
                }
            }
        }
        
        if (!coords) {
            coords = { lat: 39.8283, lng: -98.5795 }; // Default to US center
        }
        
        // Parse crime categories
        let categories = [];
        if (record.CRIME_CATEGORIES) {
            try {
                categories = record.CRIME_CATEGORIES.replace(/[\[\]']/g, '').split(',').map(c => c.trim()).filter(c => c);
            } catch (e) {
                categories = [];
            }
        }
        categories.forEach(cat => {
            allCategories.add(cat);
            categoryCounts[cat] = (categoryCounts[cat] || 0) + 1;
        });
        
        // Parse convictions
        let convictions = [];
        if (record.CONVICTED_OF) {
            try {
                convictions = record.CONVICTED_OF.replace(/[\[\]']/g, '').split(',').map(c => c.trim()).filter(c => c);
            } catch (e) {
                convictions = [];
            }
        }
        
        // Get local mugshot path
        let mugshotPath = '';
        if (record.PICTURE_LOCAL) {
            const filename = path.basename(record.PICTURE_LOCAL);
            mugshotPath = `/mugshots/${encodeURIComponent(filename)}`;
        }
        
        // Group by location key
        const locationKey = `${coords.lat.toFixed(4)},${coords.lng.toFixed(4)}`;
        if (!locationGroups[locationKey]) {
            locationGroups[locationKey] = {
                lat: coords.lat,
                lng: coords.lng,
                location: arrested,
                people: []
            };
        }
        
        locationGroups[locationKey].people.push({
            id: record.ID,
            name: record.NAME,
            country: record.COUNTRY,
            convictions: convictions,
            categories: categories,
            gang: record.GANG_AFFILIATION || '',
            mugshot: mugshotPath,
            age: record['DEEPFACE.age'] ? parseFloat(record['DEEPFACE.age']) : null,
            gender: record['DEEPFACE.gender.dominant'] || '',
            race: record['DEEPFACE.race.dominant'] || '',
            emotion: record['DEEPFACE.emotion.dominant'] || ''
        });
        
        // Stats
        const gender = record['DEEPFACE.gender.dominant'];
        if (gender === 'Man') totalMen++;
        else if (gender === 'Woman') totalWomen++;
        
        const age = parseFloat(record['DEEPFACE.age']);
        if (!isNaN(age)) {
            totalWithAge++;
            totalAge += age;
        }
        
        const country = record.COUNTRY;
        if (country) {
            countryCounts[country] = (countryCounts[country] || 0) + 1;
        }
        
        const gang = record.GANG_AFFILIATION;
        if (gang && gang.trim()) {
            gangCounts[gang] = (gangCounts[gang] || 0) + 1;
        }
        
        const race = record['DEEPFACE.race.dominant'];
        if (race && race.trim()) {
            raceCounts[race] = (raceCounts[race] || 0) + 1;
        }
    });
    
    // Sort categories and countries by count
    const sortedCategories = Object.entries(categoryCounts)
        .sort((a, b) => b[1] - a[1]);
    
    const sortedCountries = Object.entries(countryCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 20);
    
    const sortedGangs = Object.entries(gangCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 15);
    
    const sortedRaces = Object.entries(raceCounts)
        .sort((a, b) => b[1] - a[1]);
    
    return {
        locations: Object.values(locationGroups),
        categories: Array.from(allCategories).sort(),
        stats: {
            totalRecords: records.length,
            totalMen,
            totalWomen,
            avgAge: totalWithAge > 0 ? (totalAge / totalWithAge).toFixed(1) : 'N/A',
            topCountries: sortedCountries,
            topCategories: sortedCategories,
            topGangs: sortedGangs,
            raceDistribution: sortedRaces
        }
    };
}

// Load data once at startup
let cachedData = null;

function getData() {
    if (!cachedData) {
        cachedData = processData();
    }
    return cachedData;
}

// Routes
app.get('/', (req, res) => {
    const data = getData();
    res.render('index', {
        title: 'DHS WOW Interactive Map',
        categories: data.categories,
        stats: data.stats
    });
});

app.get('/api/locations', (req, res) => {
    const data = getData();
    const category = req.query.category;
    
    let filteredLocations = data.locations;
    
    if (category && category !== 'all') {
        filteredLocations = data.locations.map(loc => ({
            ...loc,
            people: loc.people.filter(p => p.categories.includes(category))
        })).filter(loc => loc.people.length > 0);
    }
    
    res.json(filteredLocations);
});

app.get('/api/stats', (req, res) => {
    const data = getData();
    res.json(data.stats);
});

app.listen(PORT, () => {
    console.log(`Server running at http://localhost:${PORT}`);
    console.log('Loading data...');
    getData(); // Pre-load data
    console.log('Data loaded successfully!');
});
