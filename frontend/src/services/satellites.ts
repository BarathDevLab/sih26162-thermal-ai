/**
 * Satellite Constellation & Orbital Tracks Service
 * Generates realistic 3D satellite orbits and positions (NOAA-20/21 VIIRS, MODIS, HLS, LEO shells)
 */

export interface SatelliteFeature {
  type: 'Feature';
  geometry: {
    type: 'Point';
    coordinates: [number, number];
  };
  properties: {
    id: string;
    name: string;
    type: 'THERMAL_NRT' | 'EARTH_OBSERVATION' | 'WEATHER' | 'SURVEILLANCE';
    altitude_km: number;
    color: string;
    sensor?: string;
  };
}

export interface OrbitLineFeature {
  type: 'Feature';
  geometry: {
    type: 'LineString';
    coordinates: [number, number][];
  };
  properties: {
    name: string;
    type: string;
    color: string;
  };
}

function calculateOrbitCoordinates(inclinationDeg: number, ascendingNodeDeg: number, numPoints: number = 180): [number, number][] {
  const inc = (inclinationDeg * Math.PI) / 180;
  const coords: [number, number][] = [];

  for (let i = 0; i <= numPoints; i++) {
    const u = (i / numPoints) * 2 * Math.PI;
    const lat = Math.asin(Math.sin(inc) * Math.sin(u)) * (180 / Math.PI);
    let lon = (Math.atan2(Math.cos(inc) * Math.sin(u), Math.cos(u)) * (180 / Math.PI) + ascendingNodeDeg);
    // Normalize to [-180, 180]
    lon = ((lon + 180) % 360 + 360) % 360 - 180;
    coords.push([lon, lat]);
  }
  return coords;
}

// 1. Generate Primary Orbital Track Rings
export function getSatelliteOrbitRings(): { type: 'FeatureCollection'; features: OrbitLineFeature[] } {
  const orbits: OrbitLineFeature[] = [
    // NOAA-20 / JPSS-1 (Sun-synchronous polar orbit ~98.7°)
    {
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: calculateOrbitCoordinates(98.7, 45) },
      properties: { name: 'NOAA-20 (VIIRS Polar Track)', type: 'THERMAL_NRT', color: '#06b6d4' }
    },
    // NOAA-21 / JPSS-2 (Polar orbit ~98.7°)
    {
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: calculateOrbitCoordinates(98.7, 165) },
      properties: { name: 'NOAA-21 (VIIRS Polar Track)', type: 'THERMAL_NRT', color: '#38bdf8' }
    },
    // Suomi-NPP (Polar orbit ~98.7°)
    {
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: calculateOrbitCoordinates(98.7, 285) },
      properties: { name: 'Suomi-NPP (VIIRS Ground Track)', type: 'THERMAL_NRT', color: '#22c55e' }
    },
    // Sentinel-2A / 2B (HLS Complement ~98.6°)
    {
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: calculateOrbitCoordinates(98.6, 90) },
      properties: { name: 'Sentinel-2 (HLS Optical Track)', type: 'EARTH_OBSERVATION', color: '#a855f7' }
    },
    // Equatorial Tracking Ring
    {
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: calculateOrbitCoordinates(0.5, 0) },
      properties: { name: 'Geostationary Belt Orbit', type: 'WEATHER', color: '#64748b' }
    },
    // Inclined Constellation Shells (53° and 68°)
    {
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: calculateOrbitCoordinates(53, 30) },
      properties: { name: 'LEO Constellation Track A', type: 'SURVEILLANCE', color: '#0ea5e9' }
    },
    {
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: calculateOrbitCoordinates(53, 210) },
      properties: { name: 'LEO Constellation Track B', type: 'SURVEILLANCE', color: '#0ea5e9' }
    }
  ];

  return {
    type: 'FeatureCollection',
    features: orbits
  };
}

