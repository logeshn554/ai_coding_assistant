import React from 'react';

/**
 * Simple CSS spinner used throughout the UI while async data is loading.
 * The component is deliberately lightweight and does not depend on any UI library.
 */
export const LoadingSpinner: React.FC<{ size?: number }> = ({ size = 16 }) => {
  const style: React.CSSProperties = {
    width: size,
    height: size,
    border: `${Math.max(2, Math.floor(size / 8))}px solid #555`,
    borderTop: `${Math.max(2, Math.floor(size / 8))}px solid #8b5cf6`,
    borderRadius: '50%',
    animation: 'spin 0.8s linear infinite'
  };
  return <div style={style} />;
};

// Add the keyframes globally – this file will be imported by the app entry point.
const styleSheet = document.styleSheets[0] as CSSStyleSheet;
const keyframes = `@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`;
if (styleSheet && styleSheet.cssRules) {
  try {
    styleSheet.insertRule(keyframes, styleSheet.cssRules.length);
  } catch (e) {
    // In case the rule already exists – ignore.
  }
}
