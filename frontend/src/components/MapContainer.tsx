import React, { useEffect, useRef, useState } from 'react';
import maplibregl, { Map as MapLibreMap, Popup } from 'maplibre-gl';
import { MapboxOverlay } from '@deck.gl/mapbox';
import { ColumnLayer } from '@deck.gl/layers';
import type { SiteGeoJSONFeatureCollection, FilterState, SiteGeoJSONFeature } from '../types/api';
import { getSatelliteOrbitRings, getSatelliteConstellation, getSensorSwathPolygons } from '../services/satellites';
import { Globe, Layers, Satellite, Flame, Radio, Zap, Sparkles } from 'lucide-react';

interface MapContainerProps {
  sitesData: SiteGeoJSONFeatureCollection | null;
  selectedSiteId: string | null;
  onSelectSite: (siteId: string) => void;
  onBoundsChange: (bbox: [number, number, number, number]) => void;
  filters: FilterState;
  is3D: boolean;
  focusedCoordinates?: [number, number] | null;
}

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
      attribution: '&copy; Esri, Maxar, Earthstar Geographics'
    },
    'esri-boundaries': {
      type: 'raster',
      tiles: [
        'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}'
      ],
      tileSize: 256
    }
  },
  layers: [
    {
      id: 'esri-imagery-layer',
      type: 'raster',
      source: 'esri-imagery',
      minzoom: 0,
      maxzoom: 20
    },
    {
      id: 'esri-boundaries-layer',
      type: 'raster',
      source: 'esri-boundaries',
      minzoom: 0,
      maxzoom: 20,
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
      attribution: '&copy; Esri &copy; OpenStreetMap'
    },
    'esri-labels': {
      type: 'raster',
      tiles: [
        'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}'
      ],
      tileSize: 256
    }
  },
  layers: [
    {
      id: 'esri-dark-base',
      type: 'raster',
      source: 'esri-dark',
      minzoom: 0,
      maxzoom: 20
    },
    {
      id: 'esri-labels-layer',
      type: 'raster',
      source: 'esri-labels',
      minzoom: 0,
      maxzoom: 20
    }
  ]
};

