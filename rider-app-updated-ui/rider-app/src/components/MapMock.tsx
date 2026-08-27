import React, { forwardRef, useImperativeHandle } from 'react';
import { View } from 'react-native';

const MapView = forwardRef((props: any, ref) => {
  useImperativeHandle(ref, () => ({
    animateCamera: () => {},
    animateToRegion: () => {},
  }));

  // Prioritize dynamic currentLocation prop over static initialRegion fallback
  const lat = props.currentLocation?.latitude ?? props.initialRegion?.latitude ?? 28.6139;
  const lng = props.currentLocation?.longitude ?? props.initialRegion?.longitude ?? 77.209;
  
  // OpenStreetMap embed URL with bounding box around user position
  const offset = 0.005;
  const bbox = `${lng - offset}%2C${lat - offset}%2C${lng + offset}%2C${lat + offset}`;
  const embedUrl = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat}%2C${lng}`;

  return (
    <View 
      style={[{ backgroundColor: '#e5e5e5', overflow: 'hidden' }, props.style]} 
      pointerEvents="auto"
    >
      <iframe
        src={embedUrl}
        width="100%"
        height="100%"
        style={{ border: 0, pointerEvents: 'auto' }}
        title="OpenStreetMap"
      />
    </View>
  );
});

export const Marker = () => null;
export const Polyline = () => null;
export const PROVIDER_DEFAULT = 'default';

export default MapView;