// 2. Generate Dense Satellite Constellation (LEO & Polar Shells)
export function getSatelliteConstellation(count: number = 1600): { type: 'FeatureCollection'; features: SatelliteFeature[] } {
  const satellites: SatelliteFeature[] = [];

  // Key primary missions
  const primaryMissions = [
    { name: 'NOAA-20 (JPSS-1)', sensor: 'VIIRS Thermal 375m', lat: 28.4, lon: 77.1, color: '#38bdf8' },
    { name: 'NOAA-21 (JPSS-2)', sensor: 'VIIRS Thermal 375m', lat: -15.2, lon: 82.5, color: '#38bdf8' },
    { name: 'Suomi-NPP', sensor: 'VIIRS Thermal 375m', lat: 45.1, lon: 72.3, color: '#22c55e' },
    { name: 'Aqua (EOS PM-1)', sensor: 'MODIS Thermal 1km', lat: 12.8, lon: 80.2, color: '#f59e0b' },
    { name: 'Terra (EOS AM-1)', sensor: 'MODIS Thermal 1km', lat: -32.5, lon: 68.4, color: '#f59e0b' },
    { name: 'Landsat-9', sensor: 'TIRS-2 Thermal 100m', lat: 21.0, lon: 78.5, color: '#a855f7' },
    { name: 'Sentinel-2A', sensor: 'MSI Optical 10m-20m', lat: 34.2, lon: 85.0, color: '#10b981' }
  ];

  primaryMissions.forEach((m, idx) => {
    satellites.push({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [m.lon, m.lat] },
      properties: {
        id: `SAT_PRI_${idx}`,
        name: m.name,
        type: 'THERMAL_NRT',
        altitude_km: 824,
        color: m.color,
        sensor: m.sensor
      }
    });
  });

  // Orbital shell colors: Cyan, Neon Green, Orange-Red, Purple
  const colorPool = ['#38bdf8', '#22c55e', '#ef4444', '#f97316', '#a855f7', '#06b6d4'];

  // Seed pseudo-random reproducible satellites
  let seed = 42;
  const pseudoRandom = () => {
    seed = (seed * 9301 + 49297) % 233280;
    return seed / 233280;
  };

  for (let i = 0; i < count; i++) {
    // Generate realistic orbit distribution (concentrated in LEO inclinations 53°, 68°, 98°)
    const u = pseudoRandom() * 2 * Math.PI;
    const incDegrees = pseudoRandom() > 0.4 ? 98.2 : (pseudoRandom() > 0.5 ? 53.0 : 68.5);
    const inc = (incDegrees * Math.PI) / 180;
    const node = pseudoRandom() * 360;

    const lat = Math.asin(Math.sin(inc) * Math.sin(u)) * (180 / Math.PI);
    let lon = (Math.atan2(Math.cos(inc) * Math.sin(u), Math.cos(u)) * (180 / Math.PI) + node);
    lon = ((lon + 180) % 360 + 360) % 360 - 180;

    const color = colorPool[Math.floor(pseudoRandom() * colorPool.length)];

    satellites.push({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [round(lon, 4), round(lat, 4)] },
      properties: {
        id: `SAT_LEO_${i}`,
        name: `LEO-SAT-${(1000 + i).toString(16).toUpperCase()}`,
        type: pseudoRandom() > 0.7 ? 'THERMAL_NRT' : 'SURVEILLANCE',
        altitude_km: Math.round(550 + pseudoRandom() * 400),
        color
      }
    });
  }

  return {
    type: 'FeatureCollection',
    features: satellites
  };
}

function round(val: number, decimals: number): number {
  const factor = Math.pow(10, decimals);
  return Math.round(val * factor) / factor;
}

// 3. Generate VIIRS 3,000 km Scanning Swath Footprints
export function getSensorSwathPolygons(): { type: 'FeatureCollection'; features: any[] } {
  // NOAA-20 active scanning swath (~3000 km cross-track width centered on ascending pass over India/Asia)
  const swathWidthDeg = 14.5; // ~1500 km half-width in degrees
  const centerNode = 78.0; // Centered near India sub-satellite track

  const leftEdge: [number, number][] = [];
  const rightEdge: [number, number][] = [];

  for (let lat = -50; lat <= 70; lat += 5) {
    const lonCenter = centerNode - (lat * 0.15); // Sun-synchronous inclination drift
    leftEdge.push([lonCenter - swathWidthDeg, lat]);
    rightEdge.push([lonCenter + swathWidthDeg, lat]);
  }

  const polygonCoords = [...leftEdge, ...rightEdge.reverse(), leftEdge[0]];

  return {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        geometry: {
          type: 'Polygon',
          coordinates: [polygonCoords]
        },
        properties: {
          id: 'SWATH_NOAA20',
          name: 'VIIRS NOAA-20 NRT 3,000km Orbit Swath',
          sensor: 'VIIRS (375m MWIR/LWIR)',
          fillColor: 'rgba(6, 182, 212, 0.08)',
          strokeColor: 'rgba(6, 182, 212, 0.35)'
        }
      }
    ]
  };
}

