// ============================================================
// city-name.js — Reverse geocode city name from map center
// Depends on: config.js (map, cityNameTimeout)
// ============================================================

async function updateCityName() {
  const center = map.getCenter();

  try {
    const response = await fetch(
      `https://nominatim.openstreetmap.org/reverse?` +
      `lat=${center.lat}&lon=${center.lng}&format=json&accept-language=en`,
      { headers: { 'User-Agent': 'UTwente-DigitalTwin/1.0 (i.l.cardenasleon@utwente.nl)' } }
    );
    const data = await response.json();

    const cityName =
      data.address.city ||
      data.address.town ||
      data.address.village ||
      data.address.municipality ||
      data.address.county ||
      'Unknown Location';

    document.querySelector('.city-name').textContent = cityName;
    console.log('City name:', cityName);
  } catch (error) {
    console.error('Error fetching city name:', error);
    document.querySelector('.city-name').textContent = 'Unknown Location';
  }
}