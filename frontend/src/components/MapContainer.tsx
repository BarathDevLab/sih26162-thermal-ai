import React, { useEffect, useMemo, useRef, useState } from 'react';
import maplibregl, { Map as MapLibreMap, Popup } from 'maplibre-gl';
import { MapboxOverlay } from '@deck.gl/mapbox';
import { ColumnLayer } from '@deck.gl/layers';
import type { SiteGeoJSONFeatureCollection, FilterState, SiteGeoJSONFeature } from '../types/api';
import { getSatelliteOrbitRings, getSatelliteConstellation, getSensorSwathPolygons } from '../services/satellites';
import { Sparkles, Plus, Minus, Compass } from 'lucide-react';

interface MapContainerProps {
  sitesData: SiteGeoJSONFeatureCollection | null;
  selectedSiteId: string | null;
  onSelectSite: (siteId: string) => void;
  onBoundsChange: (bbox: [number, number, number, number]) => void;
  filters: FilterState;
  is3D: boolean;
  focusedCoordinates?: [number, number] | null;
  isLoading: boolean;
  basemapMode?: 'SATELLITE' | 'DARK';
  show3DColumns?: boolean;
  showSatellites?: boolean;
  showSwaths?: boolean;
  showHeatBloom?: boolean;
  onMapReady?: () => void;
  onSitesRendered?: () => void;
}

function isSiteVisible(feature: SiteGeoJSONFeature, filters: FilterState): boolean {
  const properties = feature.properties;
  if (filters.aClasses.length > 0 && !filters.aClasses.includes(properties.a_class)) return false;
  if (filters.bStates.length > 0 && !filters.bStates.includes(properties.b_state)) return false;
  if (filters.cStatuses.length > 0 && !filters.cStatuses.includes(properties.c_status)) return false;
  return true;
}

const MAX_3D_COLUMNS = 2500;
const MAP_MAX_ZOOM = 20;

// Esri exposes higher tile levels, but detailed imagery coverage is not
// uniform. Requesting those native levels can return tiles whose image is the
// provider's "Map data unavailable" notice. Stop native requests at level 18
// and let MapLibre overzoom that last reliable tile for closer inspection.
const BASEMAP_NATIVE_MAX_ZOOM = 18;
const BASEMAP_LAYER_MAX_ZOOM = MAP_MAX_ZOOM + 1;

// 1. Photorealistic Earth Satellite Globe Style (ESRI World Imagery)
const SATELLITE_GLOBE_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  projection: {
    type: 'globe'
  },
  sources: {
    'esri-imagery': {
      type: 'raster',
      tiles: [
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
      ],
      tileSize: 256,
      maxzoom: BASEMAP_NATIVE_MAX_ZOOM,
      attribution: '&copy; Esri, Maxar, Earthstar Geographics'
    },
    'esri-boundaries': {
      type: 'raster',
      tiles: [
        'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}'
      ],
      tileSize: 256,
      maxzoom: BASEMAP_NATIVE_MAX_ZOOM
    }
  },
  layers: [
    {
      id: 'esri-imagery-layer',
      type: 'raster',
      source: 'esri-imagery',
      minzoom: 0,
      maxzoom: BASEMAP_LAYER_MAX_ZOOM
    },
    {
      id: 'esri-boundaries-layer',
      type: 'raster',
      source: 'esri-boundaries',
      minzoom: 0,
      maxzoom: BASEMAP_LAYER_MAX_ZOOM,
      paint: {
        'raster-opacity': 0.65
      }
    }
  ]
};

// 2. High-Contrast Dark Tactical Style
const DARK_TACTICAL_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  projection: {
    type: 'mercator'
  },
  sources: {
    'esri-dark': {
      type: 'raster',
      tiles: [
        'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}'
      ],
      tileSize: 256,
      maxzoom: BASEMAP_NATIVE_MAX_ZOOM,
      attribution: '&copy; Esri &copy; OpenStreetMap'
    },
    'esri-labels': {
      type: 'raster',
      tiles: [
        'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}'
      ],
      tileSize: 256,
      maxzoom: BASEMAP_NATIVE_MAX_ZOOM
    }
  },
  layers: [
    {
      id: 'esri-dark-base',
      type: 'raster',
      source: 'esri-dark',
      minzoom: 0,
      maxzoom: BASEMAP_LAYER_MAX_ZOOM
    },
    {
      id: 'esri-labels-layer',
      type: 'raster',
      source: 'esri-labels',
      minzoom: 0,
      maxzoom: BASEMAP_LAYER_MAX_ZOOM
    }
  ]
};

// Dynamic basemap style builder respecting projection
const getBasemapStyle = (mode: 'SATELLITE' | 'DARK', is3DMode: boolean): maplibregl.StyleSpecification => {
  const base = mode === 'SATELLITE' ? SATELLITE_GLOBE_STYLE : DARK_TACTICAL_STYLE;
  return {
    ...base,
    projection: {
      type: is3DMode ? 'globe' : 'mercator'
    }
  };
};

