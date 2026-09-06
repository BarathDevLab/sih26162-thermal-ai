import React, { useEffect, useRef, useState } from 'react';
import maplibregl, { Map as MapLibreMap, Popup } from 'maplibre-gl';
import { MapboxOverlay } from '@deck.gl/mapbox';
import { ColumnLayer } from '@deck.gl/layers';
import type { SiteGeoJSONFeatureCollection, FilterState, SiteGeoJSONFeature } from '../types/api';
import { getSatelliteOrbitRings, getSatelliteConstellation } from '../services/satellites';
import { Globe, Layers, Satellite } from 'lucide-react';

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

  const onSelectSiteRef = useRef(onSelectSite);
  onSelectSiteRef.current = onSelectSite;

  const onBoundsChangeRef = useRef(onBoundsChange);
  onBoundsChangeRef.current = onBoundsChange;

  // Add source data and layers helper
  const setupLayers = (map: MapLibreMap) => {
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
          'line-width': 1.2,
          'line-dasharray': [3, 2],
          'line-opacity': 0.75
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
          'circle-stroke-width': 1.0,
          'circle-stroke-color': '#ffffff',
          'circle-opacity': 0.9
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
            '#06b6d4',
            50,
            '#f59e0b',
            200,
            '#ef4444'
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
          'circle-opacity': 0.9,
          'circle-stroke-width': 2.5,
          'circle-stroke-color': '#000000'
        }
      });
    }
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
    if (!map.getLayer('cluster-tag-labels')) {
      map.addLayer({
        id: 'cluster-tag-labels',
        type: 'symbol',
        source: 'sites-geojson',
        filter: ['has', 'point_count'],
        minzoom: 5,
        layout: {
          'text-field': ['concat', 'MF', ['to-string', ['slice', ['to-string', ['get', 'point_count']], 0, 2]]],
          'text-size': 10,
          'text-offset': [0, 2.0]
        },
        paint: {
          'text-color': '#fbbf24',
          'text-halo-color': '#000000',
          'text-halo-width': 2.0
        }
      });
    }
  };

  // 1. Initialize MapLibre in 3D Globe Projection
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

      // Interactive Click Handling
      map.on('click', 'unclustered-point', (e) => {
        if (!e.features || !e.features[0]) return;
        const props = e.features[0].properties;
        if (props?.site_id) {
          onSelectSiteRef.current(props.site_id);
        }
      });

      // Hover Tooltip Popup
      const popup = new maplibregl.Popup({
        closeButton: false,
        closeOnClick: false,
        offset: 12
      });
      popupRef.current = popup;

      map.on('mouseenter', 'unclustered-point', (e) => {
        map.getCanvas().style.cursor = 'pointer';
        if (!e.features || !e.features[0]) return;
        const coordinates = (e.features[0].geometry as any).coordinates.slice();
        const p = e.features[0].properties as any;

        const html = `
          <div style="font-family: monospace; font-size: 11px; line-height: 1.4;">
            <div style="font-weight: bold; color: #38bdf8;">${p.site_id}</div>
            <div style="color: #94a3b8; font-size: 10px;">LAT: ${coordinates[1].toFixed(4)} | LON: ${coordinates[0].toFixed(4)}</div>
            <div style="margin-top: 4px; display: flex; gap: 4px;">
              <span style="background: rgba(245,158,11,0.2); color: #f59e0b; padding: 1px 4px; border-radius: 3px; font-size: 9px;">${p.a_class}</span>
              <span style="background: rgba(6,182,212,0.2); color: #06b6d4; padding: 1px 4px; border-radius: 3px; font-size: 9px;">${p.b_state}</span>
              <span style="background: rgba(239,68,68,0.2); color: #ef4444; padding: 1px 4px; border-radius: 3px; font-size: 9px;">${p.c_status}</span>
            </div>
            ${p.alert_severity && p.alert_severity !== 'NONE' ? `<div style="color: #ef4444; font-weight: bold; margin-top: 3px;">ALERT: ${p.alert_severity}</div>` : ''}
          </div>
        `;

        popup.setLngLat(coordinates).setHTML(html).addTo(map);
      });

      map.on('mouseleave', 'unclustered-point', () => {
        map.getCanvas().style.cursor = '';
        popup.remove();
      });

      // Hover on satellites
      map.on('mouseenter', 'satellites-layer', (e) => {
        map.getCanvas().style.cursor = 'pointer';
        if (!e.features || !e.features[0]) return;
        const coordinates = (e.features[0].geometry as any).coordinates.slice();
        const p = e.features[0].properties as any;

        const satHtml = `
          <div style="font-family: monospace; font-size: 10px; line-height: 1.3;">
            <div style="font-weight: bold; color: #38bdf8;">${p.name}</div>
            <div style="color: #94a3b8;">Type: ${p.type} &middot; Alt: ${p.altitude_km} km</div>
            ${p.sensor ? `<div style="color: #34d399;">Sensor: ${p.sensor}</div>` : ''}
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

  // 4. Focus coordinates when selecting from alert rail
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !focusedCoordinates) return;
    map.flyTo({
      center: focusedCoordinates,
      zoom: 11,
      pitch: is3D ? 50 : 0,
      duration: 1400
    });
  }, [focusedCoordinates, is3D]);

  // 5. Update GeoJSON Source & deck.gl 3D Thermal Columns
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
    if (source) {
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

    // Update 3D Deck.gl Column Spikes
    if (deck) {
      if (is3D && filteredFeatures.length > 0) {
        const spikeScale = filters.spikeHeightScale * 25000;

        const columnLayer = new ColumnLayer({
          id: 'thermal-3d-spikes',
          data: filteredFeatures,
          diskResolution: 12,
          radius: 1200,
          extruded: true,
          pickable: true,
          elevationScale: 1,
          getPosition: (d: SiteGeoJSONFeature) => d.geometry.coordinates,
          getElevation: (d: SiteGeoJSONFeature) => {
            const rawScore = d.properties.c_score ?? 0.2;
            return Math.max(800, rawScore * spikeScale);
          },
          getFillColor: (d: SiteGeoJSONFeature) => {
            const cStatus = d.properties.c_status;
            if (cStatus === 'CRITICAL') return [239, 68, 68, 230];
            if (cStatus === 'ANOMALOUS') return [249, 115, 22, 230];
            if (cStatus === 'ELEVATED') return [234, 179, 8, 230];
            if (d.properties.a_class === 'INDUSTRIAL') return [245, 158, 11, 210];
            return [16, 185, 129, 190];
          },
          getLineColor: [0, 0, 0, 255],
          lineWidthMinPixels: 2,
          onClick: (info) => {
            if (info.object) {
              onSelectSiteRef.current((info.object as SiteGeoJSONFeature).properties.site_id);
            }
          }
        });

        deck.setProps({ layers: [columnLayer] });
      } else {
        deck.setProps({ layers: [] });
      }
    }
  }, [sitesData, filters, is3D, selectedSiteId, showSatellites]);

  return (
    <div className="relative w-full h-full flex-1 bg-[#02040a] overflow-hidden">
      <div ref={mapContainerRef} className="absolute inset-0 w-full h-full" />

      {/* OSIRIS 3D Viewport Controls HUD */}
      <div className="absolute top-4 right-4 z-10 flex items-center gap-2">
        {/* Basemap Switcher */}
        <div className="flex bg-[#070a12]/90 border border-white/15 rounded p-0.5 backdrop-blur text-[10px] font-mono shadow-xl">
          <button
            onClick={() => handleToggleBasemap('SATELLITE')}
            className={`px-2 py-1 rounded flex items-center gap-1 transition-colors ${
              basemapMode === 'SATELLITE'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
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
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Layers className="w-3 h-3" />
            <span>DARK CANVAS</span>
          </button>
        </div>

        {/* Satellite Constellation Toggle */}
        <button
          onClick={() => setShowSatellites(!showSatellites)}
          className={`px-2.5 py-1 rounded border text-[10px] font-mono flex items-center gap-1.5 backdrop-blur transition-all shadow-xl ${
            showSatellites
              ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300 font-bold'
              : 'bg-[#070a12]/90 border-white/15 text-slate-400 hover:text-slate-200'
          }`}
          title="Toggle 3D Satellite Constellation & Orbit Tracks"
        >
          <Satellite className="w-3 h-3" />
          <span>SATELLITES ({showSatellites ? '1,800+' : 'OFF'})</span>
        </button>

        {/* 3D Globe Telemetry Badge */}
        {is3D && (
          <div className="bg-[#0b1120]/90 border border-cyan-500/40 px-3 py-1 rounded backdrop-blur text-[10px] font-mono text-cyan-300 shadow-[0_0_15px_rgba(6,182,212,0.2)] flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
            <span>3D SPHERICAL GLOBE</span>
          </div>
        )}
      </div>
    </div>
  );
};