export const MapContainer: React.FC<MapContainerProps> = ({
  sitesData,
  selectedSiteId,
  onSelectSite,
  onBoundsChange,
  filters,
  is3D,
  focusedCoordinates
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const deckOverlayRef = useRef<MapboxOverlay | null>(null);
  const popupRef = useRef<Popup | null>(null);

  const [basemapMode, setBasemapMode] = useState<'SATELLITE' | 'DARK'>('SATELLITE');
  const [showSatellites, setShowSatellites] = useState<boolean>(true);
  const [showHeatBloom, setShowHeatBloom] = useState<boolean>(true);
  const [showSwaths, setShowSwaths] = useState<boolean>(true);
  const [show3DColumns, setShow3DColumns] = useState<boolean>(true);

  const onSelectSiteRef = useRef(onSelectSite);
  onSelectSiteRef.current = onSelectSite;

  const onBoundsChangeRef = useRef(onBoundsChange);
  onBoundsChangeRef.current = onBoundsChange;

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

    // 2. Add Satellites Constellation Points Source & Layer
    if (!map.getSource('satellites-source')) {
      map.addSource('satellites-source', {
        type: 'geojson',
        data: getSatelliteConstellation(1800) as any
      });
    }
    if (!map.getLayer('satellites-layer')) {
      map.addLayer({
        id: 'satellites-layer',
        type: 'circle',
        source: 'satellites-source',
        paint: {
          'circle-color': ['get', 'color'],
          'circle-radius': 3.5,
          'circle-stroke-width': 1.2,
          'circle-stroke-color': '#ffffff',
          'circle-opacity': 0.95
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
        clusterRadius: 35
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
              'rgba(6, 182, 212, 0.45)', // Cyan low cluster
              25,
              'rgba(245, 158, 11, 0.55)', // Amber mid cluster
              100,
              'rgba(239, 68, 68, 0.65)'   // Red high cluster
            ],
            [
              'match',
              ['get', 'c_status'],
              'CRITICAL', 'rgba(239, 68, 68, 0.85)',
              'ANOMALOUS', 'rgba(249, 115, 22, 0.75)',
              'ELEVATED', 'rgba(234, 179, 8, 0.65)',
              [
                'match',
                ['get', 'a_class'],
                'INDUSTRIAL', 'rgba(245, 158, 11, 0.65)',
                'NONINDUSTRIAL', 'rgba(16, 185, 129, 0.45)',
                'rgba(129, 140, 248, 0.45)'
              ]
            ]
          ],
          'circle-blur': 0.82,
          'circle-radius': [
            'case',
            ['has', 'point_count'],
            [
              'step',
              ['get', 'point_count'],
              28,
              25,
              42,
              100,
              62
            ],
            [
              'case',
              ['==', ['get', 'site_id'], selectedSiteId || ''], 34,
              ['==', ['get', 'c_status'], 'CRITICAL'], 28,
              ['==', ['get', 'c_status'], 'ANOMALOUS'], 22,
              16
            ]
          ],
          'circle-opacity': [
            'interpolate',
            ['linear'],
            ['zoom'],
            2, 0.6,
            6, 0.85,
            12, 0.5
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
            50,
            27,
            200,
            36
          ],
          'circle-stroke-width': 1.6,
          'circle-stroke-color': [
            'step',
            ['get', 'point_count'],
            '#38bdf8',
            50,
            '#fbbf24',
            200,
            '#f87171'
          ],
          'circle-stroke-opacity': 0.85
        }
      });
    }

    // 3c. Main Cluster Circle Layer (Heavy Black Containment Border)
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
            '#0891b2', // deep cyan
            50,
            '#d97706', // deep amber
            200,
            '#dc2626'  // crimson red
          ],
          'circle-radius': [
            'step',
            ['get', 'point_count'],
            16,
            50,
            22,
            200,
            30
          ],
          'circle-opacity': 0.95,
          'circle-stroke-width': 2.5,
          'circle-stroke-color': '#000000'
        }
      });
    }

    // 3d. Cluster Count Text (Monospace Bold)
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
          'text-color': '#ffffff'
        }
      });
    }

    // 3e. Tactical Cluster Code Badge (TS-14 / MF-08)
    if (!map.getLayer('cluster-tag-labels')) {
      map.addLayer({
        id: 'cluster-tag-labels',
        type: 'symbol',
        source: 'sites-geojson',
        filter: ['has', 'point_count'],
        minzoom: 4.5,
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

    // 3g. Unclustered Site Points (OSIRIS Bold Black Ring + Glowing Semantic Center)
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
            ['==', ['get', 'site_id'], selectedSiteId || ''], 9.5,
            6.5
          ],
          'circle-stroke-width': 2.5,
          'circle-stroke-color': '#000000',
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

  // 1. Initialize MapLibre in 3D Globe Projection with Atmospheric Glow
  useEffect(() => {
    if (!mapContainerRef.current) return;
    let isCleanedUp = false;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: is3D ? SATELLITE_GLOBE_STYLE : DARK_TACTICAL_STYLE,
      center: [78.9629, 20.5937],
      zoom: is3D ? 2.5 : 4.8,
      pitch: is3D ? 45 : 0,
      bearing: is3D ? -12 : 0,
      maxPitch: 85
    });

    mapRef.current = map;

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-left');

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

      setupLayers(map);

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
            pitch: is3D ? 52 : map.getPitch(),
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
        offset: 14
      });
      popupRef.current = popup;

      // Hover on unclustered site layers
      siteClickLayers.forEach((layerId) => {
        map.on('mouseenter', layerId, (e) => {
          map.getCanvas().style.cursor = 'pointer';
          if (!e.features || !e.features[0]) return;
          const coordinates = (e.features[0].geometry as any).coordinates.slice();
          const p = e.features[0].properties as any;

          const html = `
            <div style="font-family: monospace; font-size: 11px; line-height: 1.45; min-width: 170px;">
              <div style="display: flex; items-center; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.15); padding-bottom: 3px; margin-bottom: 4px;">
                <span style="font-weight: bold; color: #38bdf8; letter-spacing: 0.5px;">${p.site_id}</span>
                <span style="color: #64748b; font-size: 9px;">LOC-LOCK</span>
              </div>
              <div style="color: #94a3b8; font-size: 9.5px;">COORD: ${coordinates[1].toFixed(4)}°N, ${coordinates[0].toFixed(4)}°E</div>
              <div style="margin-top: 5px; display: flex; flex-wrap: wrap; gap: 4px;">
                <span style="background: rgba(245,158,11,0.25); color: #f59e0b; border: 1px solid rgba(245,158,11,0.4); padding: 1px 4px; border-radius: 3px; font-size: 9px; font-weight: bold;">${p.a_class}</span>
                <span style="background: rgba(6,182,212,0.2); color: #06b6d4; border: 1px solid rgba(6,182,212,0.4); padding: 1px 4px; border-radius: 3px; font-size: 9px;">${p.b_state}</span>
                <span style="background: rgba(239,68,68,0.25); color: #ef4444; border: 1px solid rgba(239,68,68,0.4); padding: 1px 4px; border-radius: 3px; font-size: 9px; font-weight: bold;">${p.c_status}</span>
              </div>
              ${p.alert_severity && p.alert_severity !== 'NONE' ? `
                <div style="background: rgba(239,68,68,0.2); border: 1px solid rgba(239,68,68,0.5); color: #ef4444; font-weight: bold; font-size: 9px; padding: 2px 4px; border-radius: 3px; margin-top: 5px; text-align: center;">
                  ⚡ ALERT: ${p.alert_severity}
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
              <div style="color: #94a3b8; font-size: 9.5px;">Total Dissipation Points: <span style="color: #ffffff; font-weight: bold;">${p.point_count}</span></div>
              <div style="color: #34d399; font-size: 9px; margin-top: 2px;">Click to zoom into cluster micro-sites</div>
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
      map.on('mouseenter', 'satellites-layer', (e) => {
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

      map.on('mouseleave', 'satellites-layer', () => {
        map.getCanvas().style.cursor = '';
        popup.remove();
      });

      // Bounds change listener
      const reportBounds = () => {
        const b = map.getBounds();
        onBoundsChangeRef.current([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]);
      };

      map.on('moveend', reportBounds);
      reportBounds();
    });

    return () => {
      isCleanedUp = true;
      if (deckOverlayRef.current) {
        try {
          map.removeControl(deckOverlayRef.current as any);
        } catch (e) {}
        deckOverlayRef.current = null;
      }
      try {
        map.remove();
      } catch (e) {}
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
    };

    if (map.isStyleLoaded()) {
      applyProjection();
    } else {
      map.once('style.load', applyProjection);
    }

    map.easeTo({
      pitch: is3D ? 45 : 0,
      bearing: is3D ? -12 : 0,
      duration: 1200
    });
  }, [is3D]);

  // 3. Basemap style toggle handler
  const handleToggleBasemap = (newMode: 'SATELLITE' | 'DARK') => {
    const map = mapRef.current;
    if (!map || basemapMode === newMode) return;

    setBasemapMode(newMode);
    map.setStyle(newMode === 'SATELLITE' ? SATELLITE_GLOBE_STYLE : DARK_TACTICAL_STYLE);

    map.once('style.load', () => {
      setupLayers(map);
      try {
        if (typeof (map as any).setProjection === 'function') {
          (map as any).setProjection({ type: is3D ? 'globe' : 'mercator' });
        }
      } catch (e) {
        console.warn('Error applying projection on basemap change:', e);
      }
    });
  };

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

  // 5. Update GeoJSON Source & deck.gl 3D Volumetric Thermal Columns
  useEffect(() => {
    const map = mapRef.current;
    const deck = deckOverlayRef.current;
    if (!map || !sitesData) return;

    const filteredFeatures: SiteGeoJSONFeature[] = sitesData.features.filter(f => {
      const p = f.properties;
      if (filters.aClasses.length > 0 && !filters.aClasses.includes(p.a_class)) return false;
      if (filters.bStates.length > 0 && !filters.bStates.includes(p.b_state)) return false;
      if (filters.cStatuses.length > 0 && !filters.cStatuses.includes(p.c_status)) return false;
      return true;
    });

    const source = map.getSource('sites-geojson') as maplibregl.GeoJSONSource | undefined;
    if (source && typeof source.setData === 'function') {
      source.setData({
        type: 'FeatureCollection',
        features: filteredFeatures
      });
    }

    // Toggle satellite layer visibility
    if (map.getLayer('satellites-layer')) {
      map.setLayoutProperty('satellites-layer', 'visibility', showSatellites ? 'visible' : 'none');
    }
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

    // Update 3D Deck.gl Volumetric Columns (Thermal FRP Plumes)
    if (deck) {
      try {
        if (is3D && show3DColumns && filteredFeatures.length > 0) {
          const spikeScale = filters.spikeHeightScale * 32000;

          const columnLayer = new ColumnLayer({
            id: 'thermal-3d-spikes',
            data: filteredFeatures,
            diskResolution: 16,
            radius: 1400,
            extruded: true,
            pickable: true,
            elevationScale: 1,
            getPosition: (d: SiteGeoJSONFeature) => d.geometry.coordinates,
            getElevation: (d: SiteGeoJSONFeature) => {
              const rawScore = d.properties.c_score ?? 0.25;
              return Math.max(1200, rawScore * spikeScale);
            },
            getFillColor: (d: SiteGeoJSONFeature) => {
              const cStatus = d.properties.c_status;
              if (cStatus === 'CRITICAL') return [239, 68, 68, 245];
              if (cStatus === 'ANOMALOUS') return [249, 115, 22, 235];
              if (cStatus === 'ELEVATED') return [234, 179, 8, 220];
              if (d.properties.a_class === 'INDUSTRIAL') return [245, 158, 11, 215];
              return [16, 185, 129, 190];
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
  }, [sitesData, filters, is3D, selectedSiteId, showSatellites, showHeatBloom, showSwaths, show3DColumns]);

  return (
    <div className="relative w-full h-full flex-1 bg-[#02040a] overflow-hidden">
      <div ref={mapContainerRef} className="absolute inset-0 w-full h-full" />

      {/* Top-Right Tactical HUD Control Cluster */}
      <div className="absolute top-4 right-4 z-10 flex flex-col items-end gap-2">
        {/* Main Basemap & Sensor Swath Group */}
        <div className="flex items-center gap-1.5 p-1 rounded-lg tactical-glass shadow-2xl">
          {/* Basemap Switcher */}
          <div className="flex bg-black/40 border border-white/10 rounded p-0.5 text-[10px] font-mono">
            <button
              onClick={() => handleToggleBasemap('SATELLITE')}
              className={`px-2 py-1 rounded flex items-center gap-1 transition-colors ${
                basemapMode === 'SATELLITE'
                  ? 'bg-cyan-500/25 text-cyan-300 border border-cyan-500/40 font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Globe className="w-3 h-3" />
              <span>ORBITAL GLOBE</span>
            </button>
            <button
              onClick={() => handleToggleBasemap('DARK')}
              className={`px-2 py-1 rounded flex items-center gap-1 transition-colors ${
                basemapMode === 'DARK'
                  ? 'bg-cyan-500/25 text-cyan-300 border border-cyan-500/40 font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Layers className="w-3 h-3" />
              <span>DARK CANVAS</span>
            </button>
          </div>

          <div className="w-[1px] h-4 bg-white/10 mx-0.5" />

          {/* Heat Bloom Corona Toggle */}
          <button
            onClick={() => setShowHeatBloom(!showHeatBloom)}
            className={`px-2 py-1 rounded border text-[10px] font-mono flex items-center gap-1 transition-all ${
              showHeatBloom
                ? 'bg-amber-500/20 border-amber-500/40 text-amber-300 font-bold shadow-[0_0_10px_rgba(245,158,11,0.2)]'
                : 'bg-black/30 border-white/10 text-slate-400 hover:text-slate-200'
            }`}
            title="Toggle Radiative FRP Heat Bloom Coronas"
          >
            <Flame className="w-3 h-3 text-amber-400" />
            <span>HEAT BLOOM</span>
          </button>

          {/* 3D Thermal Plumes Toggle (in 3D mode) */}
          {is3D && (
            <button
              onClick={() => setShow3DColumns(!show3DColumns)}
              className={`px-2 py-1 rounded border text-[10px] font-mono flex items-center gap-1 transition-all ${
                show3DColumns
                  ? 'bg-red-500/20 border-red-500/40 text-red-300 font-bold shadow-[0_0_10px_rgba(239,68,68,0.2)]'
                  : 'bg-black/30 border-white/10 text-slate-400 hover:text-slate-200'
              }`}
              title="Toggle 3D Volumetric Thermal FRP Spikes"
            >
              <Zap className="w-3 h-3 text-red-400" />
              <span>3D PLUMES</span>
            </button>
          )}

          {/* Satellite Constellation Toggle */}
          <button
            onClick={() => setShowSatellites(!showSatellites)}
            className={`px-2 py-1 rounded border text-[10px] font-mono flex items-center gap-1 transition-all ${
              showSatellites
                ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300 font-bold shadow-[0_0_10px_rgba(16,185,129,0.2)]'
                : 'bg-black/30 border-white/10 text-slate-400 hover:text-slate-200'
            }`}
            title="Toggle 3D Satellite Constellation"
          >
            <Satellite className="w-3 h-3 text-emerald-400" />
            <span>SATELLITES ({showSatellites ? '1.8K' : 'OFF'})</span>
          </button>

          {/* VIIRS Swaths Toggle */}
          <button
            onClick={() => setShowSwaths(!showSwaths)}
            className={`px-2 py-1 rounded border text-[10px] font-mono flex items-center gap-1 transition-all ${
              showSwaths
                ? 'bg-cyan-500/20 border-cyan-500/40 text-cyan-300 font-bold shadow-[0_0_10px_rgba(6,182,212,0.2)]'
                : 'bg-black/30 border-white/10 text-slate-400 hover:text-slate-200'
            }`}
            title="Toggle VIIRS 3,000 km Scanning Swath Footprints"
          >
            <Radio className="w-3 h-3 text-cyan-400" />
            <span>SWATH</span>
          </button>
        </div>

        {/* 3D Spherical Atmosphere Status Badge */}
        {is3D && (
          <div className="flex items-center gap-2 px-3 py-1 rounded tactical-glass border border-cyan-500/30 text-[10px] font-mono text-cyan-300 shadow-[0_0_15px_rgba(6,182,212,0.15)]">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping-slow" />
            <span>3D SPHERICAL GLOBE &middot; ATMOSPHERE ACTIVE</span>
          </div>
        )}
      </div>

      {/* Bottom-Left Viewport Operational Telemetry Bar */}
      <div className="absolute bottom-4 left-4 z-10 hidden sm:flex items-center gap-3 px-3.5 py-1.5 rounded-lg tactical-glass border border-white/15 text-[10px] font-mono shadow-2xl">
        <div className="flex items-center gap-1.5 text-slate-300">
          <Sparkles className="w-3 h-3 text-cyan-400" />
          <span className="text-slate-400">VIEWPORT SITES:</span>
          <span className="font-bold text-white">{sitesData?.features?.length?.toLocaleString() ?? 0}</span>
        </div>
        <div className="w-[1px] h-3 bg-white/20" />
        <div className="flex items-center gap-1.5 text-slate-300">
          <span className="text-slate-400">OPTICAL RESOLUTION:</span>
          <span className="font-bold text-amber-400">375m VIIRS</span>
        </div>
        <div className="w-[1px] h-3 bg-white/20" />
        <div className="flex items-center gap-1.5 text-slate-300">
          <span className="text-slate-400">PHYSICAL CLUSTER:</span>
          <span className="font-bold text-emerald-400">750m DBSCAN</span>
        </div>
      </div>
    </div>
  );
};