// Procedurally generates authentic tactical spacecraft & satellite icon pixel data for MapLibre
function createSatelliteCraftIcon(isPrimary: boolean): ImageData {
  const size = isPrimary ? 36 : 22;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    return new ImageData(size, size);
  }
  const cx = size / 2;
  const cy = size / 2;

  ctx.clearRect(0, 0, size, size);

  if (isPrimary) {
    // 1. Outer cyan telemetry beacon glow ring
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.5)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(cx, cy, 15, 0, Math.PI * 2);
    ctx.stroke();

    // 2. Solar Arrays Left Wing [-14 to -5]
    ctx.fillStyle = '#0284c7';
    ctx.strokeStyle = '#38bdf8';
    ctx.lineWidth = 1;
    ctx.fillRect(cx - 14, cy - 4, 9, 8);
    ctx.strokeRect(cx - 14, cy - 4, 9, 8);

    // Solar Cell Divider Left
    ctx.beginPath();
    ctx.moveTo(cx - 9.5, cy - 4);
    ctx.lineTo(cx - 9.5, cy + 4);
    ctx.stroke();

    // 3. Solar Arrays Right Wing [+5 to +14]
    ctx.fillRect(cx + 5, cy - 4, 9, 8);
    ctx.strokeRect(cx + 5, cy - 4, 9, 8);

    // Solar Cell Divider Right
    ctx.beginPath();
    ctx.moveTo(cx + 9.5, cy - 4);
    ctx.lineTo(cx + 9.5, cy + 4);
    ctx.stroke();

    // 4. Center Satellite Chassis Bus (Titanium Spacecraft Body)
    ctx.fillStyle = '#070e1e';
    ctx.fillRect(cx - 4, cy - 5, 8, 10);
    ctx.strokeStyle = '#e0f2fe';
    ctx.lineWidth = 1.3;
    ctx.strokeRect(cx - 4, cy - 5, 8, 10);

    // 5. Optical Thermal Sensor Aperture (Glowing Cyan Lens)
    ctx.fillStyle = '#00f0ff';
    ctx.beginPath();
    ctx.arc(cx, cy, 2.2, 0, Math.PI * 2);
    ctx.fill();

    // 6. Sensor Mast / Downlink Antenna
    ctx.strokeStyle = '#38bdf8';
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(cx, cy + 5);
    ctx.lineTo(cx, cy + 8.5);
    ctx.stroke();
  } else {
    // Sleek Tactical Delta Spacecraft Chevron (LEO Constellation Node)
    ctx.fillStyle = 'rgba(14, 165, 233, 0.9)';
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.2;

    // Tactical Delta chevron pointing upward
    ctx.beginPath();
    ctx.moveTo(cx, cy - 7);       // Apex nose
    ctx.lineTo(cx + 6, cy + 4);   // Right wing tip
    ctx.lineTo(cx, cy + 1.5);     // Engine notch
    ctx.lineTo(cx - 6, cy + 4);   // Left wing tip
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // Glowing telemetry pinpoint core
    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.arc(cx, cy - 1.2, 1.5, 0, Math.PI * 2);
    ctx.fill();
  }

  return ctx.getImageData(0, 0, size, size);
}

export const MapContainer: React.FC<MapContainerProps> = ({
  sitesData,
  selectedSiteId,
  onSelectSite,
  onBoundsChange,
  filters,
  is3D,
  focusedCoordinates,
  isLoading,
  basemapMode = 'SATELLITE',
  show3DColumns = true,
  showSatellites = true,
  showSwaths = true,
  showHeatBloom = true,
  onMapReady,
  onSitesRendered
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const deckOverlayRef = useRef<MapboxOverlay | null>(null);
  const popupRef = useRef<Popup | null>(null);

  const [viewZoom, setViewZoom] = useState<number>(is3D ? 2.5 : 4.8);
  const [styleRevision, setStyleRevision] = useState(0);

  const onSelectSiteRef = useRef(onSelectSite);
  const onBoundsChangeRef = useRef(onBoundsChange);
  const onMapReadyRef = useRef(onMapReady);
  const onSitesRenderedRef = useRef(onSitesRendered);
  const selectedSiteIdRef = useRef(selectedSiteId);

  useEffect(() => {
    onSelectSiteRef.current = onSelectSite;
  }, [onSelectSite]);

  useEffect(() => {
    onBoundsChangeRef.current = onBoundsChange;
  }, [onBoundsChange]);

  useEffect(() => {
    onMapReadyRef.current = onMapReady;
  }, [onMapReady]);

  useEffect(() => {
    onSitesRenderedRef.current = onSitesRendered;
  }, [onSitesRendered]);

  useEffect(() => {
    selectedSiteIdRef.current = selectedSiteId;
  }, [selectedSiteId]);

  const filteredFeatures = useMemo<SiteGeoJSONFeature[]>(
    () => (sitesData?.features ?? []).filter(feature => isSiteVisible(feature, filters)),
    [sitesData, filters]
  );

  const lastFlownCoordsRef = useRef<[number, number] | null>(null);

  // Add source data and layers helper
  const setupLayers = (map: MapLibreMap) => {
    // 0. VIIRS Scanning Swath Footprints Source & Layer
    if (!map.getSource('satellite-swaths')) {
      map.addSource('satellite-swaths', {
        type: 'geojson',
        data: getSensorSwathPolygons() as any
      });
    }
    if (!map.getLayer('satellite-swaths-fill')) {
      map.addLayer({
        id: 'satellite-swaths-fill',
        type: 'fill',
        source: 'satellite-swaths',
        paint: {
          'fill-color': ['get', 'fillColor'],
          'fill-opacity': 0.65
        }
      });
    }
    if (!map.getLayer('satellite-swaths-line')) {
      map.addLayer({
        id: 'satellite-swaths-line',
        type: 'line',
        source: 'satellite-swaths',
        paint: {
          'line-color': ['get', 'strokeColor'],
          'line-width': 1.5,
          'line-dasharray': [4, 3],
          'line-opacity': 0.75
        }
      });
    }

    // 1. Add Satellite Orbits Source & Layer
    if (!map.getSource('satellite-orbits')) {
      map.addSource('satellite-orbits', {
        type: 'geojson',
        data: getSatelliteOrbitRings() as any
      });
    }
    if (!map.getLayer('satellite-orbit-lines')) {
      map.addLayer({
        id: 'satellite-orbit-lines',
        type: 'line',
        source: 'satellite-orbits',
        paint: {
          'line-color': ['get', 'color'],
          'line-width': 1.4,
          'line-dasharray': [3, 2],
          'line-opacity': 0.8
        }
      });
    }

    // Register custom spacecraft & satellite icons if not present
    if (!map.hasImage('satellite-primary-icon')) {
      map.addImage('satellite-primary-icon', createSatelliteCraftIcon(true));
    }
    if (!map.hasImage('satellite-leo-icon')) {
      map.addImage('satellite-leo-icon', createSatelliteCraftIcon(false));
    }

    // 2. Add Satellites Constellation Points Source & Layers
    if (!map.getSource('satellites-source')) {
      map.addSource('satellites-source', {
        type: 'geojson',
        data: getSatelliteConstellation(260) as any
      });
    }

    // 2a. Background LEO Constellation Nodes (Tactical Spacecraft Delta Chevrons)
    if (!map.getLayer('satellites-layer')) {
      map.addLayer({
        id: 'satellites-layer',
        type: 'symbol',
        source: 'satellites-source',
        filter: ['!=', ['get', 'is_primary'], true],
        layout: {
          'icon-image': 'satellite-leo-icon',
          'icon-size': [
            'interpolate',
            ['linear'],
            ['zoom'],
            1, 0.75,
            4, 0.9,
            8, 1.1
          ],
          'icon-allow-overlap': true,
          'icon-ignore-placement': true
        }
      });
    }

    // 2b. Primary Thermal Satellite Radar Halo Ring
    if (!map.getLayer('satellites-primary-halo')) {
      map.addLayer({
        id: 'satellites-primary-halo',
        type: 'circle',
        source: 'satellites-source',
        filter: ['==', ['get', 'is_primary'], true],
        paint: {
          'circle-color': 'transparent',
          'circle-radius': 16,
          'circle-stroke-width': 1.2,
          'circle-stroke-color': '#00f0ff',
          'circle-stroke-opacity': 0.65
        }
      });
    }

    // 2c. Primary Thermal Satellite Core Spacecraft (Solar Arrays + Titanium Bus)
    if (!map.getLayer('satellites-primary-core')) {
      map.addLayer({
        id: 'satellites-primary-core',
        type: 'symbol',
        source: 'satellites-source',
        filter: ['==', ['get', 'is_primary'], true],
        layout: {
          'icon-image': 'satellite-primary-icon',
          'icon-size': [
            'interpolate',
            ['linear'],
            ['zoom'],
            1, 0.85,
            4, 1.0,
            8, 1.25
          ],
          'icon-allow-overlap': true,
          'icon-ignore-placement': true
        }
      });
    }

    // 2d. Primary Thermal Satellite Tactical Label (e.g. "NOAA-20 (VIIRS)")
    if (!map.getLayer('satellites-primary-label')) {
      map.addLayer({
        id: 'satellites-primary-label',
        type: 'symbol',
        source: 'satellites-source',
        filter: ['==', ['get', 'is_primary'], true],
        layout: {
          'text-field': '{name}',
          'text-size': 9.5,
          'text-offset': [0, 2.0],
          'text-anchor': 'top',
          'text-allow-overlap': true
        },
        paint: {
          'text-color': '#89E5FC',
          'text-halo-color': '#070e1e',
          'text-halo-width': 2.0
        }
      });
    }

    // 3. Add Ground Thermal Sites GeoJSON Source
    if (!map.getSource('sites-geojson')) {
      map.addSource('sites-geojson', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
        cluster: true,
        clusterMaxZoom: 9,
        clusterRadius: 48
      });
    }

    // 3a. Radiative FRP Heat Bloom Corona (Underneath Sites)
    if (!map.getLayer('thermal-heat-bloom')) {
      map.addLayer({
        id: 'thermal-heat-bloom',
        type: 'circle',
        source: 'sites-geojson',
        paint: {
          'circle-color': [
            'case',
            ['has', 'point_count'],
            [
              'step',
              ['get', 'point_count'],
              'rgba(14, 165, 233, 0.35)', // Cyan low cluster
              25,
              'rgba(245, 158, 11, 0.45)', // Amber mid cluster
              100,
              'rgba(239, 68, 68, 0.55)'   // Red high cluster
            ],
            [
              'match',
              ['get', 'c_status'],
              'CRITICAL', 'rgba(239, 68, 68, 0.75)',
              'ANOMALOUS', 'rgba(249, 115, 22, 0.65)',
              'ELEVATED', 'rgba(234, 179, 8, 0.55)',
              [
                'match',
                ['get', 'a_class'],
                'INDUSTRIAL', 'rgba(245, 158, 11, 0.55)',
                'NONINDUSTRIAL', 'rgba(16, 185, 129, 0.40)',
                'rgba(129, 140, 248, 0.40)'
              ]
            ]
          ],
          'circle-blur': 0.85,
          'circle-radius': [
            'case',
            ['has', 'point_count'],
            [
              'step',
              ['get', 'point_count'],
              24,
              25,
              34,
              100,
              48
            ],
            [
              'case',
              ['==', ['get', 'site_id'], selectedSiteId || ''], 30,
              ['==', ['get', 'c_status'], 'CRITICAL'], 24,
              ['==', ['get', 'c_status'], 'ANOMALOUS'], 18,
              14
            ]
          ],
          'circle-opacity': [
            'interpolate',
            ['linear'],
            ['zoom'],
            2, 0.5,
            6, 0.75,
            12, 0.45
          ]
        }
      });
    }

    // 3b. Tactical Cluster Radar Halo Ring
    if (!map.getLayer('cluster-radar-halo')) {
      map.addLayer({
        id: 'cluster-radar-halo',
        type: 'circle',
        source: 'sites-geojson',
        filter: ['has', 'point_count'],
        paint: {
          'circle-color': 'transparent',
          'circle-radius': [
            'step',
            ['get', 'point_count'],
            21,
            25,
            28,
            100,
            37
          ],
          'circle-stroke-width': 1.0,
          'circle-stroke-color': [
            'step',
            ['get', 'point_count'],
            '#38bdf8',
            25,
            '#f59e0b',
            100,
            '#ef4444'
          ],
          'circle-stroke-opacity': 0.50
        }
      });
    }

    // 3c. Main Cluster Circle Layer (Cyber-Glass Radar Target Dial with Neon Rim)
    if (!map.getLayer('clusters')) {
      map.addLayer({
        id: 'clusters',
        type: 'circle',
        source: 'sites-geojson',
        filter: ['has', 'point_count'],
        paint: {
          'circle-color': [
            'step',
            ['get', 'point_count'],
            'rgba(3, 105, 161, 0.50)', // Translucent deep cyber sky
            25,
            'rgba(217, 119, 6, 0.60)',  // Translucent solar amber
            100,
            'rgba(225, 29, 72, 0.70)'   // Translucent thermal crimson
          ],
          'circle-radius': [
            'step',
            ['get', 'point_count'],
            15,
            25,
            20,
            100,
            27
          ],
          'circle-stroke-width': 2.0,
          'circle-stroke-color': [
            'step',
            ['get', 'point_count'],
            '#38bdf8', // Neon electric cyan
            25,
            '#fbbf24', // Radiant solar amber
            100,
            '#f87171'  // Radiant rose-crimson
          ],
          'circle-stroke-opacity': 0.95
        }
      });
    }

    // 3d. Cluster Count Text (Monospace Bold with Dark Tactical Halo)
    if (!map.getLayer('cluster-count')) {
      map.addLayer({
        id: 'cluster-count',
        type: 'symbol',
        source: 'sites-geojson',
        filter: ['has', 'point_count'],
        layout: {
          'text-field': '{point_count_abbreviated}',
          'text-size': 11
        },
        paint: {
          'text-color': '#ffffff',
          'text-halo-color': 'rgba(7, 14, 30, 0.9)',
          'text-halo-width': 1.8
        }
      });
    }

    // 3e. Tactical Cluster Code Badge (Only at Detailed Zoom)
    if (!map.getLayer('cluster-tag-labels')) {
      map.addLayer({
        id: 'cluster-tag-labels',
        type: 'symbol',
        source: 'sites-geojson',
        filter: ['has', 'point_count'],
        minzoom: 8.0,
        layout: {
          'text-field': ['concat', 'TS-', ['to-string', ['slice', ['to-string', ['get', 'point_count']], 0, 2]]],
          'text-size': 9.5,
          'text-offset': [0, 2.3]
        },
        paint: {
          'text-color': '#38bdf8',
          'text-halo-color': '#02040a',
          'text-halo-width': 2.5
        }
      });
    }

    // 3f. Tactical Target Reticle for Selected / Critical Sites
    if (!map.getLayer('unclustered-reticle')) {
      map.addLayer({
        id: 'unclustered-reticle',
        type: 'circle',
        source: 'sites-geojson',
        filter: [
          'all',
          ['!', ['has', 'point_count']],
          [
            'any',
            ['==', ['get', 'site_id'], selectedSiteId || ''],
            ['==', ['get', 'c_status'], 'CRITICAL'],
            ['==', ['get', 'c_status'], 'ANOMALOUS']
          ]
        ],
        paint: {
          'circle-color': 'transparent',
          'circle-radius': [
            'case',
            ['==', ['get', 'site_id'], selectedSiteId || ''], 16,
            13
          ],
          'circle-stroke-width': 1.8,
          'circle-stroke-color': [
            'case',
            ['==', ['get', 'c_status'], 'CRITICAL'], '#ef4444',
            ['==', ['get', 'c_status'], 'ANOMALOUS'], '#f97316',
            '#38bdf8'
          ],
          'circle-stroke-opacity': 0.9
        }
      });
    }

    // 3g. Unclustered Site Points (Glowing Semantic Thermal Core)
    if (!map.getLayer('unclustered-point')) {
      map.addLayer({
        id: 'unclustered-point',
        type: 'circle',
        source: 'sites-geojson',
        filter: ['!', ['has', 'point_count']],
        paint: {
          'circle-color': [
            'match',
            ['get', 'a_class'],
            'INDUSTRIAL', '#f59e0b',
            'NONINDUSTRIAL', '#10b981',
            'UNKNOWN', '#818cf8',
            '#64748b'
          ],
          'circle-radius': [
            'case',
            ['==', ['get', 'site_id'], selectedSiteId || ''], 8.5,
            5.5
          ],
          'circle-stroke-width': 1.4,
          'circle-stroke-color': 'rgba(255, 255, 255, 0.85)',
          'circle-opacity': 0.95
        }
      });
    }

    // 3h. Incandescent Hot Planck Core (Center Light Pinpoint)
    if (!map.getLayer('unclustered-hot-center')) {
      map.addLayer({
        id: 'unclustered-hot-center',
        type: 'circle',
        source: 'sites-geojson',
        filter: ['!', ['has', 'point_count']],
        paint: {
          'circle-color': [
            'case',
            ['==', ['get', 'c_status'], 'CRITICAL'], '#ffffff',
            ['==', ['get', 'a_class'], 'INDUSTRIAL'], '#fffbeb',
            '#ffffff'
          ],
          'circle-radius': [
            'case',
            ['==', ['get', 'site_id'], selectedSiteId || ''], 3.2,
            2.0
          ],
          'circle-opacity': 0.95
        }
      });
    }

    // 3i. Tactical Site Callout Badges
    if (!map.getLayer('tactical-site-callouts')) {
      map.addLayer({
        id: 'tactical-site-callouts',
        type: 'symbol',
        source: 'sites-geojson',
        filter: ['!', ['has', 'point_count']],
        minzoom: 6.5,
        layout: {
          'text-field': [
            'case',
            ['==', ['get', 'a_class'], 'INDUSTRIAL'],
            ['concat', 'IND-', ['slice', ['get', 'site_id'], 11, 15]],
            ['==', ['get', 'c_status'], 'CRITICAL'],
            ['concat', 'CRIT-', ['slice', ['get', 'site_id'], 11, 15]],
            ['slice', ['get', 'site_id'], 11, 15]
          ],
          'text-size': 9,
          'text-offset': [0, 1.8],
          'text-anchor': 'top',
          'text-allow-overlap': false
        },
        paint: {
          'text-color': [
            'match',
            ['get', 'a_class'],
            'INDUSTRIAL', '#fbbf24',
            'NONINDUSTRIAL', '#34d399',
            '#a5b4fc'
          ],
          'text-halo-color': '#050811',
          'text-halo-width': 2.5
        }
      });
    }
  };

  const setupLayersRef = useRef(setupLayers);
  const initialIs3DRef = useRef(is3D);
  const initialBasemapRef = useRef(basemapMode);
  const is3DRef = useRef(is3D);
  useEffect(() => {
    is3DRef.current = is3D;
  }, [is3D]);

  // 1. Initialize MapLibre in 3D Globe Projection with Atmospheric Glow
  useEffect(() => {
    if (!mapContainerRef.current) return;
    let isCleanedUp = false;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: getBasemapStyle(initialBasemapRef.current, initialIs3DRef.current),
      center: [78.9629, 20.5937],
      zoom: initialIs3DRef.current ? 2.5 : 4.8,
      pitch: initialIs3DRef.current ? 45 : 0,
      bearing: initialIs3DRef.current ? -12 : 0,
      maxPitch: 85,
      maxZoom: 19,
      attributionControl: false,
      renderWorldCopies: initialIs3DRef.current ? true : false
    });

    // Remove any lingering default MapLibre control DOM nodes
    mapContainerRef.current.querySelectorAll('.maplibregl-ctrl-top-left, .maplibregl-ctrl-bottom-right, .maplibregl-ctrl-group, .maplibregl-ctrl-attrib').forEach(el => el.remove());

    mapRef.current = map;

    map.on('load', () => {
      if (isCleanedUp) return;

      // Add Atmospheric Limb Glow & Horizon Scattering
      if (typeof (map as any).setFog === 'function') {
        (map as any).setFog({
          color: '#070d1e',
          'high-color': '#0369a1', // vivid cyan atmospheric limb glow
          'horizon-blend': 0.08,
          'space-color': '#02040a',
          'star-intensity': 0.6
        });
      }

      setupLayersRef.current(map);
      setStyleRevision(revision => revision + 1);
      onMapReadyRef.current?.();

      try {
        const deckOverlay = new MapboxOverlay({
          interleaved: false,
          layers: []
        });
        map.addControl(deckOverlay as any);
        deckOverlayRef.current = deckOverlay;
      } catch (deckErr) {
        console.warn('DeckGL overlay not initialized:', deckErr);
      }

      // 1. Progressive Hierarchical Cluster Zoom Handler
      const handleClusterClick = async (e: maplibregl.MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] }) => {
        if (!e.features || !e.features[0]) return;
        if (popupRef.current) popupRef.current.remove();

        const feature = e.features[0];
        const clusterId = feature.properties?.cluster_id;
        const pointCount = feature.properties?.point_count || 0;
        const coords = (feature.geometry as any).coordinates as [number, number];
        const source = map.getSource('sites-geojson') as maplibregl.GeoJSONSource;
        if (!source || clusterId === undefined) return;

        const currentZoom = map.getZoom();

        try {
          // Get the expansion zoom for this specific cluster (where it decomposes into child clusters or points)
          const expansionZoom = await source.getClusterExpansionZoom(clusterId);

          // Check if this cluster is already at the terminal micro-level
          // (very small point count, or expansion zoom reaches the unclustered tier >= 10)
          if (pointCount <= 3 || expansionZoom >= 10) {
            const leaves = await source.getClusterLeaves(clusterId, 50, 0);
            if (leaves && leaves.length > 0) {
              let minLon = Infinity;
              let minLat = Infinity;
              let maxLon = -Infinity;
              let maxLat = -Infinity;

              for (const leaf of leaves) {
                const c = (leaf.geometry as any).coordinates;
                if (c && c.length >= 2) {
                  if (c[0] < minLon) minLon = c[0];
                  if (c[1] < minLat) minLat = c[1];
                  if (c[0] > maxLon) maxLon = c[0];
                  if (c[1] > maxLat) maxLat = c[1];
                }
              }

              const span = Math.max(maxLon - minLon, maxLat - minLat);

              // If co-located within a single facility (< 0.015 deg ~ 1.5 km)
              if (span < 0.015) {
                map.easeTo({
                  center: [(minLon + maxLon) / 2, (minLat + maxLat) / 2],
                  zoom: 13.0,
                  duration: 750
                });
                if (leaves[0]?.properties?.site_id) {
                  onSelectSiteRef.current(leaves[0].properties.site_id);
                }
                return;
              }

              // Tight local group: frame them at micro-site resolution
              map.fitBounds(
                [
                  [minLon, minLat],
                  [maxLon, maxLat]
                ],
                {
                  padding: { top: 90, bottom: 90, left: 100, right: 100 },
                  maxZoom: 12.5,
                  duration: 800
                }
              );
              return;
            }
          }

          // Progressive Hierarchical Zoom for larger and intermediate clusters:
          // Advance zoom to break this cluster into its smaller sub-clusters.
          // Step by at least +1.6 to ensure clear cluster splitting, capped at +2.8 to prevent skipping levels.
          const minStep = 1.6;
          const maxStep = 2.8;
          let targetZoom = Math.max(expansionZoom + 0.3, currentZoom + minStep);
          if (targetZoom - currentZoom > maxStep) {
            targetZoom = currentZoom + maxStep;
          }

          map.easeTo({
            center: coords,
            zoom: targetZoom,
            duration: 650
          });
        } catch (err) {
          console.warn('Progressive cluster zoom fallback:', err);
          map.easeTo({
            center: coords,
            zoom: currentZoom + 2.0,
            duration: 600
          });
        }
      };

      // Register cluster click handlers across all cluster layers
      const clusterClickLayers = ['clusters', 'cluster-count', 'cluster-radar-halo', 'cluster-tag-labels'];
      clusterClickLayers.forEach((layerId) => {
        map.on('click', layerId, handleClusterClick);
      });

      // 2. Unclustered Site Click Handler: Select and gently ease to the site
      const handleSiteClick = (e: maplibregl.MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] }) => {
        if (!e.features || !e.features[0]) return;
        if (popupRef.current) popupRef.current.remove();
        const feature = e.features[0];
        const props = feature.properties;
        const coords = (feature.geometry as any).coordinates as [number, number];

        if (props?.site_id) {
          onSelectSiteRef.current(props.site_id);
        }

        if (coords && coords.length >= 2) {
          map.easeTo({
            center: coords,
            zoom: Math.max(map.getZoom(), 12.5),
            pitch: initialIs3DRef.current ? 52 : map.getPitch(),
            duration: 750
          });
        }
      };

      // Register site click handlers across all unclustered layers
      const siteClickLayers = ['unclustered-point', 'unclustered-hot-center', 'unclustered-reticle', 'tactical-site-callouts'];
      siteClickLayers.forEach((layerId) => {
        map.on('click', layerId, handleSiteClick);
      });

      // Also handle clicks on heat bloom (delegates to cluster or site)
      map.on('click', 'thermal-heat-bloom', (e) => {
        if (!e.features || !e.features[0]) return;
        const f = e.features[0];
        if (f.properties?.point_count) {
          handleClusterClick(e);
        } else if (f.properties?.site_id) {
          handleSiteClick(e);
        }
      });

      // Hover Tooltip Popup with Military/Tactical Target Lock HUD
      const popup = new maplibregl.Popup({
        closeButton: false,
        closeOnClick: false,
        offset: 14,
        maxWidth: '340px'
      });
      popupRef.current = popup;

      // Hover on unclustered site layers
      siteClickLayers.forEach((layerId) => {
        map.on('mouseenter', layerId, (e) => {
          map.getCanvas().style.cursor = 'pointer';
          if (!e.features || !e.features[0]) return;
          const coordinates = (e.features[0].geometry as any).coordinates.slice();
          const p = e.features[0].properties as any;

          const rawId = p.site_id || 'UNKNOWN_SITE';
          const shortId = rawId.length > 24
            ? `${rawId.slice(0, 15)}...${rawId.slice(-5)}`
            : rawId;

          if (p?.site_id && p.site_id === selectedSiteIdRef.current) return;

          const html = `
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 10px; line-height: 1.4; min-width: 170px; max-width: 270px; color: #e2e8f0;">
              <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 3px; margin-bottom: 4px;">
                <span title="${rawId}" style="font-weight: bold; color: #89e5fc; letter-spacing: 0.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 180px; display: inline-block;">${shortId}</span>
                <span style="color: #64748b; font-size: 8.5px; font-weight: 600; flex-shrink: 0; background: rgba(255,255,255,0.05); padding: 1px 4px; border-radius: 3px; border: 1px solid rgba(255,255,255,0.08);">TARGET</span>
              </div>
              <div style="color: #64748b; font-size: 9px;">COORD: ${coordinates[1].toFixed(4)}°N, ${coordinates[0].toFixed(4)}°E</div>
              <div style="margin-top: 4px; display: flex; flex-wrap: wrap; gap: 3px;">
                <span style="background: rgba(245,158,11,0.12); color: #fbbf24; border: 1px solid rgba(245,158,11,0.25); padding: 1px 5px; border-radius: 3px; font-size: 8.5px; font-weight: 600;">${p.a_class}</span>
                <span style="background: rgba(6,182,212,0.12); color: #89e5fc; border: 1px solid rgba(6,182,212,0.25); padding: 1px 5px; border-radius: 3px; font-size: 8.5px; font-weight: 600;">${p.b_state}</span>
                <span style="background: ${p.c_status === 'CRITICAL' ? 'rgba(244,63,94,0.15)' : 'rgba(16,185,129,0.12)'}; color: ${p.c_status === 'CRITICAL' ? '#fda4af' : '#34d399'}; border: 1px solid ${p.c_status === 'CRITICAL' ? 'rgba(244,63,94,0.3)' : 'rgba(16,185,129,0.25)'}; padding: 1px 5px; border-radius: 3px; font-size: 8.5px; font-weight: 600;">${p.c_status}</span>
              </div>
              ${p.alert_severity && p.alert_severity !== 'NONE' ? `
                <div style="background: rgba(244,63,94,0.12); border: 1px solid rgba(244,63,94,0.3); color: #fda4af; font-weight: bold; font-size: 8.5px; padding: 2px 4px; border-radius: 3px; margin-top: 4px; text-align: center;">
                  ALERT: ${p.alert_severity}
                </div>` : ''}
            </div>
          `;

          popup.setLngLat(coordinates).setHTML(html).addTo(map);
        });

        map.on('mouseleave', layerId, () => {
          map.getCanvas().style.cursor = '';
          popup.remove();
        });
      });

      // Hover on clusters
      clusterClickLayers.forEach((layerId) => {
        map.on('mouseenter', layerId, (e) => {
          map.getCanvas().style.cursor = 'pointer';
          if (!e.features || !e.features[0]) return;
          const coordinates = (e.features[0].geometry as any).coordinates.slice();
          const p = e.features[0].properties as any;

          const clusterHtml = `
            <div style="font-family: monospace; font-size: 10.5px; line-height: 1.4;">
              <div style="font-weight: bold; color: #38bdf8;">THERMAL CORRIDOR</div>
              <div style="color: #94a3b8; font-size: 9.5px;">Loaded sites in cluster: <span style="color: #ffffff; font-weight: bold;">${p.point_count}</span></div>
              <div style="color: #34d399; font-size: 9px; margin-top: 2px;">Zooming reveals additional sites when the viewport is capped</div>
            </div>
          `;
          popup.setLngLat(coordinates).setHTML(clusterHtml).addTo(map);
        });

        map.on('mouseleave', layerId, () => {
          map.getCanvas().style.cursor = '';
          popup.remove();
        });
      });

      // Hover on satellites
      const satHoverLayers = ['satellites-layer', 'satellites-primary-core', 'satellites-primary-halo'];
      satHoverLayers.forEach(layerId => {
        map.on('mouseenter', layerId, (e) => {
          map.getCanvas().style.cursor = 'pointer';
          if (!e.features || !e.features[0]) return;
          const coordinates = (e.features[0].geometry as any).coordinates.slice();
          const p = e.features[0].properties as any;

          const satHtml = `
            <div style="font-family: monospace; font-size: 10px; line-height: 1.35;">
              <div style="font-weight: bold; color: #38bdf8;">${p.name}</div>
              <div style="color: #94a3b8;">Type: ${p.type} &middot; Altitude: ${p.altitude_km} km</div>
              ${p.sensor ? `<div style="color: #34d399; font-size: 9.5px; font-weight: bold;">Sensor: ${p.sensor}</div>` : ''}
            </div>
          `;
          popup.setLngLat(coordinates).setHTML(satHtml).addTo(map);
        });

        map.on('mouseleave', layerId, () => {
          map.getCanvas().style.cursor = '';
          popup.remove();
        });

        map.on('click', layerId, (e) => {
          if (!e.features || !e.features[0]) return;
          const coords = (e.features[0].geometry as any).coordinates as [number, number];
          const p = e.features[0].properties as any;
          if (coords) {
            map.easeTo({
              center: coords,
              duration: 700
            });
            const satPopupHtml = `
              <div style="font-family: monospace; font-size: 11px; padding: 3px 4px; line-height: 1.4;">
                <div style="font-weight: bold; color: #00f0ff; letter-spacing: 0.05em; display: flex; align-items: center; gap: 4px;">
                  <span>🛰️</span>
                  <span>${p.name}</span>
                </div>
                <div style="color: #94a3b8; font-size: 10px; margin-top: 2px;">
                  TYPE: <span style="color: #ffffff; font-weight: 600;">${p.type}</span> &middot; ALTITUDE: <span style="color: #38bdf8; font-weight: 600;">${p.altitude_km} km</span>
                </div>
                ${p.sensor ? `<div style="color: #34d399; font-size: 9.5px; margin-top: 3px; font-weight: bold;">PAYLOAD: ${p.sensor}</div>` : ''}
              </div>
            `;
            popup.setLngLat(coords).setHTML(satPopupHtml).addTo(map);
          }
        });
      });

      // Bounds change listener
      const reportBounds = () => {
        const b = map.getBounds();
        setViewZoom(map.getZoom());
        onBoundsChangeRef.current([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]);

        // Restrict infinite horizontal panning in 2D Plane: smooth snap-back if dragged beyond ±180°
        if (!is3DRef.current) {
          const center = map.getCenter();
          if (center.lng > 180 || center.lng < -180) {
            const clampedLng = Math.max(-180, Math.min(180, center.lng));
            map.easeTo({ center: [clampedLng, center.lat], duration: 300 });
          }
        }
      };

      map.on('moveend', reportBounds);
      reportBounds();
    });

    return () => {
      isCleanedUp = true;
      if (deckOverlayRef.current) {
        try {
          map.removeControl(deckOverlayRef.current as any);
        } catch { }
        deckOverlayRef.current = null;
      }
      try {
        map.remove();
      } catch { }
    };
  }, []);

  // 2. Projection & 3D Pitch synchronization
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const applyProjection = () => {
      try {
        if (typeof (map as any).setProjection === 'function') {
          (map as any).setProjection({ type: is3D ? 'globe' : 'mercator' });
        }
      } catch (e) {
        console.warn('setProjection error:', e);
      }

      // Restrict infinite horizontal world scrolling in 2D Plane mode
      try {
        if (typeof (map as any).setRenderWorldCopies === 'function') {
          (map as any).setRenderWorldCopies(is3D ? true : false);
        }
      } catch (copiesErr) {
        console.warn('Error adjusting 2D world copies:', copiesErr);
      }
    };

    if (map.isStyleLoaded()) {
      applyProjection();
    } else {
      map.once('style.load', applyProjection);
    }

    if (typeof (map as any).setFog === 'function') {
      if (is3D) {
        (map as any).setFog({
          color: '#070d1e',
          'high-color': '#0369a1',
          'horizon-blend': 0.08,
          'space-color': '#02040a',
          'star-intensity': 0.6
        });
      } else {
        (map as any).setFog(null as any);
      }
    }

    if (!is3D && map.getZoom() < 3.8) {
      map.easeTo({
        pitch: 0,
        bearing: 0,
        zoom: 4.5,
        duration: 1200
      });
    } else {
      map.easeTo({
        pitch: is3D ? 45 : 0,
        bearing: is3D ? -12 : 0,
        duration: 1200
      });
    }
  }, [is3D]);

  // 3. Basemap style toggle synchronization (Satellite View vs Black Canvas)
  const currentBasemapRef = useRef(basemapMode);
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (currentBasemapRef.current === basemapMode) return;
    currentBasemapRef.current = basemapMode;

    const newStyle = getBasemapStyle(basemapMode, is3D);
    map.setStyle(newStyle);

    map.once('style.load', () => {
      setupLayersRef.current(map);
      setStyleRevision(revision => revision + 1);
      try {
        if (typeof (map as any).setProjection === 'function') {
          (map as any).setProjection({ type: is3D ? 'globe' : 'mercator' });
        }
      } catch (e) {
        console.warn('Error applying projection on basemap change:', e);
      }

      // Restrict infinite horizontal world scrolling in 2D Plane mode
      try {
        if (typeof (map as any).setRenderWorldCopies === 'function') {
          (map as any).setRenderWorldCopies(is3D ? true : false);
        }
      } catch (copiesErr) {
        console.warn('Error adjusting 2D world copies on style load:', copiesErr);
      }

      if (is3D && typeof (map as any).setFog === 'function') {
        (map as any).setFog({
          color: '#070d1e',
          'high-color': '#0369a1',
          'horizon-blend': 0.08,
          'space-color': '#02040a',
          'star-intensity': 0.6
        });
      }

    });
  }, [basemapMode, is3D]);

  // 4. Focus coordinates when explicitly requested (e.g. "Locate" button in Alert Rail)
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !focusedCoordinates || focusedCoordinates.length < 2) return;

    const [lon, lat] = focusedCoordinates;
    if (
      !lastFlownCoordsRef.current ||
      lastFlownCoordsRef.current[0] !== lon ||
      lastFlownCoordsRef.current[1] !== lat
    ) {
      lastFlownCoordsRef.current = [lon, lat];
      map.flyTo({
        center: [lon, lat],
        zoom: 13.0,
        pitch: is3D ? 52 : map.getPitch(),
        duration: 1000
      });
    }
  }, [focusedCoordinates, is3D]);

  // 5. Push site data to MapLibre exactly once per payload/filter/style change.
  // MapLibre clusters GeoJSON in a worker; report completion only after the map
  // reaches idle so the startup overlay reflects visible clusters, not HTTP time.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !sitesData) return;

    const source = map.getSource('sites-geojson') as maplibregl.GeoJSONSource | undefined;
    if (source && typeof source.setData === 'function') {
      let completed = false;
      const reportRendered = () => {
        if (completed) return;
        completed = true;
        window.clearTimeout(fallbackTimer);
        onSitesRenderedRef.current?.();
      };
      const fallbackTimer = window.setTimeout(reportRendered, 1_500);
      map.once('idle', reportRendered);
      source.setData({
        type: 'FeatureCollection',
        features: filteredFeatures
      });

      return () => {
        completed = true;
        window.clearTimeout(fallbackTimer);
        map.off('idle', reportRendered);
      };
    }
  }, [sitesData, filteredFeatures, styleRevision]);

  // 6. Visibility changes are cheap layout operations and must not rebuild the
  // site cluster index or the deck.gl layer.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const satAllLayers = ['satellites-layer', 'satellites-primary-halo', 'satellites-primary-core', 'satellites-primary-label'];
    satAllLayers.forEach(id => {
      if (map.getLayer(id)) {
        map.setLayoutProperty(id, 'visibility', showSatellites ? 'visible' : 'none');
      }
    });
    if (map.getLayer('satellite-orbit-lines')) {
      map.setLayoutProperty('satellite-orbit-lines', 'visibility', showSatellites ? 'visible' : 'none');
    }

    // Toggle swath visibility
    if (map.getLayer('satellite-swaths-fill')) {
      map.setLayoutProperty('satellite-swaths-fill', 'visibility', showSwaths ? 'visible' : 'none');
    }
    if (map.getLayer('satellite-swaths-line')) {
      map.setLayoutProperty('satellite-swaths-line', 'visibility', showSwaths ? 'visible' : 'none');
    }

    // Toggle heat bloom visibility
    if (map.getLayer('thermal-heat-bloom')) {
      map.setLayoutProperty('thermal-heat-bloom', 'visibility', showHeatBloom ? 'visible' : 'none');
    }
  }, [showSatellites, showSwaths, showHeatBloom, styleRevision]);

  // 7. Update deck.gl only when 3D column inputs change.
  useEffect(() => {
    const map = mapRef.current;
    const deck = deckOverlayRef.current;
    if (!map || !deck) return;

    if (deck) {
      try {
        if (is3D && show3DColumns && filteredFeatures.length > 0) {
          const columnFeatures = filteredFeatures.slice(0, MAX_3D_COLUMNS);
          const radius = viewZoom < 5 ? 20000 : (viewZoom < 7 ? 8000 : (viewZoom < 10 ? 3000 : 1400));
          const baseScale = viewZoom < 5 ? 120000 : (viewZoom < 7 ? 60000 : 32000);
          const spikeScale = (filters.spikeHeightScale || 1) * baseScale;

          const columnLayer = new ColumnLayer({
            id: 'thermal-3d-spikes',
            data: columnFeatures,
            diskResolution: 16,
            radius: radius,
            extruded: true,
            pickable: true,
            elevationScale: 1,
            getPosition: (d: SiteGeoJSONFeature) => d.geometry.coordinates,
            getElevation: (d: SiteGeoJSONFeature) => {
              const rawScore = d.properties.c_score ?? 0.3;
              const frp = d.properties.latest_frp ? Math.min(100, d.properties.latest_frp) / 50 : 0.5;
              const magnitude = Math.max(rawScore, frp);
              return Math.max(viewZoom < 5 ? 20000 : 1200, magnitude * spikeScale);
            },
            getFillColor: (d: SiteGeoJSONFeature) => {
              const cStatus = d.properties.c_status;
              if (cStatus === 'CRITICAL') return [239, 68, 68, 245];
              if (cStatus === 'ANOMALOUS') return [249, 115, 22, 235];
              if (cStatus === 'ELEVATED') return [234, 179, 8, 220];
              if (d.properties.a_class === 'INDUSTRIAL') return [245, 158, 11, 215];
              if (d.properties.a_class === 'NONINDUSTRIAL') return [16, 185, 129, 190];
              if (d.properties.a_class === 'UNKNOWN') return [129, 140, 248, 190];
              return [100, 116, 139, 170];
            },
            getLineColor: [0, 0, 0, 255],
            lineWidthMinPixels: 1.5,
            onClick: (info) => {
              if (info.object) {
                const siteObj = info.object as SiteGeoJSONFeature;
                onSelectSiteRef.current(siteObj.properties.site_id);
                const coords = siteObj.geometry.coordinates as [number, number];
                if (coords && coords.length >= 2) {
                  map.flyTo({
                    center: coords,
                    zoom: Math.max(map.getZoom(), 13.5),
                    pitch: is3D ? 55 : map.getPitch(),
                    duration: 900
                  });
                }
              }
            }
          });

          deck.setProps({ layers: [columnLayer] });
        } else {
          deck.setProps({ layers: [] });
        }
      } catch (deckUpdateErr) {
        console.warn('Deck.gl layer update error:', deckUpdateErr);
      }
    }
  }, [filteredFeatures, is3D, show3DColumns, viewZoom, filters.spikeHeightScale]);

  const visibleSiteCount = filteredFeatures.length;

  return (
    <div className="relative w-full h-full flex-1 bg-[#02040a] overflow-hidden">
      <div ref={mapContainerRef} className="absolute inset-0 w-full h-full" />

      {/* Bottom-Left Viewport Operational Telemetry Bar */}
      <div className="absolute bottom-4 left-4 z-10 hidden sm:flex items-center gap-2.5 px-3.5 py-1.5 rounded-full border border-sky-400/30 bg-[#070e1e]/85 backdrop-blur-md text-[10px] font-mono shadow-[0_4px_16px_rgba(0,0,0,0.5)]">
        <div className="flex items-center gap-1.5 text-slate-300">
          <Sparkles className="w-3 h-3 text-[#89E5FC]" />
          <span className="text-slate-400">RENDERED:</span>
          <span className="font-bold text-white">{visibleSiteCount.toLocaleString()}</span>
          {sitesData && sitesData.total_count > sitesData.returned_count && (
            <span className="text-slate-500">/{sitesData.total_count.toLocaleString()}</span>
          )}
          {isLoading && <span className="text-cyan-300 animate-pulse">UPDATING</span>}
        </div>
        <div className="w-[1px] h-3 bg-sky-400/20" />
        <div className="flex items-center gap-1 text-slate-300">
          <span className="text-slate-400">VIIRS:</span>
          <span className="font-bold text-amber-400">375m</span>
        </div>
        <div className="w-[1px] h-3 bg-sky-400/20" />
        <div className="flex items-center gap-1 text-slate-300">
          <span className="text-slate-400">DBSCAN:</span>
          <span className="font-bold text-emerald-400">750m</span>
        </div>
      </div>

      {/* Bottom-Right Tactical Navigation & Zoom HUD */}
      <div className="absolute bottom-4 right-4 z-20 flex flex-col items-center gap-1 p-1 rounded-full border border-sky-400/30 bg-[#070e1e]/85 backdrop-blur-md shadow-[0_4px_20px_rgba(0,0,0,0.65)] font-mono text-xs select-none">
        {/* Zoom In */}
        <button
          onClick={() => mapRef.current?.zoomIn({ duration: 300 })}
          aria-label="Zoom In"
          title="Zoom In"
          type="button"
          className="w-7 h-7 flex items-center justify-center rounded-full text-slate-300 hover:text-white hover:bg-[#16385c]/80 transition-all cursor-pointer active:scale-95"
        >
          <Plus className="w-3.5 h-3.5 text-[#89E5FC]" />
        </button>

        <span className="w-4 h-px bg-sky-400/20" />

        {/* Zoom Out */}
        <button
          onClick={() => mapRef.current?.zoomOut({ duration: 300 })}
          aria-label="Zoom Out"
          title="Zoom Out"
          type="button"
          className="w-7 h-7 flex items-center justify-center rounded-full text-slate-300 hover:text-white hover:bg-[#16385c]/80 transition-all cursor-pointer active:scale-95"
        >
          <Minus className="w-3.5 h-3.5 text-[#89E5FC]" />
        </button>

        <span className="w-4 h-px bg-sky-400/20" />

        {/* Reset North & Orientation */}
        <button
          onClick={() => mapRef.current?.resetNorthPitch({ duration: 600 })}
          aria-label="Reset Orientation"
          title="Reset Orientation"
          type="button"
          className="w-7 h-7 flex items-center justify-center rounded-full text-slate-300 hover:text-white hover:bg-[#16385c]/80 transition-all cursor-pointer active:scale-95 group"
        >
          <Compass className="w-3.5 h-3.5 text-sky-400 group-hover:rotate-45 transition-transform duration-300" />
        </button>
      </div>
    </div>
  );
};
